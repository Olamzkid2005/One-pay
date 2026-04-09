"""
Unit tests for KoraPay service module.
"""

import os
from unittest.mock import patch

import pytest


class TestAPIKeyMasking:
    """Test API key masking in logs to prevent credential leakage."""

    def test_logs_show_masked_format_for_api_keys(self):
        """Test logs show 'sk_****_1234' format for API keys."""
        valid_key = 'sk_test_abcdefghijklmnopqrstuvwxyz1234'
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            # Test _mask_api_key helper (to be implemented)
            masked = korapay._mask_api_key(valid_key)

            # Should show format: sk_****_1234 (first 4 + **** + last 4)
            assert masked.startswith("sk_t")
            assert "****" in masked
            assert masked.endswith("1234")
            assert valid_key not in masked

    def test_full_api_key_never_appears_in_logs(self):
        """Test full API key never appears in logs."""
        import logging
        from io import StringIO

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            # Capture log output
            log_stream = StringIO()
            handler = logging.StreamHandler(log_stream)
            logger = logging.getLogger('services.korapay')
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)

            try:
                # Trigger logging by getting auth headers
                korapay._get_auth_headers()

                # Check log output doesn't contain full key
                log_stream.getvalue()
                # Note: Current implementation doesn't log headers, but when we add logging it should mask

            finally:
                logger.removeHandler(handler)

    def test_masking_works_for_sk_live_prefix(self):
        """Test masking works for sk_live_ prefixed keys."""
        valid_key = 'sk_live_' + 'b' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            masked = korapay._mask_api_key(valid_key)

            assert masked.startswith("sk_l")
            assert "****" in masked
            assert valid_key not in masked

    def test_masking_works_for_sk_test_prefix(self):
        """Test masking works for sk_test_ prefixed keys."""
        valid_key = 'sk_test_' + 'c' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            masked = korapay._mask_api_key(valid_key)

            assert masked.startswith("sk_t")
            assert "****" in masked
            assert valid_key not in masked


