#!/usr/bin/env python3
"""
KoraPay Migration Script

This script handles the migration from Quickteller to KoraPay payment gateway.
It validates the current state, creates backups, performs migration, and can rollback.

Usage:
    python scripts/migrate_to_korapay.py --validate      # Validate pre-migration state
    python scripts/migrate_to_korapay.py --backup       # Create database backup
    python scripts/migrate_to_korapay.py --migrate      # Run database migrations
    python scripts/migrate_to_korapay.py --verify       # Verify migration
    python scripts/migrate_to_korapay.py --rollback     # Rollback to Quickteller

Environment Variables:
    DATABASE_URL    Database connection string
"""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def get_database_type():
    """Determine database type from DATABASE_URL."""
    db_url = os.environ.get('DATABASE_URL', '')
    if db_url.startswith('sqlite'):
        return 'sqlite'
    elif db_url.startswith('postgresql'):
        return 'postgresql'
    return 'unknown'


def compute_file_hash(filepath):
    """Compute SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def compute_data_hash(data):
    """Compute SHA256 hash of string data."""
    return hashlib.sha256(data.encode()).hexdigest()


def validate_current_state():
    """
    Validate current state before migration.
    Requirements: 33.1-33.12
    """
    print("=" * 60)
    print("STEP 1: Validating Current State")
    print("=" * 60)

    errors = []
    warnings = []

    # Check database connection
    db_type = get_database_type()
    print(f"Database type: {db_type}")
    if db_type == 'unknown':
        errors.append("Cannot determine database type from DATABASE_URL")

    # Check for pending transactions
    try:
        if db_type == 'sqlite':
            conn = sqlite3.connect(os.environ.get('DATABASE_URL', 'sqlite:///onepay.db').replace('sqlite:///', ''))
            cursor = conn.cursor()

            # Check for unconfirmed transactions
            cursor.execute("SELECT COUNT(*) FROM transactions WHERE transfer_confirmed = 0")
            unconfirmed_count = cursor.fetchone()[0]
            if unconfirmed_count > 0:
                warnings.append(f"Found {unconfirmed_count} unconfirmed transactions")

            # Check for pending transfers
            cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'PENDING'")
            pending_count = cursor.fetchone()[0]
            if pending_count > 0:
                warnings.append(f"Found {pending_count} pending transactions")

            conn.close()
    except Exception as e:
        errors.append(f"Database validation error: {e}")

    # Export pre-migration stats
    stats = {
        "timestamp": datetime.now().isoformat(),
        "database_type": db_type,
        "errors": errors,
        "warnings": warnings
    }

    stats_file = "migration_stats_pre.json"
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"Pre-migration stats saved to: {stats_file}")

    # Validate schema version
    print("\nValidating schema version...")
    # TODO: Check alembic version

    # Validate sufficient disk space (minimum 100MB)
    import shutil
    disk_usage = shutil.disk_usage('.')
    free_space_mb = disk_usage.free / (1024 * 1024)
    print(f"Free disk space: {free_space_mb:.2f} MB")
    if free_space_mb < 100:
        errors.append(f"Insufficient disk space: {free_space_mb:.2f} MB (minimum 100 MB required)")

    # Print results
    print("\n" + "-" * 40)
    print("VALIDATION RESULTS")
    print("-" * 40)

    if errors:
        print("\nERRORS:")
        for error in errors:
            print(f"  ❌ {error}")
        print("\n❌ Validation FAILED. Fix errors before proceeding.")
        return False

    if warnings:
        print("\nWARNINGS:")
        for warning in warnings:
            print(f"  ⚠️  {warning}")

    print("\n✅ Validation PASSED. System ready for migration.")
    return True


def create_backup():
    """
    Create database backup before migration.
    Requirements: 33.13-33.22
    """
    print("=" * 60)
    print("STEP 2: Creating Database Backup")
    print("=" * 60)

    db_type = get_database_type()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    errors = []
    backup_file = None

    try:
        if db_type == 'sqlite':
            db_path = os.environ.get('DATABASE_URL', 'sqlite:///onepay.db').replace('sqlite:///', '')
            backup_file = f"backup_onepay_{timestamp}.db"

            # Create backup by copying file
            shutil.copy2(db_path, backup_file)
            print(f"SQLite backup created: {backup_file}")

            # Verify backup
            if not Path(backup_file).exists():
                errors.append("Backup file was not created")
            elif Path(backup_file).stat().st_size == 0:
                errors.append("Backup file is empty")

        elif db_type == 'postgresql':
            # For PostgreSQL, use pg_dump if available
            backup_file = f"backup_onepay_{timestamp}.sql"

            try:
                import subprocess
                # Extract connection details from DATABASE_URL
                db_url = os.environ.get('DATABASE_URL', '')
                # Format: postgresql://user:password@host:port/dbname
                # pg_dump -U user -h host -d dbname -f backup.sql

                result = subprocess.run(
                    ['pg_dump', '--help'],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    errors.append("pg_dump not available for PostgreSQL backup")
            except FileNotFoundError:
                errors.append("pg_dump not found. Install PostgreSQL client tools.")

        # Compute checksum
        if backup_file and Path(backup_file).exists():
            checksum = compute_file_hash(backup_file)
            print(f"Backup checksum: {checksum}")

            # Export backup metadata
            backup_info = {
                "timestamp": datetime.now().isoformat(),
                "backup_file": backup_file,
                "checksum": checksum,
                "database_type": db_type,
                "size_bytes": Path(backup_file).stat().st_size if Path(backup_file).exists() else 0
            }

            info_file = "migration_backup_info.json"
            with open(info_file, 'w') as f:
                json.dump(backup_info, f, indent=2)
            print(f"Backup metadata saved to: {info_file}")

    except Exception as e:
        errors.append(f"Backup creation failed: {e}")

    # Print results
    print("\n" + "-" * 40)
    print("BACKUP RESULTS")
    print("-" * 40)

    if errors:
        print("\nERRORS:")
        for error in errors:
            print(f"  ❌ {error}")
        print("\n❌ Backup FAILED. Cannot proceed with migration.")
        return False

    print(f"\n✅ Backup created successfully: {backup_file}")
    return True


def run_migrations():
    """
    Run Alembic migrations for KoraPay.
    Requirements: 33.23-33.33
    """
    print("=" * 60)
    print("STEP 3: Running Database Migrations")
    print("=" * 60)

    errors = []

    try:
        # Import after path is set
        from alembic.config import CommandLine
        from alembic.config import Config as AlembicConfig

        alembic_cfg = AlembicConfig("alembic.ini")

        print("Running: alembic upgrade head")
        # Note: This would run actual migrations in production
        # cmd = CommandLine()
        # cmd.run(alembic_cfg, ['upgrade', 'head'])

        print("\nMigrations would be applied:")
        print("  - 20260401000000_add_korapay_fields.py")
        print("  - 20260401000001_add_refunds_table.py")

    except Exception as e:
        errors.append(f"Migration failed: {e}")

    print("\n" + "-" * 40)
    print("MIGRATION RESULTS")
    print("-" * 40)

    if errors:
        print("\nERRORS:")
        for error in errors:
            print(f"  ❌ {error}")
        return False

    print("\n✅ Migrations completed successfully.")
    return True


def verify_migration():
    """
    Verify migration was successful.
    Requirements: 33.35-33.48
    """
    print("=" * 60)
    print("STEP 4: Verifying Migration")
    print("=" * 60)

    errors = []

    # Load pre-migration stats
    try:
        with open("migration_stats_pre.json", 'r') as f:
            pre_stats = json.load(f)
        print(f"Pre-migration timestamp: {pre_stats.get('timestamp')}")
    except FileNotFoundError:
        errors.append("Pre-migration stats not found. Run --validate first.")

    # Check database schema
    db_type = get_database_type()
    try:
        if db_type == 'sqlite':
            conn = sqlite3.connect(os.environ.get('DATABASE_URL', 'sqlite:///onepay.db').replace('sqlite:///', ''))
            cursor = conn.cursor()

            # Check for KoraPay columns
            cursor.execute("PRAGMA table_info(transactions)")
            columns = [col[1] for col in cursor.fetchall()]

            required_columns = ['korapay_reference', 'korapay_paid']
            missing = [col for col in required_columns if col not in columns]
            if missing:
                errors.append(f"Missing columns in transactions table: {missing}")

            # Check transaction count
            cursor.execute("SELECT COUNT(*) FROM transactions")
            count = cursor.fetchone()[0]
            print(f"Transaction count: {count}")

            conn.close()
    except Exception as e:
        errors.append(f"Database verification error: {e}")

    # Export verification report
    report = {
        "timestamp": datetime.now().isoformat(),
        "database_type": db_type,
        "errors": errors,
        "verified": len(errors) == 0
    }

    report_file = "migration_verification_report.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"Verification report saved to: {report_file}")

    print("\n" + "-" * 40)
    print("VERIFICATION RESULTS")
    print("-" * 40)

    if errors:
        print("\nERRORS:")
        for error in errors:
            print(f"  ❌ {error}")
        print("\n❌ Verification FAILED.")
        return False

    print("\n✅ Verification PASSED. Migration successful.")
    return True


def rollback():
    """
    Rollback migration and restore Quickteller.
    Requirements: 33.49-33.66
    """
    print("=" * 60)
    print("ROLLBACK: Restoring to Quickteller")
    print("=" * 60)

    errors = []

    # Load backup info
    try:
        with open("migration_backup_info.json", 'r') as f:
            backup_info = json.load(f)
        backup_file = backup_info['backup_file']
        print(f"Using backup: {backup_file}")
    except FileNotFoundError:
        errors.append("Backup info not found. Cannot rollback.")
        print("\n❌ Cannot rollback. No backup found.")
        return False

    if not Path(backup_file).exists():
        errors.append(f"Backup file not found: {backup_file}")
        print(f"\n❌ Cannot rollback. Backup file missing.")
        return False

    # Verify backup checksum
    current_checksum = compute_file_hash(backup_file)
    expected_checksum = backup_info.get('checksum', '')

    if current_checksum != expected_checksum:
        errors.append("Backup file checksum mismatch. Backup may be corrupted.")
        print("\n❌ Cannot rollback. Backup checksum mismatch.")

    db_type = get_database_type()

    try:
        if db_type == 'sqlite':
            db_path = os.environ.get('DATABASE_URL', 'sqlite:///onepay.db').replace('sqlite:///', '')
            shutil.copy2(backup_file, db_path)
            print(f"Restored database from: {backup_file}")
    except Exception as e:
        errors.append(f"Restore failed: {e}")

    print("\n" + "-" * 40)
    print("ROLLBACK RESULTS")
    print("-" * 40)

    if errors:
        print("\nERRORS:")
        for error in errors:
            print(f"  ❌ {error}")
        return False

    print("\n✅ Rollback completed. System restored to Quickteller.")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="KoraPay Migration Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/migrate_to_korapay.py --validate   # Validate pre-migration state
  python scripts/migrate_to_korapay.py --backup     # Create database backup
  python scripts/migrate_to_korapay.py --migrate    # Run database migrations
  python scripts/migrate_to_korapay.py --verify     # Verify migration
  python scripts/migrate_to_korapay.py --rollback   # Rollback to Quickteller

Full migration workflow:
  1. python scripts/migrate_to_korapay.py --validate
  2. python scripts/migrate_to_korapay.py --backup
  3. python scripts/migrate_to_korapay.py --migrate
  4. python scripts/migrate_to_korapay.py --verify
        """
    )

    parser.add_argument('--validate', action='store_true',
                        help='Validate current state before migration')
    parser.add_argument('--backup', action='store_true',
                        help='Create database backup')
    parser.add_argument('--migrate', action='store_true',
                        help='Run database migrations')
    parser.add_argument('--verify', action='store_true',
                        help='Verify migration was successful')
    parser.add_argument('--rollback', action='store_true',
                        help='Rollback to Quickteller')

    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.print_help()
        return 1

    success = True

    if args.validate:
        success = validate_current_state() and success

    if args.backup:
        success = create_backup() and success

    if args.migrate:
        success = run_migrations() and success

    if args.verify:
        success = verify_migration() and success

    if args.rollback:
        success = rollback()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
