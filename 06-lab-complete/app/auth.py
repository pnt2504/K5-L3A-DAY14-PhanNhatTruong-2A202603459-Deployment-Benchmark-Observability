"""Authenticate clients with the API key configured for this deployment."""

from secrets import compare_digest

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from .config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    configured_key = settings.agent_api_key
    if not api_key or not configured_key or not compare_digest(
        api_key.encode("utf-8"), configured_key.encode("utf-8")
    ):
        raise HTTPException(401, "Invalid or missing API key")
    return api_key
