"""
Unit tests for KoraPay service module.
"""

import os
from unittest.mock import patch

import pytest


class TestMockModeDetection:
    """Test mock mode detection based on KORAPAY_SECRET_KEY configuration."""

    def test_is_configured_returns_false_when_secret_key_empty(self) -> None:
        """Test is_configured() returns False when KORAPAY_SECRET_KEY is empty."""
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': ''}, clear=False):
            # Reload config to pick up env changes
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay
            assert korapay.is_configured() is False

    def test_is_configured_returns_false_when_secret_key_too_short(self) -> None:
        """Test is_configured() returns False when KORAPAY_SECRET_KEY < 32 chars."""
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': 'short_key_12345'}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay
            assert korapay.is_configured() is False

    def test_is_configured_returns_true_when_secret_key_valid(self) -> None:
        """Test is_configured() returns True when KORAPAY_SECRET_KEY >= 32 chars."""
        valid_key = 'sk_test_' + 'a' * 40  # 48 chars total
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay
            assert korapay.is_configured() is True

    def test_is_mock_returns_true_when_not_configured(self) -> None:
        """Test _is_mock() returns True when not configured."""
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': ''}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay
            assert korapay._is_mock() is True

    def test_is_transfer_configured_returns_true_in_mock_mode(self) -> None:
        """Test is_transfer_configured() returns True in mock mode."""
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': ''}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay
            assert korapay.is_transfer_configured() is True


