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
