"""
Integration tests for payment link generation routes.

Tests the /api/v1/payments/link endpoint covering idempotency,
happy-path generation, and negative inputs.
"""

import json
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

import pytest

from models.transaction import Transaction


class TestPaymentLinkRoutes:
    """
    Integration tests for payment links endpoints.
    Tests Requirements: Payment link generation edge cases and security.
    """

    @pytest.fixture
    def app(self):
        """Create test Flask app."""
        from app import app as flask_app
        flask_app.config['TESTING'] = True
        flask_app.config['SECRET_KEY'] = 'test-secret-key-for-sessions'
        return flask_app

    @pytest.fixture
    def client(self, app):
        """Create test client with session support."""
        with app.test_client() as client:
            yield client

    def _setup_mock_db(self, mock_db, existing_tx_mock=None):
        """Setup mock database chain for transaction queries."""
        mock_tx_query = MagicMock()
        mock_db.query.return_value = mock_tx_query

        mock_tx_filter = MagicMock()
        mock_tx_query.filter.return_value = mock_tx_filter

        # If an existing_tx_mock is provided, it simulates an idempotent hit.
        mock_tx_filter.first.return_value = existing_tx_mock

        return mock_db

    def test_payment_link_requires_authentication(self, client):
        """
        Test that creating a link returns 401 unauthenticated when no session.
        """
        with patch('blueprints.payments.current_user_id', return_value=None):
            response = client.post('/api/v1/payments/link',
                json={"amount": 5000},
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 401

    def test_payment_link_requires_application_json(self, client):
        """
        Test that creating a link strictly requires Content-Type application/json.
        """
        with patch('blueprints.payments.current_user_id', return_value=1):
            with patch('core.api_auth.validate_api_key', return_value=(True, 1)):
                response = client.post('/api/v1/payments/link',
                    data="amount=5000",
                    headers={"Content-Type": "application/x-www-form-urlencoded", "Authorization": "Bearer onepay_live_test_key"}
                )
                assert response.status_code == 415

    def test_payment_link_rejects_negative_amounts(self, client):
        """
        Test edge case rejecting negative amounts.
        """
        with patch('blueprints.payments.current_user_id', return_value=1):
            with patch('core.api_auth.validate_api_key', return_value=(True, 1)):
                with patch('blueprints.payments.get_db') as mock_get_db:
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db

                    self._setup_mock_db(mock_db, existing_tx_mock=None)

                    response = client.post('/api/v1/payments/link',
                        json={"amount": -5000},
                        headers={"Content-Type": "application/json", "Authorization": "Bearer onepay_live_test_key"}
                    )

                    assert response.status_code == 400
                    data = json.loads(response.data)
                    assert "positive finite number" in data.get("message", "")

    def test_payment_link_rejects_too_high_amounts(self, client):
        """
        Test edge case rejecting amounts over 100 million.
        """
        with patch('blueprints.payments.current_user_id', return_value=1):
            with patch('core.api_auth.validate_api_key', return_value=(True, 1)):
                with patch('blueprints.payments.get_db') as mock_get_db:
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db

                    self._setup_mock_db(mock_db, existing_tx_mock=None)

                    response = client.post('/api/v1/payments/link',
                        json={"amount": 150000000},  # 150 Million
                        headers={"Content-Type": "application/json", "Authorization": "Bearer onepay_live_test_key"}
                    )

                    assert response.status_code == 400

    def test_payment_link_happy_path_success(self, client):
        """
        Test generating a payment link works and creates DB records correctly.
        """
        with patch('blueprints.payments.current_user_id', return_value=1):
            with patch('core.api_auth.validate_api_key', return_value=(True, 1)):
                with patch('blueprints.payments.get_db') as mock_get_db:
                    with patch('blueprints.payments.korapay') as mock_kora:
                        mock_kora.is_transfer_configured.return_value = False

                        mock_db = MagicMock()
                        mock_get_db.return_value.__enter__.return_value = mock_db
                        self._setup_mock_db(mock_db, existing_tx_mock=None)

                        response = client.post('/api/v1/payments/link',
                            json={
                                "amount": 5000,
                                "description": "Test integration item",
                                "customer_email": "test@onepay.com"
                            },
                            headers={
                                "Content-Type": "application/json",
                                "Authorization": "Bearer onepay_live_test_key"
                            }
                        )

                        assert response.status_code == 201
                        add_calls = mock_db.add.call_args_list
                        assert len(add_calls) >= 1  # Verify Transaction was added

                        transaction_arg = add_calls[0][0][0]
                        assert isinstance(transaction_arg, Transaction)
                        assert transaction_arg.amount == Decimal('5000.00')
                        assert transaction_arg.description == "Test integration item"
                        assert transaction_arg.customer_email == "test@onepay.com"

    def test_payment_link_idempotency(self, client):
        """
        Test that supplying the same idempotency key returns the existing transaction.
        """
        with patch('blueprints.payments.current_user_id', return_value=1):
            with patch('core.api_auth.validate_api_key', return_value=(True, 1)):
                with patch('blueprints.payments.get_db') as mock_get_db:
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db

                    # Create an existing mock transaction
                    existing_tx = Mock()
                    existing_tx.tx_ref = "ONEPAY-EXT-123"
                    existing_tx.amount = Decimal("5000.00")
                    existing_tx.currency = "NGN"
                    existing_tx.description = "Idempotent payment"
                    existing_tx.virtual_account_number = None
                    existing_tx.qr_code_payment_url = None
                    existing_tx.qr_code_virtual_account = None
                    existing_tx.virtual_bank_name = None
                    existing_tx.virtual_account_name = None
                    existing_tx.expires_at_utc_iso.return_value = "2027-01-01T00:00:00Z"

                    self._setup_mock_db(mock_db, existing_tx_mock=existing_tx)

                    response = client.post('/api/v1/payments/link',
                        json={"amount": 5000},
                        headers={
                            "Content-Type": "application/json",
                            "X-Idempotency-Key": "UNIQUE-CLIENT-POST-12345",
                            "Authorization": "Bearer onepay_live_test_key"
                        }
                    )

                    assert response.status_code == 200
                    data = json.loads(response.data)
                    assert data["tx_ref"] == "ONEPAY-EXT-123"

                    # Verify DB.add was NOT called, to prove idempotency stopped insertion
                    add_calls = mock_db.add.call_args_list
                    assert len(add_calls) == 0
