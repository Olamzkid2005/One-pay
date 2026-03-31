"""
Unit tests for database models.

Tests Transaction model extensions and Refund model.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from models.base import Base
from models.transaction import Transaction, TransactionStatus


class TestTransactionModelExtensions:
    """Test Transaction model has new KoraPay-specific fields."""
    
    @pytest.fixture
    def db_session(self):
        """Create in-memory SQLite database for testing."""
        engine = create_engine('sqlite:///:memory:')
        
        # Enable foreign key constraints in SQLite
        from sqlalchemy import event
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()
    
    def test_transaction_has_payment_provider_reference_column(self, db_session):
        """Test Transaction model has payment_provider_reference column."""
        # Create transaction with new field
        tx = Transaction(
            tx_ref='TEST-001',
            amount=Decimal('1500.00'),
            hash_token='test_hash',
            expires_at=datetime.now(timezone.utc),
            payment_provider_reference='KPY-CA-TEST-001'
        )
        db_session.add(tx)
        db_session.commit()
        
        # Query back and verify
        result = db_session.query(Transaction).filter_by(tx_ref='TEST-001').first()
        assert result is not None
        assert result.payment_provider_reference == 'KPY-CA-TEST-001'
    
    def test_transaction_has_provider_fee_column(self, db_session):
        """Test Transaction model has provider_fee column."""
        tx = Transaction(
            tx_ref='TEST-002',
            amount=Decimal('1500.00'),
            hash_token='test_hash',
            expires_at=datetime.now(timezone.utc),
            provider_fee=Decimal('22.50')
        )
        db_session.add(tx)
        db_session.commit()
        
        result = db_session.query(Transaction).filter_by(tx_ref='TEST-002').first()
        assert result.provider_fee == Decimal('22.50')
    
    def test_transaction_has_provider_vat_column(self, db_session):
        """Test Transaction model has provider_vat column."""
        tx = Transaction(
            tx_ref='TEST-003',
            amount=Decimal('1500.00'),
            hash_token='test_hash',
            expires_at=datetime.now(timezone.utc),
            provider_vat=Decimal('1.69')
        )
        db_session.add(tx)
        db_session.commit()
        
        result = db_session.query(Transaction).filter_by(tx_ref='TEST-003').first()
        assert result.provider_vat == Decimal('1.69')
    
    def test_transaction_has_provider_transaction_date_column(self, db_session):
        """Test Transaction model has provider_transaction_date column."""
        provider_date = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
        tx = Transaction(
            tx_ref='TEST-004',
            amount=Decimal('1500.00'),
            hash_token='test_hash',
            expires_at=datetime.now(timezone.utc),
            provider_transaction_date=provider_date
        )
        db_session.add(tx)
        db_session.commit()
        
        result = db_session.query(Transaction).filter_by(tx_ref='TEST-004').first()
        # SQLite doesn't preserve timezone info, so compare without timezone
        assert result.provider_transaction_date.replace(tzinfo=timezone.utc) == provider_date
    
    def test_transaction_has_payer_bank_details_column(self, db_session):
        """Test Transaction model has payer_bank_details column."""
        bank_details = '{"bank_name": "Test Bank", "account_number": "0000000000"}'
        tx = Transaction(
            tx_ref='TEST-005',
            amount=Decimal('1500.00'),
            hash_token='test_hash',
            expires_at=datetime.now(timezone.utc),
            payer_bank_details=bank_details
        )
        db_session.add(tx)
        db_session.commit()
        
        result = db_session.query(Transaction).filter_by(tx_ref='TEST-005').first()
        assert result.payer_bank_details == bank_details
    
    def test_transaction_has_failure_reason_column(self, db_session):
        """Test Transaction model has failure_reason column."""
        tx = Transaction(
            tx_ref='TEST-006',
            amount=Decimal('1500.00'),
            hash_token='test_hash',
            expires_at=datetime.now(timezone.utc),
            failure_reason='Insufficient funds'
        )
        db_session.add(tx)
        db_session.commit()
        
        result = db_session.query(Transaction).filter_by(tx_ref='TEST-006').first()
        assert result.failure_reason == 'Insufficient funds'
    
    def test_transaction_has_provider_status_column(self, db_session):
        """Test Transaction model has provider_status column."""
        tx = Transaction(
            tx_ref='TEST-007',
            amount=Decimal('1500.00'),
            hash_token='test_hash',
            expires_at=datetime.now(timezone.utc),
            provider_status='success'
        )
        db_session.add(tx)
        db_session.commit()
        
        result = db_session.query(Transaction).filter_by(tx_ref='TEST-007').first()
        assert result.provider_status == 'success'
    
    def test_transaction_has_bank_code_column(self, db_session):
        """Test Transaction model has bank_code column."""
        tx = Transaction(
            tx_ref='TEST-008',
            amount=Decimal('1500.00'),
            hash_token='test_hash',
            expires_at=datetime.now(timezone.utc),
            bank_code='035'
        )
        db_session.add(tx)
        db_session.commit()
        
        result = db_session.query(Transaction).filter_by(tx_ref='TEST-008').first()
        assert result.bank_code == '035'
    
    def test_transaction_has_virtual_account_expiry_column(self, db_session):
        """Test Transaction model has virtual_account_expiry column."""
        expiry = datetime(2026, 4, 1, 13, 0, 0, tzinfo=timezone.utc)
        tx = Transaction(
            tx_ref='TEST-009',
            amount=Decimal('1500.00'),
            hash_token='test_hash',
            expires_at=datetime.now(timezone.utc),
            virtual_account_expiry=expiry
        )
        db_session.add(tx)
        db_session.commit()
        
        result = db_session.query(Transaction).filter_by(tx_ref='TEST-009').first()
        # SQLite doesn't preserve timezone info, so compare without timezone
        assert result.virtual_account_expiry.replace(tzinfo=timezone.utc) == expiry
    
    def test_transaction_new_fields_are_nullable(self, db_session):
        """Test that new KoraPay fields are nullable (backward compatibility)."""
        # Create transaction without new fields
        tx = Transaction(
            tx_ref='TEST-010',
            amount=Decimal('1500.00'),
            hash_token='test_hash',
            expires_at=datetime.now(timezone.utc)
        )
        db_session.add(tx)
        db_session.commit()
        
        result = db_session.query(Transaction).filter_by(tx_ref='TEST-010').first()
        assert result.payment_provider_reference is None
        assert result.provider_fee is None
        assert result.provider_vat is None
        assert result.provider_transaction_date is None
        assert result.payer_bank_details is None
        assert result.failure_reason is None
        assert result.provider_status is None
        assert result.bank_code is None
        assert result.virtual_account_expiry is None
    
    def test_transaction_has_payment_provider_reference_index(self, db_session):
        """Test that payment_provider_reference has an index."""
        inspector = inspect(db_session.bind)
        indexes = inspector.get_indexes('transactions')
        index_names = [idx['name'] for idx in indexes]
        assert 'idx_payment_provider_reference' in index_names
    
    def test_transaction_has_provider_transaction_date_index(self, db_session):
        """Test that provider_transaction_date has an index."""
        inspector = inspect(db_session.bind)
        indexes = inspector.get_indexes('transactions')
        index_names = [idx['name'] for idx in indexes]
        assert 'idx_provider_transaction_date' in index_names


class TestRefundModel:
    """Test Refund model."""
    
    @pytest.fixture
    def db_session(self):
        """Create in-memory SQLite database for testing."""
        engine = create_engine('sqlite:///:memory:')
        
        # Enable foreign key constraints in SQLite
        from sqlalchemy import event
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()
    
    def test_refund_model_can_be_created(self, db_session):
        """Test Refund model can be created and queried."""
        from models.refund import Refund, RefundStatus
        
        # Create parent transaction first
        tx = Transaction(
            tx_ref='TEST-REFUND-001',
            amount=Decimal('1500.00'),
            hash_token='test_hash',
            expires_at=datetime.now(timezone.utc)
        )
        db_session.add(tx)
        db_session.commit()
        
        # Create refund
        refund = Refund(
            transaction_id=tx.id,
            refund_reference='REFUND-TEST-001',
            amount=Decimal('1500.00'),
            currency='NGN',
            status=RefundStatus.PROCESSING,
            reason='Customer request',
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(refund)
        db_session.commit()
        
        # Query back
        result = db_session.query(Refund).filter_by(refund_reference='REFUND-TEST-001').first()
        assert result is not None
        assert result.amount == Decimal('1500.00')
        assert result.status == RefundStatus.PROCESSING
        assert result.reason == 'Customer request'
    
    def test_refund_foreign_key_cascade_delete(self, db_session):
        """Test foreign key cascade delete works."""
        from models.refund import Refund, RefundStatus
        
        # Create transaction and refund
        tx = Transaction(
            tx_ref='TEST-CASCADE-001',
            amount=Decimal('1500.00'),
            hash_token='test_hash',
            expires_at=datetime.now(timezone.utc)
        )
        db_session.add(tx)
        db_session.commit()
        
        tx_id = tx.id
        
        refund = Refund(
            transaction_id=tx.id,
            refund_reference='REFUND-CASCADE-001',
            amount=Decimal('1500.00'),
            currency='NGN',
            status=RefundStatus.PROCESSING,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(refund)
        db_session.commit()
        
        refund_id = refund.id
        
        # Close session to avoid SQLAlchemy trying to manage the relationship
        db_session.close()
        
        # Use raw SQL to delete transaction and verify cascade
        from sqlalchemy import text
        engine = db_session.bind
        with engine.connect() as conn:
            # Delete transaction - should cascade to refund
            conn.execute(text("DELETE FROM transactions WHERE id = :id"), {"id": tx_id})
            conn.commit()
            
            # Check refund was deleted
            result = conn.execute(text("SELECT * FROM refunds WHERE id = :id"), {"id": refund_id})
            assert result.fetchone() is None
    
    def test_refund_has_required_indexes(self, db_session):
        """Test refund table has required indexes."""
        from models.refund import Refund
        
        inspector = inspect(db_session.bind)
        indexes = inspector.get_indexes('refunds')
        index_names = [idx['name'] for idx in indexes]
        
        assert 'idx_refunds_transaction_id' in index_names
        assert 'idx_refunds_status' in index_names
        assert 'idx_refunds_created_at' in index_names
    
    def test_refund_reference_is_unique(self, db_session):
        """Test refund_reference has unique constraint."""
        from models.refund import Refund, RefundStatus
        from sqlalchemy.exc import IntegrityError
        
        # Create transaction
        tx = Transaction(
            tx_ref='TEST-UNIQUE-001',
            amount=Decimal('1500.00'),
            hash_token='test_hash',
            expires_at=datetime.now(timezone.utc)
        )
        db_session.add(tx)
        db_session.commit()
        
        # Create first refund
        refund1 = Refund(
            transaction_id=tx.id,
            refund_reference='REFUND-UNIQUE-001',
            amount=Decimal('1500.00'),
            currency='NGN',
            status=RefundStatus.PROCESSING,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(refund1)
        db_session.commit()
        
        # Try to create duplicate
        refund2 = Refund(
            transaction_id=tx.id,
            refund_reference='REFUND-UNIQUE-001',  # Same reference
            amount=Decimal('500.00'),
            currency='NGN',
            status=RefundStatus.PROCESSING,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(refund2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
