"""
OnePay — Recurring Invoice database model
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from models.base import Base


class RecurringInvoice(Base):
    """Recurring invoice model for scheduled invoice generation."""
    __tablename__ = "recurring_invoices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)

    # Customer details
    customer_email = Column(String(255), nullable=False)
    customer_name = Column(String(255), nullable=True)
    customer_phone = Column(String(20), nullable=True)

    # Invoice details
    amount = Column(__import__("sqlalchemy").Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="NGN")
    description = Column(String(500), nullable=True)

    # Schedule details
    frequency = Column(String(20), nullable=False)  # daily, weekly, biweekly, monthly, quarterly, yearly
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=True)
    next_invoice_date = Column(DateTime(timezone=True), nullable=False)

    # Status
    is_active = Column(Integer, nullable=False, default=1)  # 0 = inactive, 1 = active

    # Metadata
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationship to generated invoices
    invoices = relationship("Invoice", backref="recurring_invoice", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<RecurringInvoice(id={self.id}, customer_email={self.customer_email!r}, frequency={self.frequency})>"
