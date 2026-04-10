"""
OnePay — Alert integration for security monitoring.

Supports sending alerts to Slack, PagerDuty, and email for security events.
"""

import logging
from typing import Optional

import requests

from config import Config

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages security alert delivery to multiple channels."""

    def __init__(self):
        self.slack_webhook = Config.SLACK_WEBHOOK_URL
        self.pagerduty_key = Config.PAGERDUTY_API_KEY
        self.pagerduty_service_id = Config.PAGERDUTY_SERVICE_ID
        self.sendgrid_api_key = Config.SENDGRID_API_KEY
        self.security_alert_email = Config.SECURITY_ALERT_EMAIL
        self.enabled = Config.ALERT_ENABLED

    def send_slack_alert(self, message: str, severity: str = "INFO") -> bool:
        """Send alert to Slack webhook."""
        if not self.enabled or not self.slack_webhook:
            logger.debug("Slack alerts disabled or webhook not configured")
            return False

        try:
            from slack_sdk import WebhookClient

            client = WebhookClient(self.slack_webhook)
            emoji_map = {
                "CRITICAL": ":rotating_light:",
                "HIGH": ":warning:",
                "MEDIUM": ":information_source:",
                "INFO": ":bell:",
            }
            emoji = emoji_map.get(severity, ":bell:")
            client.send(text=f"{emoji} [{severity}] {message}")
            logger.info("Slack alert sent: %s", message[:100])
            return True
        except Exception as e:
            logger.error("Failed to send Slack alert: %s", e)
            return False

    def send_pagerduty_alert(self, event: str, severity: str, detail: Optional[dict] = None) -> bool:
        """Trigger PagerDuty alert for critical security events."""
        if not self.enabled or not self.pagerduty_key:
            logger.debug("PagerDuty alerts disabled or API key not configured")
            return False

        if severity not in ["CRITICAL", "HIGH"]:
            logger.debug("PagerDuty only for CRITICAL/HIGH severity events")
            return False

        try:
            payload = {
                "routing_key": self.pagerduty_key,
                "event_action": "trigger",
                "payload": {
                    "summary": f"OnePay Security Alert: {event}",
                    "severity": severity.lower(),
                    "source": "onepay",
                    "custom_details": detail or {},
                },
                "dedup_key": f"onepay-{event}",
            }

            response = requests.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            logger.info("PagerDuty alert sent: %s", event)
            return True
        except Exception as e:
            logger.error("Failed to send PagerDuty alert: %s", e)
            return False

    def send_email_alert(self, subject: str, body: str) -> bool:
        """Send email alert via SendGrid."""
        if not self.enabled or not self.sendgrid_api_key:
            logger.debug("Email alerts disabled or SendGrid API key not configured")
            return False

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail

            message = Mail(
                from_email="alerts@onepay.com",
                to_emails=self.security_alert_email,
                subject=f"[OnePay Security] {subject}",
                html_content=body,
            )

            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)
            logger.info("Email alert sent: %s (status: %d)", subject, response.status_code)
            return response.status_code in [200, 202]
        except Exception as e:
            logger.error("Failed to send email alert: %s", e)
            return False

    def send_alert(self, message: str, severity: str = "INFO", event: Optional[str] = None) -> None:
        """Send alert based on severity to appropriate channels."""
        if not self.enabled:
            logger.debug("Alerts disabled")
            return

        # Always log the alert
        logger.warning("Security alert [%s]: %s", severity, message)

        # CRITICAL: Send to all channels
        if severity == "CRITICAL":
            self.send_slack_alert(message, severity)
            self.send_pagerduty_alert(event or message, severity)
            self.send_email_alert(f"CRITICAL: {message}", f"<p>{message}</p>")

        # HIGH: Send to Slack and email
        elif severity == "HIGH":
            self.send_slack_alert(message, severity)
            self.send_email_alert(f"Security Alert: {message}", f"<p>{message}</p>")

        # MEDIUM/INFO: Send to Slack only
        else:
            self.send_slack_alert(message, severity)


# Global alert manager instance
alert_manager = AlertManager()
