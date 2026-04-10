"""
KoraPay API Integration Service

This module provides integration with KoraPay payment gateway for virtual account
creation and transfer confirmation. Supports mock mode for testing without credentials.

Mock mode activates when KORAPAY_SECRET_KEY is empty or < 32 characters.
"""

import logging
import secrets
import threading
import time
from collections import deque
from datetime import datetime, timezone

import requests
from requests.adapters import HTTPAdapter

from config import Config

logger = logging.getLogger(__name__)


def _mask_api_key(key: str) -> str:
    """Mask API key for safe logging: sk_t****_1234"""
    if not key or len(key) < 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"


def _normalize_create_response(kora_response: dict, amount_kobo: int) -> dict:
    """Convert KoraPay virtual account response to Quickteller-compatible format."""
    bank_account = kora_response["bank_account"]
    bank_name = bank_account["bank_name"].title()
    expiry_str = bank_account["expiry_date_in_utc"]
    try:
        expiry_dt = datetime.strptime(expiry_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        validity_mins = max(0, int((expiry_dt - datetime.now(timezone.utc)).total_seconds() / 60))
    except (ValueError, KeyError):
        validity_mins = 30
    status = kora_response.get("status", "processing")
    response_code = "00" if status == "success" else ("99" if status == "failed" else "Z0")
    return {
        "accountNumber": bank_account["account_number"],
        "bankName": bank_name,
        "accountName": bank_account["account_name"],
        "amount": amount_kobo,
        "transactionReference": kora_response["reference"],
        "responseCode": response_code,
        "validityPeriodMins": validity_mins,
    }


def _normalize_confirm_response(kora_response: dict) -> dict:
    """Convert KoraPay transfer status to Quickteller-compatible format."""
    status = kora_response.get("status", "processing")
    response_code = "00" if status == "success" else ("99" if status == "failed" else "Z0")
    return {"responseCode": response_code, "transactionReference": kora_response["reference"]}


class KoraPayError(Exception):
    """Base exception for all KoraPay API errors."""

    def __init__(self, message: str, error_code: str = None, status_code: int = None):
        """
        Initialize KoraPayError.

        Args:
            message: Human-readable error message
            error_code: Optional error code from KoraPay API
            status_code: Optional HTTP status code
        """
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(message)


class CircuitBreakerState:
    """Enum-like class for circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for fault tolerance.

    Prevents cascading failures by failing fast when a service is unhealthy.
    """

    def __init__(
        self,
        failure_threshold: int = 10,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of consecutive failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery (half-open)
            half_open_max_calls: Maximum calls allowed in half-open state
        """
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls

        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._half_open_calls = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        """Get current circuit breaker state."""
        with self._lock:
            if self._state == CircuitBreakerState.OPEN:
                if (
                    self._last_failure_time
                    and time.time() - self._last_failure_time >= self._recovery_timeout
                ):
                    self._state = CircuitBreakerState.HALF_OPEN
                    self._half_open_calls = 0
            return self._state

    def is_available(self) -> bool:
        """Check if circuit allows requests."""
        return self.state != CircuitBreakerState.OPEN

    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._half_open_calls += 1
                if self._half_open_calls >= self._half_open_max_calls:
                    self._state = CircuitBreakerState.CLOSED
                    self._failure_count = 0
            elif self._state == CircuitBreakerState.CLOSED:
                self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitBreakerState.HALF_OPEN:
                self._state = CircuitBreakerState.OPEN
            elif self._failure_count >= self._failure_threshold:
                self._state = CircuitBreakerState.OPEN

    def call(self, func, *args, **kwargs):
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to call
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func call

        Raises:
            KoraPayError: If circuit is open or call fails
        """
        if not self.is_available():
            raise KoraPayError(
                "Circuit breaker is OPEN - KoraPay service unavailable",
                error_code="CIRCUIT_OPEN",
                status_code=503,
            )

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise


class KoraPayService:
    """
    KoraPay API integration service.

    Handles virtual account creation and transfer confirmation with automatic
    mock mode for testing without credentials.
    """

    # Mock mode confirmation threshold
    MOCK_CONFIRM_AFTER = 3

    def __init__(self):
        """Initialize KoraPay service with connection pooling."""
        # Initialize requests session for connection pooling
        self._session = requests.Session()
        adapter = HTTPAdapter(
            max_retries=0,  # Manual retry control
            pool_connections=10,
            pool_maxsize=10,
        )
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
        self._session.headers.update({"User-Agent": "OnePay-KoraPay/1.0"})

        # Mock mode tracking
        self._mock_poll_counts = {}

        # Health metrics tracking
        self._metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "last_request_time": None,
        }
        self._response_times = deque(
            maxlen=100
        )  # Rolling window of last 100 response times
        self._metrics_lock = threading.Lock()

        # Circuit breaker for fault tolerance
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=10, recovery_timeout=60.0, half_open_max_calls=3
        )

        # Log mode
        if self._is_mock():
            logger.warning(
                "⚠️  KORAPAY MOCK MODE ACTIVE - No real API calls will be made"
            )

    def is_configured(self) -> bool:
        """
        Check if KoraPay is configured with valid credentials.

        Returns:
            True if KORAPAY_SECRET_KEY is set and >= 32 characters
        """
        # Import Config here to get fresh value after reload
        from config import Config as FreshConfig

        secret_key = FreshConfig.KORAPAY_SECRET_KEY
        return bool(secret_key and len(secret_key) >= 32)

    def is_transfer_configured(self) -> bool:
        """
        Check if transfer functionality is configured.

        For KoraPay, this is always True (no additional config needed).
        Returns True even in mock mode to allow UI to show bank details.

        Returns:
            True always (KoraPay requires no additional transfer config)
        """
        return True

    def get_health_metrics(self) -> dict:
        """
        Get health metrics for KoraPay API monitoring.

        Returns:
            Dict containing:
            - success_rate: Percentage of successful requests (0-100)
            - avg_response_time: Average response time in milliseconds
            - failures_last_hour: Count of failures in last hour
            - total_requests: Total number of requests
            - successful_requests: Count of successful requests
            - failed_requests: Count of failed requests
        """
        with self._metrics_lock:
            total = self._metrics["total_requests"]
            successful = self._metrics["successful_requests"]
            failed = self._metrics["failed_requests"]

            # Calculate success rate
            if total > 0:
                success_rate = (successful / total) * 100
            else:
                success_rate = 100.0

            # Calculate average response time
            if self._response_times:
                avg_response_time = sum(self._response_times) / len(
                    self._response_times
                )
            else:
                avg_response_time = 0.0

            # Count failures in last hour (simplified - counts all failures)
            failures_last_hour = failed

            return {
                "success_rate": round(success_rate, 2),
                "avg_response_time": round(avg_response_time, 2),
                "failures_last_hour": failures_last_hour,
                "total_requests": total,
                "successful_requests": successful,
                "failed_requests": failed,
            }

    def _is_mock(self) -> bool:
        """
        Check if running in mock mode.

        Returns:
            True if not configured (empty or short secret key)
        """
        return not self.is_configured()

    def _get_auth_headers(self) -> dict:
        """
        Generate authentication headers for KoraPay API requests.

        Returns:
            Dict with Authorization, Content-Type, Accept, User-Agent, X-Request-ID,
            and X-Correlation-ID headers
        """
        import uuid

        from config import Config as FreshConfig

        headers = {
            "Authorization": f"Bearer {FreshConfig.KORAPAY_SECRET_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "OnePay-KoraPay/1.0",
            "X-Request-ID": str(uuid.uuid4()),
        }

        # Forward correlation ID if available (Requirement 22.4)
        try:
            from flask import g
            correlation_id = g.get("correlation_id")
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id
        except RuntimeError:
            # Outside Flask request context — skip
            pass

        return headers

    def _handle_response_status(self, response, attempt: int, max_retries: int, request_id: str) -> dict:
        """
        Handle HTTP response status codes. Returns parsed JSON on success,
        raises KoraPayError on client errors, returns None to signal retry on server errors.
        """
        import time

        if response.status_code == 429:
            if attempt < max_retries:
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.warning("Rate limited, retry after %ds | attempt=%d request_id=%s", retry_after, attempt, request_id)
                time.sleep(retry_after)
                return None  # signal retry
            raise KoraPayError(f"Rate limit exceeded after {max_retries} attempts", error_code="RATE_LIMIT", status_code=429)

        if 400 <= response.status_code < 500:
            error_msg = f"Client error: {response.status_code}"
            try:
                error_data = response.json()
                if "message" in error_data:
                    error_msg = f"{error_msg} - {error_data['message']}"
            except Exception as e:
                logger.debug("Could not parse error response body: %s", e)
            with self._metrics_lock:
                self._metrics["total_requests"] += 1
                self._metrics["failed_requests"] += 1
            raise KoraPayError(error_msg, error_code=f"HTTP_{response.status_code}", status_code=response.status_code)

        if response.status_code >= 500:
            if attempt < max_retries:
                delay = (2 ** (attempt - 1)) + (secrets.randbelow(500) / 1000)
                logger.warning("Server error, retry in %.1fs | status=%d attempt=%d request_id=%s", delay, response.status_code, attempt, request_id)
                time.sleep(delay)
                return None  # signal retry
            with self._metrics_lock:
                self._metrics["total_requests"] += 1
                self._metrics["failed_requests"] += 1
            raise KoraPayError(f"Server error after {max_retries} attempts", error_code="SERVER_ERROR", status_code=response.status_code)

        try:
            response_data = response.json()
            with self._metrics_lock:
                self._metrics["total_requests"] += 1
                self._metrics["successful_requests"] += 1
                self._metrics["last_request_time"] = time.time()
            return response_data
        except requests.exceptions.JSONDecodeError:
            logger.error("Invalid JSON response | status=%d request_id=%s", response.status_code, request_id)
            raise KoraPayError("Invalid JSON response from payment provider", error_code="INVALID_JSON")

    def _make_request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make HTTP request to KoraPay API with retry logic."""
        import time

        from config import Config as FreshConfig

        url = f"{FreshConfig.KORAPAY_BASE_URL}{endpoint}"
        headers = self._get_auth_headers()
        request_id = headers.get("X-Request-ID")
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        timeout = (FreshConfig.KORAPAY_CONNECT_TIMEOUT, FreshConfig.KORAPAY_TIMEOUT_SECONDS)
        kwargs.setdefault("verify", True)
        kwargs.setdefault("allow_redirects", False)
        max_retries = FreshConfig.KORAPAY_MAX_RETRIES
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                start_time = time.perf_counter()
                logger.info("KoraPay API request | method=%s endpoint=%s attempt=%d/%d request_id=%s", method, endpoint, attempt, max_retries, request_id)
                response = self._session.request(method=method, url=url, headers=headers, timeout=timeout, **kwargs)
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                logger.info("KoraPay API response | status=%d endpoint=%s duration=%dms request_id=%s", response.status_code, endpoint, duration_ms, request_id)
                if duration_ms > 5000:
                    logger.warning("Slow KoraPay API request | endpoint=%s duration=%dms request_id=%s", endpoint, duration_ms, request_id)

                result = self._handle_response_status(response, attempt, max_retries, request_id)
                if result is None:
                    continue  # retry
                self._response_times.append(duration_ms)
                return result

            except requests.exceptions.SSLError as e:
                logger.error("SSL verification failed | request_id=%s error=%s", request_id, str(e))
                with self._metrics_lock:
                    self._metrics["total_requests"] += 1
                    self._metrics["failed_requests"] += 1
                raise KoraPayError("Payment provider security error", error_code="SSL_ERROR")

            except (requests.Timeout, requests.ConnectionError) as e:
                last_error = e
                if attempt < max_retries:
                    delay = (2 ** (attempt - 1)) + (secrets.randbelow(500) / 1000)
                    logger.warning("Network error, retry in %.1fs | attempt=%d request_id=%s", delay, attempt, request_id)
                    time.sleep(delay)
                    continue
                with self._metrics_lock:
                    self._metrics["total_requests"] += 1
                    self._metrics["failed_requests"] += 1
                error_code = "TIMEOUT" if isinstance(e, requests.Timeout) else "CONNECTION_ERROR"
                raise KoraPayError(f"Request failed after {max_retries} attempts", error_code=error_code)

            except requests.exceptions.JSONDecodeError as e:
                logger.error("Invalid JSON response | request_id=%s error=%s", request_id, str(e))
                raise KoraPayError("Invalid JSON response from payment provider", error_code="INVALID_JSON")

        raise KoraPayError(f"Request failed after {max_retries} attempts: {last_error}", error_code="MAX_RETRIES_EXCEEDED")

    def _validate_response(self, response: dict, required_fields: list) -> None:
        """
        Validate that response contains all required fields.

        Args:
            response: Response dict from KoraPay API
            required_fields: List of required field paths (supports dot notation for nested fields)

        Raises:
            KoraPayError: If any required fields are missing
        """
        missing_fields = []

        for field_path in required_fields:
            # Split field path by dots for nested access
            parts = field_path.split(".")
            current = response

            # Navigate through nested structure
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    # Field is missing
                    missing_fields.append(field_path)
                    break

        # Raise error if any fields missing
        if missing_fields:
            raise KoraPayError(
                f"Missing required fields in response: {', '.join(missing_fields)}",
                error_code="INVALID_RESPONSE",
            )

    def _mock_create_virtual_account(
        self, transaction_reference: str, amount_kobo: int, account_name: str
    ) -> dict:
        """
        Generate mock virtual account for testing.

        Args:
            transaction_reference: Transaction reference (tx_ref)
            amount_kobo: Amount in kobo (for backward compatibility)
            account_name: Name to display on virtual account

        Returns:
            Dict with Quickteller-compatible structure
        """
        # Generate deterministic account number from tx_ref
        seed = sum(ord(c) for c in transaction_reference)
        account_number = str(3000000000 + (seed % 999999999)).zfill(10)

        # Build response
        response = {
            "accountNumber": account_number,
            "bankName": "Wema Bank (Demo)",
            "accountName": account_name,
            "amount": amount_kobo,
            "transactionReference": transaction_reference,
            "responseCode": "Z0",  # pending
            "validityPeriodMins": 30,
        }

        # Log with [MOCK] prefix
        logger.warning(
            "[MOCK] Virtual account created | ref=%s acct=%s amount=₦%.2f",
            transaction_reference,
            account_number,
            amount_kobo / 100,
        )

        return response

    def _mock_confirm_transfer(self, transaction_reference: str) -> dict:
        """
        Simulate transfer confirmation polling behavior.

        Returns 'Z0' (pending) for first 3 polls, then '00' (confirmed) on 4th+ poll.

        Args:
            transaction_reference: Transaction reference (tx_ref)

        Returns:
            Dict with Quickteller-compatible structure
        """
        # Increment poll count
        if transaction_reference not in self._mock_poll_counts:
            self._mock_poll_counts[transaction_reference] = 0
        self._mock_poll_counts[transaction_reference] += 1

        poll_count = self._mock_poll_counts[transaction_reference]

        # Check if confirmed (4th+ poll)
        if poll_count > self.MOCK_CONFIRM_AFTER:
            # Clean up counter
            del self._mock_poll_counts[transaction_reference]

            # Log confirmation
            logger.warning(
                "[MOCK] Transfer CONFIRMED | ref=%s (poll #%d)",
                transaction_reference,
                poll_count,
            )

            # Return confirmed
            return {
                "responseCode": "00",  # confirmed
                "transactionReference": transaction_reference,
            }
        else:
            # Log pending
            logger.warning(
                "[MOCK] Transfer pending | ref=%s (poll #%d/%d)",
                transaction_reference,
                poll_count,
                self.MOCK_CONFIRM_AFTER,
            )

            # Return pending
            return {
                "responseCode": "Z0",  # pending
                "transactionReference": transaction_reference,
            }

    def create_virtual_account(
        self, transaction_reference: str, amount_kobo: int, account_name: str
    ) -> dict:
        """Create a virtual bank account for a transaction."""
        if self._is_mock():
            return self._mock_create_virtual_account(transaction_reference, amount_kobo, account_name)

        from decimal import Decimal
        amount_naira = Decimal(amount_kobo) / 100
        if amount_naira < 100 or amount_naira > 999999999:
            raise KoraPayError(
                f"Amount must be between ₦100 and ₦999,999,999 (got ₦{amount_naira})",
                error_code="INVALID_AMOUNT",
            )

        response = self._make_request(
            "POST", "/merchant/api/v1/charges/bank-transfer",
            json={"reference": transaction_reference, "amount": int(amount_naira),
                  "currency": "NGN", "customer": {"account_name": account_name}},
        )
        self._validate_response(response, [
            "data.reference", "data.payment_reference", "data.status", "data.currency",
            "data.amount", "data.bank_account.account_number", "data.bank_account.bank_name",
            "data.bank_account.account_name", "data.bank_account.bank_code",
            "data.bank_account.expiry_date_in_utc",
        ])
        normalized = self._normalize_create_response(response["data"], amount_kobo)
        logger.info("Virtual account created | ref=%s bank=%s acct=%s",
                    transaction_reference, normalized.get("bankName"), normalized.get("accountNumber"))
        return normalized

    def confirm_transfer(
        self, transaction_reference: str, _retry: bool = False
    ) -> dict:
        """
        Query transfer confirmation status.

        Args:
            transaction_reference: Unique transaction reference (tx_ref)
            _retry: Internal flag for retry logic (not used currently)

        Returns:
            Dict with Quickteller-compatible structure:
            {
                "responseCode": "00",  # 00=confirmed, Z0=pending, 99=failed
                "transactionReference": "ONEPAY-..."
            }

        Raises:
            KoraPayError: On API failure or validation error
        """
        # Check if mock mode
        if self._is_mock():
            return self._mock_confirm_transfer(transaction_reference)

        # Make API request to query status
        response = self._make_request(
            "GET", f"/merchant/api/v1/charges/{transaction_reference}"
        )

        # Validate response has required fields
        required_fields = ["data.reference", "data.status"]
        self._validate_response(response, required_fields)

        # Normalize response to Quickteller format
        normalized = self._normalize_confirm_response(response["data"])

        # Log transfer status
        logger.info(
            "Transfer status | ref=%s code=%s",
            transaction_reference,
            normalized.get("responseCode"),
        )

        return normalized

    def _normalize_create_response(self, kora_response: dict, amount_kobo: int) -> dict:
        return _normalize_create_response(kora_response, amount_kobo)

    def _normalize_confirm_response(self, kora_response: dict) -> dict:
        return _normalize_confirm_response(kora_response)

    def initiate_refund(
        self,
        payment_reference: str,
        refund_reference: str = None,
        amount: int = None,
        reason: str = None,
    ) -> dict:
        """Initiate a refund for a completed payment through KoraPay API."""
        import time

        if refund_reference is None:
            refund_reference = f"REFUND-{payment_reference}-{int(time.time())}"
        if amount is not None and amount < 100:
            raise KoraPayError("Refund amount must be at least ₦100", error_code="INVALID_AMOUNT")

        body = {"payment_reference": payment_reference, "reference": refund_reference}
        if amount is not None:
            body["amount"] = amount
        if reason is not None:
            body["reason"] = reason

        logger.info("Initiating refund | payment_ref=%s refund_ref=%s amount=%s",
                    payment_reference, refund_reference, amount)
        response = self._make_request("POST", "/merchant/api/v1/refunds/initiate", json=body)
        self._validate_response(response, [
            "status", "data", "data.reference", "data.payment_reference",
            "data.amount", "data.status", "data.currency",
        ])
        data = response["data"]
        logger.info("Refund initiated | refund_ref=%s status=%s", data["reference"], data["status"])
        return data

    def query_refund(self, refund_reference: str) -> dict:
        """
        Query the status of a refund from KoraPay API.

        Args:
            refund_reference: The unique refund identifier

        Returns:
            Dict with refund status:
            {
                "reference": "REFUND-...",
                "payment_reference": "ONEPAY-...",
                "amount": 1000,
                "status": "success",
                "currency": "NGN",
                "created_at": "2024-01-01T00:00:00Z",
                "processed_at": "2024-01-01T00:05:00Z"
            }

        Raises:
            KoraPayError: If query fails or refund not found
        """
        endpoint = f"/merchant/api/v1/refunds/{refund_reference}"
        logger.info(f"Querying refund status | refund_ref={refund_reference}")

        response = self._make_request("GET", endpoint)

        # Validate response structure
        self._validate_response(
            response,
            [
                "status",
                "data",
                "data.reference",
                "data.payment_reference",
                "data.amount",
                "data.status",
                "data.currency",
            ],
        )

        # Extract data object
        data = response["data"]

        logger.info(
            f"Refund status retrieved | refund_ref={data['reference']} status={data['status']}"
        )

        return data


def verify_korapay_webhook_signature(payload: dict, signature: str) -> bool:
    """
    Verify HMAC-SHA256 signature on KoraPay webhook payload.

    KoraPay signs ONLY the 'data' object (not the full payload) using HMAC-SHA256
    with the KORAPAY_WEBHOOK_SECRET. This function verifies the signature using
    constant-time comparison to prevent timing attacks.

    Args:
        payload: Full webhook payload dict (must contain 'data' key)
        signature: Signature from x-korapay-signature header

    Returns:
        True if signature is valid, False otherwise

    Security:
        - Uses hmac.compare_digest() for constant-time comparison
        - Signs only the 'data' object (KoraPay-specific behavior)
        - Returns False on any error (missing data, missing signature, etc.)
    """
    import hashlib
    import hmac
    import json

    from config import Config as FreshConfig

    # Validate inputs
    if not signature:
        logger.warning("Webhook signature verification failed: missing signature")
        return False

    if not isinstance(payload, dict):
        logger.warning("Webhook signature verification failed: invalid payload type")
        return False

    # Extract data object
    data = payload.get("data")
    if not data:
        logger.warning("Webhook signature verification failed: missing data object")
        return False

    try:
        # Serialize data object with compact JSON (no spaces)
        # KoraPay uses separators=(',', ':') for compact JSON
        data_bytes = json.dumps(data, separators=(",", ":")).encode("utf-8")

        # Compute HMAC-SHA256 signature
        webhook_secret = FreshConfig.KORAPAY_WEBHOOK_SECRET.encode("utf-8")
        expected_signature = hmac.new(
            webhook_secret, data_bytes, hashlib.sha256
        ).hexdigest()

        # Constant-time comparison to prevent timing attacks
        is_valid = hmac.compare_digest(expected_signature, signature)

        if not is_valid:
            logger.warning(
                "Webhook signature verification failed: signature mismatch | ref=%s",
                data.get("reference", "unknown"),
            )

        return is_valid

    except Exception as e:
        logger.error("Webhook signature verification error: %s", e)
        return False


# Global singleton instance
korapay = KoraPayService()
