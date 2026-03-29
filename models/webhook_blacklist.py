"""
OnePay — Webhook Blacklist Model

Tracks malicious webhook URLs that have attempted DNS rebinding or other attacks.
URLs on this list are permanently blocked from receiving webhooks.
"""
from sqlalchemy import Column, String, DateTime, Text, Integer
from datetime import datetime, timezone

from models.base import Base


class WebhookBlacklist(Base):
    """
    Webhook URL blacklist for security violations.
    
    URLs are added when:
    - DNS rebinding detected (resolves to private/loopback IP)
    - Redirect to internal IP detected
    - AWS metadata endpoint access attempted
    - Other SSRF attack patterns detected
    """
    __tablename__ = "webhook_blacklist"
    
    url = Column(String(500), primary_key=True)
    reason = Column(Text, nullable=False)
    blacklisted_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    attempts = Column(Integer, default=1, nullable=False)
    
    def __repr__(self):
        return f"<WebhookBlacklist(url={self.url!r}, reason={self.reason!r})>"
