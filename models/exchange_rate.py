"""
OnePay — Exchange Rate database model
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_mixin

from models.base import Base


class ExchangeRate(Base):
    """Exchange rate model for multi-currency support."""
    __tablename__ = "exchange_rates"

    id = Column(__import__("sqlalchemy").Integer, primary_key=True, index=True)
    from_currency = Column(String(3), nullable=False)
    to_currency = Column(String(3), nullable=False)
    rate = Column(Numeric(10, 6), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("from_currency", "to_currency", name="uix_currency_pair"),
    )

    def __repr__(self) -> str:
        return f"<ExchangeRate({self.from_currency}->{self.to_currency}={self.rate})>"
