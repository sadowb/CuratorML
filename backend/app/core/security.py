from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel


class TokenPayload(BaseModel):
    sub: str
    exp: datetime


def build_expiration(minutes: int) -> datetime:
    return datetime.now(UTC) + timedelta(minutes=minutes)
