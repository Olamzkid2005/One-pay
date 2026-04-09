"""
OnePay — Webhook Idempotency Model

Tracks processed webhooks to prevent duplicate processing.
Records expire after 24 hours (handled by cleanup task).
"""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, String

from models.base import Base


class WebhookIdempotency(Base):
    """
    Tracks processed webhooks to prevent duplicate processing.

    Records expire after 24 hours (handled by cleanup task).
    """
    __tablename__ = "webhook_idempotency"

    id = Column(String(255), primary_key=True)  # Webhook identifier
    source = Column(String(50), nullable=False)  # korapay, voicepay, etc.
    processed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    tx_ref = Column(String(100), nullable=True)  # Associated transaction

    __table_args__ = (
        Index("ix_webhook_idempotency_processed", "processed_at"),
    )

    def __repr__(self) -> str:
        return f"<WebhookIdempotency(id={self.id!r}, source={self.source!r}, tx_ref={self.tx_ref!r})>"
