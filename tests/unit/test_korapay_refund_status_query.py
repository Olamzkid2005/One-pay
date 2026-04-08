"""
Unit tests for KoraPay service module.
"""

import pytest
from unittest.mock import patch
import os

class TestRefundStatusQuery:
    """Test refund status query functionality."""
    
    def test_query_refund_makes_get_to_refunds_reference(self):
        """Test query_refund makes GET to /refunds/{reference} endpoint."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib
            import config as config_module
            importlib.reload(config_module)
            
            from services.korapay import korapay
            from unittest.mock import MagicMock
            
            korapay._make_request = MagicMock(return_value={
                "status": True,
                "message": "Refund retrieved successfully",
                "data": {
                    "reference": "REFUND-TEST-123",
                    "payment_reference": "ONEPAY-TEST-123",
                    "amount": 1000,
                    "status": "success",
                    "currency": "NGN",
                    "created_at": "2024-01-01T00:00:00Z",
                    "processed_at": "2024-01-01T00:05:00Z"
                }
            })
            
            result = korapay.query_refund("REFUND-TEST-123")
            
            # Verify GET request was made to correct endpoint
            korapay._make_request.assert_called_once()
            call_args = korapay._make_request.call_args
            assert call_args[0][0] == "GET"
            assert "/refunds/REFUND-TEST-123" in call_args[0][1]
    
    def test_query_refund_parses_response_correctly(self):
        """Test parses response correctly with all required fields."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib
            import config as config_module
            importlib.reload(config_module)
            
            from services.korapay import korapay
            from unittest.mock import MagicMock
            
            korapay._make_request = MagicMock(return_value={
                "status": True,
                "message": "Refund retrieved successfully",
                "data": {
                    "reference": "REFUND-TEST-123",
                    "payment_reference": "ONEPAY-TEST-123",
                    "amount": 1000,
                    "status": "success",
                    "currency": "NGN",
                    "created_at": "2024-01-01T00:00:00Z",
                    "processed_at": "2024-01-01T00:05:00Z"
                }
            })
            
            result = korapay.query_refund("REFUND-TEST-123")
            
            # Verify response contains expected fields
            assert result["reference"] == "REFUND-TEST-123"
            assert result["payment_reference"] == "ONEPAY-TEST-123"
            assert result["amount"] == 1000
            assert result["status"] == "success"
            assert result["currency"] == "NGN"
    
    def test_query_refund_handles_404_not_found(self):
        """Test handles 404 error when refund not found."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib
            import config as config_module
            importlib.reload(config_module)
            
            from services.korapay import korapay, KoraPayError
            from unittest.mock import MagicMock
            
            korapay._make_request = MagicMock(side_effect=KoraPayError(
                "Refund not found",
                error_code="NOT_FOUND",
                status_code=404
            ))
            
            with pytest.raises(KoraPayError) as exc_info:
                korapay.query_refund("REFUND-NONEXISTENT")

            assert exc_info.value.status_code == 404


