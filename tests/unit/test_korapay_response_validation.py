"""
Unit tests for KoraPay service module.
"""

import pytest
from unittest.mock import patch
import os

class TestResponseValidation:
    """Test response validation for required fields."""
    
    def test_validate_response_raises_error_when_field_missing(self):
        """Test _validate_response raises KoraPayError when required field missing."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib
            import config as config_module
            importlib.reload(config_module)
            
            from services.korapay import korapay, KoraPayError
            
            response = {
                "status": "success",
                "data": {
                    "reference": "TEST-123"
                    # Missing "amount" field
                }
            }
            
            required_fields = ["data.reference", "data.amount"]
            
            with pytest.raises(KoraPayError) as exc_info:
                korapay._validate_response(response, required_fields)
            
            assert "missing" in str(exc_info.value).lower()
    
    def test_validate_response_lists_all_missing_fields(self):
        """Test _validate_response lists all missing fields in error message."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib
            import config as config_module
            importlib.reload(config_module)
            
            from services.korapay import korapay, KoraPayError
            
            response = {
                "status": "success",
                "data": {
                    "reference": "TEST-123"
                    # Missing "amount" and "currency"
                }
            }
            
            required_fields = ["data.reference", "data.amount", "data.currency"]
            
            with pytest.raises(KoraPayError) as exc_info:
                korapay._validate_response(response, required_fields)
            
            error_msg = str(exc_info.value)
            # Should list both missing fields
            assert "data.amount" in error_msg
            assert "data.currency" in error_msg
    
    def test_validate_response_passes_when_all_fields_present(self):
        """Test _validate_response passes when all required fields present."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib
            import config as config_module
            importlib.reload(config_module)
            
            from services.korapay import korapay
            
            response = {
                "status": "success",
                "data": {
                    "reference": "TEST-123",
                    "amount": 1500,
                    "currency": "NGN"
                }
            }
            
            required_fields = ["data.reference", "data.amount", "data.currency"]
            
            # Should not raise any exception
            korapay._validate_response(response, required_fields)
    
    def test_validate_response_handles_nested_field_validation(self):
        """Test _validate_response handles nested field validation."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib
            import config as config_module
            importlib.reload(config_module)
            
            from services.korapay import korapay, KoraPayError
            
            # Test deeply nested field
            response = {
                "data": {
                    "bank_account": {
                        "account_number": "1234567890"
                        # Missing "bank_name"
                    }
                }
            }
            
            required_fields = ["data.bank_account.account_number", "data.bank_account.bank_name"]
            
            with pytest.raises(KoraPayError) as exc_info:
                korapay._validate_response(response, required_fields)
            
            assert "data.bank_account.bank_name" in str(exc_info.value)



