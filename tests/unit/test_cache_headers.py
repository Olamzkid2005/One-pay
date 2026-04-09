"""
Unit tests for Cache-Control and ETag headers on static assets.

Validates:
- Cache-Control: public, max-age=31536000 for versioned assets (Req 23.1)
- Cache-Control: public, max-age=3600 for non-versioned static assets (Req 23.2)
- ETag header presence on static assets (Req 23.3)
- Non-static paths do NOT get Cache-Control headers
- Conditional request (If-None-Match) returns 304 when ETag matches
"""
import hashlib
import pytest
from flask import Flask, request as flask_request


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(tmp_path):
    """
    Minimal Flask app mirroring the add_cache_headers logic from app.py.
    Uses a temporary directory as the static folder.
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

            if response.direct_passthrough:
                response.direct_passthrough = False
            etag = '"' + hashlib.md5(response.get_data()).hexdigest() + '"'
            response.headers["ETag"] = etag

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
def client(app):
    return app.test_client()


@pytest.fixture
def versioned_file(tmp_path):
    """Static file with an 8-char alphanumeric hash extension (versioned asset)."""
    content = b"body { color: blue; }"
    filename = "style.ab12cd34"  # 8-char alnum extension
    (tmp_path / filename).write_bytes(content)
    return filename


@pytest.fixture
def static_file(tmp_path):
    """Static file with a normal extension (non-versioned asset)."""
    content = b"body { color: red; }"
    filename = "style.css"
    (tmp_path / filename).write_bytes(content)
    return filename


# ---------------------------------------------------------------------------
# Requirement 23.1 — versioned assets get 1-year Cache-Control
# ---------------------------------------------------------------------------

class TestVersionedAssetCacheControl:
    """Cache-Control: public, max-age=31536000 for versioned assets (Req 23.1)."""

    def test_versioned_asset_gets_one_year_cache(self, client, versioned_file):
        """Versioned asset (8-char hash extension) receives max-age=31536000."""
        response = client.get(f"/static/{versioned_file}")
        assert response.status_code == 200
        assert response.headers.get("Cache-Control") == "public, max-age=31536000"

    def test_versioned_asset_cache_control_is_public(self, client, versioned_file):
        """Cache-Control for versioned assets includes 'public' directive."""
        response = client.get(f"/static/{versioned_file}")
        cache_control = response.headers.get("Cache-Control", "")
        assert "public" in cache_control

    def test_versioned_asset_max_age_is_one_year(self, client, versioned_file):
        """Cache-Control max-age for versioned assets is exactly 31536000 seconds."""
        response = client.get(f"/static/{versioned_file}")
        cache_control = response.headers.get("Cache-Control", "")
        assert "max-age=31536000" in cache_control


# ---------------------------------------------------------------------------
# Requirement 23.2 — non-versioned assets get 1-hour Cache-Control
# ---------------------------------------------------------------------------

class TestNonVersionedAssetCacheControl:
    """Cache-Control: public, max-age=3600 for non-versioned static assets (Req 23.2)."""

    def test_non_versioned_asset_gets_one_hour_cache(self, client, static_file):
        """Non-versioned asset (.css) receives max-age=3600."""
        response = client.get(f"/static/{static_file}")
        assert response.status_code == 200
        assert response.headers.get("Cache-Control") == "public, max-age=3600"

    def test_non_versioned_asset_cache_control_is_public(self, client, static_file):
        """Cache-Control for non-versioned assets includes 'public' directive."""
        response = client.get(f"/static/{static_file}")
        cache_control = response.headers.get("Cache-Control", "")
        assert "public" in cache_control

    def test_non_versioned_asset_max_age_is_one_hour(self, client, static_file):
        """Cache-Control max-age for non-versioned assets is exactly 3600 seconds."""
        response = client.get(f"/static/{static_file}")
        cache_control = response.headers.get("Cache-Control", "")
        assert "max-age=3600" in cache_control

    def test_js_file_gets_one_hour_cache(self, tmp_path, app):
        """JavaScript files (non-versioned) also receive max-age=3600."""
        (tmp_path / "app.js").write_bytes(b"console.log('hello');")
        response = app.test_client().get("/static/app.js")
        assert response.headers.get("Cache-Control") == "public, max-age=3600"


# ---------------------------------------------------------------------------
# Requirement 23.3 — ETag header presence on static assets
# ---------------------------------------------------------------------------

class TestETagPresence:
    """ETag header is present on static asset responses (Req 23.3)."""

    def test_etag_present_on_versioned_asset(self, client, versioned_file):
        """Versioned static assets include an ETag header."""
        response = client.get(f"/static/{versioned_file}")
        assert "ETag" in response.headers

    def test_etag_present_on_non_versioned_asset(self, client, static_file):
        """Non-versioned static assets include an ETag header."""
        response = client.get(f"/static/{static_file}")
        assert "ETag" in response.headers

    def test_etag_is_quoted(self, client, static_file):
        """ETag value is quoted per HTTP spec (RFC 7232)."""
        response = client.get(f"/static/{static_file}")
        etag = response.headers.get("ETag")
        assert etag is not None
        assert etag.startswith('"') and etag.endswith('"')


# ---------------------------------------------------------------------------
# Non-static paths do NOT get Cache-Control headers
# ---------------------------------------------------------------------------

class TestNonStaticPathsHaveNoCacheHeaders:
    """Non-static paths must not receive Cache-Control or ETag headers."""

    def test_non_static_path_has_no_cache_control(self, client):
        """API/non-static routes do not get Cache-Control headers."""
        response = client.get("/ping")
        assert "Cache-Control" not in response.headers

    def test_non_static_path_has_no_etag(self, client):
        """API/non-static routes do not get ETag headers."""
        response = client.get("/ping")
        assert "ETag" not in response.headers


# ---------------------------------------------------------------------------
# Conditional requests (If-None-Match → 304)
# ---------------------------------------------------------------------------

class TestConditionalRequests:
    """Conditional requests via If-None-Match return 304 when ETag matches."""

    def test_matching_etag_returns_304(self, client, static_file):
        """If-None-Match with matching ETag returns 304 Not Modified."""
        r1 = client.get(f"/static/{static_file}")
        assert r1.status_code == 200
        etag = r1.headers.get("ETag")
        assert etag is not None

        r2 = client.get(f"/static/{static_file}", headers={"If-None-Match": etag})
        assert r2.status_code == 304

    def test_304_includes_etag_header(self, client, static_file):
        """304 Not Modified response still carries the ETag header."""
        r1 = client.get(f"/static/{static_file}")
        etag = r1.headers.get("ETag")

        r2 = client.get(f"/static/{static_file}", headers={"If-None-Match": etag})
        assert r2.status_code == 304
        assert r2.headers.get("ETag") == etag

    def test_stale_etag_returns_200(self, client, static_file):
        """If-None-Match with a stale ETag returns full 200 response."""
        response = client.get(
            f"/static/{static_file}",
            headers={"If-None-Match": '"stale-etag-value"'},
        )
        assert response.status_code == 200
        assert "ETag" in response.headers
