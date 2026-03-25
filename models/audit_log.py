"""
OnePay — Audit log model
Tracks security-relevant events for compliance and debugging.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from models.base import Base


class AuditLog(Base):
    """
    Audit log for security-relevant events.
    
    Events tracked:
    - merchant.login, merchant.login_failed, merchant.registered
    - link.created, link.reissued
    - payment.confirmed
    - webhook.delivered, webhook.failed
    """
    __tablename__ = "audit_logs"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    event      = Column(String(100), nullable=False, index=True)
    user_id    = Column(Integer, nullable=True, index=True)
    tx_ref     = Column(String(50), nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)
    detail     = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index("ix_audit_logs_event_created", "event", "created_at"),
        Index("ix_audit_logs_user_created", "user_id", "created_at"),
    )

    def to_dict(self):
        return {
            "id":         self.id,
            "event":      self.event,
            "user_id":    self.user_id,
            "tx_ref":     self.tx_ref,
            "ip_address": self.ip_address,
            "detail":     self.detail,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
