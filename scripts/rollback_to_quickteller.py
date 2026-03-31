#!/usr/bin/env python3
"""
Rollback to Quickteller Script

This script rolls back the KoraPay migration and restores Quickteller functionality.
It uses git to revert code and restores the database from backup.

Usage:
    python scripts/rollback_to_quickteller.py --check        # Check if rollback is needed
    python scripts/rollback_to_quickteller.py --restore-db   # Restore database from backup
    python scripts/rollback_to_quickteller.py --revert-code  # Revert code to tagged commit
    python scripts/rollback_to_quickteller.py --verify      # Verify rollback was successful

Requirements: 33.49-33.66
"""

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def compute_file_hash(filepath):
    """Compute SHA256 hash of a file."""
    import hashlib
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def check_rollback_eligibility():
    """
    Check if rollback is possible and document decision criteria.
    Requirements: 33.49, 33.50
    """
    print("=" * 60)
    print("ROLLBACK ELIGIBILITY CHECK")
    print("=" * 60)

    issues = []
    warnings = []

    # Check for backup file
    try:
        with open("migration_backup_info.json", 'r') as f:
            backup_info = json.load(f)
        print(f"✅ Backup found: {backup_info['backup_file']}")
        print(f"   Created: {backup_info['timestamp']}")
        print(f"   Checksum: {backup_info['checksum']}")
    except FileNotFoundError:
        issues.append("No backup file found. Cannot rollback without a backup.")

    # Check git status
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True
        )
        if result.stdout.strip():
            warnings.append("Git working directory is dirty. Commit or stash changes before rollback.")
    except FileNotFoundError:
        warnings.append("Git not found. Cannot revert code automatically.")

    # Check for rollback tag
    try:
        result = subprocess.run(
            ['git', 'tag', '-l', 'pre-korapay-migration'],
            capture_output=True,
            text=True
        )
        if 'pre-korapay-migration' not in result.stdout:
            warnings.append("Rollback tag 'pre-korapay-migration' not found.")
    except:
        warnings.append("Could not check for rollback tag.")

    # Print results
    print("\n" + "-" * 40)
    print("ROLLBACK ELIGIBILITY RESULTS")
    print("-" * 40)

    if issues:
        print("\nBLOCKING ISSUES:")
        for issue in issues:
            print(f"  ❌ {issue}")

    if warnings:
        print("\nWARNINGS:")
        for warning in warnings:
            print(f"  ⚠️  {warning}")

    if issues:
        print("\n❌ NOT ELIGIBLE FOR ROLLBACK")
        return False

    print("\n✅ ELIGIBLE FOR ROLLBACK")
    return True


def restore_backup():
    """
    Restore database from backup file.
    Requirements: 33.51, 33.52, 33.53
    """
    print("=" * 60)
    print("RESTORING DATABASE FROM BACKUP")
    print("=" * 60)

    errors = []

    # Load backup info
    try:
        with open("migration_backup_info.json", 'r') as f:
            backup_info = json.load(f)
        backup_file = backup_info['backup_file']
        expected_checksum = backup_info['checksum']
    except FileNotFoundError:
        print("❌ Backup info not found. Run --check first.")
        return False

    # Check backup file exists
    if not Path(backup_file).exists():
        print(f"❌ Backup file not found: {backup_file}")
        return False

    # Verify checksum
    current_checksum = compute_file_hash(backup_file)
    if current_checksum != expected_checksum:
        print("❌ Backup checksum mismatch!")
        print(f"   Expected: {expected_checksum}")
        print(f"   Current:  {current_checksum}")
        return False
    print(f"✅ Backup checksum verified")

    # Determine database type
    db_url = os.environ.get('DATABASE_URL', 'sqlite:///onepay.db')
    db_type = 'sqlite' if db_url.startswith('sqlite') else 'postgresql'

    try:
        if db_type == 'sqlite':
            db_path = db_url.replace('sqlite:///', '')
            shutil.copy2(backup_file, db_path)
            print(f"✅ Database restored from: {backup_file}")
            print(f"   Database path: {db_path}")
        else:
            print("⚠️  PostgreSQL restore requires manual intervention")
            print(f"   Backup file: {backup_file}")
            print("   Run: pg_restore -U user -d dbname < backup.sql")

    except Exception as e:
        errors.append(f"Restore failed: {e}")
        print(f"❌ {e}")
        return False

    print("\n✅ Database restored successfully")
    return True


def revert_code():
    """
    Revert code to pre-migration tagged commit.
    Requirements: 33.54, 33.55, 33.56, 33.57
    """
    print("=" * 60)
    print("REVERTING CODE TO PRE-KORAPAY MIGRATION")
    print("=" * 60)

    errors = []

    # Check for git
    try:
        subprocess.run(['git', '--version'], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("❌ Git not found. Cannot revert code automatically.")
        print("   Manual steps:")
        print("   1. git checkout pre-korapay-migration")
        print("   2. git checkout -b post-rollback")
        return False

    # Check for tag
    result = subprocess.run(
        ['git', 'tag', '-l', 'pre-korapay-migration'],
        capture_output=True,
        text=True
    )

    if 'pre-korapay-migration' not in result.stdout:
        print("❌ Tag 'pre-korapay-migration' not found.")
        print("   Create tag with: git tag pre-korapay-migration HEAD")
        return False

    print("Found tag: pre-korapay-migration")

    # Create rollback branch
    branch_name = f"rollback-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    print(f"\nCreating rollback branch: {branch_name}")

    try:
        # Check current commit
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True,
            text=True
        )
        current_commit = result.stdout.strip()
        print(f"Current commit: {current_commit}")

        # Switch to rollback branch with tagged code
        subprocess.run(['git', 'checkout', '-b', branch_name], check=True)
        subprocess.run(['git', 'checkout', 'pre-korapay-migration'], check=True)

        print(f"✅ Code reverted to: pre-korapay-migration")
        print(f"   New branch: {branch_name}")

    except subprocess.CalledProcessError as e:
        errors.append(f"Git checkout failed: {e}")
        print(f"❌ Git operation failed: {e}")
        return False

    print("\n✅ Code reverted successfully")
    print("\nNext steps:")
    print("  1. Review the reverted code")
    print("  2. Test Quickteller functionality")
    print("  3. Deploy rollback branch")
    return True


def verify_rollback():
    """
    Verify rollback was successful.
    Requirements: 33.58, 33.59, 33.60, 33.61, 33.62, 33.63, 33.64, 33.65, 33.66
    """
    print("=" * 60)
    print("VERIFYING ROLLBACK")
    print("=" * 60)

    errors = []
    warnings = []

    # Check git status
    try:
        result = subprocess.run(
            ['git', 'branch', '--show-current'],
            capture_output=True,
            text=True
        )
        current_branch = result.stdout.strip()
        print(f"Current branch: {current_branch}")
    except:
        warnings.append("Could not determine current branch")

    # Verify Quickteller service exists
    if Path('services/quickteller.py').exists():
        print("✅ Quickteller service found")
    else:
        errors.append("Quickteller service not found")

    # Verify KoraPay service doesn't exist or is disabled
    korapay_service = Path('services/korapay.py')
    if korapay_service.exists():
        warnings.append("KoraPay service still exists (may need manual removal)")
    else:
        print("✅ KoraPay service removed")

    # Check database schema
    db_url = os.environ.get('DATABASE_URL', 'sqlite:///onepay.db')
    db_type = 'sqlite' if db_url.startswith('sqlite') else 'postgresql'

    try:
        if db_type == 'sqlite':
            db_path = db_url.replace('sqlite:///', '')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check for Quickteller-related columns
            cursor.execute("PRAGMA table_info(transactions)")
            columns = [col[1] for col in cursor.fetchall()]

            if 'quickteller_ref' in columns or 'quickteller_reference' in columns:
                print("✅ Quickteller columns found in transactions")
            else:
                warnings.append("Quickteller columns not found (may have been removed)")

            # Check for KoraPay columns (shouldn't exist after rollback)
            if 'korapay_reference' in columns:
                warnings.append("KoraPay columns still present in transactions")
            else:
                print("✅ KoraPay columns removed")

            conn.close()
    except Exception as e:
        errors.append(f"Database verification error: {e}")

    # Print results
    print("\n" + "-" * 40)
    print("VERIFICATION RESULTS")
    print("-" * 40)

    if errors:
        print("\nERRORS:")
        for error in errors:
            print(f"  ❌ {error}")

    if warnings:
        print("\nWARNINGS:")
        for warning in warnings:
            print(f"  ⚠️  {warning}")

    if errors:
        print("\n❌ VERIFICATION FAILED")
        return False

    print("\n✅ VERIFICATION PASSED - ROLLBACK COMPLETE")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Rollback to Quickteller Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/rollback_to_quickteller.py --check        # Check if rollback is possible
  python scripts/rollback_to_quickteller.py --restore-db   # Restore database from backup
  python scripts/rollback_to_quickteller.py --revert-code  # Revert code to tagged commit
  python scripts/rollback_to_quickteller.py --verify       # Verify rollback was successful

Full rollback workflow:
  1. python scripts/rollback_to_quickteller.py --check
  2. python scripts/rollback_to_quickteller.py --restore-db
  3. python scripts/rollback_to_quickteller.py --revert-code
  4. python scripts/rollback_to_quickteller.py --verify

Rollback Decision Criteria:
  - Migration caused critical data integrity issues
  - KoraPay API is consistently unavailable (>1 hour downtime)
  - Security vulnerability discovered in KoraPay integration
  - Business decision to revert to Quickteller

Rollback Time Estimate:
  - Database restore: 1-5 minutes (depending on size)
  - Code revert: < 1 minute
  - Verification: 5-10 minutes
  - Total estimated time: 10-15 minutes
        """
    )

    parser.add_argument('--check', action='store_true',
                        help='Check if rollback is eligible')
    parser.add_argument('--restore-db', action='store_true',
                        help='Restore database from backup')
    parser.add_argument('--revert-code', action='store_true',
                        help='Revert code to pre-korapay-migration tag')
    parser.add_argument('--verify', action='store_true',
                        help='Verify rollback was successful')

    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.print_help()
        return 1

    success = True

    if args.check:
        success = check_rollback_eligibility() and success

    if args.restore_db:
        success = restore_backup() and success

    if args.revert_code:
        success = revert_code() and success

    if args.verify:
        success = verify_rollback() and success

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
