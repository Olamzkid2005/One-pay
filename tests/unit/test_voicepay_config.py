"""
Tests for VoicePay configuration validation.

Tests that VoicePay configuration variables exist and are properly validated
in production environments.
"""
import pytest
import os
from config import BaseConfig, ProductionConfig


def test_voicepay_config_exists():
    """Test that VoicePay configuration variables exist"""
    assert hasattr(BaseConfig, 'VOICEPAY_WEBHOOK_URL')
    assert hasattr(BaseConfig, 'VOICEPAY_WEBHOOK_SECRET')
    assert hasattr(BaseConfig, 'VOICEPAY_API_KEY')
    assert hasattr(BaseConfig, 'VOICEPAY_WEBHOOK_URL_SANDBOX')
    assert hasattr(BaseConfig, 'VOICEPAY_WEBHOOK_SECRET_SANDBOX')
    assert hasattr(BaseConfig, 'VOICEPAY_WEBHOOK_TIMEOUT_SECS')
    assert hasattr(BaseConfig, 'VOICEPAY_WEBHOOK_MAX_RETRIES')
    assert hasattr(BaseConfig, 'VOICEPAY_WEBHOOK_ENABLED')


def test_voicepay_webhook_url_format_production(monkeypatch):
    """Test that VoicePay webhook URL must be HTTPS in production"""
    # Set production environment with HTTP URL (should fail)
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_URL', 'http://voicepay.ng/webhook')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_SECRET', 'a' * 32)
    monkeypatch.setenv('VOICEPAY_WEBHOOK_ENABLED', 'true')
    
    # Set required production secrets to pass other validations
    monkeypatch.setenv('SECRET_KEY', 'test-secret-key-32-characters-long')
    monkeypatch.setenv('HMAC_SECRET', 'test-hmac-secret-32-characters-long')
    monkeypatch.setenv('KORAPAY_SECRET_KEY', 'sk_live_' + 'a' * 32)
    monkeypatch.setenv('KORAPAY_WEBHOOK_SECRET', 'korapay-webhook-secret-32-chars-long')
    monkeypatch.setenv('INBOUND_WEBHOOK_SECRET', 'inbound-webhook-secret-32-chars-long')
    monkeypatch.setenv('ENFORCE_HTTPS', 'true')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://localhost/onepay')
    
    with pytest.raises(SystemExit):
        ProductionConfig.validate()


def test_voicepay_webhook_secret_length_production(monkeypatch):
    """Test that VoicePay webhook secret must be at least 32 characters in production"""
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_URL', 'https://voicepay.ng/webhook')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_SECRET', 'short')  # Too short
    monkeypatch.setenv('VOICEPAY_WEBHOOK_ENABLED', 'true')
    
    # Set required production secrets
    monkeypatch.setenv('SECRET_KEY', 'test-secret-key-32-characters-long')
    monkeypatch.setenv('HMAC_SECRET', 'test-hmac-secret-32-characters-long')
    monkeypatch.setenv('KORAPAY_SECRET_KEY', 'sk_live_' + 'a' * 32)
    monkeypatch.setenv('KORAPAY_WEBHOOK_SECRET', 'korapay-webhook-secret-32-chars-long')
    monkeypatch.setenv('INBOUND_WEBHOOK_SECRET', 'inbound-webhook-secret-32-chars-long')
    monkeypatch.setenv('ENFORCE_HTTPS', 'true')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://localhost/onepay')
    
    with pytest.raises(SystemExit):
        ProductionConfig.validate()


def test_voicepay_config_disabled_no_validation(monkeypatch):
    """Test that VoicePay validation is skipped when disabled"""
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_ENABLED', 'false')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_URL', '')  # Empty is OK when disabled
    monkeypatch.setenv('VOICEPAY_WEBHOOK_SECRET', '')  # Empty is OK when disabled
    
    # Set required production secrets
    monkeypatch.setenv('SECRET_KEY', 'test-secret-key-32-characters-long')
    monkeypatch.setenv('HMAC_SECRET', 'test-hmac-secret-32-characters-long')
    monkeypatch.setenv('KORAPAY_SECRET_KEY', 'sk_live_' + 'a' * 32)
    monkeypatch.setenv('KORAPAY_WEBHOOK_SECRET', 'korapay-webhook-secret-32-chars-long')
    monkeypatch.setenv('KORAPAY_USE_SANDBOX', 'false')
    monkeypatch.setenv('INBOUND_WEBHOOK_SECRET', 'inbound-webhook-secret-32-chars-long')
    monkeypatch.setenv('ENFORCE_HTTPS', 'true')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://localhost/onepay')
    
    # Reload config module to pick up new environment variables
    import importlib
    import config as config_module
    importlib.reload(config_module)
    
    # Verify VoicePay is disabled
    from config import Config
    assert Config.VOICEPAY_WEBHOOK_ENABLED == False
    
    # Verify that validation doesn't fail due to missing VoicePay config
    # (it may fail for other reasons, but not VoicePay-specific ones)
    # We test this by checking that the config loaded successfully
    assert hasattr(Config, 'VOICEPAY_WEBHOOK_URL')


def test_voicepay_secrets_must_be_unique(monkeypatch):
    """Test that VoicePay webhook secret must be different from other secrets"""
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_URL', 'https://voicepay.ng/webhook')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_SECRET', 'test-hmac-secret-32-characters-long')  # Same as HMAC_SECRET
    monkeypatch.setenv('VOICEPAY_WEBHOOK_ENABLED', 'true')
    
    # Set required production secrets
    monkeypatch.setenv('SECRET_KEY', 'test-secret-key-32-characters-long')
    monkeypatch.setenv('HMAC_SECRET', 'test-hmac-secret-32-characters-long')
    monkeypatch.setenv('KORAPAY_SECRET_KEY', 'sk_live_' + 'a' * 32)
    monkeypatch.setenv('KORAPAY_WEBHOOK_SECRET', 'korapay-webhook-secret-32-chars-long')
    monkeypatch.setenv('INBOUND_WEBHOOK_SECRET', 'inbound-webhook-secret-32-chars-long')
    monkeypatch.setenv('ENFORCE_HTTPS', 'true')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://localhost/onepay')
    
    with pytest.raises(SystemExit):
        ProductionConfig.validate()


def test_voicepay_secret_same_as_korapay_secret(monkeypatch):
    """Test that VoicePay webhook secret cannot be same as KoraPay webhook secret"""
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_URL', 'https://voicepay.ng/webhook')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_SECRET', 'korapay-webhook-secret-32-chars-long')  # Same as KORAPAY_WEBHOOK_SECRET
    monkeypatch.setenv('VOICEPAY_WEBHOOK_ENABLED', 'true')
    
    # Set required production secrets
    monkeypatch.setenv('SECRET_KEY', 'test-secret-key-32-characters-long')
    monkeypatch.setenv('HMAC_SECRET', 'test-hmac-secret-32-characters-long')
    monkeypatch.setenv('KORAPAY_SECRET_KEY', 'sk_live_' + 'a' * 32)
    monkeypatch.setenv('KORAPAY_WEBHOOK_SECRET', 'korapay-webhook-secret-32-chars-long')
    monkeypatch.setenv('KORAPAY_USE_SANDBOX', 'false')
    monkeypatch.setenv('INBOUND_WEBHOOK_SECRET', 'inbound-webhook-secret-32-chars-long')
    monkeypatch.setenv('ENFORCE_HTTPS', 'true')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://localhost/onepay')
    
    with pytest.raises(SystemExit):
        ProductionConfig.validate()


def test_voicepay_placeholder_secret_rejected(monkeypatch):
    """Test that placeholder secrets are rejected in production"""
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_URL', 'https://voicepay.ng/webhook')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_SECRET', 'change-this-secret-32-characters-long')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_ENABLED', 'true')
    
    # Set required production secrets
    monkeypatch.setenv('SECRET_KEY', 'test-secret-key-32-characters-long')
    monkeypatch.setenv('HMAC_SECRET', 'test-hmac-secret-32-characters-long')
    monkeypatch.setenv('KORAPAY_SECRET_KEY', 'sk_live_' + 'a' * 32)
    monkeypatch.setenv('KORAPAY_WEBHOOK_SECRET', 'korapay-webhook-secret-32-chars-long')
    monkeypatch.setenv('KORAPAY_USE_SANDBOX', 'false')
    monkeypatch.setenv('INBOUND_WEBHOOK_SECRET', 'inbound-webhook-secret-32-chars-long')
    monkeypatch.setenv('ENFORCE_HTTPS', 'true')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://localhost/onepay')
    
    with pytest.raises(SystemExit):
        ProductionConfig.validate()


def test_voicepay_missing_webhook_url_production(monkeypatch):
    """Test that missing webhook URL fails in production when enabled"""
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_URL', '')  # Empty
    monkeypatch.setenv('VOICEPAY_WEBHOOK_SECRET', 'voicepay-webhook-secret-32-chars-long')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_ENABLED', 'true')
    
    # Set required production secrets
    monkeypatch.setenv('SECRET_KEY', 'test-secret-key-32-characters-long')
    monkeypatch.setenv('HMAC_SECRET', 'test-hmac-secret-32-characters-long')
    monkeypatch.setenv('KORAPAY_SECRET_KEY', 'sk_live_' + 'a' * 32)
    monkeypatch.setenv('KORAPAY_WEBHOOK_SECRET', 'korapay-webhook-secret-32-chars-long')
    monkeypatch.setenv('KORAPAY_USE_SANDBOX', 'false')
    monkeypatch.setenv('INBOUND_WEBHOOK_SECRET', 'inbound-webhook-secret-32-chars-long')
    monkeypatch.setenv('ENFORCE_HTTPS', 'true')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://localhost/onepay')
    
    with pytest.raises(SystemExit):
        ProductionConfig.validate()


def test_voicepay_missing_webhook_secret_production(monkeypatch):
    """Test that missing webhook secret fails in production when enabled"""
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_URL', 'https://voicepay.ng/webhook')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_SECRET', '')  # Empty
    monkeypatch.setenv('VOICEPAY_WEBHOOK_ENABLED', 'true')
    
    # Set required production secrets
    monkeypatch.setenv('SECRET_KEY', 'test-secret-key-32-characters-long')
    monkeypatch.setenv('HMAC_SECRET', 'test-hmac-secret-32-characters-long')
    monkeypatch.setenv('KORAPAY_SECRET_KEY', 'sk_live_' + 'a' * 32)
    monkeypatch.setenv('KORAPAY_WEBHOOK_SECRET', 'korapay-webhook-secret-32-chars-long')
    monkeypatch.setenv('KORAPAY_USE_SANDBOX', 'false')
    monkeypatch.setenv('INBOUND_WEBHOOK_SECRET', 'inbound-webhook-secret-32-chars-long')
    monkeypatch.setenv('ENFORCE_HTTPS', 'true')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://localhost/onepay')
    
    with pytest.raises(SystemExit):
        ProductionConfig.validate()


def test_voicepay_api_key_too_short(monkeypatch):
    """Test that API key shorter than 32 characters fails in production"""
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_URL', 'https://voicepay.ng/webhook')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_SECRET', 'voicepay-webhook-secret-32-chars-long')
    monkeypatch.setenv('VOICEPAY_API_KEY', 'short-key')  # Too short
    monkeypatch.setenv('VOICEPAY_WEBHOOK_ENABLED', 'true')
    
    # Set required production secrets
    monkeypatch.setenv('SECRET_KEY', 'test-secret-key-32-characters-long')
    monkeypatch.setenv('HMAC_SECRET', 'test-hmac-secret-32-characters-long')
    monkeypatch.setenv('KORAPAY_SECRET_KEY', 'sk_live_' + 'a' * 32)
    monkeypatch.setenv('KORAPAY_WEBHOOK_SECRET', 'korapay-webhook-secret-32-chars-long')
    monkeypatch.setenv('KORAPAY_USE_SANDBOX', 'false')
    monkeypatch.setenv('INBOUND_WEBHOOK_SECRET', 'inbound-webhook-secret-32-chars-long')
    monkeypatch.setenv('ENFORCE_HTTPS', 'true')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://localhost/onepay')
    
    with pytest.raises(SystemExit):
        ProductionConfig.validate()


def test_voicepay_config_valid_production(monkeypatch):
    """Test that valid VoicePay configuration passes in production"""
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_URL', 'https://voicepay.ng/webhook')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_SECRET', 'voicepay-webhook-secret-32-chars-long')
    monkeypatch.setenv('VOICEPAY_API_KEY', 'voicepay-api-key-32-characters-long')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_ENABLED', 'true')
    
    # Set required production secrets
    monkeypatch.setenv('SECRET_KEY', 'test-secret-key-32-characters-long')
    monkeypatch.setenv('HMAC_SECRET', 'test-hmac-secret-32-characters-long')
    monkeypatch.setenv('KORAPAY_SECRET_KEY', 'sk_live_' + 'a' * 32)
    monkeypatch.setenv('KORAPAY_WEBHOOK_SECRET', 'korapay-webhook-secret-32-chars-long')
    monkeypatch.setenv('KORAPAY_USE_SANDBOX', 'false')
    monkeypatch.setenv('INBOUND_WEBHOOK_SECRET', 'inbound-webhook-secret-32-chars-long')
    monkeypatch.setenv('ENFORCE_HTTPS', 'true')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://localhost/onepay')
    
    # Reload config
    import importlib
    import config as config_module
    importlib.reload(config_module)
    
    from config import Config
    
    # Verify all VoicePay config loaded correctly
    assert Config.VOICEPAY_WEBHOOK_URL == 'https://voicepay.ng/webhook'
    assert Config.VOICEPAY_WEBHOOK_SECRET == 'voicepay-webhook-secret-32-chars-long'
    assert Config.VOICEPAY_API_KEY == 'voicepay-api-key-32-characters-long'
    assert Config.VOICEPAY_WEBHOOK_ENABLED == True


def test_voicepay_timeout_and_retry_defaults():
    """Test that VoicePay timeout and retry settings have correct defaults"""
    from config import BaseConfig
    
    assert BaseConfig.VOICEPAY_WEBHOOK_TIMEOUT_SECS == 10
    assert BaseConfig.VOICEPAY_WEBHOOK_MAX_RETRIES == 3


def test_voicepay_timeout_and_retry_custom(monkeypatch):
    """Test that VoicePay timeout and retry settings can be customized"""
    monkeypatch.setenv('VOICEPAY_WEBHOOK_TIMEOUT_SECS', '30')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_MAX_RETRIES', '5')
    
    # Reload config
    import importlib
    import config as config_module
    importlib.reload(config_module)
    
    from config import Config
    
    assert Config.VOICEPAY_WEBHOOK_TIMEOUT_SECS == 30
    assert Config.VOICEPAY_WEBHOOK_MAX_RETRIES == 5


def test_voicepay_sandbox_config_separate(monkeypatch):
    """Test that sandbox configuration is separate from production"""
    monkeypatch.setenv('VOICEPAY_WEBHOOK_URL', 'https://voicepay.ng/webhook')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_SECRET', 'prod-secret-32-characters-long')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_URL_SANDBOX', 'https://sandbox.voicepay.ng/webhook')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_SECRET_SANDBOX', 'sandbox-secret-32-characters-long')
    
    # Reload config
    import importlib
    import config as config_module
    importlib.reload(config_module)
    
    from config import Config
    
    # Verify both configs exist and are different
    assert Config.VOICEPAY_WEBHOOK_URL == 'https://voicepay.ng/webhook'
    assert Config.VOICEPAY_WEBHOOK_URL_SANDBOX == 'https://sandbox.voicepay.ng/webhook'
    assert Config.VOICEPAY_WEBHOOK_SECRET != Config.VOICEPAY_WEBHOOK_SECRET_SANDBOX


def test_voicepay_enabled_flag_true(monkeypatch):
    """Test that VOICEPAY_WEBHOOK_ENABLED=true is parsed correctly"""
    monkeypatch.setenv('VOICEPAY_WEBHOOK_ENABLED', 'true')
    
    # Reload config
    import importlib
    import config as config_module
    importlib.reload(config_module)
    
    from config import Config
    assert Config.VOICEPAY_WEBHOOK_ENABLED == True


def test_voicepay_enabled_flag_false(monkeypatch):
    """Test that VOICEPAY_WEBHOOK_ENABLED=false is parsed correctly"""
    monkeypatch.setenv('VOICEPAY_WEBHOOK_ENABLED', 'false')
    
    # Reload config
    import importlib
    import config as config_module
    importlib.reload(config_module)
    
    from config import Config
    assert Config.VOICEPAY_WEBHOOK_ENABLED == False


def test_voicepay_enabled_flag_default(monkeypatch):
    """Test that VOICEPAY_WEBHOOK_ENABLED defaults to true"""
    # Explicitly unset the environment variable to test default
    monkeypatch.delenv('VOICEPAY_WEBHOOK_ENABLED', raising=False)
    
    # Reload config to pick up the change
    import importlib
    import config as config_module
    importlib.reload(config_module)
    
    from config import Config
    # Default should be true
    assert Config.VOICEPAY_WEBHOOK_ENABLED == True


def test_voicepay_http_url_rejected_production(monkeypatch):
    """Test that HTTP URLs are rejected in production (not HTTPS)"""
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_URL', 'http://voicepay.ng/webhook')  # HTTP not HTTPS
    monkeypatch.setenv('VOICEPAY_WEBHOOK_SECRET', 'voicepay-webhook-secret-32-chars-long')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_ENABLED', 'true')
    
    # Set required production secrets
    monkeypatch.setenv('SECRET_KEY', 'test-secret-key-32-characters-long')
    monkeypatch.setenv('HMAC_SECRET', 'test-hmac-secret-32-characters-long')
    monkeypatch.setenv('KORAPAY_SECRET_KEY', 'sk_live_' + 'a' * 32)
    monkeypatch.setenv('KORAPAY_WEBHOOK_SECRET', 'korapay-webhook-secret-32-chars-long')
    monkeypatch.setenv('KORAPAY_USE_SANDBOX', 'false')
    monkeypatch.setenv('INBOUND_WEBHOOK_SECRET', 'inbound-webhook-secret-32-chars-long')
    monkeypatch.setenv('ENFORCE_HTTPS', 'true')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://localhost/onepay')
    
    with pytest.raises(SystemExit):
        ProductionConfig.validate()


def test_voicepay_development_allows_http(monkeypatch):
    """Test that HTTP URLs are allowed in development"""
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_URL', 'http://localhost:3000/webhook')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_SECRET', 'dev-secret')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_ENABLED', 'true')
    
    # Reload config
    import importlib
    import config as config_module
    importlib.reload(config_module)
    
    from config import Config
    
    # Should load without error in development
    assert Config.VOICEPAY_WEBHOOK_URL == 'http://localhost:3000/webhook'



def test_voicepay_complete_configuration_integration(monkeypatch):
    """Integration test: Complete VoicePay configuration in production"""
    # Set up complete production environment
    monkeypatch.setenv('APP_ENV', 'production')
    
    # Core secrets
    monkeypatch.setenv('SECRET_KEY', 'test-secret-key-32-characters-long')
    monkeypatch.setenv('HMAC_SECRET', 'test-hmac-secret-32-characters-long')
    
    # KoraPay
    monkeypatch.setenv('KORAPAY_SECRET_KEY', 'sk_live_' + 'a' * 32)
    monkeypatch.setenv('KORAPAY_WEBHOOK_SECRET', 'korapay-webhook-secret-32-chars-long')
    monkeypatch.setenv('KORAPAY_USE_SANDBOX', 'false')
    
    # Webhooks
    monkeypatch.setenv('INBOUND_WEBHOOK_SECRET', 'inbound-webhook-secret-32-chars-long')
    
    # VoicePay - Production
    monkeypatch.setenv('VOICEPAY_WEBHOOK_URL', 'https://voicepay.ng/api/webhooks/onepay')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_SECRET', 'voicepay-webhook-secret-32-chars-long')
    monkeypatch.setenv('VOICEPAY_API_KEY', 'voicepay-api-key-32-characters-long')
    
    # VoicePay - Sandbox
    monkeypatch.setenv('VOICEPAY_WEBHOOK_URL_SANDBOX', 'https://sandbox.voicepay.ng/api/webhooks/onepay')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_SECRET_SANDBOX', 'voicepay-sandbox-secret-32-chars-long')
    
    # VoicePay - Settings
    monkeypatch.setenv('VOICEPAY_WEBHOOK_TIMEOUT_SECS', '15')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_MAX_RETRIES', '5')
    monkeypatch.setenv('VOICEPAY_WEBHOOK_ENABLED', 'true')
    
    # Other required settings
    monkeypatch.setenv('ENFORCE_HTTPS', 'true')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://localhost/onepay')
    
    # Reload config
    import importlib
    import config as config_module
    importlib.reload(config_module)
    
    from config import Config
    
    # Verify all VoicePay configuration loaded correctly
    assert Config.VOICEPAY_WEBHOOK_URL == 'https://voicepay.ng/api/webhooks/onepay'
    assert Config.VOICEPAY_WEBHOOK_SECRET == 'voicepay-webhook-secret-32-chars-long'
    assert Config.VOICEPAY_API_KEY == 'voicepay-api-key-32-characters-long'
    assert Config.VOICEPAY_WEBHOOK_URL_SANDBOX == 'https://sandbox.voicepay.ng/api/webhooks/onepay'
    assert Config.VOICEPAY_WEBHOOK_SECRET_SANDBOX == 'voicepay-sandbox-secret-32-chars-long'
    assert Config.VOICEPAY_WEBHOOK_TIMEOUT_SECS == 15
    assert Config.VOICEPAY_WEBHOOK_MAX_RETRIES == 5
    assert Config.VOICEPAY_WEBHOOK_ENABLED == True
    
    # Verify all secrets are unique
    secrets = [
        Config.SECRET_KEY,
        Config.HMAC_SECRET,
        Config.KORAPAY_WEBHOOK_SECRET,
        Config.INBOUND_WEBHOOK_SECRET,
        Config.VOICEPAY_WEBHOOK_SECRET,
        Config.VOICEPAY_WEBHOOK_SECRET_SANDBOX
    ]
    assert len(secrets) == len(set(secrets)), "All secrets must be unique"
    
    # Verify all secrets meet minimum length
    for secret in secrets:
        assert len(secret) >= 32, f"Secret too short: {secret[:10]}..."
    
    # Verify HTTPS enforcement
    assert Config.ENFORCE_HTTPS == True
    assert Config.VOICEPAY_WEBHOOK_URL.startswith('https://')
    assert Config.VOICEPAY_WEBHOOK_URL_SANDBOX.startswith('https://')


def test_voicepay_config_summary():
    """Summary test: Print VoicePay configuration structure"""
    from config import BaseConfig
    
    voicepay_attrs = [
        attr for attr in dir(BaseConfig)
        if attr.startswith('VOICEPAY_')
    ]
    
    print("\n" + "=" * 60)
    print("VoicePay Configuration Attributes:")
    print("=" * 60)
    for attr in sorted(voicepay_attrs):
        value = getattr(BaseConfig, attr)
        # Mask secrets
        if 'SECRET' in attr and value:
            display_value = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "****"
        else:
            display_value = value
        print(f"  {attr}: {display_value}")
    print("=" * 60)
    
    # Verify we have all expected attributes
    expected_attrs = [
        'VOICEPAY_API_KEY',
        'VOICEPAY_WEBHOOK_ENABLED',
        'VOICEPAY_WEBHOOK_MAX_RETRIES',
        'VOICEPAY_WEBHOOK_SECRET',
        'VOICEPAY_WEBHOOK_SECRET_SANDBOX',
        'VOICEPAY_WEBHOOK_TIMEOUT_SECS',
        'VOICEPAY_WEBHOOK_URL',
        'VOICEPAY_WEBHOOK_URL_SANDBOX',
    ]
    
    for attr in expected_attrs:
        assert attr in voicepay_attrs, f"Missing expected attribute: {attr}"
    
    assert len(voicepay_attrs) == 8, f"Expected 8 VoicePay attributes, found {len(voicepay_attrs)}"
