"""
Unit tests for KoraPay service module.
"""

import os
from unittest.mock import patch

import pytest


class TestConfirmTransfer:
    """Test transfer status confirmation functionality."""

    def test_confirm_transfer_calls_mock_in_mock_mode(self) -> None:
        """Test confirm_transfer calls _mock_confirm_transfer in mock mode."""
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': ''}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            # Reset mock state
            korapay._mock_poll_counts.clear()

            tx_ref = "ONEPAY-TEST-CONFIRM"
            result = korapay.confirm_transfer(tx_ref)

            # Should return mock response
            assert result["responseCode"] is not None
            assert result["transactionReference"] == tx_ref

    def test_confirm_transfer_makes_get_request_in_live_mode(self) -> None:
        """Test confirm_transfer makes GET to /charges/{reference} in live mode."""
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
                "message": "Transaction retrieved",
                "data": {
                    "reference": "ONEPAY-TEST-12345",
                    "payment_reference": "KPY-PAY-TEST-12345",
                    "status": "success",
                    "amount": 1500,
                    "currency": "NGN"
                }
            }

            with patch.object(korapay, '_make_request', return_value=mock_response) as mock_request:
                korapay.confirm_transfer("ONEPAY-TEST-12345")

                # Verify GET request was made
                mock_request.assert_called_once()
                call_args = mock_request.call_args
                assert call_args[0][0] == "GET"
                assert "/charges/ONEPAY-TEST-12345" in call_args[0][1]

    def test_confirm_transfer_maps_success_status_to_00(self) -> None:
        """Test confirm_transfer maps 'success' status to responseCode '00'."""
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
                    "reference": "TEST-REF",
                    "payment_reference": "KPY-PAY-TEST",
                    "status": "success",
                    "amount": 1500,
                    "currency": "NGN"
                }
            }

            with patch.object(korapay, '_make_request', return_value=mock_response):
                result = korapay.confirm_transfer("TEST-REF")

                assert result["responseCode"] == "00"

    def test_confirm_transfer_maps_processing_status_to_z0(self) -> None:
        """Test confirm_transfer maps 'processing' status to responseCode 'Z0'."""
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
                    "reference": "TEST-REF",
                    "payment_reference": "KPY-CA-TEST",
                    "status": "processing",
                    "amount": 1500,
                    "currency": "NGN"
                }
            }

            with patch.object(korapay, '_make_request', return_value=mock_response):
                result = korapay.confirm_transfer("TEST-REF")

                assert result["responseCode"] == "Z0"

    def test_confirm_transfer_maps_failed_status_to_99(self) -> None:
        """Test confirm_transfer maps 'failed' status to responseCode '99'."""
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
                    "reference": "TEST-REF",
                    "payment_reference": "KPY-PAY-TEST",
                    "status": "failed",
                    "amount": 1500,
                    "currency": "NGN"
                }
            }

            with patch.object(korapay, '_make_request', return_value=mock_response):
                result = korapay.confirm_transfer("TEST-REF")

                assert result["responseCode"] == "99"

    def test_confirm_transfer_handles_404_error(self) -> None:
        """Test confirm_transfer handles 404 error (transaction not found)."""
        from unittest.mock import Mock, patch

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import KoraPayError, korapay

            # Mock 404 error response
            with patch.object(korapay, '_make_request', side_effect=KoraPayError("Transaction not found", status_code=404)):
                with pytest.raises(KoraPayError) as exc_info:
                    korapay.confirm_transfer("NONEXISTENT-REF")

                assert exc_info.value.status_code == 404

    def test_confirm_transfer_handles_timeout_error(self) -> None:
        """Test confirm_transfer handles timeout error."""
        from unittest.mock import Mock, patch

        valid_key = 'sk_test_' + 'a' * 40
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': valid_key}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import KoraPayError, korapay

            # Mock timeout error
            with patch.object(korapay, '_make_request', side_effect=KoraPayError("Request timeout", error_code="TIMEOUT")):
                with pytest.raises(KoraPayError) as exc_info:
                    korapay.confirm_transfer("TEST-REF")

                assert exc_info.value.error_code == "TIMEOUT"

    def test_confirm_transfer_validates_response_structure(self) -> None:
        """Test confirm_transfer validates response structure."""
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
                    "reference": "TEST-REF"
                    # Missing status field
                }
            }

            with patch.object(korapay, '_make_request', return_value=mock_response):
                with pytest.raises(KoraPayError) as exc_info:
                    korapay.confirm_transfer("TEST-REF")

                assert "missing" in str(exc_info.value).lower()


