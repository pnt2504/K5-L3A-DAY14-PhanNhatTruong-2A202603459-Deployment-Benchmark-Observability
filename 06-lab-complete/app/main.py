"""Production-ready FastAPI entry point for the Day 14 agent."""

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from utils.mock_llm import MOCK_RESPONSES, ask as llm_ask

from .auth import verify_api_key
from .config import settings
from .cost_guard import check_budget, record_cost, release_budget
from .rate_limiter import check_rate_limit
from .redis_client import r, redis_healthy

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())
logger.propagate = False

# Mock responses are fixed strings. Reserve enough for the longest one.
MAX_MOCK_OUTPUT_TOKENS = max(
    len(reply.split()) for replies in MOCK_RESPONSES.values() for reply in replies
)


def log_event(event: str, **fields: object) -> None:
    logger.info(json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": "INFO",
        "event": event,
        **fields,
    }))


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_event("startup", environment=settings.environment)
    try:
        yield
    finally:
        r.close()
        log_event("shutdown")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = None


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        log_event(
            "request",
            method=request.method,
            path=request.url.path,
            status=status,
            ms=round((perf_counter() - started) * 1000, 2),
        )


@app.exception_handler(RedisError)
async def redis_unavailable(request: Request, error: RedisError):
    return JSONResponse({"detail": "Redis unavailable"}, status_code=503)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(503, "Redis unavailable")
    return {"status": "ready"}


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)
    input_tokens = len(body.question.split())
    reservation = check_budget(input_tokens, MAX_MOCK_OUTPUT_TOKENS)
    try:
        answer = llm_ask(body.question)
    except Exception:
        release_budget(reservation)
        raise
    record_cost(reservation, input_tokens, len(answer.split()))
    return {"question": body.question, "answer": answer}
