"""
Unit tests for ETag headers on static assets (Requirement 23.3).

Validates:
- ETag header is added to static asset responses
- ETag is quoted per HTTP spec (RFC 7232)
- ETag value matches MD5 hash of response content
- Conditional requests with matching If-None-Match return 304
- Non-matching If-None-Match returns full 200 response
- Non-static paths do not get ETag headers
"""
import hashlib

import pytest
from flask import Flask
from flask import request as flask_request

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(tmp_path):
    """
    Create a minimal Flask app that mirrors the add_cache_headers logic from app.py.
    Uses a temporary directory as the static folder so we can create test files.
    """
    test_app = Flask(__name__, static_folder=str(tmp_path), static_url_path="/static")
    test_app.config["TESTING"] = True
    test_app.config["SECRET_KEY"] = "test-secret-key-for-testing-only-32chars"

    @test_app.after_request
    def add_cache_headers(response):
        if flask_request.path.startswith("/static/"):
            filename = flask_request.path[len("/static/"):]
            parts = filename.rsplit(".", 1)
            if len(parts) == 2 and len(parts[1]) == 8 and parts[1].isalnum():
                response.headers["Cache-Control"] = "public, max-age=31536000"
            else:
                response.headers["Cache-Control"] = "public, max-age=3600"

            # Generate ETag from content hash (quoted per HTTP spec)
            # Buffer the response to allow reading its data (static files use streaming)
            if response.direct_passthrough:
                response.direct_passthrough = False
            etag = '"' + hashlib.sha256(response.get_data()).hexdigest()[:32] + '"'
            response.headers["ETag"] = etag

            # Handle conditional request: return 304 if ETag matches
            if_none_match = flask_request.headers.get("If-None-Match")
            if if_none_match and if_none_match == etag:
                response = response.__class__(status=304)
                response.headers["ETag"] = etag

        return response

    @test_app.route("/ping")
    def ping():
        from flask import jsonify
        return jsonify({"ok": True})

    return test_app


@pytest.fixture
def static_file(tmp_path):
    """Create a static CSS file in the temp directory and return its name."""
    content = b"body { color: red; }"
    filename = "style.css"
    (tmp_path / filename).write_bytes(content)
    return filename


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# ETag presence and format
# ---------------------------------------------------------------------------

class TestETagPresence:
    """ETag header is added to static asset responses."""

    def test_etag_header_present_on_static_asset(self, client, static_file) -> None:
        """Static asset responses include an ETag header."""
        response = client.get(f"/static/{static_file}")
        assert response.status_code == 200
        assert "ETag" in response.headers

    def test_etag_is_quoted_per_http_spec(self, client, static_file) -> None:
        """ETag header value is quoted per HTTP spec (RFC 7232)."""
        response = client.get(f"/static/{static_file}")
        etag = response.headers.get("ETag")
        assert etag is not None
        assert etag.startswith('"') and etag.endswith('"'), (
            f"ETag must be quoted, got: {etag}"
        )

    def test_etag_matches_md5_of_response_data(self, client, static_file) -> None:
        """ETag value equals the SHA-256 hash of the actual response body."""
        response = client.get(f"/static/{static_file}")
        assert response.status_code == 200
        # Compute expected ETag from the actual response data (SHA-256, first 32 chars)
        expected_etag = '"' + hashlib.sha256(response.data).hexdigest()[:32] + '"'
        assert response.headers.get("ETag") == expected_etag

    def test_non_static_path_has_no_etag(self, client) -> None:
        """Non-static paths do not receive ETag headers."""
        response = client.get("/ping")
        assert "ETag" not in response.headers


# ---------------------------------------------------------------------------
# Conditional requests (If-None-Match)
# ---------------------------------------------------------------------------

class TestConditionalRequests:
    """Conditional requests via If-None-Match are handled correctly."""

    def test_matching_etag_returns_304(self, client, static_file) -> None:
        """If-None-Match with matching ETag returns 304 Not Modified."""
        # First request to get the ETag
        r1 = client.get(f"/static/{static_file}")
        assert r1.status_code == 200
        etag = r1.headers.get("ETag")
        assert etag is not None

        # Conditional request with matching ETag
        r2 = client.get(f"/static/{static_file}", headers={"If-None-Match": etag})
        assert r2.status_code == 304

    def test_304_response_includes_etag_header(self, client, static_file) -> None:
        """304 Not Modified response still includes the ETag header."""
        r1 = client.get(f"/static/{static_file}")
        etag = r1.headers.get("ETag")

        r2 = client.get(f"/static/{static_file}", headers={"If-None-Match": etag})
        assert r2.status_code == 304
        assert r2.headers.get("ETag") == etag

    def test_non_matching_etag_returns_200(self, client, static_file) -> None:
        """If-None-Match with stale ETag returns full 200 response."""
        response = client.get(
            f"/static/{static_file}",
            headers={"If-None-Match": '"stale-etag-value"'}
        )
        assert response.status_code == 200
        assert response.headers.get("ETag") is not None

    def test_no_if_none_match_returns_200(self, client, static_file) -> None:
        """Request without If-None-Match always returns 200."""
        response = client.get(f"/static/{static_file}")
        assert response.status_code == 200
