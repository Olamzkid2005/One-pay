"""
Unit tests for KoraPay service module.
"""

import os
from unittest.mock import patch

import pytest


class TestMockTransferConfirmation:
    """Test mock transfer confirmation with polling simulation."""

    def test_mock_confirm_returns_z0_for_first_poll(self) -> None:
        """Test _mock_confirm_transfer returns 'Z0' for first poll."""
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': ''}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            # Reset state
            korapay._mock_poll_counts.clear()

            tx_ref = "TEST-POLL-1"
            result = korapay._mock_confirm_transfer(tx_ref)

            assert result["responseCode"] == "Z0"

    def test_mock_confirm_returns_z0_for_second_poll(self) -> None:
        """Test _mock_confirm_transfer returns 'Z0' for second poll."""
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': ''}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            # Reset state
            korapay._mock_poll_counts.clear()

            tx_ref = "TEST-POLL-2"
            korapay._mock_confirm_transfer(tx_ref)  # First poll
            result = korapay._mock_confirm_transfer(tx_ref)  # Second poll

            assert result["responseCode"] == "Z0"

    def test_mock_confirm_returns_z0_for_third_poll(self) -> None:
        """Test _mock_confirm_transfer returns 'Z0' for third poll."""
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': ''}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            # Reset state
            korapay._mock_poll_counts.clear()

            tx_ref = "TEST-POLL-3"
            korapay._mock_confirm_transfer(tx_ref)  # First
            korapay._mock_confirm_transfer(tx_ref)  # Second
            result = korapay._mock_confirm_transfer(tx_ref)  # Third

            assert result["responseCode"] == "Z0"

    def test_mock_confirm_returns_00_on_fourth_poll(self) -> None:
        """Test _mock_confirm_transfer returns '00' on 4th poll."""
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': ''}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            # Reset state
            korapay._mock_poll_counts.clear()

            tx_ref = "TEST-POLL-4"
            korapay._mock_confirm_transfer(tx_ref)  # 1
            korapay._mock_confirm_transfer(tx_ref)  # 2
            korapay._mock_confirm_transfer(tx_ref)  # 3
            result = korapay._mock_confirm_transfer(tx_ref)  # 4

            assert result["responseCode"] == "00"

    def test_mock_confirm_poll_counter_increments(self) -> None:
        """Test poll counter increments correctly."""
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': ''}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            # Reset state
            korapay._mock_poll_counts.clear()

            tx_ref = "TEST-INCREMENT"

            assert tx_ref not in korapay._mock_poll_counts

            korapay._mock_confirm_transfer(tx_ref)
            assert korapay._mock_poll_counts[tx_ref] == 1

            korapay._mock_confirm_transfer(tx_ref)
            assert korapay._mock_poll_counts[tx_ref] == 2

    def test_mock_confirm_cleanup_after_confirmation(self) -> None:
        """Test poll counter cleanup after confirmation."""
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': ''}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            # Reset state
            korapay._mock_poll_counts.clear()

            tx_ref = "TEST-CLEANUP"

            # Poll until confirmed
            for _ in range(4):
                korapay._mock_confirm_transfer(tx_ref)

            # Counter should be cleaned up
            assert tx_ref not in korapay._mock_poll_counts

    def test_mock_confirm_logs_poll_count(self, caplog) -> None:
        """Test logs poll count and threshold."""
        with patch.dict(os.environ, {'KORAPAY_SECRET_KEY': ''}, clear=False):
            import importlib

            import config as config_module
            importlib.reload(config_module)

            from services.korapay import korapay

            # Reset state
            korapay._mock_poll_counts.clear()

            tx_ref = "TEST-LOG"

            with caplog.at_level('WARNING'):
                korapay._mock_confirm_transfer(tx_ref)

            # Check log contains poll count info
            assert any('poll' in record.message.lower() for record in caplog.records)


