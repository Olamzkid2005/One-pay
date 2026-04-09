"""
Unit tests for KoraPay service module.
"""

import os
from unittest.mock import patch

import pytest


class TestResponseNormalization:
    """Test response normalization for virtual account creation."""

    def test_normalize_create_response_converts_korapay_to_quickteller_format(self):
        """Test _normalize_create_response converts KoraPay format to Quickteller format."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            kora_response = {
                "reference": "ONEPAY-TEST",
                "payment_reference": "KPY-CA-TEST",
                "status": "processing",
                "currency": "NGN",
                "amount": 1500,
                "fee": 22.5,
                "vat": 1.69,
                "amount_expected": 1524.19,
                "bank_account": {
                    "account_number": "1234567890",
                    "bank_name": "wema bank",
                    "account_name": "Test Merchant",
                    "bank_code": "035",
                    "expiry_date_in_utc": "2024-01-01T12:30:00Z"
                }
            }

            result = korapay._normalize_create_response(kora_response, 150000)

            # Check all fields are mapped correctly
            assert result["accountNumber"] == "1234567890"
            assert result["bankName"] == "Wema Bank"  # Capitalized
            assert result["accountName"] == "Test Merchant"
            assert result["amount"] == 150000  # kobo
            assert result["transactionReference"] == "ONEPAY-TEST"
            assert result["responseCode"] == "Z0"

    def test_normalize_create_response_maps_account_number(self):
        """Test _normalize_create_response maps data.bank_account.account_number to accountNumber."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            kora_response = {
                "reference": "TEST",
                "payment_reference": "KPY-CA-TEST",
                "status": "processing",
                "bank_account": {
                    "account_number": "9876543210",
                    "bank_name": "Test Bank",
                    "account_name": "Test",
                    "bank_code": "035",
                    "expiry_date_in_utc": "2024-01-01T12:30:00Z"
                }
            }

            result = korapay._normalize_create_response(kora_response, 100000)
            assert result["accountNumber"] == "9876543210"

    def test_normalize_create_response_capitalizes_bank_name(self):
        """Test _normalize_create_response maps data.bank_account.bank_name to bankName (capitalize)."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            kora_response = {
                "reference": "TEST",
                "payment_reference": "KPY-CA-TEST",
                "status": "processing",
                "bank_account": {
                    "account_number": "1234567890",
                    "bank_name": "access bank",
                    "account_name": "Test",
                    "bank_code": "044",
                    "expiry_date_in_utc": "2024-01-01T12:30:00Z"
                }
            }

            result = korapay._normalize_create_response(kora_response, 100000)
            assert result["bankName"] == "Access Bank"

    def test_normalize_create_response_maps_account_name(self):
        """Test _normalize_create_response maps data.bank_account.account_name to accountName."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            kora_response = {
                "reference": "TEST",
                "payment_reference": "KPY-CA-TEST",
                "status": "processing",
                "bank_account": {
                    "account_number": "1234567890",
                    "bank_name": "Test Bank",
                    "account_name": "John Doe - OnePay Payment",
                    "bank_code": "035",
                    "expiry_date_in_utc": "2024-01-01T12:30:00Z"
                }
            }

            result = korapay._normalize_create_response(kora_response, 100000)
            assert result["accountName"] == "John Doe - OnePay Payment"

    def test_normalize_create_response_converts_amount_to_kobo(self):
        """Test _normalize_create_response converts amount from Naira to kobo (multiply by 100)."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            kora_response = {
                "reference": "TEST",
                "payment_reference": "KPY-CA-TEST",
                "status": "processing",
                "amount": 2500,  # Naira
                "bank_account": {
                    "account_number": "1234567890",
                    "bank_name": "Test Bank",
                    "account_name": "Test",
                    "bank_code": "035",
                    "expiry_date_in_utc": "2024-01-01T12:30:00Z"
                }
            }

            # Pass original amount_kobo
            result = korapay._normalize_create_response(kora_response, 250000)
            assert result["amount"] == 250000  # kobo

    def test_normalize_create_response_sets_response_code_z0_for_processing(self):
        """Test _normalize_create_response sets responseCode to 'Z0' for processing status."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            kora_response = {
                "reference": "TEST",
                "payment_reference": "KPY-CA-TEST",
                "status": "processing",
                "bank_account": {
                    "account_number": "1234567890",
                    "bank_name": "Test Bank",
                    "account_name": "Test",
                    "bank_code": "035",
                    "expiry_date_in_utc": "2024-01-01T12:30:00Z"
                }
            }

            result = korapay._normalize_create_response(kora_response, 100000)
            assert result["responseCode"] == "Z0"

    def test_normalize_create_response_extracts_validity_period_mins(self):
        """Test _normalize_create_response extracts validityPeriodMins from expiry_date_in_utc."""
        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from datetime import datetime, timedelta, timezone

            from services.korapay import korapay

            # Create expiry 30 minutes from now
            now = datetime.now(timezone.utc)
            expiry = now + timedelta(minutes=30)
            expiry_str = expiry.strftime("%Y-%m-%dT%H:%M:%SZ")

            kora_response = {
                "reference": "TEST",
                "payment_reference": "KPY-CA-TEST",
                "status": "processing",
                "bank_account": {
                    "account_number": "1234567890",
                    "bank_name": "Test Bank",
                    "account_name": "Test",
                    "bank_code": "035",
                    "expiry_date_in_utc": expiry_str
                }
            }

            result = korapay._normalize_create_response(kora_response, 100000)
            # Should be approximately 30 minutes (allow some tolerance for test execution time)
            assert 28 <= result["validityPeriodMins"] <= 32


