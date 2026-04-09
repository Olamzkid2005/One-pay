"""
Unit tests for KoraPay service module.
"""

import os
from unittest.mock import patch

import pytest


class TestStatusMapping:
    """Test status mapping for transfer confirmation."""

    def test_normalize_confirm_response_maps_success_to_00(self):
        """Test _normalize_confirm_response maps 'success' to '00'."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            kora_response = {
                "reference": "TEST-REF",
                "payment_reference": "KPY-PAY-TEST",
                "status": "success",
                "amount": 1500,
                "currency": "NGN"
            }

            result = korapay._normalize_confirm_response(kora_response)
            assert result["responseCode"] == "00"

    def test_normalize_confirm_response_maps_processing_to_z0(self):
        """Test _normalize_confirm_response maps 'processing' to 'Z0'."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            kora_response = {
                "reference": "TEST-REF",
                "payment_reference": "KPY-CA-TEST",
                "status": "processing",
                "amount": 1500,
                "currency": "NGN"
            }

            result = korapay._normalize_confirm_response(kora_response)
            assert result["responseCode"] == "Z0"

    def test_normalize_confirm_response_maps_failed_to_99(self):
        """Test _normalize_confirm_response maps 'failed' to '99'."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            kora_response = {
                "reference": "TEST-REF",
                "payment_reference": "KPY-PAY-TEST",
                "status": "failed",
                "amount": 1500,
                "currency": "NGN"
            }

            result = korapay._normalize_confirm_response(kora_response)
            assert result["responseCode"] == "99"

    def test_normalize_confirm_response_preserves_transaction_reference(self):
        """Test _normalize_confirm_response preserves transaction_reference in response."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            kora_response = {
                "reference": "ONEPAY-UNIQUE-REF-12345",
                "payment_reference": "KPY-PAY-TEST",
                "status": "success",
                "amount": 1500,
                "currency": "NGN"
            }

            result = korapay._normalize_confirm_response(kora_response)
            assert result["transactionReference"] == "ONEPAY-UNIQUE-REF-12345"



