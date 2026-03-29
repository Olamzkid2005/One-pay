"""
OnePay — User (Merchant) model
"""
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text
from sqlalchemy.orm import Session
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

    # OAuth provider data
    google_id           = Column(String(255), unique=True, index=True, nullable=True)
    profile_picture_url = Column(String(500), nullable=True)
    full_name           = Column(String(255), nullable=True)
    auth_provider       = Column(String(20), default='traditional', nullable=False)

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

    @staticmethod
    def generate_username_from_email(db: Session, email: str) -> str:
        """
        Generate a unique username from an email address.
        
        Algorithm:
        1. Extract local part of email (before @)
        2. Remove non-alphanumeric characters except underscores
        3. Truncate to 30 characters
        4. Check for uniqueness
        5. If not unique, append numeric suffix (e.g., john_doe_2)
        6. Retry up to 10 times with incrementing suffix
        
        Args:
            db: Database session
            email: Email address to generate username from
        
        Returns:
            str: Unique username
        
        Raises:
            ValueError: If unable to generate unique username after 10 attempts
        """
        # Extract local part (before @)
        local_part = email.split('@')[0]
        
        # Remove special characters except underscores, keep alphanumeric
        base_username = re.sub(r'[^a-zA-Z0-9_]', '_', local_part)
        
        # Truncate to 30 characters
        base_username = base_username[:30]
        
        # Try base username first
        if not db.query(User).filter(User.username == base_username).first():
            return base_username
        
        # If collision, try with numeric suffix
        for i in range(2, 12):  # Try suffixes 2-11 (10 attempts)
            # Calculate available space for suffix
            suffix = f"_{i}"
            max_base_len = 30 - len(suffix)
            username = base_username[:max_base_len] + suffix
            
            if not db.query(User).filter(User.username == username).first():
                return username
        
        # If still no unique username after 10 attempts, raise error
        raise ValueError(f"Unable to generate unique username from email: {email}")

    @staticmethod
    def find_by_google_id(db: Session, google_id: str) -> Optional['User']:
        """
        Find user by Google ID.
        
        Args:
            db: Database session
            google_id: Google user ID (sub claim from ID token)
        
        Returns:
            User or None if not found
        """
        return db.query(User).filter(User.google_id == google_id).first()

    @staticmethod
    def find_by_email(db: Session, email: str) -> Optional['User']:
        """
        Find user by email address.
        
        Args:
            db: Database session
            email: Email address (should be normalized to lowercase)
        
        Returns:
            User or None if not found
        """
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def create_from_google(db: Session, profile: dict) -> 'User':
        """
        Create new user from Google profile.
        
        Args:
            db: Database session
            profile: Profile dict from GoogleProfileExtractor with keys:
                - google_id: Google user ID
                - email: Normalized email address
                - full_name: User's full name
                - profile_picture_url: Profile picture URL
        
        Returns:
            User: Newly created user
        """
        # Generate unique username from email
        username = User.generate_username_from_email(db, profile['email'])
        
        # Create user
        user = User(
            username=username,
            email=profile['email'],
            google_id=profile['google_id'],
            full_name=profile['full_name'],
            profile_picture_url=profile['profile_picture_url'],
            auth_provider='google'
        )
        
        # Set random secure password hash to prevent password-based login
        random_password = secrets.token_urlsafe(32)
        user.set_password(random_password)
        
        db.add(user)
        db.flush()
        db.refresh(user)
        
        return user

    def link_google_account(self, google_id: str, profile_picture_url: str, full_name: str):
        """
        Link Google account to existing user.
        
        Args:
            google_id: Google user ID
            profile_picture_url: Profile picture URL
            full_name: User's full name
        """
        self.google_id = google_id
        
        # Update profile picture if not already set
        if not self.profile_picture_url:
            self.profile_picture_url = profile_picture_url
        
        # Update full name if not already set
        if not self.full_name:
            self.full_name = full_name
        
        # Update auth_provider to 'both' if currently 'traditional'
        if self.auth_provider == 'traditional':
            self.auth_provider = 'both'
