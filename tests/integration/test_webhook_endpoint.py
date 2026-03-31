"""
Integration tests for KoraPay webhook endpoint.

Tests webhook signature verification, payment processing, idempotency,
rate limiting, and audit logging.

Requirements tested: 9.1-9.45
"""
import pytest
import json
import hmac
import hashlib
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from models.transaction import TransactionStatus


class TestWebhookEndpoint:
    """
    Integration tests for KoraPay webhook endpoint.
    
    Tests Requirements: 9.7, 9.8, 9.9, 9.10, 9.11, 9.12, 9.23, 9.30, 9.31, 9.44
    """
    
    @pytest.fixture
    def app(self):
        """Create test Flask app."""
        from app import app as flask_app
        flask_app.config['TESTING'] = True
        flask_app.config['SECRET_KEY'] = 'test-secret-key-for-sessions'
        flask_app.config['KORAPAY_SECRET_KEY'] = 'sk_test_1234567890abcdef1234567890abcdef'
        flask_app.config['KORAPAY_WEBHOOK_SECRET'] = 'webhook-secret-32-chars-long-test'
        return flask_app
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        with app.test_client() as client:
            yield client
    
    def _generate_valid_signature(self, data: dict, secret: str) -> str:
        """Generate valid HMAC-SHA256 signature for webhook data."""
        data_bytes = json.dumps(data, separators=(',', ':')).encode('utf-8')
        return hmac.new(
            secret.encode('utf-8'),
            data_bytes,
            hashlib.sha256
        ).hexdigest()
    
    def test_webhook_with_valid_signature_processes_payment(self, client):
        """
        Test that webhook with valid signature processes payment.
        Requirements 9.1, 9.2, 9.7: Valid webhook processing
        """
        with patch('config.Config.KORAPAY_WEBHOOK_SECRET', 'webhook-secret-32-chars-long-test'):
            with patch('blueprints.public.get_db') as mock_get_db:
                with patch('blueprints.public.check_rate_limit', return_value=True):
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db
                    
                    # Create mock transaction
                    mock_tx = Mock()
                    mock_tx.tx_ref = 'ONEPAY-TEST-123'
                    mock_tx.amount = Decimal('1500.00')
                    mock_tx.transfer_confirmed = False
                    mock_tx.webhook_url = None
                    mock_tx.user_id = 1
                    mock_db.query().filter().first.return_value = mock_tx
                    
                    # Build webhook payload
                    payload = {
                        "event": "charge.success",
                        "data": {
                            "reference": "ONEPAY-TEST-123",
                            "status": "success",
                            "amount": 1500
                        }
                    }
                    
                    # Generate valid signature
                    signature = self._generate_valid_signature(
                        payload["data"],
                        'webhook-secret-32-chars-long-test'
                    )
                    
                    with patch('services.webhook.sync_invoice_on_transaction_update'):
                        response = client.post(
                            '/api/webhooks/korapay',
                            data=json.dumps(payload),
                            headers={
                                'Content-Type': 'application/json',
                                'x-korapay-signature': signature
                            }
                        )
                        
                        assert response.status_code == 200
                        data = json.loads(response.data)
                        assert data['success'] is True
    
    def test_webhook_with_invalid_signature_returns_401(self, client):
        """
        Test that webhook with invalid signature returns 401.
        Requirements 9.8, 9.9: Signature validation
        """
        with patch('blueprints.public.get_db') as mock_get_db:
            with patch('blueprints.public.check_rate_limit', return_value=True):
                mock_db = MagicMock()
                mock_get_db.return_value.__enter__.return_value = mock_db
                
                # Build webhook payload
                payload = {
                    "event": "charge.success",
                    "data": {
                        "reference": "ONEPAY-TEST-123",
                        "status": "success",
                        "amount": 1500
                    }
                }
                
                # Use invalid signature
                invalid_signature = "0" * 64
                
                response = client.post(
                    '/api/webhooks/korapay',
                    data=json.dumps(payload),
                    headers={
                        'Content-Type': 'application/json',
                        'x-korapay-signature': invalid_signature
                    }
                )
                
                assert response.status_code == 401
    
    def test_webhook_with_missing_signature_returns_401(self, client):
        """
        Test that webhook with missing signature returns 401.
        Requirement 9.10: Missing signature handling
        """
        with patch('blueprints.public.get_db') as mock_get_db:
            with patch('blueprints.public.check_rate_limit', return_value=True):
                mock_db = MagicMock()
                mock_get_db.return_value.__enter__.return_value = mock_db
                
                # Build webhook payload
                payload = {
                    "event": "charge.success",
                    "data": {
                        "reference": "ONEPAY-TEST-123",
                        "status": "success",
                        "amount": 1500
                    }
                }
                
                # No signature header
                response = client.post(
                    '/api/webhooks/korapay',
                    data=json.dumps(payload),
                    headers={'Content-Type': 'application/json'}
                )
                
                assert response.status_code == 401
    
    def test_webhook_with_invalid_json_returns_400(self, client):
        """
        Test that webhook with invalid JSON returns 400.
        Requirement 9.11: Invalid JSON handling
        """
        with patch('blueprints.public.get_db') as mock_get_db:
            with patch('blueprints.public.check_rate_limit', return_value=True):
                mock_db = MagicMock()
                mock_get_db.return_value.__enter__.return_value = mock_db
                
                # Send invalid JSON
                response = client.post(
                    '/api/webhooks/korapay',
                    data='invalid json {',
                    headers={
                        'Content-Type': 'application/json',
                        'x-korapay-signature': '0' * 64
                    }
                )
                
                assert response.status_code == 400
    
    def test_webhook_with_missing_data_object_returns_400(self, client):
        """
        Test that webhook with missing data object returns 400.
        Requirement 9.12: Missing data object handling
        """
        with patch('blueprints.public.get_db') as mock_get_db:
            with patch('blueprints.public.check_rate_limit', return_value=True):
                mock_db = MagicMock()
                mock_get_db.return_value.__enter__.return_value = mock_db
                
                # Build payload without data object
                payload = {
                    "event": "charge.success"
                    # Missing "data" key
                }
                
                response = client.post(
                    '/api/webhooks/korapay',
                    data=json.dumps(payload),
                    headers={
                        'Content-Type': 'application/json',
                        'x-korapay-signature': '0' * 64
                    }
                )
                
                assert response.status_code == 400
    
    def test_webhook_for_already_confirmed_transaction_is_idempotent(self, client):
        """
        Test that webhook for already confirmed transaction is idempotent.
        Requirements 9.30, 9.31: Idempotency
        """
        with patch('config.Config.KORAPAY_WEBHOOK_SECRET', 'webhook-secret-32-chars-long-test'):
            with patch('blueprints.public.get_db') as mock_get_db:
                with patch('blueprints.public.check_rate_limit', return_value=True):
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db
                    
                    # Create mock transaction that's already confirmed
                    mock_tx = Mock()
                    mock_tx.tx_ref = 'ONEPAY-TEST-123'
                    mock_tx.amount = Decimal('1500.00')
                    mock_tx.transfer_confirmed = True  # Already confirmed
                    mock_tx.status = TransactionStatus.VERIFIED
                    mock_db.query().filter().first.return_value = mock_tx
                    
                    # Build webhook payload
                    payload = {
                        "event": "charge.success",
                        "data": {
                            "reference": "ONEPAY-TEST-123",
                            "status": "success",
                            "amount": 1500
                        }
                    }
                    
                    # Generate valid signature
                    signature = self._generate_valid_signature(
                        payload["data"],
                        'webhook-secret-32-chars-long-test'
                    )
                    
                    response = client.post(
                        '/api/webhooks/korapay',
                        data=json.dumps(payload),
                        headers={
                            'Content-Type': 'application/json',
                            'x-korapay-signature': signature
                        }
                    )
                    
                    assert response.status_code == 200
                    data = json.loads(response.data)
                    assert data['success'] is True
                    
                    # Verify transaction status wasn't changed again
                    assert mock_tx.transfer_confirmed is True
    
    def test_webhook_logs_audit_event_on_signature_failure(self, client):
        """
        Test that webhook logs audit event on signature failure.
        Requirement 9.23: Audit logging
        """
        with patch('blueprints.public.get_db') as mock_get_db:
            with patch('blueprints.public.check_rate_limit', return_value=True):
                with patch('blueprints.public.log_event') as mock_log_event:
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db
                    
                    # Build webhook payload
                    payload = {
                        "event": "charge.success",
                        "data": {
                            "reference": "ONEPAY-TEST-123",
                            "status": "success",
                            "amount": 1500
                        }
                    }
                    
                    # Use invalid signature
                    invalid_signature = "0" * 64
                    
                    response = client.post(
                        '/api/webhooks/korapay',
                        data=json.dumps(payload),
                        headers={
                            'Content-Type': 'application/json',
                            'x-korapay-signature': invalid_signature
                        }
                    )
                    
                    assert response.status_code == 401
                    
                    # Verify audit event was logged
                    mock_log_event.assert_called()
                    call_args = mock_log_event.call_args
                    assert 'webhook.signature_failed' in str(call_args)
    
    def test_webhook_rate_limiting(self, client):
        """
        Test that webhook endpoint enforces rate limiting (100 requests/min).
        Requirement 9.44: Rate limiting
        """
        with patch('blueprints.public.get_db') as mock_get_db:
            with patch('blueprints.public.check_rate_limit', return_value=False):
                mock_db = MagicMock()
                mock_get_db.return_value.__enter__.return_value = mock_db
                
                # Build webhook payload
                payload = {
                    "event": "charge.success",
                    "data": {
                        "reference": "ONEPAY-TEST-123",
                        "status": "success",
                        "amount": 1500
                    }
                }
                
                # Generate valid signature
                signature = self._generate_valid_signature(
                    payload["data"],
                    'webhook-secret-32-chars-long-test'
                )
                
                response = client.post(
                    '/api/webhooks/korapay',
                    data=json.dumps(payload),
                    headers={
                        'Content-Type': 'application/json',
                        'x-korapay-signature': signature
                    }
                )
                
                assert response.status_code == 429
    
    def test_webhook_validates_amount_matches(self, client):
        """
        Test that webhook validates amount matches transaction.
        Requirement 9.13: Amount validation
        """
        with patch('config.Config.KORAPAY_WEBHOOK_SECRET', 'webhook-secret-32-chars-long-test'):
            with patch('blueprints.public.get_db') as mock_get_db:
                with patch('blueprints.public.check_rate_limit', return_value=True):
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db
                    
                    # Create mock transaction with different amount
                    mock_tx = Mock()
                    mock_tx.tx_ref = 'ONEPAY-TEST-123'
                    mock_tx.amount = Decimal('2000.00')  # Different from webhook
                    mock_tx.transfer_confirmed = False
                    mock_db.query().filter().first.return_value = mock_tx
                    
                    # Build webhook payload with different amount
                    payload = {
                        "event": "charge.success",
                        "data": {
                            "reference": "ONEPAY-TEST-123",
                            "status": "success",
                            "amount": 1500  # Mismatch
                        }
                    }
                    
                    # Generate valid signature
                    signature = self._generate_valid_signature(
                        payload["data"],
                        'webhook-secret-32-chars-long-test'
                    )
                    
                    response = client.post(
                        '/api/webhooks/korapay',
                        data=json.dumps(payload),
                        headers={
                            'Content-Type': 'application/json',
                            'x-korapay-signature': signature
                        }
                    )
                    
                    assert response.status_code == 400
    
    def test_webhook_updates_transaction_status(self, client):
        """
        Test that webhook updates transaction status if not confirmed.
        Requirements 9.14, 9.15: Transaction update
        """
        with patch('config.Config.KORAPAY_WEBHOOK_SECRET', 'webhook-secret-32-chars-long-test'):
            with patch('blueprints.public.get_db') as mock_get_db:
                with patch('blueprints.public.check_rate_limit', return_value=True):
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db
                    
                    # Create mock transaction
                    mock_tx = Mock()
                    mock_tx.tx_ref = 'ONEPAY-TEST-123'
                    mock_tx.amount = Decimal('1500.00')
                    mock_tx.transfer_confirmed = False
                    mock_tx.webhook_url = None
                    mock_tx.user_id = 1
                    mock_db.query().filter().first.return_value = mock_tx
                    
                    # Build webhook payload
                    payload = {
                        "event": "charge.success",
                        "data": {
                            "reference": "ONEPAY-TEST-123",
                            "status": "success",
                            "amount": 1500
                        }
                    }
                    
                    # Generate valid signature
                    signature = self._generate_valid_signature(
                        payload["data"],
                        'webhook-secret-32-chars-long-test'
                    )
                    
                    with patch('services.webhook.sync_invoice_on_transaction_update'):
                        response = client.post(
                            '/api/webhooks/korapay',
                            data=json.dumps(payload),
                            headers={
                                'Content-Type': 'application/json',
                                'x-korapay-signature': signature
                            }
                        )
                        
                        assert response.status_code == 200
                        
                        # Verify transaction was updated
                        assert mock_tx.transfer_confirmed is True
                        assert mock_tx.status == TransactionStatus.VERIFIED
    
    def test_webhook_syncs_invoice_status(self, client):
        """
        Test that webhook syncs invoice status.
        Requirement 9.16: Invoice sync
        """
        with patch('config.Config.KORAPAY_WEBHOOK_SECRET', 'webhook-secret-32-chars-long-test'):
            with patch('blueprints.public.get_db') as mock_get_db:
                with patch('blueprints.public.check_rate_limit', return_value=True):
                    with patch('services.webhook.sync_invoice_on_transaction_update') as mock_sync:
                        mock_db = MagicMock()
                        mock_get_db.return_value.__enter__.return_value = mock_db
                        
                        # Create mock transaction
                        mock_tx = Mock()
                        mock_tx.tx_ref = 'ONEPAY-TEST-123'
                        mock_tx.amount = Decimal('1500.00')
                        mock_tx.transfer_confirmed = False
                        mock_tx.webhook_url = None
                        mock_tx.user_id = 1
                        mock_db.query().filter().first.return_value = mock_tx
                        
                        # Build webhook payload
                        payload = {
                            "event": "charge.success",
                            "data": {
                                "reference": "ONEPAY-TEST-123",
                                "status": "success",
                                "amount": 1500
                            }
                        }
                        
                        # Generate valid signature
                        signature = self._generate_valid_signature(
                            payload["data"],
                            'webhook-secret-32-chars-long-test'
                        )
                        
                        response = client.post(
                            '/api/webhooks/korapay',
                            data=json.dumps(payload),
                            headers={
                                'Content-Type': 'application/json',
                                'x-korapay-signature': signature
                            }
                        )
                        
                        assert response.status_code == 200
                        
                        # Verify invoice sync was called
                        mock_sync.assert_called_once()
    
    def test_webhook_logs_audit_event_on_success(self, client):
        """
        Test that webhook logs audit event on successful payment confirmation.
        Requirement 9.17: Audit logging
        """
        with patch('config.Config.KORAPAY_WEBHOOK_SECRET', 'webhook-secret-32-chars-long-test'):
            with patch('blueprints.public.get_db') as mock_get_db:
                with patch('blueprints.public.check_rate_limit', return_value=True):
                    with patch('blueprints.public.log_event') as mock_log_event:
                        mock_db = MagicMock()
                        mock_get_db.return_value.__enter__.return_value = mock_db
                        
                        # Create mock transaction
                        mock_tx = Mock()
                        mock_tx.tx_ref = 'ONEPAY-TEST-123'
                        mock_tx.amount = Decimal('1500.00')
                        mock_tx.transfer_confirmed = False
                        mock_tx.webhook_url = None
                        mock_tx.user_id = 1
                        mock_db.query().filter().first.return_value = mock_tx
                        
                        # Build webhook payload
                        payload = {
                            "event": "charge.success",
                            "data": {
                                "reference": "ONEPAY-TEST-123",
                                "status": "success",
                                "amount": 1500
                            }
                        }
                        
                        # Generate valid signature
                        signature = self._generate_valid_signature(
                            payload["data"],
                            'webhook-secret-32-chars-long-test'
                        )
                        
                        with patch('services.webhook.sync_invoice_on_transaction_update'):
                            response = client.post(
                                '/api/webhooks/korapay',
                                data=json.dumps(payload),
                                headers={
                                    'Content-Type': 'application/json',
                                    'x-korapay-signature': signature
                                }
                            )
                            
                            assert response.status_code == 200
                            
                            # Verify audit event was logged
                            mock_log_event.assert_called()
                            call_args = mock_log_event.call_args
                            assert 'payment.confirmed_via_webhook' in str(call_args)



class TestWebhookIdempotencyProperty:
    """
    Property test for webhook processing idempotency.
    
    Tests Requirements: 9.30, 9.31, 49.20
    Property 14: Webhook Processing Idempotency
    
    Validates that processing the same webhook multiple times produces
    the same database state as processing it once.
    """
    
    @pytest.fixture
    def app(self):
        """Create test Flask app."""
        from app import app as flask_app
        flask_app.config['TESTING'] = True
        flask_app.config['SECRET_KEY'] = 'test-secret-key-for-sessions'
        flask_app.config['KORAPAY_SECRET_KEY'] = 'sk_test_1234567890abcdef1234567890abcdef'
        flask_app.config['KORAPAY_WEBHOOK_SECRET'] = 'webhook-secret-32-chars-long-test'
        return flask_app
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        with app.test_client() as client:
            yield client
    
    def _generate_valid_signature(self, data: dict, secret: str) -> str:
        """Generate valid HMAC-SHA256 signature for webhook data."""
        data_bytes = json.dumps(data, separators=(',', ':')).encode('utf-8')
        return hmac.new(
            secret.encode('utf-8'),
            data_bytes,
            hashlib.sha256
        ).hexdigest()
    
    def test_webhook_idempotency_multiple_deliveries(self, client):
        """
        Test that processing webhook N times produces same state as once.
        
        Property: For any valid webhook payload, processing it N times (N >= 1)
        results in the same database state as processing it once.
        
        Requirements: 9.30, 9.31, 49.20
        """
        # Test with different numbers of webhook deliveries
        for n_deliveries in [1, 2, 3, 5, 10]:
            with patch('config.Config.KORAPAY_WEBHOOK_SECRET', 'webhook-secret-32-chars-long-test'):
                with patch('blueprints.public.get_db') as mock_get_db:
                    with patch('blueprints.public.check_rate_limit', return_value=True):
                        mock_db = MagicMock()
                        mock_get_db.return_value.__enter__.return_value = mock_db
                        
                        # Create mock transaction
                        mock_tx = Mock()
                        mock_tx.tx_ref = 'ONEPAY-TEST-123'
                        mock_tx.amount = Decimal('1500.00')
                        mock_tx.transfer_confirmed = False
                        mock_tx.webhook_url = None
                        mock_tx.user_id = 1
                        mock_tx.status = TransactionStatus.PENDING
                        
                        mock_db.query().filter().first.return_value = mock_tx
                        
                        # Build webhook payload
                        payload = {
                            "event": "charge.success",
                            "data": {
                                "reference": "ONEPAY-TEST-123",
                                "status": "success",
                                "amount": 1500
                            }
                        }
                        
                        # Generate valid signature
                        signature = self._generate_valid_signature(
                            payload["data"],
                            'webhook-secret-32-chars-long-test'
                        )
                        
                        # Deliver webhook N times
                        with patch('services.webhook.sync_invoice_on_transaction_update'):
                            for i in range(n_deliveries):
                                response = client.post(
                                    '/api/webhooks/korapay',
                                    data=json.dumps(payload),
                                    headers={
                                        'Content-Type': 'application/json',
                                        'x-korapay-signature': signature
                                    }
                                )
                                
                                # All deliveries should succeed
                                assert response.status_code == 200
                        
                        # Verify final state is correct regardless of N
                        assert mock_tx.transfer_confirmed is True
                        assert mock_tx.status == TransactionStatus.VERIFIED
                        
                        # The key property: state is same whether N=1 or N=10
                        # This is verified by the fact that all assertions pass
                        # for all values of n_deliveries
    
    def test_webhook_idempotency_no_duplicate_webhooks_delivered(self, client):
        """
        Test that duplicate webhook deliveries don't trigger duplicate outbound webhooks.
        
        Property: Processing the same webhook N times should only deliver
        outbound webhook once (on first processing).
        
        Requirement: 9.30, 9.31
        """
        with patch('config.Config.KORAPAY_WEBHOOK_SECRET', 'webhook-secret-32-chars-long-test'):
            with patch('blueprints.public.get_db') as mock_get_db:
                with patch('blueprints.public.check_rate_limit', return_value=True):
                    with patch('services.webhook.deliver_webhook') as mock_deliver:
                        mock_db = MagicMock()
                        mock_get_db.return_value.__enter__.return_value = mock_db
                        
                        # Create mock transaction with webhook URL
                        mock_tx = Mock()
                        mock_tx.tx_ref = 'ONEPAY-TEST-123'
                        mock_tx.amount = Decimal('1500.00')
                        mock_tx.transfer_confirmed = False
                        mock_tx.webhook_url = 'https://merchant.example.com/webhook'
                        mock_tx.user_id = 1
                        
                        mock_db.query().filter().first.return_value = mock_tx
                        
                        # Build webhook payload
                        payload = {
                            "event": "charge.success",
                            "data": {
                                "reference": "ONEPAY-TEST-123",
                                "status": "success",
                                "amount": 1500
                            }
                        }
                        
                        # Generate valid signature
                        signature = self._generate_valid_signature(
                            payload["data"],
                            'webhook-secret-32-chars-long-test'
                        )
                        
                        # Deliver webhook 5 times
                        with patch('services.webhook.sync_invoice_on_transaction_update'):
                            for i in range(5):
                                # Reset for first delivery
                                if i == 0:
                                    mock_tx.transfer_confirmed = False
                                
                                response = client.post(
                                    '/api/webhooks/korapay',
                                    data=json.dumps(payload),
                                    headers={
                                        'Content-Type': 'application/json',
                                        'x-korapay-signature': signature
                                    }
                                )
                                
                                assert response.status_code == 200
                                
                                # Set confirmed after first delivery
                                if i == 0:
                                    mock_tx.transfer_confirmed = True
                                    mock_tx.status = TransactionStatus.VERIFIED
                        
                        # Verify outbound webhook was only delivered once
                        assert mock_deliver.call_count == 1
    
    def test_webhook_idempotency_no_duplicate_emails(self, client):
        """
        Test that duplicate webhook deliveries don't trigger duplicate emails.
        
        Property: Processing the same webhook N times should only trigger
        email notifications once (via invoice sync on first processing).
        
        Requirement: 9.30, 9.31
        """
        with patch('config.Config.KORAPAY_WEBHOOK_SECRET', 'webhook-secret-32-chars-long-test'):
            with patch('blueprints.public.get_db') as mock_get_db:
                with patch('blueprints.public.check_rate_limit', return_value=True):
                    with patch('services.webhook.sync_invoice_on_transaction_update') as mock_sync:
                        mock_db = MagicMock()
                        mock_get_db.return_value.__enter__.return_value = mock_db
                        
                        # Create mock transaction
                        mock_tx = Mock()
                        mock_tx.tx_ref = 'ONEPAY-TEST-123'
                        mock_tx.amount = Decimal('1500.00')
                        mock_tx.transfer_confirmed = False
                        mock_tx.webhook_url = None
                        mock_tx.user_id = 1
                        
                        mock_db.query().filter().first.return_value = mock_tx
                        
                        # Build webhook payload
                        payload = {
                            "event": "charge.success",
                            "data": {
                                "reference": "ONEPAY-TEST-123",
                                "status": "success",
                                "amount": 1500
                            }
                        }
                        
                        # Generate valid signature
                        signature = self._generate_valid_signature(
                            payload["data"],
                            'webhook-secret-32-chars-long-test'
                        )
                        
                        # Deliver webhook 5 times
                        for i in range(5):
                            # Reset for first delivery
                            if i == 0:
                                mock_tx.transfer_confirmed = False
                            
                            response = client.post(
                                '/api/webhooks/korapay',
                                data=json.dumps(payload),
                                headers={
                                    'Content-Type': 'application/json',
                                    'x-korapay-signature': signature
                                }
                            )
                            
                            assert response.status_code == 200
                            
                            # Set confirmed after first delivery
                            if i == 0:
                                mock_tx.transfer_confirmed = True
                                mock_tx.status = TransactionStatus.VERIFIED
                        
                        # Verify invoice sync (which triggers emails) was only called once
                        assert mock_sync.call_count == 1
