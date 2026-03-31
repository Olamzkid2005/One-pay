"""
Integration tests for refund routes.

Tests the /api/payments/refund/<tx_ref> endpoint for KoraPay refund integration.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from models.transaction import TransactionStatus


class TestRefundRoutes:
    """
    Integration tests for refund route endpoints.

    Tests Requirements: Refund API integration
    """

    @pytest.fixture
    def app(self):
        """Create test Flask app."""
        from app import app as flask_app
        flask_app.config['TESTING'] = True
        flask_app.config['SECRET_KEY'] = 'test-secret-key-for-sessions'
        flask_app.config['KORAPAY_SECRET_KEY'] = ''  # Mock mode
        return flask_app

    @pytest.fixture
    def client(self, app):
        """Create test client with session support."""
        with app.test_client() as client:
            yield client

    def _create_transaction_mock(self):
        """Create a mock transaction."""
        mock_tx = Mock()
        mock_tx.id = 1
        mock_tx.tx_ref = 'ONEPAY-TEST-123'
        mock_tx.user_id = 1
        mock_tx.status = TransactionStatus.VERIFIED
        mock_tx.amount = Decimal('1500.00')
        return mock_tx

    def _setup_mock_db(self, mock_db, transaction_mock, existing_refund_mock=None):
        """Setup mock database chain for transaction and refund queries."""
        mock_tx_query = MagicMock()
        mock_refund_query = MagicMock()

        def query_side_effect(model):
            if hasattr(model, '__name__') and 'Refund' in str(model):
                return mock_refund_query
            return mock_tx_query

        mock_db.query.side_effect = query_side_effect

        mock_tx_filter = MagicMock()
        mock_tx_query.filter.return_value = mock_tx_filter
        mock_tx_filter.first.return_value = transaction_mock

        mock_refund_filter = MagicMock()
        mock_refund_query.filter.return_value = mock_refund_filter
        mock_refund_filter.first.return_value = existing_refund_mock

        return mock_db

    def test_initiate_refund_requires_authentication(self, client):
        """
        Test that initiate_refund returns 401 when not authenticated.
        """
        with patch('blueprints.payments.get_db'):
            response = client.post('/api/payments/refund/ONEPAY-TEST-123',
                json={}
            )
            assert response.status_code == 401

    def test_initiate_refund_validates_transaction_is_verified(self, client):
        """
        Test that initiate_refund returns 400 for non-verified transactions.
        """
        with patch('blueprints.payments.current_user_id', return_value=1):
            with patch('blueprints.payments.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value.__enter__.return_value = mock_db

                mock_tx = Mock()
                mock_tx.tx_ref = 'ONEPAY-TEST-123'
                mock_tx.user_id = 1
                mock_tx.status = TransactionStatus.PENDING  # Not verified

                mock_tx_query = MagicMock()
                mock_db.query.return_value = mock_tx_query
                mock_tx_filter = MagicMock()
                mock_tx_query.filter.return_value = mock_tx_filter
                mock_tx_filter.first.return_value = mock_tx

                response = client.post('/api/payments/refund/ONEPAY-TEST-123',
                    json={}
                )

                assert response.status_code == 400

    def test_initiate_refund_calls_korapay_service(self, client):
        """
        Test that initiate_refund calls korapay.initiate_refund.
        """
        with patch('blueprints.payments.current_user_id', return_value=1):
            with patch('blueprints.payments.get_db') as mock_get_db:
                with patch('blueprints.payments.korapay') as mock_korapay:
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db

                    mock_tx = self._create_transaction_mock()
                    self._setup_mock_db(mock_db, mock_tx, existing_refund_mock=None)

                    mock_korapay.initiate_refund.return_value = {
                        "reference": "REFUND-ONEPAY-TEST-123-1234567890",
                        "payment_reference": "ONEPAY-TEST-123",
                        "amount": 1500,
                        "status": "processing",
                        "currency": "NGN"
                    }

                    response = client.post('/api/payments/refund/ONEPAY-TEST-123',
                        json={}
                    )

                    assert response.status_code == 200
                    mock_korapay.initiate_refund.assert_called_once()

    def test_initiate_refund_creates_refund_record(self, client):
        """
        Test that initiate_refund creates a refund record in the database.
        """
        with patch('blueprints.payments.current_user_id', return_value=1):
            with patch('blueprints.payments.get_db') as mock_get_db:
                with patch('blueprints.payments.korapay') as mock_korapay:
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db

                    mock_tx = self._create_transaction_mock()
                    self._setup_mock_db(mock_db, mock_tx, existing_refund_mock=None)

                    mock_korapay.initiate_refund.return_value = {
                        "reference": "REFUND-ONEPAY-TEST-123-1234567890",
                        "payment_reference": "ONEPAY-TEST-123",
                        "amount": 1500,
                        "status": "processing",
                        "currency": "NGN"
                    }

                    response = client.post('/api/payments/refund/ONEPAY-TEST-123',
                        json={}
                    )

                    assert response.status_code == 200
                    add_calls = mock_db.add.call_args_list
                    assert len(add_calls) >= 1

    def test_initiate_refund_logs_audit_event(self, client):
        """
        Test that initiate_refund logs an audit event.
        """
        with patch('blueprints.payments.current_user_id', return_value=1):
            with patch('blueprints.payments.get_db') as mock_get_db:
                with patch('blueprints.payments.korapay') as mock_korapay:
                    with patch('blueprints.payments.log_event') as mock_log:
                        mock_db = MagicMock()
                        mock_get_db.return_value.__enter__.return_value = mock_db

                        mock_tx = self._create_transaction_mock()
                        self._setup_mock_db(mock_db, mock_tx, existing_refund_mock=None)

                        mock_korapay.initiate_refund.return_value = {
                            "reference": "REFUND-ONEPAY-TEST-123-1234567890",
                            "payment_reference": "ONEPAY-TEST-123",
                            "amount": 1500,
                            "status": "processing",
                            "currency": "NGN"
                        }

                        response = client.post('/api/payments/refund/ONEPAY-TEST-123',
                            json={}
                        )

                        assert response.status_code == 200
                        mock_log.assert_called_once()

    def test_initiate_refund_handles_korapay_error(self, client):
        """
        Test that initiate_refund handles KoraPay errors gracefully.
        """
        with patch('blueprints.payments.current_user_id', return_value=1):
            with patch('blueprints.payments.get_db') as mock_get_db:
                with patch('blueprints.payments.korapay') as mock_korapay:
                    from services.korapay import KoraPayError
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db

                    mock_tx = self._create_transaction_mock()
                    self._setup_mock_db(mock_db, mock_tx, existing_refund_mock=None)

                    mock_korapay.initiate_refund.side_effect = KoraPayError(
                        "Refund failed",
                        error_code="REFUND_FAILED"
                    )

                    response = client.post('/api/payments/refund/ONEPAY-TEST-123',
                        json={}
                    )

                    assert response.status_code == 500

    def test_initiate_refund_returns_success_response(self, client):
        """
        Test that initiate_refund returns proper success response.
        """
        with patch('blueprints.payments.current_user_id', return_value=1):
            with patch('blueprints.payments.get_db') as mock_get_db:
                with patch('blueprints.payments.korapay') as mock_korapay:
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db

                    mock_tx = self._create_transaction_mock()
                    self._setup_mock_db(mock_db, mock_tx, existing_refund_mock=None)

                    mock_korapay.initiate_refund.return_value = {
                        "reference": "REFUND-ONEPAY-TEST-123-1234567890",
                        "payment_reference": "ONEPAY-TEST-123",
                        "amount": 1500,
                        "status": "processing",
                        "currency": "NGN"
                    }

                    response = client.post('/api/payments/refund/ONEPAY-TEST-123',
                        json={}
                    )

                    assert response.status_code == 200
                    data = json.loads(response.data)
                    assert data['success'] is True
                    assert 'refund_reference' in data
                    assert data['status'] == 'processing'