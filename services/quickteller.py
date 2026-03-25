"""
OnePay — Quickteller / Interswitch API service
Handles OAuth token management and dynamic transfer virtual accounts.

All calls are synchronous (requests library) — no async needed in Flask.

MOCK MODE
---------
When Quickteller credentials are not set in .env, the service automatically
runs in mock mode. This lets you test the full payment flow without real API
keys. Mock mode:
  - Creates a fake virtual account (Wema Bank, realistic account number)
  - Returns "pending" for the first 3 polls, then "confirmed" on the 4th
  - Logs clearly so you always know mock is active

To switch to live mode: add real credentials to .env. No code changes needed.
"""
import base64
import logging
from datetime import datetime, timedelta, timezone

import requests

from config import Config

logger = logging.getLogger(__name__)


class QuicktellerError(Exception):
    """Raised when any Quickteller API call fails."""
    pass


# ── Mock state ────────────────────────────────────────────────────────────────
# Tracks how many times each tx_ref has been polled so the mock can
# return "pending" a few times before confirming — exactly like the real API.
_mock_poll_counts: dict = {}
MOCK_CONFIRM_AFTER = 3   # confirm on the 3rd poll


class QuicktellerService:
    """
    Wrapper around the Interswitch payment APIs.

    One instance is created at startup and reused across all requests.
    The OAuth token is cached and refreshed automatically when it expires.

    When credentials are missing, all methods delegate to _mock_* methods
    so the full UI flow can be tested without hitting any real API.
    """

    def __init__(self):
        self._access_token     = None
        self._token_expires_at = None

    # ── Mock detection ─────────────────────────────────────────────────────────

    def is_configured(self) -> bool:
        """True if OAuth credentials are set."""
        return bool(Config.QUICKTELLER_CLIENT_ID and Config.QUICKTELLER_CLIENT_SECRET)

    def is_transfer_configured(self) -> bool:
        """
        True if dynamic transfer is fully configured.
        In mock mode this returns True so the UI shows bank details.
        """
        if not self.is_configured():
            return True   # mock mode — always "configured"
        return bool(Config.MERCHANT_CODE and Config.PAYABLE_CODE)

    def _is_mock(self) -> bool:
        """Return True when running without real credentials."""
        return not self.is_configured()

    # ── OAuth ──────────────────────────────────────────────────────────────────

    def _get_auth_header(self) -> str:
        """Build the Basic Auth header for the OAuth token request."""
        credentials = f"{Config.QUICKTELLER_CLIENT_ID}:{Config.QUICKTELLER_CLIENT_SECRET}"
        encoded     = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def get_access_token(self) -> str:
        """
        Return a valid OAuth Bearer token, fetching a new one if needed.
        Token is cached for its lifetime minus a 5-minute safety margin.
        Not called in mock mode.
        """
        now = datetime.now(timezone.utc)

        # Return cached token if still valid
        if self._access_token and self._token_expires_at:
            if now < self._token_expires_at - timedelta(minutes=5):
                return self._access_token

        # Fetch a fresh token
        url = f"{Config.QUICKTELLER_BASE_URL}/passport/oauth/token"
        headers = {
            "Authorization": self._get_auth_header(),
            "Content-Type":  "application/x-www-form-urlencoded",
        }
        data = {"grant_type": "client_credentials"}

        try:
            response = requests.post(url, headers=headers, data=data, timeout=30)
            response.raise_for_status()
            token_data = response.json()
        except requests.exceptions.JSONDecodeError:
            raise QuicktellerError("Invalid JSON in OAuth token response")
        except requests.exceptions.RequestException as e:
            raise QuicktellerError(f"OAuth token request failed: {e}")

        self._access_token = token_data.get("access_token")
        if not self._access_token:
            raise QuicktellerError("No access_token in OAuth response")

        expires_in             = token_data.get("expires_in", 3600)
        self._token_expires_at = now + timedelta(seconds=expires_in)

        logger.info("Quickteller OAuth token refreshed")
        return self._access_token

    # ── Mock implementations ───────────────────────────────────────────────────

    def _mock_create_virtual_account(
        self,
        transaction_reference: str,
        amount_kobo: int,
        account_name: str,
    ) -> dict:
        """
        Return a realistic-looking fake virtual account.
        The account number is deterministic from the tx_ref so it's
        consistent if the merchant refreshes the page.
        """
        # Generate a stable 10-digit account number from the tx_ref
        seed        = sum(ord(c) for c in transaction_reference)
        acct_number = str(3000000000 + (seed % 999999999)).zfill(10)
        amount_ngn  = amount_kobo / 100

        logger.warning(
            "[MOCK] Virtual account created | ref=%s acct=%s amount=₦%.2f",
            transaction_reference, acct_number, amount_ngn,
        )

        return {
            "accountNumber":        acct_number,
            "bankName":             "Wema Bank (Demo)",
            "accountName":          account_name or "OnePay Demo Payment",
            "amount":               amount_kobo,
            "transactionReference": transaction_reference,
            "responseCode":         "Z0",     # Z0 = pending (account created)
            "validityPeriodMins":   30,
        }

    def _mock_confirm_transfer(self, transaction_reference: str) -> dict:
        """
        Simulate Interswitch polling behaviour:
          - First MOCK_CONFIRM_AFTER calls return Z0 (pending)
          - After that, return 00 (confirmed)

        This gives you time to see the "Waiting for transfer…" UI state
        before the success screen appears.
        """
        count = _mock_poll_counts.get(transaction_reference, 0) + 1
        _mock_poll_counts[transaction_reference] = count

        if count >= MOCK_CONFIRM_AFTER:
            logger.warning(
                "[MOCK] Transfer CONFIRMED | ref=%s (poll #%d)",
                transaction_reference, count,
            )
            # Clean up poll count for confirmed transactions
            _mock_poll_counts.pop(transaction_reference, None)
            return {
                "responseCode":         "00",
                "transactionReference": transaction_reference,
            }
        else:
            logger.warning(
                "[MOCK] Transfer pending | ref=%s (poll #%d/%d)",
                transaction_reference, count, MOCK_CONFIRM_AFTER,
            )
            return {
                "responseCode":         "Z0",
                "transactionReference": transaction_reference,
            }

    # ── Public API (live or mock) ──────────────────────────────────────────────

    def create_virtual_account(
        self,
        transaction_reference: str,
        amount_kobo: int,
        account_name: str = "OnePay Payment",
    ) -> dict:
        """
        Generate a one-time virtual bank account for a specific transaction.

        In mock mode: returns a fake Wema Bank account instantly.
        In live mode: calls the Interswitch API.

        Args:
            transaction_reference: Unique tx_ref string
            amount_kobo:           Amount in kobo. ₦1,000 = 100000 kobo
            account_name:          Label shown on the bank transfer screen

        Returns:
            Dict with: accountNumber, bankName, accountName,
                       amount, transactionReference, responseCode, validityPeriodMins
        """
        if self._is_mock():
            return self._mock_create_virtual_account(
                transaction_reference, amount_kobo, account_name
            )

        # ── Live API call ──────────────────────────────────────────────────────
        token = self.get_access_token()
        url   = f"{Config.VIRTUAL_ACCOUNT_BASE_URL}/paymentgateway/api/v1/virtualaccounts/transaction"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
            "accept":        "application/json",
        }
        body = {
            "merchantCode":         Config.MERCHANT_CODE,
            "payableCode":          Config.PAYABLE_CODE,
            "currencyCode":         "566",
            "amount":               str(amount_kobo),
            "accountName":          account_name,
            "transactionReference": transaction_reference,
        }

        try:
            response = requests.post(url, headers=headers, json=body, timeout=30)
            response.raise_for_status()
            result = response.json()
        except requests.exceptions.JSONDecodeError:
            raise QuicktellerError("Invalid JSON in create_virtual_account response")
        except requests.exceptions.RequestException as e:
            raise QuicktellerError(f"create_virtual_account request failed: {e}")

        logger.info(
            "Virtual account created | ref=%s bank=%s acct=%s",
            transaction_reference,
            result.get("bankName"),
            result.get("accountNumber"),
        )
        return result

    def confirm_transfer(self, transaction_reference: str, _retry: bool = False) -> dict:
        """
        Poll whether the customer has completed their bank transfer.

        responseCode meanings:
          "00"  → Transfer received — payment confirmed ✅
          "Z0"  → Still waiting ⏳
          other → Error / declined ❌

        In mock mode: returns Z0 a few times then 00.
        In live mode: calls the Interswitch API.
        """
        if self._is_mock():
            return self._mock_confirm_transfer(transaction_reference)

        # ── Live API call ──────────────────────────────────────────────────────
        token = self.get_access_token()
        url   = (
            f"{Config.VIRTUAL_ACCOUNT_BASE_URL}"
            f"/paymentgateway/api/v1/virtualaccounts/transaction"
            f"?merchantCode={Config.MERCHANT_CODE}"
            f"&transactionReference={transaction_reference}"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "accept":        "application/json",
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)

            # 401 → token expired — refresh once and retry
            if response.status_code == 401 and not _retry:
                logger.info("Token expired during confirm_transfer, refreshing...")
                self._access_token     = None
                self._token_expires_at = None
                return self.confirm_transfer(transaction_reference, _retry=True)

            response.raise_for_status()
            result = response.json()
        except requests.exceptions.JSONDecodeError:
            raise QuicktellerError("Invalid JSON in confirm_transfer response")
        except requests.exceptions.RequestException as e:
            raise QuicktellerError(f"confirm_transfer request failed: {e}")

        logger.info(
            "Transfer status | ref=%s code=%s",
            transaction_reference,
            result.get("responseCode"),
        )
        return result


# Single shared instance — reused across all requests
quickteller = QuicktellerService()
