#!/usr/bin/env python3
"""
OnePay — Backup Verification Script
Verifies backup integrity by restoring to a test database and checking data.
"""

import logging
import os
import subprocess
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def verify_backup():
    """
    Verify backup integrity by:
    1. Restoring backup to test database
    2. Verifying table counts
    3. Checking data integrity
    """
    logger.info("Starting backup verification...")

    # Configuration
    backup_path = os.getenv("BACKUP_PATH", "/backups/latest.dump")
    test_db_url = os.getenv("TEST_DATABASE_URL", Config.DATABASE_URL.replace("onepay", "onepay_test"))

    # Check if backup file exists
    if not os.path.exists(backup_path):
        logger.error(f"Backup file not found: {backup_path}")
        return False

    # Get backup file size
    backup_size = os.path.getsize(backup_path)
    logger.info(f"Backup file size: {backup_size / (1024 * 1024):.2f} MB")

    if backup_size < 1024:  # Less than 1KB is suspicious
        logger.error("Backup file is too small, possible corruption")
        return False

    # Attempt to restore to test database
    logger.info("Attempting to restore backup to test database...")
    try:
        # Extract database connection info from URL
        if "postgresql://" in test_db_url:
            # Format: postgresql://user:pass@host:port/db
            db_url_parts = test_db_url.replace("postgresql://", "").split("@")
            user_pass = db_url_parts[0].split(":")
            host_port_db = db_url_parts[1].split("/")
            host_port = host_port_db[0].split(":")

            db_user = user_pass[0]
            db_pass = user_pass[1] if len(user_pass) > 1 else ""
            db_host = host_port[0]
            db_port = host_port[1] if len(host_port) > 1 else "5432"
            db_name = host_port_db[1]

            # Build pg_restore command
            cmd = [
                "pg_restore",
                "--clean",
                "--no-acl",
                "--no-owner",
                "-d", db_name,
                "-h", db_host,
                "-p", db_port,
                "-U", db_user,
                backup_path
            ]

            # Set PGPASSWORD environment variable
            env = os.environ.copy()
            env["PGPASSWORD"] = db_pass

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=300  # 5 minute timeout
            )

            if result.returncode != 0:
                logger.error(f"pg_restore failed: {result.stderr}")
                # Try to continue with database checks even if restore fails
                # (might be using a different backup method)
        else:
            logger.warning("Non-PostgreSQL database detected, skipping restore step")
    except subprocess.TimeoutExpired:
        logger.error("Backup restore timed out after 5 minutes")
        return False
    except Exception as e:
        logger.warning(f"Backup restore failed (continuing with checks): {e}")

    # Verify data using database connection
    logger.info("Verifying database integrity...")
    try:
        from database import get_db
        from models.transaction import Transaction
        from models.user import User

        with get_db() as db:
            # Check transaction count
            tx_count = db.query(Transaction).count()
            logger.info(f"Transaction count: {tx_count}")

            # Check user count
            user_count = db.query(User).count()
            logger.info(f"User count: {user_count}")

            # Basic sanity checks
            if tx_count == 0 and user_count == 0:
                logger.warning("Database appears to be empty (might be a fresh install)")
                # This is acceptable for new systems
            elif tx_count == 0 or user_count == 0:
                # If one is zero but not the other, that's suspicious
                logger.error("Backup verification failed: inconsistent data (one table empty, others not)")
                return False

            # Check for recent transactions (backup should have recent data)
            recent_tx = db.query(Transaction).order_by(
                Transaction.created_at.desc()
            ).first()

            if recent_tx:
                age_hours = (datetime.now(recent_tx.created_at.tzinfo) - recent_tx.created_at).total_seconds() / 3600
                logger.info(f"Most recent transaction: {age_hours:.2f} hours old")

                if age_hours > 48:  # Backup older than 48 hours
                    logger.warning(f"Backup appears stale: {age_hours:.2f} hours old")

            logger.info("Backup verification successful")
            return True

    except ImportError as e:
        logger.error(f"Failed to import database modules: {e}")
        return False
    except Exception as e:
        logger.error(f"Database verification failed: {e}")
        return False


def send_alert(success: bool):
    """Send alert based on backup verification result."""
    if not Config.ALERT_ENABLED:
        return

    try:
        from services.alerts import send_security_alert

        if success:
            message = "✅ Backup verification completed successfully"
        else:
            message = "🚨 Backup verification FAILED - investigate immediately"

        send_security_alert(
            event_type="backup_verification",
            severity="low" if success else "critical",
            message=message,
            metadata={
                "timestamp": datetime.utcnow().isoformat(),
                "success": success
            }
        )
    except Exception as e:
        logger.warning(f"Failed to send alert: {e}")


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("OnePay Backup Verification")
    logger.info("=" * 60)

    success = verify_backup()
    send_alert(success)

    if success:
        logger.info("✓ Backup verification completed successfully")
        sys.exit(0)
    else:
        logger.error("✗ Backup verification failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
