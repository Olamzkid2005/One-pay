"""
OnePay — Background thread management.
Extracted from app.py to reduce create_app() complexity.
"""
import logging
import threading
import time

logger = logging.getLogger(__name__)


def start_background_threads(shutdown_event: threading.Event, app) -> None:
    """Start all background daemon threads."""
    _start_webhook_retry_thread(shutdown_event, app)
    _start_security_monitor_thread(shutdown_event, app)

    try:
        from app_cleanup import start_cleanup_threads
        start_cleanup_threads()
    except ImportError:
        pass


def _start_webhook_retry_thread(shutdown_event: threading.Event, app) -> None:
    def _loop():
        time.sleep(5)
        while not shutdown_event.is_set():
            try:
                from database import get_db
                from services.webhook import retry_failed_webhooks
                with app.app_context():
                    with get_db() as db:
                        retry_failed_webhooks(db)
            except Exception as e:
                logger.error("Webhook retry loop error: %s", e)
            if not shutdown_event.is_set():
                shutdown_event.wait(60)

    t = threading.Thread(target=_loop, daemon=True, name="webhook-retry")
    t.start()
    logger.info("Webhook retry thread started")


def _start_security_monitor_thread(shutdown_event: threading.Event, app) -> None:
    def _loop():
        time.sleep(10)
        while not shutdown_event.is_set():
            try:
                from database import get_db
                from services.security_monitor import detect_suspicious_activity
                with app.app_context():
                    with get_db() as db:
                        alerts = detect_suspicious_activity(db)
                        if alerts:
                            logger.info("Security monitoring detected %d alerts", len(alerts))
            except Exception as e:
                logger.error("Security monitoring error: %s", e)
            if not shutdown_event.is_set():
                shutdown_event.wait(300)

    t = threading.Thread(target=_loop, daemon=True, name="security-monitor")
    t.start()
    logger.info("Security monitoring thread started")
