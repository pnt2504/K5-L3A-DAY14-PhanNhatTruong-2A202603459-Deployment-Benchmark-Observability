"""Redis-backed sliding window shared by all agent workers."""

from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException

from .config import settings
from .redis_client import r

WINDOW_MS = 60_000

# Redis supplies a common clock and runs admission as a single operation.
check_window = r.register_script("""
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local now = redis.call("TIME")
local now_ms = now[1] * 1000 + math.floor(now[2] / 1000)
redis.call("ZREMRANGEBYSCORE", KEYS[1], "-inf", now_ms - window)

if limit <= 0 then
    return math.ceil(window / 1000)
end

if redis.call("ZCARD", KEYS[1]) >= limit then
    local oldest = redis.call("ZRANGE", KEYS[1], 0, 0, "WITHSCORES")
    return math.max(1, math.ceil((oldest[2] + window - now_ms) / 1000))
end

redis.call("ZADD", KEYS[1], now_ms, ARGV[3])
redis.call("PEXPIRE", KEYS[1], window)
return 0
""")


def check_rate_limit(key: str) -> None:
    key_hash = sha256(key.encode("utf-8")).hexdigest()
    retry_after = check_window(
        keys=[f"agent:rate:{key_hash}"],
        args=[WINDOW_MS, settings.rate_limit_per_minute, uuid4().hex],
    )
    if retry_after:
        raise HTTPException(
            429,
            "Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
