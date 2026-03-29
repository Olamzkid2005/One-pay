"""
OnePay — Invoice database models
"""
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Numeric, DateTime, Integer,
    Enum, Boolean, ForeignKey, Text, Index,
)
from sqlalchemy.orm import relationship

from models.base import Base


class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(20), unique=True, nullable=False, index=True)

    # Relationships
    transaction_id = Column(
        Integer,
        ForeignKey("transactions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # SQLAlchemy relationships
    transaction = relationship("Transaction", backref="invoice", uselist=False)

    # Invoice details (denormalized for historical accuracy)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="NGN", server_default="NGN")
    description = Column(String(255), nullable=True)
    customer_email = Column(String(255), nullable=True)
    customer_phone = Column(String(20), nullable=True)

    # Merchant branding (snapshot at creation time)
    business_name = Column(String(255), nullable=True)
    business_address = Column(Text, nullable=True)
    business_tax_id = Column(String(100), nullable=True)
    business_logo_url = Column(String(500), nullable=True)
    payment_terms = Column(Text, nullable=True)

    # Status tracking
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.DRAFT)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    sent_at = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)

    # Email delivery tracking
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime(timezone=True), nullable=True)
    email_attempts = Column(Integer, default=0)
    email_last_error = Column(Text, nullable=True)

    # Performance indexes for common queries
    __table_args__ = (
        Index("ix_invoices_user_created", "user_id", "created_at"),
        Index("ix_invoices_user_status", "user_id", "status"),
        Index("ix_invoices_transaction", "transaction_id"),
    )

    # ── Timezone helpers ───────────────────────────────────────────────────────

    def _to_utc(self, dt):
        """Convert a datetime field to timezone-aware UTC.
        Treats naive datetimes as UTC (consistent with SQLite behaviour).
        """
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def created_at_utc_iso(self) -> str | None:
        dt = self._to_utc(self.created_at)
        return dt.isoformat() if dt else None

    def sent_at_utc_iso(self) -> str | None:
        dt = self._to_utc(self.sent_at)
        return dt.isoformat() if dt else None

    def paid_at_utc_iso(self) -> str | None:
        dt = self._to_utc(self.paid_at)
        return dt.isoformat() if dt else None

    def to_dict(self):
        """Safe dict for JSON responses."""
        return {
            "invoice_number": self.invoice_number,
            "transaction_id": self.transaction_id,
            "amount": str(self.amount),
            "currency": self.currency,
            "description": self.description,
            "customer_email": self.customer_email,
            "customer_phone": self.customer_phone,
            "business_name": self.business_name,
            "business_address": self.business_address,
            "business_tax_id": self.business_tax_id,
            "payment_terms": self.payment_terms,
            "status": self.status.value if hasattr(self.status, 'value') else str(self.status),
            "created_at": self.created_at_utc_iso(),
            "sent_at": self.sent_at_utc_iso(),
            "paid_at": self.paid_at_utc_iso(),
            "email_sent": self.email_sent,
        }

    def __repr__(self):
        return f"<Invoice(invoice_number={self.invoice_number}, status={self.status})>"


class InvoiceSettings(Base):
    __tablename__ = "invoice_settings"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )

    # Branding
    business_name = Column(String(255), nullable=True)
    business_address = Column(Text, nullable=True)
    business_tax_id = Column(String(100), nullable=True)
    business_logo_url = Column(String(500), nullable=True)

    # Defaults
    default_payment_terms = Column(Text, default="Payment due upon receipt")
    auto_send_email = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self):
        """Safe dict for JSON responses."""
        return {
            "business_name": self.business_name,
            "business_address": self.business_address,
            "business_tax_id": self.business_tax_id,
            "business_logo_url": self.business_logo_url,
            "default_payment_terms": self.default_payment_terms,
            "auto_send_email": self.auto_send_email,
        }

    def __repr__(self):
        return f"<InvoiceSettings(user_id={self.user_id}, business_name={self.business_name})>"
