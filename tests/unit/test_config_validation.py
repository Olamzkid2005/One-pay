"""
Unit tests for configuration validation.

Tests KoraPay configuration validation in production environment.
"""

import pytest
import os
import sys
from unittest.mock import patch


class TestKoraPayConfigValidation:
    """Test KoraPay configuration validation in production."""
    
    def test_valid_production_configuration_passes(self):
        """Test that valid production configuration passes validation."""
        with patch.dict(os.environ, {
            'APP_ENV': 'production',
            'SECRET_KEY': 'a' * 64,
            'HMAC_SECRET': 'b' * 64,
            'KORAPAY_SECRET_KEY': 'sk_live_' + 'c' * 40,
            'KORAPAY_WEBHOOK_SECRET': 'd' * 64,
            'DATABASE_URL': 'postgresql://user:pass@localhost/db',
            'ENFORCE_HTTPS': 'true',
            'GOOGLE_CLIENT_ID': '',  # Empty to skip Google OAuth validation
        }, clear=True):
            # Reload config module to pick up new env vars
            import importlib
            import config as config_module
            importlib.reload(config_module)
            
            # Should not raise
            try:
                config_module.Config.validate()
            except SystemExit:
                pytest.fail("Valid configuration should not abort startup")
    
    def test_missing_korapay_secret_key_in_production_fails(self):
        """Test that missing KORAPAY_SECRET_KEY in production fails validation."""
        with patch.dict(os.environ, {
            'APP_ENV': 'production',
            'SECRET_KEY': 'a' * 64,
            'HMAC_SECRET': 'b' * 64,
            'KORAPAY_SECRET_KEY': '',
            'KORAPAY_WEBHOOK_SECRET': 'd' * 64,
            'DATABASE_URL': 'postgresql://user:pass@localhost/db',
            'ENFORCE_HTTPS': 'true',
        }):
            import importlib
            import config as config_module
            importlib.reload(config_module)
            
            with pytest.raises(SystemExit):
                config_module.Config.validate()
    
    def test_short_korapay_secret_key_fails(self):
        """Test that KORAPAY_SECRET_KEY < 32 chars fails validation."""
        with patch.dict(os.environ, {
            'APP_ENV': 'production',
            'SECRET_KEY': 'a' * 64,
            'HMAC_SECRET': 'b' * 64,
            'KORAPAY_SECRET_KEY': 'sk_live_short',
            'KORAPAY_WEBHOOK_SECRET': 'd' * 64,
            'DATABASE_URL': 'postgresql://user:pass@localhost/db',
            'ENFORCE_HTTPS': 'true',
        }):
            import importlib
            import config as config_module
            importlib.reload(config_module)
            
            with pytest.raises(SystemExit):
                config_module.Config.validate()
    
    def test_sk_test_key_in_production_fails(self):
        """Test that sk_test_ key in production fails validation."""
        with patch.dict(os.environ, {
            'APP_ENV': 'production',
            'SECRET_KEY': 'a' * 64,
            'HMAC_SECRET': 'b' * 64,
            'KORAPAY_SECRET_KEY': 'sk_test_' + 'c' * 40,
            'KORAPAY_WEBHOOK_SECRET': 'd' * 64,
            'DATABASE_URL': 'postgresql://user:pass@localhost/db',
            'ENFORCE_HTTPS': 'true',
        }):
            import importlib
            import config as config_module
            importlib.reload(config_module)
            
            with pytest.raises(SystemExit):
                config_module.Config.validate()
    
    def test_duplicate_secrets_fail_validation(self):
        """Test that duplicate secrets fail validation."""
        with patch.dict(os.environ, {
            'APP_ENV': 'production',
            'SECRET_KEY': 'a' * 64,
            'HMAC_SECRET': 'b' * 64,
            'KORAPAY_SECRET_KEY': 'sk_live_' + 'c' * 40,
            'KORAPAY_WEBHOOK_SECRET': 'b' * 64,  # Same as HMAC_SECRET
            'DATABASE_URL': 'postgresql://user:pass@localhost/db',
            'ENFORCE_HTTPS': 'true',
        }):
            import importlib
            import config as config_module
            importlib.reload(config_module)
            
            with pytest.raises(SystemExit):
                config_module.Config.validate()
    
    def test_placeholder_values_fail_in_production(self):
        """Test that placeholder values fail in production."""
        with patch.dict(os.environ, {
            'APP_ENV': 'production',
            'SECRET_KEY': 'a' * 64,
            'HMAC_SECRET': 'b' * 64,
            'KORAPAY_SECRET_KEY': 'sk_live_change-this-in-production',
            'KORAPAY_WEBHOOK_SECRET': 'd' * 64,
            'DATABASE_URL': 'postgresql://user:pass@localhost/db',
            'ENFORCE_HTTPS': 'true',
        }):
            import importlib
            import config as config_module
            importlib.reload(config_module)
            
            with pytest.raises(SystemExit):
                config_module.Config.validate()
