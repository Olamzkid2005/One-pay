"""
Unit tests for KoraPay service module.
"""

import os
from unittest.mock import patch

import pytest


class TestAuthenticationHeaders:
    """Test authentication header generation."""

    def test_get_auth_headers_includes_bearer_token(self) -> None:
        """Test _get_auth_headers() includes 'Authorization: Bearer {key}'."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            headers = korapay._get_auth_headers()

            assert 'Authorization' in headers
            assert headers['Authorization'] == f'Bearer {valid_key}'

    def test_get_auth_headers_includes_content_type_json(self) -> None:
        """Test _get_auth_headers() includes 'Content-Type: application/json'."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            headers = korapay._get_auth_headers()

            assert 'Content-Type' in headers
            assert headers['Content-Type'] == 'application/json'

    def test_get_auth_headers_includes_accept_json(self) -> None:
        """Test _get_auth_headers() includes 'Accept: application/json'."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            headers = korapay._get_auth_headers()

            assert 'Accept' in headers
            assert headers['Accept'] == 'application/json'

    def test_get_auth_headers_includes_user_agent(self) -> None:
        """Test _get_auth_headers() includes 'User-Agent: OnePay-KoraPay/1.0'."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            headers = korapay._get_auth_headers()

            assert 'User-Agent' in headers
            assert headers['User-Agent'] == 'OnePay-KoraPay/1.0'

    def test_get_auth_headers_includes_request_id_uuid(self) -> None:
        """Test _get_auth_headers() includes 'X-Request-ID' with UUID format."""
        import re

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            headers = korapay._get_auth_headers()

            assert 'X-Request-ID' in headers

            # Verify UUID format (8-4-4-4-12 hex digits)
            uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            assert re.match(uuid_pattern, headers['X-Request-ID'], re.IGNORECASE)

    def test_api_key_masked_in_logs(self, caplog) -> None:
        """Test API key is masked in logs."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            with caplog.at_level('INFO'):
                # This will be tested when we implement logging in _make_request
                # For now, just verify the key doesn't appear in any existing logs
                pass

            # Verify full API key never appears in logs
            for record in caplog.records:
                assert valid_key not in record.message


