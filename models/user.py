"""
OnePay — User (Merchant) model
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text
import bcrypt

from models.base import Base


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    username      = Column(String(50), unique=True, index=True, nullable=False)
    email         = Column(String(255), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Webhook — merchant-level default webhook URL for payment events
    webhook_url   = Column(String(500), nullable=True)

    # Account lockout
    failed_login_attempts = Column(Integer, default=0)
    locked_until          = Column(DateTime(timezone=True), nullable=True)

    # Password reset
    reset_token            = Column(String(255), nullable=True, index=True)
    reset_token_expires_at = Column(DateTime(timezone=True), nullable=True)

    def set_password(self, password: str):
        """Hash and store the password using bcrypt with 13 rounds (OWASP 2024 recommendation)."""
        salt = bcrypt.gensalt(rounds=13)
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def check_password(self, password: str) -> bool:
        """Return True if password matches the stored hash."""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
        except (ValueError, AttributeError):
            # Handle legacy werkzeug hashes gracefully
            from werkzeug.security import check_password_hash
            return check_password_hash(self.password_hash, password)

    def is_locked(self) -> bool:
        """Return True if the account is currently locked out."""
        if not self.locked_until:
            return False
        locked_until = self.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < locked_until

    def record_failed_login(self, max_attempts: int, lockout_secs: int):
        """Increment failed attempts and lock if threshold reached."""
        self.failed_login_attempts = (self.failed_login_attempts or 0) + 1
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = datetime.now(timezone.utc) + timedelta(seconds=lockout_secs)

    def record_successful_login(self):
        """Reset lockout state on successful login."""
        self.failed_login_attempts = 0
        self.locked_until = None

    def __repr__(self):
        return f"<User(username={self.username})>"
