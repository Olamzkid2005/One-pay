"""
Unit tests for KoraPay service module.
"""

import pytest
from unittest.mock import patch
import os

class TestErrorHandling:
    """Test comprehensive error handling in _make_request method."""
    
    def test_timeout_error_returns_user_friendly_message(self):
        """Test timeout errors return user-friendly message with TIMEOUT code."""
        import requests
        from unittest.mock import Mock
        
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib
            import config as config_module
            importlib.reload(config_module)
            
            from services.korapay import korapay, KoraPayError
            
            # Mock session to raise Timeout
            with patch.object(korapay._session, 'request', side_effect=requests.Timeout("Connection timeout")):
                with pytest.raises(KoraPayError) as exc_info:
                    korapay._make_request("GET", "/test")
                
                assert "timeout" in exc_info.value.message.lower()
                assert exc_info.value.error_code == "TIMEOUT"
    
    def test_401_error_returns_authentication_error_message(self):
        """Test 401 errors return authentication error message."""
        import requests
        from unittest.mock import Mock
        
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib
            import config as config_module
            importlib.reload(config_module)
            
            from services.korapay import korapay, KoraPayError
            
            # Mock 401 response
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.json.return_value = {"message": "Invalid API key"}
            
            with patch.object(korapay._session, 'request', return_value=mock_response):
                with pytest.raises(KoraPayError) as exc_info:
                    korapay._make_request("GET", "/test")
                
                assert exc_info.value.status_code == 401
                assert "401" in exc_info.value.message
    
    def test_500_error_triggers_retry_logic(self):
        """Test 500 errors trigger retry logic with exponential backoff."""
        import requests
        from unittest.mock import Mock, call
        import time
        
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key, 'KORAPAY_MAX_RETRIES': '3'}, clear=False):
            import importlib
            import config as config_module
            importlib.reload(config_module)
            
            from services.korapay import korapay, KoraPayError
            
            # Mock 500 response
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.json.return_value = {}
            
            with patch.object(korapay._session, 'request', return_value=mock_response):
                with patch('time.sleep') as mock_sleep:
                    with pytest.raises(KoraPayError) as exc_info:
                        korapay._make_request("GET", "/test")
                    
                    # Should retry 3 times (attempts 1, 2, 3)
                    assert korapay._session.request.call_count == 3
                    assert "Server error" in exc_info.value.message
                    assert exc_info.value.error_code == "SERVER_ERROR"
                    
                    # Verify exponential backoff (sleep called between retries)
                    assert mock_sleep.call_count == 2  # Sleep between attempt 1-2 and 2-3
    
    def test_connection_error_returns_connection_error_message(self):
        """Test connection errors return connection error message with CONNECTION_ERROR code."""
        import requests
        from unittest.mock import Mock
        
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib
            import config as config_module
            importlib.reload(config_module)
            
            from services.korapay import korapay, KoraPayError
            
            # Mock session to raise ConnectionError
            with patch.object(korapay._session, 'request', side_effect=requests.ConnectionError("Failed to connect")):
                with pytest.raises(KoraPayError) as exc_info:
                    korapay._make_request("GET", "/test")
                
                assert "Connection failed" in exc_info.value.message
                assert exc_info.value.error_code == "CONNECTION_ERROR"
    
    def test_ssl_error_returns_security_error_message(self):
        """Test SSL errors return security error message with SSL_ERROR code and no retry."""
        import requests
        from unittest.mock import Mock
        
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib
            import config as config_module
            importlib.reload(config_module)
            
            from services.korapay import korapay, KoraPayError
            
            # Mock session to raise SSLError
            with patch.object(korapay._session, 'request', side_effect=requests.exceptions.SSLError("SSL verification failed")):
                with pytest.raises(KoraPayError) as exc_info:
                    korapay._make_request("GET", "/test")
                
                # Should not retry SSL errors
                assert korapay._session.request.call_count == 1
                assert "security error" in exc_info.value.message.lower()
                assert exc_info.value.error_code == "SSL_ERROR"
    
    def test_json_decode_error_returns_invalid_response_message(self):
        """Test JSON decode errors return invalid response message with INVALID_JSON code."""
        import requests
        from unittest.mock import Mock
        
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib
            import config as config_module
            importlib.reload(config_module)
            
            from services.korapay import korapay, KoraPayError
            
            # Mock response with invalid JSON
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.side_effect = requests.exceptions.JSONDecodeError("Invalid JSON", "", 0)
            
            with patch.object(korapay._session, 'request', return_value=mock_response):
                with pytest.raises(KoraPayError) as exc_info:
                    korapay._make_request("GET", "/test")
                
                assert "INVALID_JSON" in exc_info.value.error_code
    
    def test_missing_field_errors_list_all_missing_fields(self):
        """Test missing field errors list all missing fields in error message."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib
            import config as config_module
            importlib.reload(config_module)
            
            from services.korapay import korapay, KoraPayError
            
            # Response missing multiple fields
            response = {
                "data": {
                    "reference": "REF123"
                    # Missing: status, amount, bank_account
                }
            }
            
            required_fields = [
                "data.reference",
                "data.status",
                "data.amount",
                "data.bank_account.account_number"
            ]
            
            with pytest.raises(KoraPayError) as exc_info:
                korapay._validate_response(response, required_fields)
            
            # Should list all missing fields
            assert "data.status" in exc_info.value.message
            assert "data.amount" in exc_info.value.message
            assert "data.bank_account.account_number" in exc_info.value.message
            assert "data.reference" not in exc_info.value.message  # This one exists
    
    def test_api_keys_never_appear_in_error_messages(self):
        """Test API keys never appear in error messages (should be masked)."""
        import requests
        from unittest.mock import Mock
        
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib
            import config as config_module
            importlib.reload(config_module)
            
            from services.korapay import korapay, KoraPayError
            
            # Mock 401 response
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.json.return_value = {"message": "Invalid API key"}
            
            with patch.object(korapay._session, 'request', return_value=mock_response):
                with pytest.raises(KoraPayError) as exc_info:
                    korapay._make_request("GET", "/test")
                
                # API key should NOT appear in error message
                assert valid_key not in exc_info.value.message
                assert valid_key not in str(exc_info.value)


