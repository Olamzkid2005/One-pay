"""
Edge case tests for VoicePay webhook service.

Tests various edge cases and error conditions for the VoicePay integration.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from services.voicepay_webhook import (
    generate_voicepay_signature,
    build_voicepay_payload
)


class TestSignatureEdgeCases:
    """Test signature generation edge cases"""
    
    def test_signature_with_special_characters(self):
        """Test signature generation with special characters in payload"""
        payload = {
            "description": "Payment for DSTV: Premium Package (₦9,000)",
            "customer_name": "O'Brien & Sons Ltd.",
            "tx_ref": "VP-BILL-123"
        }
        secret = "test-secret-key"
        
        sig = generate_voicepay_signature(payload, secret)
        
        # Verify signature is valid hex
        assert len(sig) == 64
        assert all(c in '0123456789abcdef' for c in sig)
    
    def test_signature_with_unicode(self):
        """Test signature generation with Unicode characters"""
        payload = {
            "customer_name": "José García",
            "description": "Paiement pour électricité",
            "tx_ref": "VP-BILL-456"
        }
        secret = "test-secret-key"
        
        sig = generate_voicepay_signature(payload, secret)
        assert len(sig) == 64
    
    def test_signature_with_empty_values(self):
        """Test signature generation with empty/null values"""
        payload = {
            "tx_ref": "VP-BILL-000",
            "description": "",
            "metadata": None,
            "amount": 0
        }
        secret = "test-secret-key"
        
        sig = generate_voicepay_signature(payload, secret)
        assert len(sig) == 64
    
    def test_signature_with_very_long_strings(self):
        """Test signature generation with very long string values"""
        payload = {
            "tx_ref": "VP-BILL-LONG",
            "description": "A" * 10000,  # 10KB description
            "customer_email": "user@" + "example" * 100 + ".com"
        }
        secret = "test-secret-key"
        
        sig = generate_voicepay_signature(payload, secret)
        assert len(sig) == 64
    
    def test_signature_with_numeric_string_keys(self):
        """Test signature generation with numeric string keys"""
        payload = {
            "123": "value1",
            "456": "value2",
            "tx_ref": "VP-BILL-NUM"
        }
        secret = "test-secret-key"
        
        sig = generate_voicepay_signature(payload, secret)
        assert len(sig) == 64


class TestPayloadBuildingEdgeCases:
    """Test payload building edge cases"""
    
    def test_build_payload_with_very_large_amount(self):
        """Test payload building with very large transaction amount"""
        from models.transaction import Transaction, TransactionStatus
        
        # Create mock transaction with large amount
        transaction = Transaction(
            tx_ref="VP-BILL-LARGE",
            amount=Decimal("99999999.99"),
            status=TransactionStatus.VERIFIED,
            customer_email="user@example.com",
            description="Large payment",
            hash_token="test-hash",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            created_at=datetime.now(timezone.utc),
            verified_at=datetime.now(timezone.utc)
        )
        
        payload = build_voicepay_payload(transaction)
        
        assert payload["amount"] == 99999999.99
        assert isinstance(payload["amount"], float)
    
    def test_build_payload_with_zero_amount(self):
        """Test payload building with zero amount"""
        from models.transaction import Transaction, TransactionStatus
        
        transaction = Transaction(
            tx_ref="VP-BILL-ZERO",
            amount=Decimal("0.00"),
            status=TransactionStatus.VERIFIED,
            customer_email="user@example.com",
            description="Zero payment",
            hash_token="test-hash",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            created_at=datetime.now(timezone.utc),
            verified_at=datetime.now(timezone.utc)
        )
        
        payload = build_voicepay_payload(transaction)
        
        assert payload["amount"] == 0.0
        assert isinstance(payload["amount"], float)
    
    def test_build_payload_with_special_characters_in_description(self):
        """Test payload building with special characters in description"""
        from models.transaction import Transaction, TransactionStatus
        
        transaction = Transaction(
            tx_ref="VP-BILL-SPECIAL",
            amount=Decimal("5000.00"),
            status=TransactionStatus.VERIFIED,
            customer_email="user@example.com",
            description="Payment for: DSTV Premium (₦5,000) - O'Brien & Co.",
            hash_token="test-hash",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            created_at=datetime.now(timezone.utc),
            verified_at=datetime.now(timezone.utc)
        )
        
        payload = build_voicepay_payload(transaction)
        
        assert payload["description"] == "Payment for: DSTV Premium (₦5,000) - O'Brien & Co."
        assert payload["tx_ref"] == "VP-BILL-SPECIAL"
    
    def test_build_payload_with_missing_optional_fields(self):
        """Test payload building when optional fields are None"""
        from models.transaction import Transaction, TransactionStatus
        
        transaction = Transaction(
            tx_ref="VP-BILL-MINIMAL",
            amount=Decimal("1000.00"),
            status=TransactionStatus.VERIFIED,
            customer_email=None,  # Optional
            description=None,  # Optional
            hash_token="test-hash",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            created_at=datetime.now(timezone.utc),
            verified_at=datetime.now(timezone.utc)
        )
        
        payload = build_voicepay_payload(transaction)
        
        assert payload["tx_ref"] == "VP-BILL-MINIMAL"
        assert payload["amount"] == 1000.0
        assert payload["customer_email"] is None
        assert payload["description"] is None
    
    def test_build_payload_with_pending_status(self):
        """Test payload building with PENDING status"""
        from models.transaction import Transaction, TransactionStatus
        
        transaction = Transaction(
            tx_ref="VP-BILL-PENDING",
            amount=Decimal("2000.00"),
            status=TransactionStatus.PENDING,
            customer_email="user@example.com",
            description="Pending payment",
            hash_token="test-hash",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            created_at=datetime.now(timezone.utc),
            verified_at=None  # Not verified yet
        )
        
        payload = build_voicepay_payload(transaction)
        
        assert payload["status"] == "pending"
        assert payload["verified_at"] is None
    
    def test_build_payload_with_failed_status(self):
        """Test payload building with FAILED status"""
        from models.transaction import Transaction, TransactionStatus
        
        transaction = Transaction(
            tx_ref="VP-BILL-FAILED",
            amount=Decimal("3000.00"),
            status=TransactionStatus.FAILED,
            customer_email="user@example.com",
            description="Failed payment",
            hash_token="test-hash",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            created_at=datetime.now(timezone.utc),
            verified_at=None
        )
        
        payload = build_voicepay_payload(transaction)
        
        assert payload["status"] == "failed"
        assert payload["event"] == "payment.verified"
