"""
Unit tests for KoraPay service module.
"""

import os
from unittest.mock import patch

import pytest


class TestRetryLogic:
    """Test HTTP request retry logic with exponential backoff."""

    def test_make_request_retries_500_errors_three_times(self) -> None:
        """Test _make_request retries 500 errors 3 times with exponential backoff."""
        from unittest.mock import Mock, patch

        import requests

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import KoraPayError, korapay

            # Mock response with 500 error
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"

            with patch.object(korapay._session, 'request', return_value=mock_response) as mock_request:
                with patch('time.sleep'):  # Skip actual sleep delays
                    with pytest.raises(KoraPayError) as exc_info:
                        korapay._make_request('GET', '/test-endpoint')

                    # Should have tried 3 times (initial + 2 retries)
                    assert mock_request.call_count == 3
                    assert 'after 3 attempts' in str(exc_info.value).lower()

    def test_make_request_retries_502_errors(self) -> None:
        """Test _make_request retries 502 errors."""
        from unittest.mock import Mock, patch

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import KoraPayError, korapay

            mock_response = Mock()
            mock_response.status_code = 502
            mock_response.text = "Bad Gateway"

            with patch.object(korapay._session, 'request', return_value=mock_response):
                with patch('time.sleep'):
                    with pytest.raises(KoraPayError):
                        korapay._make_request('GET', '/test-endpoint')

    def test_make_request_retries_503_errors(self) -> None:
        """Test _make_request retries 503 errors."""
        from unittest.mock import Mock, patch

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import KoraPayError, korapay

            mock_response = Mock()
            mock_response.status_code = 503
            mock_response.text = "Service Unavailable"

            with patch.object(korapay._session, 'request', return_value=mock_response):
                with patch('time.sleep'):
                    with pytest.raises(KoraPayError):
                        korapay._make_request('GET', '/test-endpoint')

    def test_make_request_retries_504_errors(self) -> None:
        """Test _make_request retries 504 errors."""
        from unittest.mock import Mock, patch

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import KoraPayError, korapay

            mock_response = Mock()
            mock_response.status_code = 504
            mock_response.text = "Gateway Timeout"

            with patch.object(korapay._session, 'request', return_value=mock_response):
                with patch('time.sleep'):
                    with pytest.raises(KoraPayError):
                        korapay._make_request('GET', '/test-endpoint')

    def test_make_request_retries_timeout_errors(self) -> None:
        """Test _make_request retries timeout errors."""
        from unittest.mock import patch

        import requests

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import KoraPayError, korapay

            with patch.object(korapay._session, 'request', side_effect=requests.Timeout("Request timeout")):
                with patch('time.sleep'):
                    with pytest.raises(KoraPayError) as exc_info:
                        korapay._make_request('GET', '/test-endpoint')

                    assert 'timeout' in str(exc_info.value).lower()

    def test_make_request_retries_connection_error(self) -> None:
        """Test _make_request retries ConnectionError."""
        from unittest.mock import patch

        import requests

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import KoraPayError, korapay

            with patch.object(korapay._session, 'request', side_effect=requests.ConnectionError("Connection failed")):
                with patch('time.sleep'):
                    with pytest.raises(KoraPayError) as exc_info:
                        korapay._make_request('GET', '/test-endpoint')

                    assert 'connection' in str(exc_info.value).lower() or 'failed' in str(exc_info.value).lower()

    def test_make_request_does_not_retry_400_errors(self) -> None:
        """Test _make_request does NOT retry 400-499 errors (except 429)."""
        from unittest.mock import Mock, patch

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import KoraPayError, korapay

            # Test various 4xx errors
            for status_code in [400, 401, 403, 404, 422]:
                mock_response = Mock()
                mock_response.status_code = status_code
                mock_response.text = f"Error {status_code}"
                mock_response.json.return_value = {"message": f"Error {status_code}"}

                with patch.object(korapay._session, 'request', return_value=mock_response) as mock_request:
                    with pytest.raises(KoraPayError):
                        korapay._make_request('GET', '/test-endpoint')

                    # Should only try once (no retries for 4xx)
                    assert mock_request.call_count == 1
                    mock_request.reset_mock()

    def test_make_request_retries_429_with_retry_after_header(self) -> None:
        """Test _make_request retries 429 with Retry-After header."""
        from unittest.mock import Mock, patch

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import KoraPayError, korapay

            # First call returns 429, subsequent calls also return 429
            mock_response_429 = Mock()
            mock_response_429.status_code = 429
            mock_response_429.headers = {'Retry-After': '2'}
            mock_response_429.text = "Rate limit exceeded"

            with patch.object(korapay._session, 'request', return_value=mock_response_429) as mock_request:
                with patch('time.sleep') as mock_sleep:
                    with pytest.raises(KoraPayError):
                        korapay._make_request('GET', '/test-endpoint')

                    # Should retry 429 errors
                    assert mock_request.call_count == 3
                    # Should use Retry-After header value
                    assert any(call[0][0] == 2 for call in mock_sleep.call_args_list)

    def test_exponential_backoff_delays(self) -> None:
        """Test exponential backoff delays: 1s, 2s, 4s."""
        from unittest.mock import Mock, patch

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import KoraPayError, korapay

            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"

            with patch.object(korapay._session, 'request', return_value=mock_response):
                with patch('time.sleep') as mock_sleep:
                    with pytest.raises(KoraPayError):
                        korapay._make_request('GET', '/test-endpoint')

                    # Check that sleep was called with exponential backoff
                    # First retry: ~1s, second retry: ~2s
                    sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
                    assert len(sleep_calls) == 2  # 2 retries after initial attempt

                    # Verify exponential pattern (allowing for jitter)
                    # First delay should be around 1s (2^0 + jitter)
                    assert 0.5 <= sleep_calls[0] <= 2.0
                    # Second delay should be around 2s (2^1 + jitter)
                    assert 1.5 <= sleep_calls[1] <= 3.0

    def test_max_three_retry_attempts(self) -> None:
        """Test max 3 retry attempts."""
        from unittest.mock import Mock, patch

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import KoraPayError, korapay

            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"

            with patch.object(korapay._session, 'request', return_value=mock_response) as mock_request:
                with patch('time.sleep'):
                    with pytest.raises(KoraPayError):
                        korapay._make_request('GET', '/test-endpoint')

                    # Should try exactly 3 times (initial + 2 retries)
                    assert mock_request.call_count == 3


