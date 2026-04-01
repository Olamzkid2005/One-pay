"""
OnePay — Configuration
Environment-specific subclasses selected by APP_ENV env var.

Usage in app factory:
    app.config.from_object(get_config())
"""
import os
from dotenv import load_dotenv

load_dotenv()


class BaseConfig:
    # ── App ──────────────────────────────────────────────────────────────────
    SECRET_KEY  = os.getenv("SECRET_KEY", "change-this-in-production")
    DEBUG       = False
    TESTING     = False

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///onepay.db")

    # ── Security ─────────────────────────────────────────────────────────────
    HMAC_SECRET     = os.getenv("HMAC_SECRET", "change-this-hmac-secret")
    HMAC_SECRET_OLD = os.getenv("HMAC_SECRET_OLD", "")
    LINK_EXPIRATION_MINUTES = int(os.getenv("LINK_EXPIRATION_MINUTES", "5"))

    # ── Proxy trust ───────────────────────────────────────────────────────────
    TRUST_X_FORWARDED_FOR   = os.getenv("TRUST_X_FORWARDED_FOR",   "false").lower() == "true"
    TRUST_X_FORWARDED_PROTO = os.getenv("TRUST_X_FORWARDED_PROTO", "false").lower() == "true"

    # ── Account lockout ───────────────────────────────────────────────────────
    LOGIN_MAX_ATTEMPTS    = int(os.getenv("LOGIN_MAX_ATTEMPTS",    "5"))
    LOCKOUT_DURATION_SECS = int(os.getenv("LOCKOUT_DURATION_SECS", "900"))

    # ── Email ─────────────────────────────────────────────────────────────────
    MAIL_SERVER   = os.getenv("MAIL_SERVER",   "smtp.gmail.com")
    MAIL_PORT     = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS  = os.getenv("MAIL_USE_TLS",  "true").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_FROM     = os.getenv("MAIL_FROM",     "noreply@onepay.com")

    # ── KoraPay Payment Gateway ───────────────────────────────────────────────
    KORAPAY_SECRET_KEY      = os.getenv("KORAPAY_SECRET_KEY", "")
    KORAPAY_WEBHOOK_SECRET  = os.getenv("KORAPAY_WEBHOOK_SECRET", "")
    KORAPAY_BASE_URL        = os.getenv("KORAPAY_BASE_URL", "https://api.korapay.com")
    KORAPAY_USE_SANDBOX     = os.getenv("KORAPAY_USE_SANDBOX", "false").lower() == "true"
    KORAPAY_TIMEOUT_SECONDS = int(os.getenv("KORAPAY_TIMEOUT_SECONDS", "30"))
    KORAPAY_CONNECT_TIMEOUT = int(os.getenv("KORAPAY_CONNECT_TIMEOUT", "10"))
    KORAPAY_MAX_RETRIES     = int(os.getenv("KORAPAY_MAX_RETRIES", "3"))

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_LINK_CREATE           = int(os.getenv("RATE_LIMIT_LINK_CREATE",           "10"))
    RATE_LIMIT_VERIFY                = int(os.getenv("RATE_LIMIT_VERIFY",                "20"))
    RATE_LIMIT_VERIFY_PAGE_ATTEMPTS  = int(os.getenv("RATE_LIMIT_VERIFY_PAGE_ATTEMPTS",  "5"))
    RATE_LIMIT_VERIFY_PAGE_WINDOW_SECS = int(os.getenv("RATE_LIMIT_VERIFY_PAGE_WINDOW_SECS", "300"))

    # ── API Keys ──────────────────────────────────────────────────────────────
    API_KEY_MAX_PER_USER = int(os.getenv("API_KEY_MAX_PER_USER", "10"))
    API_KEY_GENERATION_RATE_LIMIT = int(os.getenv("API_KEY_GENERATION_RATE_LIMIT", "5"))

    # ── Inbound Webhooks ──────────────────────────────────────────────────────
    INBOUND_WEBHOOK_SECRET = os.getenv("INBOUND_WEBHOOK_SECRET", "")

    # ── API Rate Limits ───────────────────────────────────────────────────────
    RATE_LIMIT_API_LINK_CREATE = int(os.getenv("RATE_LIMIT_API_LINK_CREATE", "100"))
    RATE_LIMIT_API_STATUS_CHECK = int(os.getenv("RATE_LIMIT_API_STATUS_CHECK", "500"))

    # ── Session lifetime ──────────────────────────────────────────────────────
    # SESSION_LIFETIME_HOURS: how long a permanent session lasts (default 24h)
    PERMANENT_SESSION_LIFETIME = int(os.getenv("SESSION_LIFETIME_HOURS", "24"))

    # ── Session inactivity timeout ────────────────────────────────────────────
    # Minutes before session expires due to inactivity
    SESSION_TIMEOUT_AUTHENTICATED = int(os.getenv("SESSION_TIMEOUT_AUTHENTICATED", "30"))
    SESSION_TIMEOUT_UNAUTHENTICATED = int(os.getenv("SESSION_TIMEOUT_UNAUTHENTICATED", "60"))

    # ── HTTPS ─────────────────────────────────────────────────────────────────
    ENFORCE_HTTPS = os.getenv("ENFORCE_HTTPS", "false").lower() == "true"

    # ── Webhook ───────────────────────────────────────────────────────────────
    # Separate signing secret for outbound webhooks.
    # Falls back to HMAC_SECRET if not set — set this to a distinct value in production.
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

    WEBHOOK_TIMEOUT_SECS = int(os.getenv("WEBHOOK_TIMEOUT_SECS", "10"))
    WEBHOOK_MAX_RETRIES  = int(os.getenv("WEBHOOK_MAX_RETRIES",  "3"))

    # ── VoicePay Integration ──────────────────────────────────────────────────
    VOICEPAY_WEBHOOK_URL = os.getenv("VOICEPAY_WEBHOOK_URL", "")
    VOICEPAY_WEBHOOK_SECRET = os.getenv("VOICEPAY_WEBHOOK_SECRET", "")
    VOICEPAY_API_KEY = os.getenv("VOICEPAY_API_KEY", "")

    # Sandbox configuration
    VOICEPAY_WEBHOOK_URL_SANDBOX = os.getenv("VOICEPAY_WEBHOOK_URL_SANDBOX", "")
    VOICEPAY_WEBHOOK_SECRET_SANDBOX = os.getenv("VOICEPAY_WEBHOOK_SECRET_SANDBOX", "")

    # Webhook timeout and retry settings
    VOICEPAY_WEBHOOK_TIMEOUT_SECS = int(os.getenv("VOICEPAY_WEBHOOK_TIMEOUT_SECS", "10"))
    VOICEPAY_WEBHOOK_MAX_RETRIES = int(os.getenv("VOICEPAY_WEBHOOK_MAX_RETRIES", "3"))

    # Enable/disable VoicePay webhook forwarding
    VOICEPAY_WEBHOOK_ENABLED = os.getenv("VOICEPAY_WEBHOOK_ENABLED", "true").lower() == "true"

    # ── Google OAuth ──────────────────────────────────────────────────────────
    GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI", "")

    @classmethod
    def validate(cls):
        """Enforce strong secrets in production. Called explicitly from app factory."""
        import logging as _logging
        import sys as _sys
        import os as _os
        _logger = _logging.getLogger(__name__)
        
        errors = []
        warnings = []
        
        # Check for placeholder secrets
        if "change-this" in cls.SECRET_KEY.lower():
            errors.append("SECRET_KEY contains placeholder value")
        if "change-this" in cls.HMAC_SECRET.lower():
            errors.append("HMAC_SECRET contains placeholder value")
        if cls.WEBHOOK_SECRET and "change-this" in cls.WEBHOOK_SECRET.lower():
            errors.append("WEBHOOK_SECRET contains placeholder value")
        
        # Check minimum entropy (32 bytes = 64 hex chars)
        if len(cls.SECRET_KEY) < 32:
            errors.append("SECRET_KEY too short (minimum 32 characters)")
        if len(cls.HMAC_SECRET) < 32:
            errors.append("HMAC_SECRET too short (minimum 32 characters)")
        
        # Check secrets are different
        if cls.SECRET_KEY == cls.HMAC_SECRET:
            errors.append("SECRET_KEY and HMAC_SECRET must be different")
        if cls.WEBHOOK_SECRET and cls.WEBHOOK_SECRET == cls.HMAC_SECRET:
            errors.append("WEBHOOK_SECRET and HMAC_SECRET must be different")
        
        # Check DEBUG mode in production
        app_env = _os.getenv("APP_ENV", "development").lower()
        
        # Check KoraPay configuration in production
        if app_env == "production":
            if not cls.KORAPAY_SECRET_KEY:
                errors.append("KORAPAY_SECRET_KEY is required in production")
            elif len(cls.KORAPAY_SECRET_KEY) < 32:
                errors.append("KORAPAY_SECRET_KEY too short (minimum 32 characters)")
            elif not cls.KORAPAY_SECRET_KEY.startswith("sk_live_"):
                errors.append("KORAPAY_SECRET_KEY must start with sk_live_ in production")
            elif cls.KORAPAY_SECRET_KEY.startswith("sk_test_"):
                errors.append("Cannot use test API key (sk_test_) in production")
            elif "change-this" in cls.KORAPAY_SECRET_KEY.lower():
                errors.append("KORAPAY_SECRET_KEY contains placeholder value")
            
            if not cls.KORAPAY_WEBHOOK_SECRET:
                errors.append("KORAPAY_WEBHOOK_SECRET is required in production")
            elif len(cls.KORAPAY_WEBHOOK_SECRET) < 32:
                errors.append("KORAPAY_WEBHOOK_SECRET too short (minimum 32 characters)")
            elif "change-this" in cls.KORAPAY_WEBHOOK_SECRET.lower():
                errors.append("KORAPAY_WEBHOOK_SECRET contains placeholder value")
            
            # Validate secrets are unique
            if cls.KORAPAY_SECRET_KEY and cls.KORAPAY_SECRET_KEY == cls.KORAPAY_WEBHOOK_SECRET:
                errors.append("KORAPAY_SECRET_KEY and KORAPAY_WEBHOOK_SECRET must be different")
            if cls.KORAPAY_WEBHOOK_SECRET and cls.KORAPAY_WEBHOOK_SECRET == cls.HMAC_SECRET:
                errors.append("KORAPAY_WEBHOOK_SECRET and HMAC_SECRET must be different")
            
            if cls.KORAPAY_USE_SANDBOX:
                errors.append("KORAPAY_USE_SANDBOX must be false in production")
            
            # Check inbound webhook secret
            if not cls.INBOUND_WEBHOOK_SECRET:
                errors.append("INBOUND_WEBHOOK_SECRET is required in production")
            elif len(cls.INBOUND_WEBHOOK_SECRET) < 32:
                errors.append("INBOUND_WEBHOOK_SECRET too short (minimum 32 characters)")
        
        # Check Google OAuth configuration in production
        if app_env == "production" and cls.GOOGLE_CLIENT_ID:
            if len(cls.GOOGLE_CLIENT_SECRET) < 32:
                errors.append("GOOGLE_CLIENT_SECRET too short (minimum 32 characters)")
            if cls.GOOGLE_REDIRECT_URI and not cls.GOOGLE_REDIRECT_URI.startswith("https://"):
                errors.append("GOOGLE_REDIRECT_URI must use HTTPS in production")
        
        # Check VoicePay configuration in production
        if app_env == "production" and cls.VOICEPAY_WEBHOOK_ENABLED:
            if not cls.VOICEPAY_WEBHOOK_URL:
                errors.append("VOICEPAY_WEBHOOK_URL is required when VoicePay integration is enabled")
            elif not cls.VOICEPAY_WEBHOOK_URL.startswith("https://"):
                errors.append("VOICEPAY_WEBHOOK_URL must use HTTPS in production")
            
            if not cls.VOICEPAY_WEBHOOK_SECRET:
                errors.append("VOICEPAY_WEBHOOK_SECRET is required when VoicePay integration is enabled")
            elif len(cls.VOICEPAY_WEBHOOK_SECRET) < 32:
                errors.append("VOICEPAY_WEBHOOK_SECRET too short (minimum 32 characters)")
            elif "change-this" in cls.VOICEPAY_WEBHOOK_SECRET.lower():
                errors.append("VOICEPAY_WEBHOOK_SECRET contains placeholder value")
            
            if not cls.VOICEPAY_API_KEY:
                warnings.append("VOICEPAY_API_KEY not set - VoicePay will need to generate this")
            elif len(cls.VOICEPAY_API_KEY) < 32:
                errors.append("VOICEPAY_API_KEY too short (minimum 32 characters)")
            
            # Validate secrets are unique
            if cls.VOICEPAY_WEBHOOK_SECRET and cls.VOICEPAY_WEBHOOK_SECRET == cls.HMAC_SECRET:
                errors.append("VOICEPAY_WEBHOOK_SECRET and HMAC_SECRET must be different")
            if cls.VOICEPAY_WEBHOOK_SECRET and cls.VOICEPAY_WEBHOOK_SECRET == cls.KORAPAY_WEBHOOK_SECRET:
                errors.append("VOICEPAY_WEBHOOK_SECRET and KORAPAY_WEBHOOK_SECRET must be different")
        
        if app_env == "production" and cls.DEBUG:
            errors.append("DEBUG mode is enabled in production environment")
        
        # Check HTTPS enforcement in production
        if app_env == "production":
            if not cls.ENFORCE_HTTPS:
                errors.append("ENFORCE_HTTPS must be true in production")
            if "sqlite" in cls.DATABASE_URL.lower():
                errors.append("SQLite not allowed in production (use PostgreSQL)")
        
        # Log warnings
        for warning in warnings:
            _logger.warning("SECURITY WARNING: %s", warning)
        
        # CRITICAL: Abort on errors in ALL environments
        if errors:
            _logger.critical(
                "STARTUP ABORTED: Security validation failed:\n  - %s\n"
                "Generate strong secrets with: python -c \"import secrets; print(secrets.token_hex(32))\"",
                "\n  - ".join(errors)
            )
            _sys.exit(1)  # Exit unconditionally


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    # Shorter link expiry in dev so you don't wait around
    LINK_EXPIRATION_MINUTES = int(os.getenv("LINK_EXPIRATION_MINUTES", "30"))


class TestingConfig(BaseConfig):
    TESTING     = True
    DEBUG       = True
    DATABASE_URL = "sqlite:///:memory:"
    # Disable rate limiting in tests
    RATE_LIMIT_LINK_CREATE          = 9999
    RATE_LIMIT_VERIFY               = 9999
    RATE_LIMIT_VERIFY_PAGE_ATTEMPTS = 9999
    # Fast lockout for auth tests
    LOGIN_MAX_ATTEMPTS    = 3
    LOCKOUT_DURATION_SECS = 5
    # Use fixed secrets so HMAC is deterministic in tests
    SECRET_KEY   = "test-secret-key"
    HMAC_SECRET  = "test-hmac-secret"


class ProductionConfig(BaseConfig):
    # SECURITY FIX: Always enforce HTTPS in production, no override allowed
    ENFORCE_HTTPS = True  # Hardcoded to True, cannot be overridden
    
    @classmethod
    def validate(cls):
        """Enforce strong secrets and HTTPS in production."""
        super().validate()  # Call parent validation first
        
        # SECURITY FIX: Ensure HTTPS is enforced (redundant check for safety)
        if not cls.ENFORCE_HTTPS:
            import logging as _logging
            import sys as _sys
            _logger = _logging.getLogger(__name__)
            _logger.critical("STARTUP ABORTED: HTTPS enforcement cannot be disabled in production")
            _sys.exit(1)


# ── Config selector ────────────────────────────────────────────────────────────

_configs = {
    "development": DevelopmentConfig,
    "testing":     TestingConfig,
    "production":  ProductionConfig,
}

def get_config():
    """
    Return the config class for the current APP_ENV.
    Defaults to DevelopmentConfig so local dev works with no env vars set.
    """
    env = os.getenv("APP_ENV", "development").lower()
    return _configs.get(env, DevelopmentConfig)

# Convenience alias — existing code that does `from config import Config` keeps working
Config = get_config()
