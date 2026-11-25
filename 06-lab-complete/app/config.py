"""Environment configuration for the agent."""

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def read_budget(name: str) -> Decimal | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation as error:
        raise ValueError(f"{name} must be a non-negative amount in USD") from error
    if not value.is_finite() or value < 0:
        raise ValueError(f"{name} must be a non-negative amount in USD")
    return value


@dataclass(frozen=True)
class Settings:
    port: int
    environment: str
    agent_api_key: str
    redis_url: str
    rate_limit_per_minute: int
    daily_budget_usd: Decimal | None
    monthly_budget_usd: Decimal | None


daily_budget = read_budget("DAILY_BUDGET_USD")
monthly_budget = read_budget("MONTHLY_BUDGET_USD")
if daily_budget is None and monthly_budget is None:
    monthly_budget = Decimal("10")

settings = Settings(
    port=int(os.getenv("PORT", "8000")),
    environment=os.getenv("ENVIRONMENT", "development"),
    agent_api_key=os.getenv("AGENT_API_KEY", ""),
    redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
    rate_limit_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "10")),
    daily_budget_usd=daily_budget,
    monthly_budget_usd=monthly_budget,
)
