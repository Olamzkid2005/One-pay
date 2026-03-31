"""
OnePay — Transaction database model
"""
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Numeric, DateTime, Integer,
    Enum, Boolean, ForeignKey, Text, Index,
)

from models.base import Base


class TransactionStatus(str, enum.Enum):
    PENDING  = "pending"
    VERIFIED = "verified"
    FAILED   = "failed"
    EXPIRED  = "expired"


class Transaction(Base):
    __tablename__ = "transactions"

    id      = Column(Integer, primary_key=True, index=True)
    tx_ref  = Column(String(100), unique=True, index=True, nullable=False)

    # Idempotency key — merchant-supplied to prevent duplicate link creation
    idempotency_key = Column(String(255), unique=True, nullable=True, index=True)

    # Owner — which merchant created this link
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Payment details
    amount      = Column(Numeric(12, 2), nullable=False)
    currency    = Column(String(10), default="NGN", server_default="NGN")
    description = Column(String(255), nullable=True)
    return_url  = Column(String(500), nullable=True)

    # Customer info (optional)
    customer_email = Column(String(255), nullable=True)
    customer_phone = Column(String(20),  nullable=True)

    # Security
    hash_token = Column(String(255), nullable=False)

    # Status
    status  = Column(Enum(TransactionStatus), default=TransactionStatus.PENDING)
    is_used = Column(Boolean, default=False)

    # Timestamps
    created_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at  = Column(DateTime(timezone=True), nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)

    # Dynamic Transfer — virtual account
    virtual_account_number = Column(String(20),  nullable=True)
    virtual_bank_name      = Column(String(100), nullable=True)
    virtual_account_name   = Column(String(255), nullable=True)
    transfer_confirmed     = Column(Boolean, default=False)

    # QR Code data
    qr_code_payment_url    = Column(Text, nullable=True)     # Base64 data URI for payment QR
    qr_code_virtual_account = Column(Text, nullable=True)     # Base64 data URI for virtual account QR

    # Webhook delivery
    webhook_url            = Column(String(500), nullable=True)
    webhook_delivered      = Column(Boolean, default=False)
    webhook_delivered_at   = Column(DateTime(timezone=True), nullable=True)
    webhook_attempts       = Column(Integer, default=0)
    webhook_last_error     = Column(Text, nullable=True)

    # KoraPay-specific fields (all nullable for backward compatibility)
    payment_provider_reference = Column(String(100), nullable=True)
    provider_fee              = Column(Numeric(12, 2), nullable=True)
    provider_vat              = Column(Numeric(12, 2), nullable=True)
    provider_transaction_date = Column(DateTime(timezone=True), nullable=True)
    payer_bank_details        = Column(Text, nullable=True)
    failure_reason            = Column(Text, nullable=True)
    provider_status           = Column(String(50), nullable=True)
    bank_code                 = Column(String(10), nullable=True)
    virtual_account_expiry    = Column(DateTime(timezone=True), nullable=True)

    # Performance indexes for common queries
    __table_args__ = (
        Index("ix_transactions_user_created", "user_id", "created_at"),
        Index("ix_transactions_user_status", "user_id", "status"),
        Index("ix_transactions_expires_status", "expires_at", "status"),
        Index("idx_payment_provider_reference", "payment_provider_reference"),
        Index("idx_provider_transaction_date", "provider_transaction_date"),
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

    def expires_at_utc_iso(self) -> str | None:
        dt = self._to_utc(self.expires_at)
        return dt.isoformat() if dt else None

    def created_at_utc_iso(self) -> str | None:
        dt = self._to_utc(self.created_at)
        return dt.isoformat() if dt else None

    def verified_at_utc_iso(self) -> str | None:
        dt = self._to_utc(self.verified_at)
        return dt.isoformat() if dt else None

    def effective_status_value(self) -> str:
        """
        Compute a time-aware status for API/UI.
        Treats pending/failed links as expired once they pass expires_at,
        even if the DB row hasn't been updated yet.
        """
        status = self.status or TransactionStatus.PENDING
        if not self.is_used and self.is_expired():
            if status in (TransactionStatus.PENDING, TransactionStatus.FAILED):
                return TransactionStatus.EXPIRED.value
        return status.value

    def to_dict(self):
        """Safe dict for JSON responses — never exposes hash_token."""
        return {
            "tx_ref":          self.tx_ref,
            "amount":          str(self.amount),
            "currency":        self.currency,
            "description":     self.description,
            "status":          self.effective_status_value(),
            "is_used":         self.is_used,
            "is_expired":      self.is_expired(),
            "created_at":      self.created_at_utc_iso(),
            "expires_at":      self.expires_at_utc_iso(),
            "verified_at":     self.verified_at_utc_iso(),
            "virtual_account_number": self.virtual_account_number,
            "virtual_bank_name":      self.virtual_bank_name,
            "virtual_account_name":   self.virtual_account_name,
            "transfer_confirmed":     self.transfer_confirmed,
            "webhook_delivered":      self.webhook_delivered,
            "qr_code_payment_url":     self.qr_code_payment_url,
            "qr_code_virtual_account": self.qr_code_virtual_account,
        }

    def is_expired(self):
        """Check if the payment link has passed its expiry time."""
        now = datetime.now(timezone.utc)
        exp_utc = self._to_utc(self.expires_at)
        if exp_utc is None:
            return True
        return now > exp_utc
