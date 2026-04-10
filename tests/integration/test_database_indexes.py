"""
OnePay — Database Index Integration Tests

Tests for database index migrations (Requirement 8):
- Verify migration files exist and define the correct indexes
- Verify index names match the spec
- Test that upgrade/downgrade functions are callable
- Use SQLite in-memory for actual DB tests

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6
"""

import importlib
import os
import sys

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, inspect, text

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MIGRATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "alembic", "versions",
)

TRANSACTION_MIGRATION = "20260408000001_add_transaction_indexes"
AUDIT_LOG_MIGRATION = "20260408000002_add_audit_log_indexes"

EXPECTED_TRANSACTION_INDEXES = [
    "ix_transactions_created_at",
    "ix_transactions_status",
    "ix_transactions_user_created",
    "ix_transactions_user_status",
]

EXPECTED_AUDIT_LOG_INDEXES = [
    "ix_audit_logs_created_at",
    "ix_audit_logs_user_id",
]


def _load_migration(module_name: str):
    """Dynamically load an Alembic migration module by filename stem."""
    path = os.path.join(MIGRATION_DIR, f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def transaction_migration():
    return _load_migration(TRANSACTION_MIGRATION)


@pytest.fixture(scope="module")
def audit_log_migration():
    return _load_migration(AUDIT_LOG_MIGRATION)


@pytest.fixture()
def sqlite_engine_with_tables():
    """
    In-memory SQLite engine with minimal transactions and audit_logs tables
    so we can run the Alembic upgrade/downgrade operations against a real DB.
    """
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                status TEXT,
                created_at DATETIME
            )
        """))
        conn.execute(text("""
            CREATE TABLE audit_logs (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                created_at DATETIME
            )
        """))
    return engine


# ---------------------------------------------------------------------------
# 1. Migration file existence
# ---------------------------------------------------------------------------

class TestMigrationFilesExist:
    """Verify the migration files are present on disk."""

    def test_transaction_migration_file_exists(self) -> None:
        path = os.path.join(MIGRATION_DIR, f"{TRANSACTION_MIGRATION}.py")
        assert os.path.isfile(path), f"Migration file not found: {path}"

    def test_audit_log_migration_file_exists(self) -> None:
        path = os.path.join(MIGRATION_DIR, f"{AUDIT_LOG_MIGRATION}.py")
        assert os.path.isfile(path), f"Migration file not found: {path}"


# ---------------------------------------------------------------------------
# 2. Revision metadata
# ---------------------------------------------------------------------------

class TestMigrationMetadata:
    """Verify revision IDs and dependency chain."""

    def test_transaction_migration_revision_id(self, transaction_migration) -> None:
        assert transaction_migration.revision == "20260408000001"

    def test_audit_log_migration_revision_id(self, audit_log_migration) -> None:
        assert audit_log_migration.revision == "20260408000002"

    def test_audit_log_depends_on_transaction_migration(self, audit_log_migration) -> None:
        """Audit log migration must follow the transaction migration."""
        assert audit_log_migration.down_revision == "20260408000001"


# ---------------------------------------------------------------------------
# 3. Index names defined in upgrade()
# ---------------------------------------------------------------------------

class TestTransactionIndexNames:
    """
    Verify the transaction migration source defines all required index names.
    Requirements: 8.1, 8.2, 8.3, 8.4
    """

    def _source(self, transaction_migration) -> str:
        import inspect
        return inspect.getsource(transaction_migration.upgrade)

    def test_index_created_at_defined(self, transaction_migration) -> None:
        """Requirement 8.1 — index on transactions.created_at"""
        assert "ix_transactions_created_at" in self._source(transaction_migration)

    def test_index_status_defined(self, transaction_migration) -> None:
        """Requirement 8.2 — index on transactions.status"""
        assert "ix_transactions_status" in self._source(transaction_migration)

    def test_composite_index_user_created_defined(self, transaction_migration) -> None:
        """Requirement 8.3 — composite index on transactions(user_id, created_at)"""
        assert "ix_transactions_user_created" in self._source(transaction_migration)

    def test_composite_index_user_status_defined(self, transaction_migration) -> None:
        """Requirement 8.4 — composite index on transactions(user_id, status)"""
        assert "ix_transactions_user_status" in self._source(transaction_migration)

    def test_all_transaction_indexes_present(self, transaction_migration) -> None:
        """All four transaction indexes must be defined in upgrade()."""
        import inspect
        src = inspect.getsource(transaction_migration.upgrade)
        for name in EXPECTED_TRANSACTION_INDEXES:
            assert name in src, f"Missing index: {name}"


class TestAuditLogIndexNames:
    """
    Verify the audit log migration source defines all required index names.
    Requirements: 8.5, 8.6
    """

    def _source(self, audit_log_migration) -> str:
        import inspect
        return inspect.getsource(audit_log_migration.upgrade)

    def test_index_created_at_defined(self, audit_log_migration) -> None:
        """Requirement 8.5 — index on audit_logs.created_at"""
        assert "ix_audit_logs_created_at" in self._source(audit_log_migration)

    def test_index_user_id_defined(self, audit_log_migration) -> None:
        """Requirement 8.6 — index on audit_logs.user_id"""
        assert "ix_audit_logs_user_id" in self._source(audit_log_migration)

    def test_all_audit_log_indexes_present(self, audit_log_migration) -> None:
        """Both audit log indexes must be defined in upgrade()."""
        import inspect
        src = inspect.getsource(audit_log_migration.upgrade)
        for name in EXPECTED_AUDIT_LOG_INDEXES:
            assert name in src, f"Missing index: {name}"


# ---------------------------------------------------------------------------
# 4. Downgrade removes the same indexes
# ---------------------------------------------------------------------------

class TestDowngradeRemovesIndexes:
    """Verify downgrade() references the same index names for removal."""

    def _downgrade_source(self, migration) -> str:
        import inspect
        return inspect.getsource(migration.downgrade)

    def test_transaction_downgrade_removes_all_indexes(self, transaction_migration) -> None:
        src = self._downgrade_source(transaction_migration)
        for name in EXPECTED_TRANSACTION_INDEXES:
            assert name in src, f"downgrade() missing drop for: {name}"

    def test_audit_log_downgrade_removes_all_indexes(self, audit_log_migration) -> None:
        src = self._downgrade_source(audit_log_migration)
        for name in EXPECTED_AUDIT_LOG_INDEXES:
            assert name in src, f"downgrade() missing drop for: {name}"


# ---------------------------------------------------------------------------
# 5. upgrade() / downgrade() are callable
# ---------------------------------------------------------------------------

class TestUpgradeDowngradeCallable:
    """Verify the migration functions exist and are callable."""

    def test_transaction_upgrade_callable(self, transaction_migration) -> None:
        assert callable(transaction_migration.upgrade)

    def test_transaction_downgrade_callable(self, transaction_migration) -> None:
        assert callable(transaction_migration.downgrade)

    def test_audit_log_upgrade_callable(self, audit_log_migration) -> None:
        assert callable(audit_log_migration.upgrade)

    def test_audit_log_downgrade_callable(self, audit_log_migration) -> None:
        assert callable(audit_log_migration.downgrade)


# ---------------------------------------------------------------------------
# 6. Actual index creation on SQLite in-memory DB
# ---------------------------------------------------------------------------

class TestIndexCreationOnSQLite:
    """
    Run upgrade() against a real SQLite in-memory database and verify
    the indexes are actually created.  Uses Alembic's MigrationContext
    so op.* calls work without a live PostgreSQL instance.
    """

    @staticmethod
    def _run_migration_fn(engine, fn):
        """Execute a migration function (upgrade/downgrade) using a real connection."""
        from unittest.mock import patch

        import alembic.op as alembic_op_module
        from alembic.operations import Operations
        from alembic.runtime.migration import MigrationContext

        with engine.begin() as conn:
            ctx = MigrationContext.configure(conn)
            op_obj = Operations(ctx)
            # Patch every op.* function used by the migrations onto the module
            with patch.object(alembic_op_module, "create_index", op_obj.create_index), \
                 patch.object(alembic_op_module, "drop_index", op_obj.drop_index):
                fn()

    def _get_index_names(self, engine, table_name: str):
        insp = inspect(engine)
        return {idx["name"] for idx in insp.get_indexes(table_name)}

    def test_transaction_indexes_created_after_upgrade(
        self, sqlite_engine_with_tables, transaction_migration
    ) -> None:
        self._run_migration_fn(sqlite_engine_with_tables, transaction_migration.upgrade)
        index_names = self._get_index_names(sqlite_engine_with_tables, "transactions")
        for name in EXPECTED_TRANSACTION_INDEXES:
            assert name in index_names, f"Index not created: {name}"

    def test_transaction_indexes_removed_after_downgrade(
        self, sqlite_engine_with_tables, transaction_migration
    ) -> None:
        # Ensure indexes exist first
        try:
            self._run_migration_fn(sqlite_engine_with_tables, transaction_migration.upgrade)
        except Exception:
            pass  # already applied
        self._run_migration_fn(sqlite_engine_with_tables, transaction_migration.downgrade)
        index_names = self._get_index_names(sqlite_engine_with_tables, "transactions")
        for name in EXPECTED_TRANSACTION_INDEXES:
            assert name not in index_names, f"Index not removed by downgrade: {name}"

    def test_audit_log_indexes_created_after_upgrade(
        self, sqlite_engine_with_tables, audit_log_migration
    ) -> None:
        self._run_migration_fn(sqlite_engine_with_tables, audit_log_migration.upgrade)
        index_names = self._get_index_names(sqlite_engine_with_tables, "audit_logs")
        for name in EXPECTED_AUDIT_LOG_INDEXES:
            assert name in index_names, f"Index not created: {name}"

    def test_audit_log_indexes_removed_after_downgrade(
        self, sqlite_engine_with_tables, audit_log_migration
    ) -> None:
        try:
            self._run_migration_fn(sqlite_engine_with_tables, audit_log_migration.upgrade)
        except Exception:
            pass
        self._run_migration_fn(sqlite_engine_with_tables, audit_log_migration.downgrade)
        index_names = self._get_index_names(sqlite_engine_with_tables, "audit_logs")
        for name in EXPECTED_AUDIT_LOG_INDEXES:
            assert name not in index_names, f"Index not removed by downgrade: {name}"
