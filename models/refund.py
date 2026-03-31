"""
OnePay — Refund database model
"""
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Numeric, DateTime, Integer,
    Enum, ForeignKey, Text, Index,
)
from sqlalchemy.orm import relationship

from models.base import Base


class RefundStatus(str, enum.Enum):
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key to transaction
    transaction_id = Column(Integer, ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False)
    
    # Refund details
    refund_reference = Column(String(100), unique=True, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="NGN", server_default="NGN")
    status = Column(String(20), nullable=False)
    reason = Column(String(200), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Provider details
    failure_reason = Column(Text, nullable=True)
    provider_refund_id = Column(String(100), nullable=True)
    
    # Relationship to Transaction
    transaction = relationship("Transaction", backref="refunds")
    
    # Performance indexes for common queries
    __table_args__ = (
        Index("idx_refunds_transaction_id", "transaction_id"),
        Index("idx_refunds_status", "status"),
        Index("idx_refunds_created_at", "created_at"),
    )
