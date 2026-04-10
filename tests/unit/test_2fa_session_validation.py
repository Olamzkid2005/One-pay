"""
Unit tests for 2FA page session validation.

Validates Requirement 4.5: WHERE the 2FA verification page is accessed without
a pre_2fa_user_id in session, THE System SHALL redirect to the login page.
"""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask


@pytest.fixture
def app():
    """Create a minimal Flask app with the auth blueprint registered."""
    from app import app as flask_app
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret-key-that-is-long-enough-32chars"
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


class TestVerify2FASessionValidation:
    """Tests for session validation on the /verify-2fa endpoint."""

    def test_get_without_session_redirects_to_login(self, client) -> None:
        """GET /api/v1/verify-2fa without pre_2fa_user_id in session must redirect to login."""
        response = client.get("/api/v1/verify-2fa")

        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_post_without_session_redirects_to_login(self, client) -> None:
        """POST /api/v1/verify-2fa without pre_2fa_user_id in session must redirect to login."""
        response = client.post("/api/v1/verify-2fa", data={"csrf_token": "any"})

        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_get_with_session_renders_page(self, client) -> None:
        """GET /api/v1/verify-2fa with pre_2fa_user_id in session must render the 2FA page."""
        with client.session_transaction() as sess:
            sess["pre_2fa_user_id"] = 42

        response = client.get("/api/v1/verify-2fa")

        assert response.status_code == 200

    def test_direct_navigation_without_login_redirects(self, client) -> None:
        """Direct navigation to /api/v1/verify-2fa without going through login must redirect."""
        # Simulate a fresh session with no pre_2fa_user_id (direct navigation)
        response = client.get("/api/v1/verify-2fa", follow_redirects=False)

        assert response.status_code == 302
        location = response.headers["Location"]
        assert "login" in location

    def test_stale_session_without_pre_2fa_user_id_redirects(self, client) -> None:
        """A session that has other keys but not pre_2fa_user_id must still redirect."""
        with client.session_transaction() as sess:
            sess["user_id"] = 99  # some other session data, but not pre_2fa_user_id

        response = client.get("/api/v1/verify-2fa")

        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_post_with_valid_session_proceeds_to_verification(self, client) -> None:
        """POST /api/v1/verify-2fa with pre_2fa_user_id in session must attempt verification."""
        with client.session_transaction() as sess:
            sess["pre_2fa_user_id"] = 1

        with patch("blueprints.auth.is_valid_csrf_token", return_value=False):
            # CSRF failure means we get past session check but fail on CSRF
            response = client.post(
                "/api/v1/verify-2fa",
                data={"csrf_token": "bad-token"},
            )

        # Should NOT redirect to login (session check passed), but fail on CSRF
        assert response.status_code == 200
