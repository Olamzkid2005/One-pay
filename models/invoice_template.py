"""
OnePay — Invoice Template database model
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


class InvoiceTemplate(Base):
    """Invoice template model for custom invoice designs."""
    __tablename__ = "invoice_templates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)

    # Template details
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)

    # Template content (HTML/CSS)
    html_template = Column(Text, nullable=False)
    css_styles = Column(Text, nullable=True)

    # Metadata
    is_default = Column(Integer, nullable=False, default=0)  # 0 = false, 1 = true

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

    def __repr__(self) -> str:
        return f"<InvoiceTemplate(id={self.id}, name={self.name!r}, user_id={self.user_id})>"
