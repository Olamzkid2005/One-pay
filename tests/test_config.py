# tests/test_config.py
"""Tests for configuration values"""
import os
import pytest


def test_api_key_config_defaults():
    """Test API key configuration defaults"""
    from config import BaseConfig
    
    assert BaseConfig.API_KEY_MAX_PER_USER == 10
    assert BaseConfig.API_KEY_GENERATION_RATE_LIMIT == 5


def test_inbound_webhook_config_defaults():
    """Test inbound webhook configuration defaults"""
    from config import BaseConfig
    
    assert BaseConfig.INBOUND_WEBHOOK_SECRET == ""


def test_api_rate_limit_config_defaults():
    """Test API rate limit configuration defaults"""
    from config import BaseConfig
    
    assert BaseConfig.RATE_LIMIT_API_LINK_CREATE == 100
    assert BaseConfig.RATE_LIMIT_API_STATUS_CHECK == 500


def test_production_validates_inbound_webhook_secret(monkeypatch):
    """Test production requires INBOUND_WEBHOOK_SECRET"""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "a" * 32)
    monkeypatch.setenv("HMAC_SECRET", "b" * 32)
    monkeypatch.setenv("WEBHOOK_SECRET", "c" * 32)
    monkeypatch.setenv("KORAPAY_SECRET_KEY", "sk_live_" + "d" * 32)
    monkeypatch.setenv("KORAPAY_WEBHOOK_SECRET", "e" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.setenv("INBOUND_WEBHOOK_SECRET", "")  # Empty
    
    from config import ProductionConfig
    
    with pytest.raises(SystemExit):
        ProductionConfig.validate()


def test_production_validates_inbound_webhook_secret_length(monkeypatch):
    """Test production requires INBOUND_WEBHOOK_SECRET minimum 32 chars"""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "a" * 32)
    monkeypatch.setenv("HMAC_SECRET", "b" * 32)
    monkeypatch.setenv("WEBHOOK_SECRET", "c" * 32)
    monkeypatch.setenv("KORAPAY_SECRET_KEY", "sk_live_" + "d" * 32)
    monkeypatch.setenv("KORAPAY_WEBHOOK_SECRET", "e" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.setenv("INBOUND_WEBHOOK_SECRET", "short")  # Too short
    
    from config import ProductionConfig
    
    with pytest.raises(SystemExit):
        ProductionConfig.validate()
