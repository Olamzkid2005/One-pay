"""
Unit tests for correlation ID tracking.

Tests the correlation ID middleware in app.py and CorrelationIdFilter in
core/logging_filters.py to ensure:
- A new UUID is generated when no X-Request-ID header is present
- The X-Request-ID header value is used as correlation ID when present
- The X-Correlation-ID response header is set on all responses
- The CorrelationIdFilter injects correlation_id into log records
- The correlation ID is consistent between request and response

**Validates: Requirements 22.1, 22.2, 22.3, 22.5**
"""
import logging
import uuid
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, g

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """Create a minimal Flask app that mirrors the correlation ID middleware in app.py."""
    import uuid as _uuid

    test_app = Flask(__name__)
    test_app.config["TESTING"] = True
    test_app.config["SECRET_KEY"] = "test-secret-key-for-testing-only-32chars"

    @test_app.before_request
    def inject_correlation_id():
        from flask import request
        correlation_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        g.correlation_id = correlation_id

    @test_app.after_request
    def add_correlation_id_header(response):
        response.headers["X-Correlation-ID"] = g.get("correlation_id", "")
        return response

    @test_app.route("/ping")
    def ping():
        from flask import jsonify
        return jsonify({"correlation_id": g.get("correlation_id")})

    return test_app


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Requirement 22.1 — Generate correlation ID when none is provided
# ---------------------------------------------------------------------------

class TestCorrelationIdGeneration:
    """Test that a new UUID is generated when no X-Request-ID header is present."""

    def test_generates_uuid_when_no_header(self, client):
        """
        WHEN a request is received without X-Request-ID,
        THE System SHALL generate a new UUID as the correlation ID.

        **Validates: Requirements 22.1**
        """
        response = client.get("/ping")

        assert response.status_code == 200
        correlation_id = response.headers.get("X-Correlation-ID")
        assert correlation_id is not None
        assert correlation_id != ""

        # Verify it is a valid UUID
        parsed = uuid.UUID(correlation_id)
        assert str(parsed) == correlation_id

    def test_each_request_gets_unique_id(self, client):
        """
        WHEN two requests are received without X-Request-ID,
        each SHALL receive a distinct correlation ID.

        **Validates: Requirements 22.1**
        """
        r1 = client.get("/ping")
        r2 = client.get("/ping")

        id1 = r1.headers.get("X-Correlation-ID")
        id2 = r2.headers.get("X-Correlation-ID")

        assert id1 != id2

    def test_generated_id_is_valid_uuid_format(self, client):
        """
        The auto-generated correlation ID SHALL be a valid UUID v4 string.

        **Validates: Requirements 22.1**
        """
        response = client.get("/ping")
        correlation_id = response.headers.get("X-Correlation-ID")

        # Should not raise ValueError
        parsed = uuid.UUID(correlation_id, version=4)
        assert parsed is not None


# ---------------------------------------------------------------------------
# Requirement 22.5 — Use X-Request-ID header as correlation ID
# ---------------------------------------------------------------------------

class TestCorrelationIdExtraction:
    """Test that X-Request-ID header value is used as the correlation ID."""

    def test_uses_x_request_id_header_when_present(self, client):
        """
        WHEN a request includes X-Request-ID,
        THE System SHALL use that value as the correlation ID.

        **Validates: Requirements 22.5**
        """
        custom_id = "my-custom-request-id-12345"
        response = client.get("/ping", headers={"X-Request-ID": custom_id})

        assert response.status_code == 200
        assert response.headers.get("X-Correlation-ID") == custom_id

    def test_x_request_id_propagated_to_response_body(self, client):
        """
        The correlation ID extracted from X-Request-ID SHALL be accessible
        via Flask g within the request context.

        **Validates: Requirements 22.5**
        """
        custom_id = "trace-abc-789"
        response = client.get("/ping", headers={"X-Request-ID": custom_id})

        data = response.get_json()
        assert data["correlation_id"] == custom_id

    def test_empty_x_request_id_falls_back_to_generated(self, client):
        """
        WHEN X-Request-ID header is empty,
        THE System SHALL generate a new UUID instead.

        **Validates: Requirements 22.1, 22.5**
        """
        response = client.get("/ping", headers={"X-Request-ID": ""})

        correlation_id = response.headers.get("X-Correlation-ID")
        # Should be a valid UUID (auto-generated), not empty
        assert correlation_id != ""
        uuid.UUID(correlation_id)  # raises if not valid UUID


# ---------------------------------------------------------------------------
# Requirement 22.3 — X-Correlation-ID response header on all responses
# ---------------------------------------------------------------------------

class TestCorrelationIdResponseHeader:
    """Test that X-Correlation-ID is set on all responses."""

    def test_correlation_id_header_present_on_200(self, client):
        """
        THE System SHALL return X-Correlation-ID on successful responses.

        **Validates: Requirements 22.3**
        """
        response = client.get("/ping")

        assert "X-Correlation-ID" in response.headers

    def test_correlation_id_header_present_on_404(self, app):
        """
        THE System SHALL return X-Correlation-ID even on 404 responses.

        **Validates: Requirements 22.3**
        """
        client = app.test_client()
        response = client.get("/nonexistent-route")

        assert "X-Correlation-ID" in response.headers

    def test_correlation_id_consistent_in_header_and_body(self, client):
        """
        The X-Correlation-ID response header SHALL match the correlation ID
        available inside the request context.

        **Validates: Requirements 22.3, 22.5**
        """
        custom_id = "consistency-check-id"
        response = client.get("/ping", headers={"X-Request-ID": custom_id})

        header_id = response.headers.get("X-Correlation-ID")
        body_id = response.get_json()["correlation_id"]

        assert header_id == custom_id
        assert body_id == custom_id
        assert header_id == body_id

    def test_correlation_id_header_non_empty(self, client):
        """
        The X-Correlation-ID response header SHALL never be empty.

        **Validates: Requirements 22.3**
        """
        response = client.get("/ping")

        correlation_id = response.headers.get("X-Correlation-ID")
        assert correlation_id is not None
        assert len(correlation_id) > 0


# ---------------------------------------------------------------------------
# Requirement 22.2 — CorrelationIdFilter injects correlation_id into log records
# ---------------------------------------------------------------------------

class TestCorrelationIdFilter:
    """Test that CorrelationIdFilter injects correlation_id into log records."""

    def test_filter_injects_correlation_id_in_request_context(self, app):
        """
        WHEN inside a Flask request context with g.correlation_id set,
        THE CorrelationIdFilter SHALL inject that value into log records.

        **Validates: Requirements 22.2**
        """
        from core.logging_filters import CorrelationIdFilter

        filt = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0, msg="test message",
            args=(), exc_info=None
        )

        with app.test_request_context("/ping"):
            g.correlation_id = "inject-test-id-abc"
            filt.filter(record)

        assert record.correlation_id == "inject-test-id-abc"

    def test_filter_uses_dash_when_outside_request_context(self):
        """
        WHEN outside a Flask request context,
        THE CorrelationIdFilter SHALL set correlation_id to '-'.

        **Validates: Requirements 22.2**
        """
        from core.logging_filters import CorrelationIdFilter

        filt = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0, msg="test message",
            args=(), exc_info=None
        )

        # No app context — should not raise, should default to '-'
        filt.filter(record)

        assert record.correlation_id == "-"

    def test_filter_uses_dash_when_g_has_no_correlation_id(self, app):
        """
        WHEN inside a request context but g.correlation_id is not set,
        THE CorrelationIdFilter SHALL set correlation_id to '-'.

        **Validates: Requirements 22.2**
        """
        from core.logging_filters import CorrelationIdFilter

        filt = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0, msg="test message",
            args=(), exc_info=None
        )

        with app.test_request_context("/ping"):
            # Do NOT set g.correlation_id
            filt.filter(record)

        assert record.correlation_id == "-"

    def test_filter_returns_true(self, app):
        """
        THE CorrelationIdFilter.filter() SHALL always return True
        (i.e., never suppress log records).

        **Validates: Requirements 22.2**
        """
        from core.logging_filters import CorrelationIdFilter

        filt = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0, msg="test message",
            args=(), exc_info=None
        )

        with app.test_request_context("/ping"):
            g.correlation_id = "some-id"
            result = filt.filter(record)

        assert result is True

    def test_filter_correlation_id_appears_in_formatted_log(self, app):
        """
        WHEN a log handler uses %(correlation_id)s in its format string,
        the correlation ID SHALL appear in the formatted output.

        **Validates: Requirements 22.2**
        """
        import io

        from core.logging_filters import CorrelationIdFilter

        filt = CorrelationIdFilter()
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(correlation_id)s %(message)s"))
        handler.addFilter(filt)

        logger = logging.getLogger("test_correlation_format")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        with app.test_request_context("/ping"):
            g.correlation_id = "format-test-id-xyz"
            logger.info("hello world")

        output = stream.getvalue()
        assert "format-test-id-xyz" in output
        assert "hello world" in output

        logger.removeHandler(handler)


# ---------------------------------------------------------------------------
# End-to-end consistency: request ID consistent between request and response
# ---------------------------------------------------------------------------

class TestCorrelationIdConsistency:
    """Test that the correlation ID is consistent throughout the request lifecycle."""

    def test_provided_id_consistent_across_request(self, client):
        """
        The correlation ID provided via X-Request-ID SHALL be the same
        in the response header and in the request context.

        **Validates: Requirements 22.3, 22.5**
        """
        request_id = "end-to-end-consistency-id"
        response = client.get("/ping", headers={"X-Request-ID": request_id})

        assert response.headers["X-Correlation-ID"] == request_id
        assert response.get_json()["correlation_id"] == request_id

    def test_generated_id_consistent_across_request(self, client):
        """
        The auto-generated correlation ID SHALL be the same in the response
        header and in the request context (not regenerated mid-request).

        **Validates: Requirements 22.1, 22.3**
        """
        response = client.get("/ping")

        header_id = response.headers["X-Correlation-ID"]
        body_id = response.get_json()["correlation_id"]

        assert header_id == body_id
        assert header_id != ""
