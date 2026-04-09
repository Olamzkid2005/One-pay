"""API Key model for machine-to-machine authentication"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String

from models.base import Base


class APIKey(Base):
    """API Key model for authenticating external services"""

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key_hash = Column(String(255), unique=True, nullable=False, index=True)
    key_prefix = Column(String(20), nullable=False)
    name = Column(String(100), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("idx_api_keys_user_id", "user_id"),
        Index("idx_api_keys_key_hash", "key_hash"),
    )

    def to_dict(self) -> dict:
        """Safe dict for JSON responses - never exposes full key"""
        return {
            "id": self.id,
            "name": self.name,
            "key_prefix": self.key_prefix,
            "created_at": self.created_at.astimezone(timezone.utc).isoformat()
            if self.created_at
            else None,
            "last_used_at": self.last_used_at.astimezone(timezone.utc).isoformat()
            if self.last_used_at
            else None,
            "expires_at": self.expires_at.astimezone(timezone.utc).isoformat()
            if self.expires_at
            else None,
            "is_active": self.is_active,
        }
