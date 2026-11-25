"""Reserve model spend in Redis and settle it after the mock LLM call."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from .config import settings
from .redis_client import r

# $0.00015 input and $0.0006 output per 1,000 tokens.
NANO_USD_PER_DOLLAR = 1_000_000_000
INPUT_NANO_USD_PER_TOKEN = 150
OUTPUT_NANO_USD_PER_TOKEN = 600

reserve_cost = r.register_script("""
local estimated = tonumber(ARGV[1])
for index, key in ipairs(KEYS) do
    local spent = tonumber(redis.call("GET", key) or "0")
    if spent + estimated > tonumber(ARGV[2 * index]) then
        return 0
    end
end
for index, key in ipairs(KEYS) do
    redis.call("INCRBY", key, ARGV[1])
    redis.call("EXPIREAT", key, ARGV[2 * index + 1])
end
return 1
""")

adjust_cost = r.register_script("""
for _, key in ipairs(KEYS) do
    if redis.call("EXISTS", key) == 1 then
        redis.call("INCRBY", key, ARGV[1])
    end
end
""")


@dataclass(frozen=True)
class BudgetReservation:
    keys: tuple[str, ...]
    estimated: int


def cost_of(input_tokens: int, output_tokens: int) -> int:
    return input_tokens * INPUT_NANO_USD_PER_TOKEN + output_tokens * OUTPUT_NANO_USD_PER_TOKEN


def check_budget(input_tokens: int, max_output_tokens: int) -> BudgetReservation:
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    periods = (
        (settings.daily_budget_usd, today.strftime("%Y-%m-%d"), today + timedelta(days=1)),
        (settings.monthly_budget_usd, month_start.strftime("%Y-%m"), next_month),
    )
    keys = []
    estimated = cost_of(input_tokens, max_output_tokens)
    args = [estimated]
    for budget, period, expires_at in periods:
        if budget is not None:
            keys.append(f"agent:budget:{period}")
            args.extend((int(budget * NANO_USD_PER_DOLLAR), int(expires_at.timestamp())))

    if not reserve_cost(keys=keys, args=args):
        raise HTTPException(402, "LLM budget exceeded")
    return BudgetReservation(tuple(keys), estimated)


def record_cost(reservation: BudgetReservation, input_tokens: int, output_tokens: int) -> float:
    actual = cost_of(input_tokens, output_tokens)
    adjust_cost(keys=reservation.keys, args=[actual - reservation.estimated])
    return actual / NANO_USD_PER_DOLLAR


def release_budget(reservation: BudgetReservation) -> None:
    adjust_cost(keys=reservation.keys, args=[-reservation.estimated])
