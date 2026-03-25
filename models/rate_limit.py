"""
OnePay — DB-backed rate limit tracking.
Replaces the in-memory defaultdict so limits survive restarts
and work correctly across multiple worker processes.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Index, UniqueConstraint

from models.base import Base


class RateLimit(Base):
    __tablename__ = "rate_limits"

    id         = Column(Integer, primary_key=True, index=True)
    key        = Column(String(255), nullable=False)   # e.g. "login:1.2.3.4"
    window_start = Column(DateTime(timezone=True), nullable=False)
    count      = Column(Integer, default=1, nullable=False)

    __table_args__ = (
        Index("ix_rate_limits_key_window", "key", "window_start"),
        UniqueConstraint("key", "window_start", name="uq_rate_limits_key_window"),
    )
