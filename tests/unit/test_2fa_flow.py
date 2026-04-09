"""
Unit tests for the 2FA flow.

Validates:
  - Requirement 4.1: WHEN a user with two_factor_enabled=True logs in,
    THE Auth_System SHALL require 2FA verification before granting full access.
  - Requirement 4.2: WHEN the 2FA code is incorrect, THE Auth_System SHALL
    increment a failed attempt counter.
  - Requirement 4.3: WHEN failed 2FA attempts exceed 5 within 15 minutes,
    THE Auth_System SHALL temporarily lock the account.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Minimal Flask app for route-level tests."""
    from app import app as flask_app
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret-key-that-is-long-enough-32chars"
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def _set_pre_2fa_session(client, user_id=1):
    """Helper: put pre_2fa_user_id into the session."""
    with client.session_transaction() as sess:
        sess["pre_2fa_user_id"] = user_id
        sess["csrf_token"] = "test-csrf"


# ---------------------------------------------------------------------------
# User model unit tests
# ---------------------------------------------------------------------------


class TestUserModel2FAMethods:
    """Direct unit tests for User model 2FA helper methods."""

    def _make_user(self):
        """Create a bare User instance (no DB needed)."""
        from models.user import User
        u = User()
        u.failed_2fa_attempts = 0
        u.twofa_locked_until = None
        return u

    # ── is_2fa_locked ──────────────────────────────────────────────────────

    def test_is_2fa_locked_returns_false_when_no_lockout(self):
        """is_2fa_locked() is False when twofa_locked_until is None."""
        user = self._make_user()
        assert user.is_2fa_locked() is False

    def test_is_2fa_locked_returns_true_when_locked_in_future(self):
        """is_2fa_locked() is True when lockout expires in the future."""
        user = self._make_user()
        user.twofa_locked_until = datetime.now(timezone.utc) + timedelta(minutes=10)
        assert user.is_2fa_locked() is True

    def test_is_2fa_locked_returns_false_when_lockout_expired(self):
        """is_2fa_locked() is False when lockout time has already passed."""
        user = self._make_user()
        user.twofa_locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert user.is_2fa_locked() is False

    def test_is_2fa_locked_handles_naive_datetime(self):
        """is_2fa_locked() handles naive datetimes by treating them as UTC."""
        user = self._make_user()
        # Naive datetime in the future
        user.twofa_locked_until = datetime.utcnow() + timedelta(minutes=5)
        assert user.is_2fa_locked() is True

    # ── record_failed_2fa ──────────────────────────────────────────────────

    def test_record_failed_2fa_increments_counter(self):
        """record_failed_2fa() increments failed_2fa_attempts by 1."""
        user = self._make_user()
        user.record_failed_2fa()
        assert user.failed_2fa_attempts == 1

    def test_record_failed_2fa_increments_multiple_times(self):
        """record_failed_2fa() accumulates across multiple calls."""
        user = self._make_user()
        for _ in range(3):
            user.record_failed_2fa()
        assert user.failed_2fa_attempts == 3

    def test_record_failed_2fa_no_lockout_below_threshold(self):
        """No lockout is set when attempts are below the threshold (default 5)."""
        user = self._make_user()
        for _ in range(4):
            user.record_failed_2fa()
        assert user.twofa_locked_until is None

    def test_record_failed_2fa_locks_at_threshold(self):
        """Account is locked when failed attempts reach the threshold (default 5)."""
        user = self._make_user()
        for _ in range(5):
            user.record_failed_2fa()
        assert user.twofa_locked_until is not None
        assert user.is_2fa_locked() is True

    def test_record_failed_2fa_lockout_duration(self):
        """Lockout duration is approximately window_secs (default 900s = 15 min)."""
        user = self._make_user()
        before = datetime.now(timezone.utc)
        for _ in range(5):
            user.record_failed_2fa()
        after = datetime.now(timezone.utc)

        locked_until = user.twofa_locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)

        # Should be ~15 minutes from now
        assert locked_until >= before + timedelta(seconds=890)
        assert locked_until <= after + timedelta(seconds=910)

    def test_record_failed_2fa_custom_threshold(self):
        """Custom max_attempts parameter is respected."""
        user = self._make_user()
        user.record_failed_2fa(max_attempts=3)
        user.record_failed_2fa(max_attempts=3)
        assert user.twofa_locked_until is None  # not yet at 3
        user.record_failed_2fa(max_attempts=3)
        assert user.is_2fa_locked() is True

    def test_record_failed_2fa_custom_window(self):
        """Custom window_secs parameter sets the lockout duration."""
        user = self._make_user()
        before = datetime.now(timezone.utc)
        for _ in range(5):
            user.record_failed_2fa(window_secs=60)
        after = datetime.now(timezone.utc)

        locked_until = user.twofa_locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)

        assert locked_until >= before + timedelta(seconds=55)
        assert locked_until <= after + timedelta(seconds=65)

    # ── record_successful_2fa ──────────────────────────────────────────────

    def test_record_successful_2fa_resets_counter(self):
        """record_successful_2fa() resets failed_2fa_attempts to 0."""
        user = self._make_user()
        user.failed_2fa_attempts = 3
        user.record_successful_2fa()
        assert user.failed_2fa_attempts == 0

    def test_record_successful_2fa_clears_lockout(self):
        """record_successful_2fa() clears twofa_locked_until."""
        user = self._make_user()
        user.twofa_locked_until = datetime.now(timezone.utc) + timedelta(minutes=10)
        user.record_successful_2fa()
        assert user.twofa_locked_until is None
        assert user.is_2fa_locked() is False

    def test_record_successful_2fa_idempotent_on_clean_state(self):
        """record_successful_2fa() is safe to call when no lockout is active."""
        user = self._make_user()
        user.record_successful_2fa()
        assert user.failed_2fa_attempts == 0
        assert user.twofa_locked_until is None


# ---------------------------------------------------------------------------
# Route-level tests: 2FA required for enabled users (Req 4.1)
# ---------------------------------------------------------------------------


class TestLoginRedirectsTo2FA:
    """Req 4.1 — Login must redirect to verify-2fa for users with two_factor_enabled=True."""

    def _mock_db(self, user):
        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.first.return_value = user
        return mock_db

    def test_login_redirects_to_verify_2fa_when_enabled(self, client):
        """POST /api/v1/login with valid credentials and two_factor_enabled=True redirects to verify-2fa."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = "testuser"
        mock_user.is_active = True
        mock_user.two_factor_enabled = True
        mock_user.is_locked.return_value = False
        mock_user.check_password.return_value = True

        with patch("blueprints.auth.is_valid_csrf_token", return_value=True), \
             patch("blueprints.auth.check_rate_limit", return_value=True), \
             patch("blueprints.auth.get_db") as mock_get_db, \
             patch("blueprints.auth.log_event"), \
             patch("blueprints.auth.client_ip", return_value="127.0.0.1"), \
             patch("services.email.send_2fa_code"):

            mock_get_db.return_value = self._mock_db(mock_user)

            response = client.post(
                "/api/v1/login",
                data={"username": "testuser", "password": "pass", "csrf_token": "tok"},
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert "verify-2fa" in response.headers["Location"]

    def test_login_does_not_redirect_to_2fa_when_disabled(self, client):
        """POST /api/v1/login with two_factor_enabled=False must NOT redirect to verify-2fa."""
        mock_user = MagicMock()
        mock_user.id = 2
        mock_user.username = "nofa_user"
        mock_user.is_active = True
        mock_user.two_factor_enabled = False
        mock_user.is_locked.return_value = False
        mock_user.check_password.return_value = True

        with patch("blueprints.auth.is_valid_csrf_token", return_value=True), \
             patch("blueprints.auth.check_rate_limit", return_value=True), \
             patch("blueprints.auth.get_db") as mock_get_db, \
             patch("blueprints.auth.log_event"), \
             patch("blueprints.auth.client_ip", return_value="127.0.0.1"), \
             patch("blueprints.auth._regenerate_session_secure"):

            mock_get_db.return_value = self._mock_db(mock_user)

            response = client.post(
                "/api/v1/login",
                data={"username": "nofa_user", "password": "pass", "csrf_token": "tok"},
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert "verify-2fa" not in response.headers["Location"]

    def test_login_stores_pre_2fa_user_id_in_session(self, client):
        """pre_2fa_user_id must be stored in session when 2FA is required."""
        mock_user = MagicMock()
        mock_user.id = 42
        mock_user.username = "testuser"
        mock_user.is_active = True
        mock_user.two_factor_enabled = True
        mock_user.is_locked.return_value = False
        mock_user.check_password.return_value = True

        with patch("blueprints.auth.is_valid_csrf_token", return_value=True), \
             patch("blueprints.auth.check_rate_limit", return_value=True), \
             patch("blueprints.auth.get_db") as mock_get_db, \
             patch("blueprints.auth.log_event"), \
             patch("blueprints.auth.client_ip", return_value="127.0.0.1"), \
             patch("services.email.send_2fa_code"):

            mock_get_db.return_value = self._mock_db(mock_user)

            client.post(
                "/api/v1/login",
                data={"username": "testuser", "password": "pass", "csrf_token": "tok"},
            )

        with client.session_transaction() as sess:
            assert sess.get("pre_2fa_user_id") == 42


# ---------------------------------------------------------------------------
# Route-level tests: failed attempt counter (Req 4.2)
# ---------------------------------------------------------------------------


class TestFailedAttemptCounter:
    """Req 4.2 — Wrong 2FA code must increment the failed attempt counter."""

    def _mock_db_with_user(self, user):
        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.first.return_value = user
        return mock_db

    def test_wrong_code_calls_record_failed_2fa(self, client):
        """Submitting a wrong code must call user.record_failed_2fa()."""
        _set_pre_2fa_session(client, user_id=1)

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.is_2fa_locked.return_value = False
        mock_user.email_otp = "123456"
        mock_user.email_otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        mock_user.failed_2fa_attempts = 0

        with patch("blueprints.auth.is_valid_csrf_token", return_value=True), \
             patch("blueprints.auth.check_rate_limit", return_value=True), \
             patch("blueprints.auth.get_db") as mock_get_db, \
             patch("blueprints.auth.log_event"), \
             patch("blueprints.auth.client_ip", return_value="127.0.0.1"):

            mock_get_db.return_value = self._mock_db_with_user(mock_user)

            client.post(
                "/api/v1/verify-2fa",
                data={
                    "csrf_token": "test-csrf",
                    "code1": "9", "code2": "9", "code3": "9",
                    "code4": "9", "code5": "9", "code6": "9",
                },
            )

        mock_user.record_failed_2fa.assert_called_once()

    def test_correct_code_calls_record_successful_2fa(self, client):
        """Submitting the correct code must call user.record_successful_2fa()."""
        _set_pre_2fa_session(client, user_id=1)

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = "testuser"
        mock_user.is_2fa_locked.return_value = False
        mock_user.email_otp = "123456"
        mock_user.email_otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

        with patch("blueprints.auth.is_valid_csrf_token", return_value=True), \
             patch("blueprints.auth.check_rate_limit", return_value=True), \
             patch("blueprints.auth.get_db") as mock_get_db, \
             patch("blueprints.auth.log_event"), \
             patch("blueprints.auth.client_ip", return_value="127.0.0.1"), \
             patch("blueprints.auth._regenerate_session_secure"):

            mock_get_db.return_value = self._mock_db_with_user(mock_user)

            client.post(
                "/api/v1/verify-2fa",
                data={
                    "csrf_token": "test-csrf",
                    "code1": "1", "code2": "2", "code3": "3",
                    "code4": "4", "code5": "5", "code6": "6",
                },
            )

        mock_user.record_successful_2fa.assert_called_once()

    def test_wrong_code_returns_error_page(self, client):
        """Wrong code must return 200 with the verify_2fa template (not a redirect)."""
        _set_pre_2fa_session(client, user_id=1)

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.is_2fa_locked.return_value = False
        mock_user.email_otp = "123456"
        mock_user.email_otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

        with patch("blueprints.auth.is_valid_csrf_token", return_value=True), \
             patch("blueprints.auth.check_rate_limit", return_value=True), \
             patch("blueprints.auth.get_db") as mock_get_db, \
             patch("blueprints.auth.log_event"), \
             patch("blueprints.auth.client_ip", return_value="127.0.0.1"):

            mock_get_db.return_value = self._mock_db_with_user(mock_user)

            response = client.post(
                "/api/v1/verify-2fa",
                data={
                    "csrf_token": "test-csrf",
                    "code1": "0", "code2": "0", "code3": "0",
                    "code4": "0", "code5": "0", "code6": "0",
                },
                follow_redirects=False,
            )

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Route-level tests: account lockout (Req 4.3)
# ---------------------------------------------------------------------------


class TestAccountLockout:
    """Req 4.3 — Account must be locked after 5 failed 2FA attempts."""

    def _mock_db_with_user(self, user):
        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.first.return_value = user
        return mock_db

    def test_locked_user_cannot_verify_2fa(self, client):
        """A locked user must see an error and not be allowed to verify."""
        _set_pre_2fa_session(client, user_id=1)

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.is_2fa_locked.return_value = True  # already locked

        with patch("blueprints.auth.is_valid_csrf_token", return_value=True), \
             patch("blueprints.auth.check_rate_limit", return_value=True), \
             patch("blueprints.auth.get_db") as mock_get_db, \
             patch("blueprints.auth.log_event"), \
             patch("blueprints.auth.client_ip", return_value="127.0.0.1"):

            mock_get_db.return_value = self._mock_db_with_user(mock_user)

            response = client.post(
                "/api/v1/verify-2fa",
                data={
                    "csrf_token": "test-csrf",
                    "code1": "1", "code2": "2", "code3": "3",
                    "code4": "4", "code5": "5", "code6": "6",
                },
                follow_redirects=False,
            )

        # Must stay on the 2FA page (200), not redirect to dashboard
        assert response.status_code == 200
        # record_failed_2fa must NOT be called when already locked
        mock_user.record_failed_2fa.assert_not_called()

    def test_lockout_triggered_after_5_failed_attempts(self):
        """User model locks after exactly 5 failed attempts (Req 4.3)."""
        from models.user import User
        user = User()
        user.failed_2fa_attempts = 0
        user.twofa_locked_until = None

        for i in range(1, 5):
            user.record_failed_2fa()
            assert user.twofa_locked_until is None, f"Should not be locked after {i} attempts"

        user.record_failed_2fa()  # 5th attempt
        assert user.is_2fa_locked() is True

    def test_lockout_lasts_15_minutes(self):
        """Lockout window is 15 minutes (900 seconds) by default."""
        from models.user import User
        user = User()
        user.failed_2fa_attempts = 0
        user.twofa_locked_until = None

        before = datetime.now(timezone.utc)
        for _ in range(5):
            user.record_failed_2fa()

        locked_until = user.twofa_locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)

        # Should be ~15 minutes (900 seconds) from now
        delta = (locked_until - before).total_seconds()
        assert 890 <= delta <= 910

    def test_locked_user_get_request_shows_error(self, client):
        """GET /api/v1/verify-2fa for a locked user must show the locked error message."""
        _set_pre_2fa_session(client, user_id=1)

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.is_2fa_locked.return_value = True

        with patch("blueprints.auth.is_valid_csrf_token", return_value=True), \
             patch("blueprints.auth.check_rate_limit", return_value=True), \
             patch("blueprints.auth.get_db") as mock_get_db, \
             patch("blueprints.auth.log_event"), \
             patch("blueprints.auth.client_ip", return_value="127.0.0.1"):

            mock_get_db.return_value = self._mock_db_with_user(mock_user)

            response = client.post(
                "/api/v1/verify-2fa",
                data={"csrf_token": "test-csrf",
                      "code1": "1", "code2": "2", "code3": "3",
                      "code4": "4", "code5": "5", "code6": "6"},
            )

        assert response.status_code == 200
        assert b"locked" in response.data.lower()
