"""
Unit tests for secret validation at startup (Requirement 21).

Tests cover:
- Short secret rejection (< 32 characters)
- Identical secret rejection (SECRET_KEY == HMAC_SECRET)
- Development vs production behavior
- Placeholder secret detection
"""

import os
import sys
from unittest.mock import Mock, patch

import pytest


class TestSecretValidation:
    """Test secret validation at application startup."""

    def test_short_secret_key_rejected_in_production(self):
        """SECRET_KEY < 32 characters should cause startup failure in production."""
        with patch.dict(os.environ, {"APP_ENV": "production"}):
            with patch('config.BaseConfig.SECRET_KEY', 'short-secret'):
                with patch('config.BaseConfig.HMAC_SECRET', 'a' * 32):
                    with patch('sys.exit') as mock_exit:
                        from config import BaseConfig
                        BaseConfig.validate()

                        # Should call sys.exit(1) in production
                        mock_exit.assert_called_once_with(1)

    def test_short_hmac_secret_rejected_in_production(self):
        """HMAC_SECRET < 32 characters should cause startup failure in production."""
        with patch.dict(os.environ, {"APP_ENV": "production"}):
            with patch('config.BaseConfig.SECRET_KEY', 'a' * 32):
                with patch('config.BaseConfig.HMAC_SECRET', 'short-hmac'):
                    with patch('sys.exit') as mock_exit:
                        from config import BaseConfig
                        BaseConfig.validate()

                        # Should call sys.exit(1) in production
                        mock_exit.assert_called_once_with(1)

    def test_identical_secrets_rejected_in_production(self):
        """SECRET_KEY == HMAC_SECRET should cause startup failure in production."""
        with patch.dict(os.environ, {"APP_ENV": "production"}):
            same_secret = 'a' * 32
            with patch('config.BaseConfig.SECRET_KEY', same_secret):
                with patch('config.BaseConfig.HMAC_SECRET', same_secret):
                    with patch('sys.exit') as mock_exit:
                        from config import BaseConfig
                        BaseConfig.validate()

                        # Should call sys.exit(1) in production
                        mock_exit.assert_called_once_with(1)

    def test_placeholder_secret_key_rejected_in_production(self):
        """SECRET_KEY with 'change-this' should cause startup failure in production."""
        with patch.dict(os.environ, {"APP_ENV": "production"}):
            with patch('config.BaseConfig.SECRET_KEY', 'change-this-in-production'):
                with patch('config.BaseConfig.HMAC_SECRET', 'a' * 32):
                    with patch('sys.exit') as mock_exit:
                        from config import BaseConfig
                        BaseConfig.validate()

                        # Should call sys.exit(1) in production
                        mock_exit.assert_called_once_with(1)

    def test_placeholder_hmac_secret_rejected_in_production(self):
        """HMAC_SECRET with 'change-this' should cause startup failure in production."""
        with patch.dict(os.environ, {"APP_ENV": "production"}):
            with patch('config.BaseConfig.SECRET_KEY', 'a' * 32):
                with patch('config.BaseConfig.HMAC_SECRET', 'change-this-hmac-secret'):
                    with patch('sys.exit') as mock_exit:
                        from config import BaseConfig
                        BaseConfig.validate()

                        # Should call sys.exit(1) in production
                        mock_exit.assert_called_once_with(1)

    def test_short_secret_key_warns_in_development(self, caplog):
        """SECRET_KEY < 32 characters should log warning in development but not exit."""
        with patch.dict(os.environ, {"APP_ENV": "development"}):
            with patch('config.BaseConfig.SECRET_KEY', 'short-secret'):
                with patch('config.BaseConfig.HMAC_SECRET', 'a' * 32):
                    with patch('config.BaseConfig.INBOUND_WEBHOOK_SECRET', 'b' * 32):
                        with patch('sys.exit') as mock_exit:
                            from config import BaseConfig

                            # Clear any previous logs
                            caplog.clear()

                            BaseConfig.validate()

                            # Should NOT call sys.exit in development
                            mock_exit.assert_not_called()

                            # Should log warning
                            assert any('SECURITY WARNINGS' in record.message for record in caplog.records)
                            assert any('SECRET_KEY too short' in record.message for record in caplog.records)

    def test_identical_secrets_warn_in_development(self, caplog):
        """SECRET_KEY == HMAC_SECRET should log warning in development but not exit."""
        with patch.dict(os.environ, {"APP_ENV": "development"}):
            same_secret = 'a' * 32
            with patch('config.BaseConfig.SECRET_KEY', same_secret):
                with patch('config.BaseConfig.HMAC_SECRET', same_secret):
                    with patch('config.BaseConfig.INBOUND_WEBHOOK_SECRET', 'b' * 32):
                        with patch('sys.exit') as mock_exit:
                            from config import BaseConfig

                            # Clear any previous logs
                            caplog.clear()

                            BaseConfig.validate()

                            # Should NOT call sys.exit in development
                            mock_exit.assert_not_called()

                            # Should log warning
                            assert any('SECURITY WARNINGS' in record.message for record in caplog.records)
                            assert any('must be different' in record.message for record in caplog.records)

    def test_valid_secrets_pass_in_production(self):
        """Valid secrets (>= 32 chars, different) should pass in production."""
        with patch.dict(os.environ, {"APP_ENV": "production"}):
            with patch('config.BaseConfig.SECRET_KEY', 'a' * 32):
                with patch('config.BaseConfig.HMAC_SECRET', 'b' * 32):
                    with patch('config.BaseConfig.INBOUND_WEBHOOK_SECRET', 'c' * 32):
                        with patch('config.BaseConfig.KORAPAY_SECRET_KEY', 'sk_live_' + 'd' * 32):
                            with patch('config.BaseConfig.KORAPAY_WEBHOOK_SECRET', 'e' * 32):
                                with patch('config.BaseConfig.KORAPAY_USE_SANDBOX', False):
                                    with patch('config.BaseConfig.ENFORCE_HTTPS', True):
                                        with patch('config.BaseConfig.DEBUG', False):
                                            with patch('config.BaseConfig.DATABASE_URL', 'postgresql://localhost/test'):
                                                with patch('config.BaseConfig.GOOGLE_CLIENT_ID', ''):
                                                    with patch('config.BaseConfig.VOICEPAY_WEBHOOK_ENABLED', False):
                                                        with patch('sys.exit') as mock_exit:
                                                            from config import BaseConfig
                                                            BaseConfig.validate()

                                                            # Should NOT call sys.exit with valid secrets
                                                            mock_exit.assert_not_called()

    def test_valid_secrets_pass_in_development(self):
        """Valid secrets should pass in development without warnings."""
        with patch.dict(os.environ, {"APP_ENV": "development"}):
            with patch('config.BaseConfig.SECRET_KEY', 'a' * 32):
                with patch('config.BaseConfig.HMAC_SECRET', 'b' * 32):
                    with patch('config.BaseConfig.INBOUND_WEBHOOK_SECRET', 'c' * 32):
                        with patch('sys.exit') as mock_exit:
                            from config import BaseConfig
                            BaseConfig.validate()

                            # Should NOT call sys.exit
                            mock_exit.assert_not_called()

    def test_exactly_32_chars_passes(self):
        """Secrets with exactly 32 characters should pass validation."""
        with patch.dict(os.environ, {"APP_ENV": "production"}):
            with patch('config.BaseConfig.SECRET_KEY', 'a' * 32):
                with patch('config.BaseConfig.HMAC_SECRET', 'b' * 32):
                    with patch('config.BaseConfig.INBOUND_WEBHOOK_SECRET', 'c' * 32):
                        with patch('config.BaseConfig.KORAPAY_SECRET_KEY', 'sk_live_' + 'd' * 32):
                            with patch('config.BaseConfig.KORAPAY_WEBHOOK_SECRET', 'e' * 32):
                                with patch('config.BaseConfig.KORAPAY_USE_SANDBOX', False):
                                    with patch('config.BaseConfig.ENFORCE_HTTPS', True):
                                        with patch('config.BaseConfig.DEBUG', False):
                                            with patch('config.BaseConfig.DATABASE_URL', 'postgresql://localhost/test'):
                                                with patch('config.BaseConfig.GOOGLE_CLIENT_ID', ''):
                                                    with patch('config.BaseConfig.VOICEPAY_WEBHOOK_ENABLED', False):
                                                        with patch('sys.exit') as mock_exit:
                                                            from config import BaseConfig
                                                            BaseConfig.validate()

                                                            # Should NOT call sys.exit
                                                            mock_exit.assert_not_called()

    def test_31_chars_fails(self):
        """Secrets with 31 characters should fail validation."""
        with patch.dict(os.environ, {"APP_ENV": "production"}):
            with patch('config.BaseConfig.SECRET_KEY', 'a' * 31):
                with patch('config.BaseConfig.HMAC_SECRET', 'b' * 32):
                    with patch('sys.exit') as mock_exit:
                        from config import BaseConfig
                        BaseConfig.validate()

                        # Should call sys.exit(1) in production
                        mock_exit.assert_called_once_with(1)

    def test_multiple_errors_reported(self, caplog):
        """Multiple validation errors should all be reported."""
        with patch.dict(os.environ, {"APP_ENV": "development"}):
            with patch('config.BaseConfig.SECRET_KEY', 'short'):
                with patch('config.BaseConfig.HMAC_SECRET', 'short'):
                    with patch('config.BaseConfig.INBOUND_WEBHOOK_SECRET', ''):
                        with patch('sys.exit') as mock_exit:
                            from config import BaseConfig

                            # Clear any previous logs
                            caplog.clear()

                            BaseConfig.validate()

                            # Should NOT call sys.exit in development
                            mock_exit.assert_not_called()

                            # Should log multiple errors
                            log_messages = ' '.join([record.message for record in caplog.records])
                            assert 'SECRET_KEY too short' in log_messages
                            assert 'HMAC_SECRET too short' in log_messages
                            assert 'INBOUND_WEBHOOK_SECRET is required' in log_messages

    def test_testing_environment_uses_fixed_secrets(self):
        """Testing environment should use fixed secrets for deterministic tests."""
        from config import TestingConfig

        # TestingConfig should have fixed secrets
        assert TestingConfig.SECRET_KEY == "test-secret-key"
        assert TestingConfig.HMAC_SECRET == "test-hmac-secret"

        # Fixed secrets should be different
        assert TestingConfig.SECRET_KEY != TestingConfig.HMAC_SECRET
