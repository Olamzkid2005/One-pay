"""
Unit tests for KoraPay service module.
"""

import os
from unittest.mock import patch

import pytest


class TestMockVirtualAccountCreation:
    """Test mock virtual account creation functionality."""

    def test_mock_create_returns_deterministic_account_number(self) -> None:
        """Test _mock_create_virtual_account returns deterministic account number."""
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': ''}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            tx_ref = "ONEPAY-TEST-12345"
            result = korapay._mock_create_virtual_account(tx_ref, 150000, "Test Merchant")

            # Calculate expected account number
            seed = sum(ord(c) for c in tx_ref)
            expected_account = str(3000000000 + (seed % 999999999)).zfill(10)

            assert result["accountNumber"] == expected_account

    def test_mock_create_account_number_formula(self) -> None:
        """Test account number uses correct formula: 3000000000 + (sum(ord(c)) % 999999999)."""
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': ''}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            tx_ref = "ABC"
            result = korapay._mock_create_virtual_account(tx_ref, 100000, "Test")

            # ABC: A=65, B=66, C=67, sum=198
            # 3000000000 + (198 % 999999999) = 3000000198
            assert result["accountNumber"] == "3000000198"

    def test_mock_create_returns_wema_bank_demo(self) -> None:
        """Test returns bank name 'Wema Bank (Demo)'."""
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': ''}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            result = korapay._mock_create_virtual_account("TEST-REF", 100000, "Merchant")
            assert result["bankName"] == "Wema Bank (Demo)"

    def test_mock_create_returns_matching_account_name(self) -> None:
        """Test returns account name matching input parameter."""
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': ''}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            account_name = "John Doe - OnePay Payment"
            result = korapay._mock_create_virtual_account("REF", 100000, account_name)
            assert result["accountName"] == account_name

    def test_mock_create_returns_30_minute_validity(self) -> None:
        """Test returns validity period of 30 minutes."""
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': ''}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            result = korapay._mock_create_virtual_account("REF", 100000, "Merchant")
            assert result["validityPeriodMins"] == 30

    def test_mock_create_returns_response_code_z0(self) -> None:
        """Test returns response code 'Z0' (pending)."""
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': ''}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            result = korapay._mock_create_virtual_account("REF", 100000, "Merchant")
            assert result["responseCode"] == "Z0"

    def test_mock_create_returns_amount_in_kobo(self) -> None:
        """Test returns amount in kobo matching input."""
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': ''}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            amount_kobo = 250000
            result = korapay._mock_create_virtual_account("REF", amount_kobo, "Merchant")
            assert result["amount"] == amount_kobo

    def test_mock_create_logs_with_mock_prefix(self, caplog) -> None:
        """Test logs with '[MOCK]' prefix in log messages."""
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': ''}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            with caplog.at_level('WARNING'):
                korapay._mock_create_virtual_account("REF", 100000, "Merchant")

            # Check that at least one log message contains [MOCK]
            assert any('[MOCK]' in record.message for record in caplog.records)


