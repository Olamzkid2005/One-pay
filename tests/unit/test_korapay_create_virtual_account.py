"""
Unit tests for KoraPay service module.
"""

import os
from unittest.mock import patch

import pytest


class TestCreateVirtualAccount:
    """Test virtual account creation functionality."""

    def test_create_virtual_account_calls_mock_in_mock_mode(self):
        """Test create_virtual_account calls _mock_create_virtual_account in mock mode."""
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': ''}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            tx_ref = "ONEPAY-TEST-12345"
            amount_kobo = 150000
            account_name = "Test Merchant"

            result = korapay.create_virtual_account(tx_ref, amount_kobo, account_name)

            # Should return mock response
            assert result["accountNumber"] is not None
            assert result["bankName"] == "Wema Bank (Demo)"
            assert result["responseCode"] == "Z0"

    def test_create_virtual_account_makes_post_request_in_live_mode(self):
        """Test create_virtual_account makes POST to /charges/bank-transfer in live mode."""
        from unittest.mock import Mock, patch

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            # Mock successful API response
            mock_response = {
                "status": "success",
                "message": "Virtual account created",
                "data": {
                    "reference": "ONEPAY-TEST-12345",
                    "payment_reference": "KPY-CA-TEST-12345",
                    "status": "processing",
                    "currency": "NGN",
                    "amount": 1500,
                    "fee": 22.5,
                    "vat": 1.69,
                    "amount_expected": 1524.19,
                    "bank_account": {
                        "account_number": "1234567890",
                        "bank_name": "Wema Bank",
                        "account_name": "Test Merchant",
                        "bank_code": "035",
                        "expiry_date_in_utc": "2024-01-01T12:30:00Z"
                    }
                }
            }

            with patch.object(korapay, '_make_request', return_value=mock_response) as mock_request:
                korapay.create_virtual_account("ONEPAY-TEST-12345", 150000, "Test Merchant")

                # Verify POST request was made
                mock_request.assert_called_once()
                call_args = mock_request.call_args
                assert call_args[0][0] == "POST"
                assert "/charges/bank-transfer" in call_args[0][1]

    def test_create_virtual_account_converts_amount_kobo_to_naira(self):
        """Test create_virtual_account converts amount_kobo to Naira (divide by 100)."""
        from decimal import Decimal
        from unittest.mock import Mock, patch

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            mock_response = {
                "status": "success",
                "data": {
                    "reference": "TEST",
                    "payment_reference": "KPY-CA-TEST",
                    "status": "processing",
                    "currency": "NGN",
                    "amount": 1500,
                    "fee": 22.5,
                    "vat": 1.69,
                    "amount_expected": 1524.19,
                    "bank_account": {
                        "account_number": "1234567890",
                        "bank_name": "Wema Bank",
                        "account_name": "Test",
                        "bank_code": "035",
                        "expiry_date_in_utc": "2024-01-01T12:30:00Z"
                    }
                }
            }

            with patch.object(korapay, '_make_request', return_value=mock_response) as mock_request:
                # 150000 kobo = 1500 Naira
                korapay.create_virtual_account("TEST", 150000, "Test")

                # Check request body has amount in Naira
                call_args = mock_request.call_args
                request_body = call_args[1]['json']
                assert request_body['amount'] == 1500

    def test_create_virtual_account_includes_correct_request_body_fields(self):
        """Test create_virtual_account includes correct request body fields."""
        from unittest.mock import Mock, patch

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            mock_response = {
                "status": "success",
                "data": {
                    "reference": "TEST",
                    "payment_reference": "KPY-CA-TEST",
                    "status": "processing",
                    "currency": "NGN",
                    "amount": 1500,
                    "fee": 22.5,
                    "vat": 1.69,
                    "amount_expected": 1524.19,
                    "bank_account": {
                        "account_number": "1234567890",
                        "bank_name": "Wema Bank",
                        "account_name": "Test",
                        "bank_code": "035",
                        "expiry_date_in_utc": "2024-01-01T12:30:00Z"
                    }
                }
            }

            with patch.object(korapay, '_make_request', return_value=mock_response) as mock_request:
                korapay.create_virtual_account("TEST-REF", 150000, "Test Account")

                # Check request body structure
                call_args = mock_request.call_args
                request_body = call_args[1]['json']

                assert 'reference' in request_body
                assert request_body['reference'] == "TEST-REF"
                assert 'amount' in request_body
                assert 'currency' in request_body
                assert request_body['currency'] == "NGN"
                assert 'customer' in request_body
                assert 'account_name' in request_body['customer']
                assert request_body['customer']['account_name'] == "Test Account"

    def test_create_virtual_account_handles_400_error(self):
        """Test create_virtual_account handles 400 error with field validation."""
        from unittest.mock import Mock, patch

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import KoraPayError, korapay

            # Mock 400 error response
            with patch.object(korapay, '_make_request', side_effect=KoraPayError("Bad request", status_code=400)):
                with pytest.raises(KoraPayError) as exc_info:
                    korapay.create_virtual_account("TEST", 150000, "Test")

                assert exc_info.value.status_code == 400

    def test_create_virtual_account_handles_401_authentication_error(self):
        """Test create_virtual_account handles 401 authentication error."""
        from unittest.mock import Mock, patch

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import KoraPayError, korapay

            # Mock 401 error response
            with patch.object(korapay, '_make_request', side_effect=KoraPayError("Authentication failed", status_code=401)):
                with pytest.raises(KoraPayError) as exc_info:
                    korapay.create_virtual_account("TEST", 150000, "Test")

                assert exc_info.value.status_code == 401

    def test_create_virtual_account_handles_timeout_error(self):
        """Test create_virtual_account handles timeout error."""
        from unittest.mock import Mock, patch

        import requests

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import KoraPayError, korapay

            # Mock timeout error
            with patch.object(korapay, '_make_request', side_effect=KoraPayError("Request timeout", error_code="TIMEOUT")):
                with pytest.raises(KoraPayError) as exc_info:
                    korapay.create_virtual_account("TEST", 150000, "Test")

                assert exc_info.value.error_code == "TIMEOUT"

    def test_create_virtual_account_validates_response_has_required_fields(self):
        """Test create_virtual_account validates response has required fields."""
        from unittest.mock import Mock, patch

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import KoraPayError, korapay

            # Mock response missing required fields
            mock_response = {
                "status": "success",
                "data": {
                    "reference": "TEST"
                    # Missing bank_account and other fields
                }
            }

            with patch.object(korapay, '_make_request', return_value=mock_response):
                with pytest.raises(KoraPayError) as exc_info:
                    korapay.create_virtual_account("TEST", 150000, "Test")

                assert "missing" in str(exc_info.value).lower()

    def test_create_virtual_account_normalizes_korapay_response_to_quickteller_format(self):
        """Test create_virtual_account normalizes KoraPay response to Quickteller format."""
        from unittest.mock import Mock, patch

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            mock_response = {
                "status": "success",
                "data": {
                    "reference": "ONEPAY-TEST-12345",
                    "payment_reference": "KPY-CA-TEST-12345",
                    "status": "processing",
                    "currency": "NGN",
                    "amount": 1500,
                    "fee": 22.5,
                    "vat": 1.69,
                    "amount_expected": 1524.19,
                    "bank_account": {
                        "account_number": "1234567890",
                        "bank_name": "Wema Bank",
                        "account_name": "Test Merchant",
                        "bank_code": "035",
                        "expiry_date_in_utc": "2024-01-01T12:30:00Z"
                    }
                }
            }

            with patch.object(korapay, '_make_request', return_value=mock_response):
                result = korapay.create_virtual_account("ONEPAY-TEST-12345", 150000, "Test Merchant")

                # Check Quickteller-compatible format
                assert "accountNumber" in result
                assert result["accountNumber"] == "1234567890"
                assert "bankName" in result
                assert result["bankName"] == "Wema Bank"
                assert "accountName" in result
                assert result["accountName"] == "Test Merchant"
                assert "amount" in result
                assert result["amount"] == 150000  # Back to kobo
                assert "transactionReference" in result
                assert result["transactionReference"] == "ONEPAY-TEST-12345"
                assert "responseCode" in result
                assert result["responseCode"] == "Z0"  # processing -> Z0


