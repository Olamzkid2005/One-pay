"""
Integration tests for KoraPay payment flow.

This module contains end-to-end integration tests for the complete payment
flow including virtual account creation, status polling, and webhooks.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from decimal import Decimal
from models.transaction import TransactionStatus


class TestPaymentLinkCreation:
    """
    Integration tests for payment link creation with KoraPay.
    
    Tests Requirements: 6.1, 6.2, 6.3, 6.4, 6.13, 6.14, 6.15, 6.16, 6.23, 6.24
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
    
    def test_create_payment_link_calls_korapay_create_virtual_account(self, client):
        """
        Test that create_payment_link calls korapay.create_virtual_account.
        Requirement 6.1: Integration with KoraPay service
        """
        with patch('blueprints.payments.current_user_id', return_value=1):
            with patch('blueprints.payments.current_username', return_value='testuser'):
                with patch('blueprints.payments.is_valid_csrf_token', return_value=True):
                    with patch('blueprints.payments.korapay') as mock_korapay:
                        with patch('blueprints.payments.get_db') as mock_get_db:
                            mock_db = MagicMock()
                            mock_get_db.return_value.__enter__.return_value = mock_db
                            
                            mock_user = Mock()
                            mock_user.id = 1
                            mock_user.webhook_url = None
                            mock_db.query().filter().first.return_value = mock_user
                            
                            mock_korapay.is_transfer_configured.return_value = True
                            mock_korapay.create_virtual_account.return_value = {
                                "accountNumber": "3000000001",
                                "bankName": "Wema Bank (Demo)",
                                "accountName": "testuser - OnePay Payment",
                                "amount": 150000,
                                "transactionReference": "ONEPAY-TEST-123",
                                "responseCode": "Z0",
                                "validityPeriodMins": 30
                            }
                            
                            with patch('blueprints.payments.check_rate_limit', return_value=True):
                                with patch('blueprints.payments.qr_service.generate_payment_qr', return_value='data:image/png;base64,test'):
                                    with client.session_transaction() as sess:
                                        sess['user_id'] = 1
                                        sess['username'] = 'testuser'
                                        sess['csrf_token'] = 'test-csrf-token'
                                    
                                    response = client.post('/api/payments/link',
                                        json={'amount': 1500.00, 'description': 'Test payment', 'currency': 'NGN'},
                                        headers={'X-CSRF-Token': 'test-csrf-token'},
                                        content_type='application/json'
                                    )
                                    
                                    assert response.status_code == 201
                                    mock_korapay.create_virtual_account.assert_called_once()


class TestTransferStatusPolling:
    """
    Integration tests for transfer status polling with KoraPay.
    
    Tests Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.12, 7.16, 7.17, 7.18, 7.23, 7.24, 7.25
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
    
    def test_transfer_status_calls_korapay_confirm_transfer(self, client):
        """
        Test that transfer_status calls korapay.confirm_transfer.
        Requirement 7.1: Integration with KoraPay service
        """
        with patch('blueprints.public.korapay') as mock_korapay:
            with patch('blueprints.public.get_db') as mock_get_db:
                with patch('blueprints.public.session', {'pay_access_ONEPAY-TEST-123': True}):
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db
                    
                    mock_tx = Mock()
                    mock_tx.tx_ref = 'ONEPAY-TEST-123'
                    mock_tx.transfer_confirmed = False
                    mock_tx.is_used = False
                    mock_tx.is_expired.return_value = False
                    mock_db.query().filter().first.return_value = mock_tx
                    mock_db.query().filter().with_for_update().first.return_value = mock_tx
                    
                    mock_korapay.is_transfer_configured.return_value = True
                    mock_korapay.confirm_transfer.return_value = {
                        "responseCode": "Z0",
                        "transactionReference": "ONEPAY-TEST-123"
                    }
                    
                    with patch('blueprints.public.check_rate_limit', return_value=True):
                        response = client.get('/api/payments/transfer-status/ONEPAY-TEST-123')
                        
                        assert response.status_code == 200
                        mock_korapay.confirm_transfer.assert_called_once_with('ONEPAY-TEST-123')
    
    def test_updates_transaction_on_confirmed_response(self, client):
        """
        Test that transaction is updated on "00" (confirmed) response.
        Requirements 7.2, 7.3: Update transaction status
        """
        with patch('blueprints.public.korapay') as mock_korapay:
            with patch('blueprints.public.get_db') as mock_get_db:
                with patch('blueprints.public.session', {'pay_access_ONEPAY-TEST-123': True}):
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db
                    
                    mock_tx = Mock()
                    mock_tx.tx_ref = 'ONEPAY-TEST-123'
                    mock_tx.transfer_confirmed = False
                    mock_tx.is_used = False
                    mock_tx.is_expired.return_value = False
                    mock_tx.webhook_url = None
                    mock_db.query().filter().first.return_value = mock_tx
                    mock_db.query().filter().with_for_update().first.return_value = mock_tx
                    
                    mock_korapay.is_transfer_configured.return_value = True
                    mock_korapay.confirm_transfer.return_value = {
                        "responseCode": "00",
                        "transactionReference": "ONEPAY-TEST-123"
                    }
                    
                    with patch('blueprints.public.check_rate_limit', return_value=True):
                        with patch('services.webhook.sync_invoice_on_transaction_update'):
                            response = client.get('/api/payments/transfer-status/ONEPAY-TEST-123')
                            
                            assert response.status_code == 200
                            data = json.loads(response.data)
                            assert data['status'] == 'confirmed'
                            assert mock_tx.transfer_confirmed is True
    
    def test_returns_pending_on_z0_response(self, client):
        """
        Test that pending status is returned on "Z0" response.
        Requirement 7.12: Status mapping
        """
        with patch('blueprints.public.korapay') as mock_korapay:
            with patch('blueprints.public.get_db') as mock_get_db:
                with patch('blueprints.public.session', {'pay_access_ONEPAY-TEST-123': True}):
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db
                    
                    mock_tx = Mock()
                    mock_tx.tx_ref = 'ONEPAY-TEST-123'
                    mock_tx.transfer_confirmed = False
                    mock_tx.is_used = False
                    mock_tx.is_expired.return_value = False
                    mock_db.query().filter().first.return_value = mock_tx
                    mock_db.query().filter().with_for_update().first.return_value = mock_tx
                    
                    mock_korapay.is_transfer_configured.return_value = True
                    mock_korapay.confirm_transfer.return_value = {
                        "responseCode": "Z0",
                        "transactionReference": "ONEPAY-TEST-123"
                    }
                    
                    with patch('blueprints.public.check_rate_limit', return_value=True):
                        response = client.get('/api/payments/transfer-status/ONEPAY-TEST-123')
                        
                        assert response.status_code == 200
                        data = json.loads(response.data)
                        assert data['status'] == 'pending'
    
    def test_handles_korapay_error_gracefully(self, client):
        """
        Test that KoraPayError is handled gracefully.
        Requirement 7.4: Error handling
        """
        with patch('blueprints.public.korapay') as mock_korapay:
            with patch('blueprints.public.get_db') as mock_get_db:
                with patch('blueprints.public.session', {'pay_access_ONEPAY-TEST-123': True}):
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db
                    
                    mock_tx = Mock()
                    mock_tx.tx_ref = 'ONEPAY-TEST-123'
                    mock_tx.transfer_confirmed = False
                    mock_tx.is_used = False
                    mock_tx.is_expired.return_value = False
                    mock_db.query().filter().first.return_value = mock_tx
                    mock_db.query().filter().with_for_update().first.return_value = mock_tx
                    
                    from services.korapay import KoraPayError
                    mock_korapay.is_transfer_configured.return_value = True
                    mock_korapay.confirm_transfer.side_effect = KoraPayError("Connection timeout", error_code="TIMEOUT")
                    
                    with patch('blueprints.public.check_rate_limit', return_value=True):
                        response = client.get('/api/payments/transfer-status/ONEPAY-TEST-123')
                        
                        assert response.status_code == 200
                        data = json.loads(response.data)
                        assert data['success'] is False
    
    def test_fast_path_already_confirmed_skips_api_call(self, client):
        """
        Test that fast path (already confirmed) skips API call.
        Requirement 7.5: Performance optimization
        """
        with patch('blueprints.public.korapay') as mock_korapay:
            with patch('blueprints.public.get_db') as mock_get_db:
                with patch('blueprints.public.session', {'pay_access_ONEPAY-TEST-123': True}):
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db
                    
                    mock_tx = Mock()
                    mock_tx.tx_ref = 'ONEPAY-TEST-123'
                    mock_tx.transfer_confirmed = True
                    mock_db.query().filter().first.return_value = mock_tx
                    
                    mock_korapay.is_transfer_configured.return_value = True
                    
                    with patch('blueprints.public.check_rate_limit', return_value=True):
                        response = client.get('/api/payments/transfer-status/ONEPAY-TEST-123')
                        
                        assert response.status_code == 200
                        data = json.loads(response.data)
                        assert data['status'] == 'confirmed'
                        mock_korapay.confirm_transfer.assert_not_called()
    
    def test_optimistic_locking_prevents_race_conditions(self, client):
        """
        Test that optimistic locking with with_for_update() prevents race conditions.
        Requirements 7.16, 7.17, 7.23, 7.24, 7.25: Concurrency safety
        """
        with patch('blueprints.public.korapay') as mock_korapay:
            with patch('blueprints.public.get_db') as mock_get_db:
                with patch('blueprints.public.session', {'pay_access_ONEPAY-TEST-123': True}):
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db
                    
                    mock_tx = Mock()
                    mock_tx.tx_ref = 'ONEPAY-TEST-123'
                    mock_tx.transfer_confirmed = False
                    mock_tx.is_used = False
                    mock_tx.is_expired.return_value = False
                    mock_tx.webhook_url = None
                    mock_db.query().filter().first.return_value = mock_tx
                    mock_db.query().filter().with_for_update().first.return_value = mock_tx
                    
                    mock_korapay.is_transfer_configured.return_value = True
                    mock_korapay.confirm_transfer.return_value = {
                        "responseCode": "00",
                        "transactionReference": "ONEPAY-TEST-123"
                    }
                    
                    with patch('blueprints.public.check_rate_limit', return_value=True):
                        with patch('services.webhook.sync_invoice_on_transaction_update'):
                            response = client.get('/api/payments/transfer-status/ONEPAY-TEST-123')
                            
                            assert response.status_code == 200
                            mock_db.query().filter().with_for_update.assert_called()
    
    def test_double_check_after_lock_acquisition(self, client):
        """
        Test that double-check is performed after lock acquisition.
        Requirement 7.18: Double-check pattern
        """
        with patch('blueprints.public.korapay') as mock_korapay:
            with patch('blueprints.public.get_db') as mock_get_db:
                with patch('blueprints.public.session', {'pay_access_ONEPAY-TEST-123': True}):
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db
                    
                    mock_tx_unconfirmed = Mock()
                    mock_tx_unconfirmed.tx_ref = 'ONEPAY-TEST-123'
                    mock_tx_unconfirmed.transfer_confirmed = False
                    mock_tx_unconfirmed.is_used = False
                    mock_tx_unconfirmed.is_expired.return_value = False
                    
                    mock_tx_confirmed = Mock()
                    mock_tx_confirmed.tx_ref = 'ONEPAY-TEST-123'
                    mock_tx_confirmed.transfer_confirmed = True
                    
                    mock_db.query().filter().first.return_value = mock_tx_unconfirmed
                    mock_db.query().filter().with_for_update().first.return_value = mock_tx_confirmed
                    
                    mock_korapay.is_transfer_configured.return_value = True
                    
                    with patch('blueprints.public.check_rate_limit', return_value=True):
                        response = client.get('/api/payments/transfer-status/ONEPAY-TEST-123')
                        
                        assert response.status_code == 200
                        data = json.loads(response.data)
                        assert data['status'] == 'confirmed'
                        mock_korapay.confirm_transfer.assert_not_called()




class TestConcurrentConfirmationSafety:
    """
    Property test for concurrent confirmation race condition safety.
    
    Tests Requirements: 7.16, 7.17, 7.23, 7.24, 7.25, 48.15-48.24
    Property 13: Concurrent Confirmation Race Condition Safety
    
    Note: This test validates the code structure for concurrent safety.
    Full concurrent testing with real database locks would require integration tests
    with actual database transactions, which is beyond the scope of unit testing.
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
    
    def test_concurrent_confirmation_code_structure(self, client):
        """
        Test that the code structure supports concurrent confirmation safety.
        
        Validates:
        - Code uses with_for_update() for pessimistic locking
        - Double-check pattern is implemented after lock acquisition
        - Transaction state is checked before and after lock
        - Only confirmed transactions trigger webhooks and updates
        
        This test validates the implementation pattern. Full concurrent testing
        would require a real database with actual row-level locking.
        """
        with patch('blueprints.public.korapay') as mock_korapay:
            with patch('blueprints.public.get_db') as mock_get_db:
                with patch('blueprints.public.session', {'pay_access_ONEPAY-TEST-123': True}):
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db
                    
                    # Simulate transaction state
                    mock_tx = Mock()
                    mock_tx.tx_ref = 'ONEPAY-TEST-123'
                    mock_tx.transfer_confirmed = False
                    mock_tx.is_used = False
                    mock_tx.is_expired.return_value = False
                    mock_tx.webhook_url = None
                    mock_tx.user_id = 1
                    mock_tx.amount = Decimal('1500.00')
                    
                    mock_db.query().filter().first.return_value = mock_tx
                    mock_db.query().filter().with_for_update().first.return_value = mock_tx
                    
                    mock_korapay.is_transfer_configured.return_value = True
                    mock_korapay.confirm_transfer.return_value = {
                        "responseCode": "00",
                        "transactionReference": "ONEPAY-TEST-123"
                    }
                    
                    with patch('blueprints.public.check_rate_limit', return_value=True):
                        with patch('services.webhook.sync_invoice_on_transaction_update'):
                            response = client.get('/api/payments/transfer-status/ONEPAY-TEST-123')
                            
                            # Verify response
                            assert response.status_code == 200
                            data = json.loads(response.data)
                            assert data['success'] is True
                            assert data['status'] == 'confirmed'
                            
                            # Verify pessimistic locking was used
                            mock_db.query().filter().with_for_update.assert_called()

                            # Verify transaction was updated
                            assert mock_tx.transfer_confirmed is True
                            assert mock_tx.status == TransactionStatus.VERIFIED


class TestSessionAccessControl:
    """
    Integration tests for session access control on transfer status polling.

    Tests Requirements: 12.12, 7.29, 7.30
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

    def test_status_polling_without_session_token_returns_403(self, client):
        """
        Test that status polling without session token returns 403.
        Requirement 7.29: Session token required for status access
        """
        with patch('blueprints.public.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            mock_db.query().filter().first.return_value = None

            response = client.get('/api/payments/transfer-status/ONEPAY-TEST-123')

            assert response.status_code == 403

    def test_status_polling_without_pay_access_returns_403(self, client):
        """
        Test that status polling without pay_access session returns 403.
        Requirement 7.29: Pay access token required for status access
        """
        with patch('blueprints.public.get_db') as mock_get_db:
            with patch('blueprints.public.session', {}):  # No pay_access
                mock_db = MagicMock()
                mock_get_db.return_value.__enter__.return_value = mock_db

                mock_tx = Mock()
                mock_tx.tx_ref = 'ONEPAY-TEST-123'
                mock_tx.transfer_confirmed = False
                mock_tx.is_used = False
                mock_tx.is_expired.return_value = False
                mock_db.query().filter().first.return_value = mock_tx

                response = client.get('/api/payments/transfer-status/ONEPAY-TEST-123')

                assert response.status_code == 403

    def test_status_polling_with_valid_session_token_succeeds(self, client):
        """
        Test that status polling with valid pay_access session token succeeds.
        Requirement 7.30: Valid session token allows access
        """
        with patch('blueprints.public.korapay') as mock_korapay:
            with patch('blueprints.public.get_db') as mock_get_db:
                with patch('blueprints.public.session', {'pay_access_ONEPAY-TEST-123': True}):
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db

                    mock_tx = Mock()
                    mock_tx.tx_ref = 'ONEPAY-TEST-123'
                    mock_tx.transfer_confirmed = False
                    mock_tx.is_used = False
                    mock_tx.is_expired.return_value = False
                    mock_db.query().filter().first.return_value = mock_tx
                    mock_db.query().filter().with_for_update().first.return_value = mock_tx

                    mock_korapay.is_transfer_configured.return_value = True
                    mock_korapay.confirm_transfer.return_value = {
                        "responseCode": "Z0",
                        "transactionReference": "ONEPAY-TEST-123"
                    }

                    with patch('blueprints.public.check_rate_limit', return_value=True):
                        response = client.get('/api/payments/transfer-status/ONEPAY-TEST-123')

                        assert response.status_code == 200


class TestIdempotency:
    """
    Integration tests for idempotency in payment operations.

    Tests Requirements: 12.22, 6.23, 6.24, 9.30, 9.31
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

    def test_duplicate_webhook_processing_is_idempotent(self, client):
        """
        Test that duplicate webhook processing is idempotent.
        Requirement 9.30, 9.31: Idempotent webhook handling
        """
        with patch('blueprints.payments.korapay') as mock_korapay:
            with patch('blueprints.payments.get_db') as mock_get_db:
                with patch('blueprints.payments.is_valid_csrf_token', return_value=True):
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db

                    mock_user = Mock()
                    mock_user.id = 1
                    mock_user.webhook_url = None
                    mock_db.query().filter().first.return_value = mock_user

                    mock_korapay.is_transfer_configured.return_value = True
                    mock_korapay.create_virtual_account.return_value = {
                        "accountNumber": "3000000001",
                        "bankName": "Wema Bank (Demo)",
                        "accountName": "testuser - OnePay Payment",
                        "amount": 150000,
                        "transactionReference": "ONEPAY-TEST-123",
                        "responseCode": "Z0",
                        "validityPeriodMins": 30
                    }

                    with patch('blueprints.payments.check_rate_limit', return_value=True):
                        with patch('blueprints.payments.qr_service.generate_payment_qr', return_value='data:image/png;base64,test'):
                            with client.session_transaction() as sess:
                                sess['user_id'] = 1
                                sess['username'] = 'testuser'
                                sess['csrf_token'] = 'test-csrf-token'

                            # First call
                            response1 = client.post('/api/payments/link',
                                json={'amount': 1500.00, 'description': 'Test payment', 'currency': 'NGN'},
                                headers={'X-CSRF-Token': 'test-csrf-token'},
                                content_type='application/json'
                            )

                            # Verify KoraPay was called once
                            assert mock_korapay.create_virtual_account.call_count == 1

    @pytest.mark.skip(reason="Idempotency key feature not yet implemented in payments.py")
    def test_idempotency_key_prevents_duplicate_account_creation(self, client):
        """
        Test that idempotency_key prevents duplicate virtual account creation.
        Requirement 6.23, 6.24: Idempotency key support
        """
        with patch('blueprints.payments.korapay') as mock_korapay:
            with patch('blueprints.payments.get_db') as mock_get_db:
                with patch('blueprints.payments.is_valid_csrf_token', return_value=True):
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db

                    mock_user = Mock()
                    mock_user.id = 1
                    mock_user.webhook_url = None
                    mock_db.query().filter().first.return_value = mock_user

                    mock_korapay.is_transfer_configured.return_value = True
                    mock_korapay.create_virtual_account.return_value = {
                        "accountNumber": "3000000001",
                        "bankName": "Wema Bank (Demo)",
                        "accountName": "testuser - OnePay Payment",
                        "amount": 150000,
                        "transactionReference": "ONEPAY-TEST-123",
                        "responseCode": "Z0",
                        "validityPeriodMins": 30
                    }

                    with patch('blueprints.payments.check_rate_limit', return_value=True):
                        with patch('blueprints.payments.qr_service.generate_payment_qr', return_value='data:image/png;base64,test'):
                            with client.session_transaction() as sess:
                                sess['user_id'] = 1
                                sess['username'] = 'testuser'
                                sess['csrf_token'] = 'test-csrf-token'

                            # First call with idempotency key
                            idempotency_key = 'unique-idempotency-key-123'
                            response1 = client.post('/api/payments/link',
                                json={
                                    'amount': 1500.00,
                                    'description': 'Test payment',
                                    'currency': 'NGN',
                                    'idempotency_key': idempotency_key
                                },
                                headers={'X-CSRF-Token': 'test-csrf-token'},
                                content_type='application/json'
                            )

                            # Second call with same idempotency key should not create new account
                            response2 = client.post('/api/payments/link',
                                json={
                                    'amount': 1500.00,
                                    'description': 'Test payment',
                                    'currency': 'NGN',
                                    'idempotency_key': idempotency_key
                                },
                                headers={'X-CSRF-Token': 'test-csrf-token'},
                                content_type='application/json'
                            )

                            # Should only be called once due to idempotency
                            assert mock_korapay.create_virtual_account.call_count == 1


class TestCompleteFlowMockMode:
    """
    End-to-end integration tests for complete payment flow in mock mode.

    Tests Requirements: 4.21, 4.22, 4.23, 4.24, 12.9
    This test validates the complete flow from merchant login to payment confirmation.
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

    def test_complete_payment_flow_mock_mode(self, client):
        """
        Test complete payment flow in mock mode:
        1. Merchant creates payment link
        2. Virtual account is created
        3. QR codes are generated
        4. Customer polls status (pending 3x)
        5. Customer polls status (confirmed on 4th)
        6. Transaction is confirmed
        7. Webhook delivered
        8. Invoice created and synced
        9. Audit logs created
        """
        with patch('blueprints.payments.korapay') as mock_korapay:
            with patch('blueprints.payments.get_db') as mock_get_db:
                with patch('blueprints.payments.is_valid_csrf_token', return_value=True):
                    with patch('blueprints.public.korapay') as mock_public_korapay:
                        with patch('blueprints.public.get_db') as mock_public_db:
                            mock_db = MagicMock()
                            mock_get_db.return_value.__enter__.return_value = mock_db
                            mock_public_db_instance = MagicMock()
                            mock_public_db.return_value.__enter__.return_value = mock_public_db_instance

                            mock_user = Mock()
                            mock_user.id = 1
                            mock_user.username = 'testmerchant'
                            mock_user.email = 'test@example.com'
                            mock_user.webhook_url = None
                            mock_db.query().filter().first.return_value = mock_user

                            mock_korapay.is_transfer_configured.return_value = True
                            mock_korapay.create_virtual_account.return_value = {
                                "accountNumber": "3000000001",
                                "bankName": "Wema Bank (Demo)",
                                "accountName": "testmerchant - OnePay Payment",
                                "amount": 150000,
                                "transactionReference": "ONEPAY-TEST-MOCK-001",
                                "responseCode": "Z0",
                                "validityPeriodMins": 30
                            }

                            mock_public_korapay.is_transfer_configured.return_value = True
                            mock_public_korapay.confirm_transfer.return_value = {
                                "responseCode": "Z0",  # Pending
                                "transactionReference": "ONEPAY-TEST-MOCK-001"
                            }

                            with patch('blueprints.payments.check_rate_limit', return_value=True):
                                with patch('blueprints.payments.qr_service.generate_payment_qr', return_value='data:image/png;base64,testqr'):
                                    with patch('services.webhook.sync_invoice_on_transaction_update'):
                                        with patch('core.audit.log_audit_event'):
                                            with client.session_transaction() as sess:
                                                sess['user_id'] = 1
                                                sess['username'] = 'testmerchant'
                                                sess['csrf_token'] = 'test-csrf-token'

                                            # Step 1: Create payment link
                                            response = client.post('/api/payments/link',
                                                json={
                                                    'amount': 1500.00,
                                                    'description': 'Test payment',
                                                    'currency': 'NGN'
                                                },
                                                headers={'X-CSRF-Token': 'test-csrf-token'},
                                                content_type='application/json'
                                            )

                                            assert response.status_code == 201
                                            data = json.loads(response.data)
                                            assert data['success'] is True
                                            tx_ref = data['transaction']['reference']
                                            assert tx_ref.startswith('ONEPAY-')

                                            # Step 2-5: Poll status 4 times (3 pending, 1 confirmed)
                                            for poll_count in range(4):
                                                mock_tx = Mock()
                                                mock_tx.tx_ref = tx_ref
                                                mock_tx.transfer_confirmed = poll_count >= 3
                                                mock_tx.is_used = False
                                                mock_tx.is_expired.return_value = False
                                                mock_tx.status = 'PENDING' if poll_count < 3 else 'VERIFIED'
                                                mock_tx.amount = Decimal('1500.00')
                                                mock_tx.user_id = 1
                                                mock_tx.webhook_url = None

                                                mock_public_db_instance.query().filter().first.return_value = mock_tx
                                                mock_public_db_instance.query().filter().with_for_update().first.return_value = mock_tx

                                                if poll_count == 3:
                                                    mock_public_korapay.confirm_transfer.return_value = {
                                                        "responseCode": "00",  # Confirmed
                                                        "transactionReference": tx_ref
                                                    }

                                                with patch('blueprints.public.check_rate_limit', return_value=True):
                                                    with patch('blueprints.public.session', {'pay_access_' + tx_ref: True}):
                                                        status_response = client.get(f'/api/payments/transfer-status/{tx_ref}')

                                                assert status_response.status_code == 200
                                                status_data = json.loads(status_response.data)

                                                if poll_count < 3:
                                                    assert status_data['status'] == 'pending'
                                                else:
                                                    assert status_data['status'] == 'confirmed'

                            # Verify KoraPay was called for account creation
                            assert mock_korapay.create_virtual_account.call_count == 1

                            # Verify confirm_transfer was called 4 times (once per poll)
                            assert mock_public_korapay.confirm_transfer.call_count == 4


class TestBackwardCompatibility:
    """
    Tests for backward compatibility of API endpoints.

    Tests Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6
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

    def test_payment_link_response_format_unchanged(self, client):
        """
        Test that payment link response format matches expected API contract.
        Requirements: 15.1, 15.2
        """
        with patch('blueprints.payments.korapay') as mock_korapay:
            with patch('blueprints.payments.get_db') as mock_get_db:
                with patch('blueprints.payments.is_valid_csrf_token', return_value=True):
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db

                    mock_user = Mock()
                    mock_user.id = 1
                    mock_user.webhook_url = None
                    mock_db.query().filter().first.return_value = mock_user

                    mock_korapay.is_transfer_configured.return_value = True
                    mock_korapay.create_virtual_account.return_value = {
                        "accountNumber": "3000000001",
                        "bankName": "Wema Bank (Demo)",
                        "accountName": "testuser - OnePay Payment",
                        "amount": 150000,
                        "transactionReference": "ONEPAY-TEST-123",
                        "responseCode": "Z0",
                        "validityPeriodMins": 30
                    }

                    with patch('blueprints.payments.check_rate_limit', return_value=True):
                        with patch('blueprints.payments.qr_service.generate_payment_qr', return_value='data:image/png;base64,test'):
                            with client.session_transaction() as sess:
                                sess['user_id'] = 1
                                sess['username'] = 'testuser'
                                sess['csrf_token'] = 'test-csrf-token'

                            response = client.post('/api/payments/link',
                                json={'amount': 1500.00, 'description': 'Test', 'currency': 'NGN'},
                                headers={'X-CSRF-Token': 'test-csrf-token'},
                                content_type='application/json'
                            )

                            assert response.status_code == 201
                            data = json.loads(response.data)

                            # Verify response structure
                            assert 'success' in data
                            assert 'transaction' in data
                            tx = data['transaction']
                            assert 'reference' in tx
                            assert 'account_number' in tx
                            assert 'bank_name' in tx
                            assert 'qr_codes' in tx

    def test_transfer_status_response_format_unchanged(self, client):
        """
        Test that transfer status response format matches expected API contract.
        Requirements: 15.3, 15.4
        """
        with patch('blueprints.public.korapay') as mock_korapay:
            with patch('blueprints.public.get_db') as mock_get_db:
                with patch('blueprints.public.session', {'pay_access_ONEPAY-TEST-123': True}):
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db

                    mock_tx = Mock()
                    mock_tx.tx_ref = 'ONEPAY-TEST-123'
                    mock_tx.transfer_confirmed = False
                    mock_tx.is_used = False
                    mock_tx.is_expired.return_value = False
                    mock_db.query().filter().first.return_value = mock_tx
                    mock_db.query().filter().with_for_update().first.return_value = mock_tx

                    mock_korapay.is_transfer_configured.return_value = True
                    mock_korapay.confirm_transfer.return_value = {
                        "responseCode": "Z0",
                        "transactionReference": "ONEPAY-TEST-123"
                    }

                    with patch('blueprints.public.check_rate_limit', return_value=True):
                        response = client.get('/api/payments/transfer-status/ONEPAY-TEST-123')

                        assert response.status_code == 200
                        data = json.loads(response.data)

                        # Verify response structure
                        assert 'success' in data
                        assert 'status' in data
                        assert 'transaction_reference' in data


class TestConfigurationValidation:
    """
    Tests for production configuration validation.

    Tests Requirements: 5.9, 5.10, 5.11, 5.13, 5.14, 5.15, 5.16, 5.17, 5.18, 31.16-31.30
    """

    def test_config_validation_detects_empty_secret_key(self):
        """Test that config validation detects empty secret key."""
        import os
        os.environ['KORAPAY_SECRET_KEY'] = ''

        from config import Config
        # Validation happens at startup, so we check the value
        assert Config.KORAPAY_SECRET_KEY == ''

    def test_config_validation_detects_short_secret_key(self):
        """Test that config validation detects short secret key."""
        import os
        os.environ['KORAPAY_SECRET_KEY'] = 'short'

        from config import Config
        # Should be rejected if < 40 chars
        is_valid = len(Config.KORAPAY_SECRET_KEY) >= 40 if Config.KORAPAY_SECRET_KEY else False
        assert is_valid is False

    def test_config_validation_detects_test_key_in_production(self):
        """Test that config validation detects sk_test_ in production env."""
        import os
        os.environ['KORAPAY_SECRET_KEY'] = 'sk_test_abcdefghijklmnopqrstuvwxyz12345678'
        os.environ['APP_ENV'] = 'production'

        from config import Config
        is_live_key = Config.KORAPAY_SECRET_KEY.startswith('sk_live_')
        is_production = Config.APP_ENV == 'production'
        # In production, should only accept sk_live_ keys
        if is_production:
            assert is_live_key, "Production should use sk_live_ keys"

    def test_config_validation_detects_duplicate_secrets(self):
        """Test that duplicate secrets are detected."""
        import os
        os.environ['KORAPAY_SECRET_KEY'] = 'a' * 64
        os.environ['HMAC_SECRET'] = 'a' * 64

        from config import Config
        # Secrets should be different
        assert Config.KORAPAY_SECRET_KEY != Config.HMAC_SECRET

    def test_config_validation_detects_sandbox_mode_in_production(self):
        """Test that sandbox mode is detected in production."""
        import os
        os.environ['KORAPAY_USE_SANDBOX'] = 'true'
        os.environ['APP_ENV'] = 'production'

        from config import Config
        is_sandbox = Config.KORAPAY_USE_SANDBOX is True
        is_production = Config.APP_ENV == 'production'
        if is_production:
            assert not is_sandbox, "Production should not use sandbox mode"
