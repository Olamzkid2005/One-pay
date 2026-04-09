"""
Unit tests for the 2FA disable flow.

Validates Requirement 4.4: WHEN a user disables 2FA, THE System SHALL set
two_factor_enabled to False.
"""

import pytest
from unittest.mock import patch, MagicMock
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


def _make_session(client, user_id=1, csrf_token="test-csrf-token"):
    """Helper to set up an authenticated session."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["username"] = "testuser"
        sess["csrf_token"] = csrf_token


class TestDisable2FA:
    """Tests for the /account/2fa/disable endpoint."""

    def test_disable_2fa_sets_flag_to_false(self, client):
        """Disabling 2FA must set two_factor_enabled to False on the user."""
        _make_session(client)

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = "testuser"
        mock_user.two_factor_enabled = True

        with patch("blueprints.auth.current_user_id", return_value=1), \
             patch("blueprints.auth.is_valid_csrf_token", return_value=True), \
             patch("blueprints.auth.get_db") as mock_get_db, \
             patch("blueprints.auth.log_event"), \
             patch("blueprints.auth.client_ip", return_value="127.0.0.1"):

            mock_db = MagicMock()
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)
            mock_db.query.return_value.filter.return_value.first.return_value = mock_user
            mock_get_db.return_value = mock_db

            response = client.post(
                "/api/v1/account/2fa/disable",
                json={},
                headers={"X-CSRFToken": "test-csrf-token", "Content-Type": "application/json"},
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        # The flag must have been set to False
        assert mock_user.two_factor_enabled is False

    def test_disable_2fa_returns_success_json(self, client):
        """Response must be JSON with success=True."""
        _make_session(client)

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = "testuser"
        mock_user.two_factor_enabled = True

        with patch("blueprints.auth.current_user_id", return_value=1), \
             patch("blueprints.auth.is_valid_csrf_token", return_value=True), \
             patch("blueprints.auth.get_db") as mock_get_db, \
             patch("blueprints.auth.log_event"), \
             patch("blueprints.auth.client_ip", return_value="127.0.0.1"):

            mock_db = MagicMock()
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)
            mock_db.query.return_value.filter.return_value.first.return_value = mock_user
            mock_get_db.return_value = mock_db

            response = client.post(
                "/api/v1/account/2fa/disable",
                json={},
                headers={"X-CSRFToken": "test-csrf-token", "Content-Type": "application/json"},
            )

        assert response.content_type == "application/json"
        data = response.get_json()
        assert data["success"] is True
        assert "message" in data

    def test_disable_2fa_requires_authentication(self, client):
        """Unauthenticated requests must be rejected."""
        with patch("blueprints.auth.current_user_id", return_value=None):
            response = client.post(
                "/api/v1/account/2fa/disable",
                json={},
                headers={"Content-Type": "application/json"},
            )

        # Should return 401 (AuthenticationError)
        assert response.status_code == 401

    def test_disable_2fa_requires_json_content_type(self, client):
        """Non-JSON content type must be rejected."""
        _make_session(client)

        with patch("blueprints.auth.current_user_id", return_value=1):
            response = client.post(
                "/api/v1/account/2fa/disable",
                data="{}",
                content_type="application/x-www-form-urlencoded",
            )

        assert response.status_code == 400

    def test_disable_2fa_requires_valid_csrf(self, client):
        """Invalid CSRF token must be rejected."""
        _make_session(client)

        with patch("blueprints.auth.current_user_id", return_value=1), \
             patch("blueprints.auth.is_valid_csrf_token", return_value=False), \
             patch("core.api_auth.is_api_key_authenticated", return_value=False):

            response = client.post(
                "/api/v1/account/2fa/disable",
                json={},
                headers={"X-CSRFToken": "bad-token", "Content-Type": "application/json"},
            )

        assert response.status_code == 403

    def test_disable_2fa_logs_audit_event(self, client):
        """Disabling 2FA must log a 2fa.disabled audit event."""
        _make_session(client)

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = "testuser"
        mock_user.two_factor_enabled = True

        with patch("blueprints.auth.current_user_id", return_value=1), \
             patch("blueprints.auth.is_valid_csrf_token", return_value=True), \
             patch("blueprints.auth.get_db") as mock_get_db, \
             patch("blueprints.auth.log_event") as mock_log_event, \
             patch("blueprints.auth.client_ip", return_value="127.0.0.1"):

            mock_db = MagicMock()
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)
            mock_db.query.return_value.filter.return_value.first.return_value = mock_user
            mock_get_db.return_value = mock_db

            client.post(
                "/api/v1/account/2fa/disable",
                json={},
                headers={"X-CSRFToken": "test-csrf-token", "Content-Type": "application/json"},
            )

        mock_log_event.assert_called_once()
        call_args = mock_log_event.call_args
        assert call_args[0][1] == "2fa.disabled"
