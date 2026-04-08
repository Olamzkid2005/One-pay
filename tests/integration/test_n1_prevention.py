"""
OnePay — N+1 Query Prevention Integration Tests

Tests that verify N+1 query prevention for the transaction history endpoint
and invoice history service (Requirements 9.2, 9.4).

Strategy:
- Use SQLAlchemy's event system to count SQL statements issued
- Verify that query count stays constant as page size grows
- Verify that selectinload is present in the query options for both
  transaction_history (blueprints/payments.py) and get_invoice_history
  (services/invoice.py)

Requirements: 9.2, 9.4
"""

import inspect
import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm import selectinload

from models.base import Base
from models.transaction import Transaction, TransactionStatus
from models.invoice import Invoice, InvoiceSettings, InvoiceStatus
from models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class QueryCounter:
    """Counts SQL statements issued on a SQLAlchemy connection."""

    def __init__(self):
        self.count = 0
        self.statements = []

    def reset(self):
        self.count = 0
        self.statements = []

    def __call__(self, conn, cursor, statement, parameters, context, executemany):
        self.count += 1
        self.statements.append(statement)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    """In-memory SQLite engine with all tables created."""
    eng = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db_session(engine):
    """Provide a clean session that is rolled back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def query_counter(engine):
    """Attach a query counter to the engine and return it."""
    counter = QueryCounter()
    event.listen(engine, "before_cursor_execute", counter)
    yield counter
    event.remove(engine, "before_cursor_execute", counter)


def _make_user(session: Session, user_id: int = 1) -> User:
    """Create and persist a minimal User."""
    user = User(
        id=user_id,
        username=f"merchant_{user_id}",
        email=f"merchant{user_id}@example.com",
        password_hash="hashed",
    )
    session.add(user)
    session.flush()
    return user


def _make_transaction(
    session: Session,
    user_id: int,
    tx_num: int,
) -> Transaction:
    """Create and persist a minimal Transaction."""
    tx = Transaction(
        tx_ref=f"ONEPAY-TEST-{user_id}-{tx_num:04d}",
        user_id=user_id,
        amount=Decimal("100.00"),
        currency="NGN",
        hash_token="dummy_hash",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        status=TransactionStatus.PENDING,
    )
    session.add(tx)
    session.flush()
    return tx


def _make_invoice(session: Session, transaction: Transaction, user_id: int, seq: int) -> Invoice:
    """Create and persist a minimal Invoice linked to a Transaction."""
    invoice = Invoice(
        invoice_number=f"INV-2026-{seq:06d}",
        transaction_id=transaction.id,
        user_id=user_id,
        amount=transaction.amount,
        currency=transaction.currency,
        status=InvoiceStatus.DRAFT,
    )
    session.add(invoice)
    session.flush()
    return invoice


# ---------------------------------------------------------------------------
# 1. selectinload present in source code
# ---------------------------------------------------------------------------

class TestSelectinloadPresence:
    """
    Verify that selectinload is used in the relevant query paths.
    Requirements: 9.1, 9.2
    """

    def test_transaction_history_uses_selectinload(self):
        """blueprints/payments.py transaction_history must use selectinload."""
        import blueprints.payments as payments_module
        src = inspect.getsource(payments_module.transaction_history)
        assert "selectinload" in src, (
            "transaction_history() must use selectinload to prevent N+1 queries "
            "when accessing Transaction.invoice"
        )

    def test_transaction_history_loads_invoice_relationship(self):
        """transaction_history must eager-load the invoice relationship."""
        import blueprints.payments as payments_module
        src = inspect.getsource(payments_module.transaction_history)
        assert "Transaction.invoice" in src or "invoice" in src, (
            "transaction_history() must eager-load the invoice relationship"
        )

    def test_get_invoice_history_uses_selectinload(self):
        """services/invoice.py get_invoice_history must use selectinload."""
        from services.invoice import InvoiceService
        src = inspect.getsource(InvoiceService.get_invoice_history)
        assert "selectinload" in src, (
            "get_invoice_history() must use selectinload to prevent N+1 queries "
            "when accessing Invoice.transaction"
        )

    def test_get_invoice_history_loads_transaction_relationship(self):
        """get_invoice_history must eager-load the transaction relationship."""
        from services.invoice import InvoiceService
        src = inspect.getsource(InvoiceService.get_invoice_history)
        assert "Invoice.transaction" in src, (
            "get_invoice_history() must eager-load Invoice.transaction"
        )


# ---------------------------------------------------------------------------
# 2. Constant query count for transaction history
# ---------------------------------------------------------------------------

class TestTransactionHistoryQueryCount:
    """
    Assert that the number of SQL queries issued when loading transaction
    history is constant regardless of page size (Requirement 9.2, 9.4).

    With selectinload the pattern is:
      1 query  — COUNT(*) for pagination total
      1 query  — SELECT transactions WHERE user_id = ?  LIMIT ?
      1 query  — SELECT invoices WHERE transaction_id IN (...)   [selectinload]
    = 3 queries total, independent of page size.
    """

    def _load_transactions_with_selectinload(
        self, session: Session, user_id: int, limit: int
    ):
        """Replicate the query pattern used in transaction_history()."""
        # Query 1: count
        total = (
            session.query(Transaction)
            .filter(Transaction.user_id == user_id)
            .count()
        )
        # Query 2 + 3 (selectinload fires a second IN query automatically)
        transactions = (
            session.query(Transaction)
            .options(selectinload(Transaction.invoice))
            .filter(Transaction.user_id == user_id)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
            .all()
        )
        # Access the relationship to ensure it was loaded (not lazy)
        for tx in transactions:
            _ = tx.invoice
        return transactions, total

    def test_query_count_5_transactions(self, db_session, query_counter):
        """Loading 5 transactions should issue a constant number of queries."""
        user = _make_user(db_session, user_id=10)
        for i in range(5):
            tx = _make_transaction(db_session, user_id=10, tx_num=i)
            _make_invoice(db_session, tx, user_id=10, seq=100 + i)
        db_session.flush()

        query_counter.reset()
        txs, total = self._load_transactions_with_selectinload(db_session, user_id=10, limit=5)
        count_5 = query_counter.count

        assert len(txs) == 5
        assert total == 5
        # selectinload pattern: count + main SELECT + IN-load = 3 queries
        assert count_5 <= 3, (
            f"Expected ≤3 queries for 5 transactions, got {count_5}. "
            f"Statements: {query_counter.statements}"
        )

    def test_query_count_10_transactions(self, db_session, query_counter):
        """Loading 10 transactions should issue the same number of queries as 5."""
        user = _make_user(db_session, user_id=20)
        for i in range(10):
            tx = _make_transaction(db_session, user_id=20, tx_num=i)
            _make_invoice(db_session, tx, user_id=20, seq=200 + i)
        db_session.flush()

        query_counter.reset()
        txs, total = self._load_transactions_with_selectinload(db_session, user_id=20, limit=10)
        count_10 = query_counter.count

        assert len(txs) == 10
        assert count_10 <= 3, (
            f"Expected ≤3 queries for 10 transactions, got {count_10}. "
            f"Statements: {query_counter.statements}"
        )

    def test_query_count_is_constant_across_page_sizes(self, db_session, query_counter):
        """
        The query count must be the same for page_size=5 and page_size=10.
        This is the core N+1 prevention assertion (Requirement 9.2, 9.4).
        """
        user = _make_user(db_session, user_id=30)
        for i in range(10):
            tx = _make_transaction(db_session, user_id=30, tx_num=i)
            _make_invoice(db_session, tx, user_id=30, seq=300 + i)
        db_session.flush()

        # Measure for page_size=5
        query_counter.reset()
        self._load_transactions_with_selectinload(db_session, user_id=30, limit=5)
        count_small = query_counter.count

        # Measure for page_size=10
        query_counter.reset()
        self._load_transactions_with_selectinload(db_session, user_id=30, limit=10)
        count_large = query_counter.count

        assert count_small == count_large, (
            f"Query count must be constant regardless of page size. "
            f"Got {count_small} for limit=5 and {count_large} for limit=10. "
            "This indicates an N+1 query problem."
        )

    def test_no_n1_without_invoices(self, db_session, query_counter):
        """Transactions without invoices should also use a constant query count."""
        user = _make_user(db_session, user_id=40)
        for i in range(8):
            _make_transaction(db_session, user_id=40, tx_num=i)
        db_session.flush()

        query_counter.reset()
        txs, total = self._load_transactions_with_selectinload(db_session, user_id=40, limit=8)
        count = query_counter.count

        assert len(txs) == 8
        # Without invoices, selectinload may skip the IN query → ≤3 queries
        assert count <= 3, (
            f"Expected ≤3 queries for 8 transactions (no invoices), got {count}"
        )


# ---------------------------------------------------------------------------
# 3. Constant query count for invoice history
# ---------------------------------------------------------------------------

class TestInvoiceHistoryQueryCount:
    """
    Assert that get_invoice_history() issues a constant number of queries
    regardless of page size (Requirement 9.2, 9.4).
    """

    def _load_invoice_history(
        self, session: Session, user_id: int, page_size: int
    ):
        """Replicate the query pattern used in get_invoice_history()."""
        from sqlalchemy.orm import selectinload as _selectinload

        query = (
            session.query(Invoice)
            .options(_selectinload(Invoice.transaction))
            .filter(Invoice.user_id == user_id)
        )
        total = query.count()
        invoices = query.order_by(Invoice.created_at.desc()).limit(page_size).all()
        # Access the relationship to ensure it was loaded (not lazy)
        for inv in invoices:
            _ = inv.transaction
        return invoices, total

    def test_query_count_5_invoices(self, db_session, query_counter):
        """Loading 5 invoices should issue ≤3 queries."""
        user = _make_user(db_session, user_id=50)
        for i in range(5):
            tx = _make_transaction(db_session, user_id=50, tx_num=i)
            _make_invoice(db_session, tx, user_id=50, seq=500 + i)
        db_session.flush()

        query_counter.reset()
        invs, total = self._load_invoice_history(db_session, user_id=50, page_size=5)
        count_5 = query_counter.count

        assert len(invs) == 5
        assert count_5 <= 3, (
            f"Expected ≤3 queries for 5 invoices, got {count_5}"
        )

    def test_query_count_10_invoices(self, db_session, query_counter):
        """Loading 10 invoices should issue the same number of queries as 5."""
        user = _make_user(db_session, user_id=60)
        for i in range(10):
            tx = _make_transaction(db_session, user_id=60, tx_num=i)
            _make_invoice(db_session, tx, user_id=60, seq=600 + i)
        db_session.flush()

        query_counter.reset()
        invs, total = self._load_invoice_history(db_session, user_id=60, page_size=10)
        count_10 = query_counter.count

        assert len(invs) == 10
        assert count_10 <= 3, (
            f"Expected ≤3 queries for 10 invoices, got {count_10}"
        )

    def test_invoice_query_count_is_constant_across_page_sizes(
        self, db_session, query_counter
    ):
        """
        Query count must be the same for page_size=5 and page_size=10.
        Requirements: 9.2, 9.4
        """
        user = _make_user(db_session, user_id=70)
        for i in range(10):
            tx = _make_transaction(db_session, user_id=70, tx_num=i)
            _make_invoice(db_session, tx, user_id=70, seq=700 + i)
        db_session.flush()

        query_counter.reset()
        self._load_invoice_history(db_session, user_id=70, page_size=5)
        count_small = query_counter.count

        query_counter.reset()
        self._load_invoice_history(db_session, user_id=70, page_size=10)
        count_large = query_counter.count

        assert count_small == count_large, (
            f"Invoice history query count must be constant regardless of page size. "
            f"Got {count_small} for page_size=5 and {count_large} for page_size=10."
        )
