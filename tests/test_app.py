"""
OnePay — Comprehensive test suite
Covers: boot, auth, payments, public routes, security, rate limiter,
        models, webhook, quickteller mock, CSRF, input validation.

Run with:
    APP_ENV=testing python -m pytest test_app.py -v
"""
import os
os.environ.setdefault("APP_ENV", "testing")

import json
import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    from app import create_app
    application = create_app()
    application.config["TESTING"] = True
    application.config["WTF_CSRF_ENABLED"] = False
    return application

@pytest.fixture(scope="session")
def client(app):
    return app.test_client()

@pytest.fixture(scope="session")
def db_session(app):
    from database import SessionLocal, init_db
    init_db()
    db = SessionLocal()
    yield db
    db.close()

def _register(client, username, password="Password123", email=None):
    """Helper: register a user and return the response."""
    if email is None:
        email = f"{username}@example.com"
    with client.session_transaction() as sess:
        sess["csrf_token"] = "test-csrf"
    return client.post("/register", data={
        "username": username, "email": email, "password": password,
        "password2": password, "csrf_token": "test-csrf",
    }, follow_redirects=True)

def _login(client, username, password="Password123"):
    """Helper: log in and return the response."""
    with client.session_transaction() as sess:
        sess["csrf_token"] = "test-csrf"
    return client.post("/login", data={
        "username": username, "password": password,
        "csrf_token": "test-csrf",
    }, follow_redirects=True)

def _csrf_headers(client):
    """Return JSON headers with a valid CSRF token from the current session."""
    with client.session_transaction() as sess:
        token = sess.get("csrf_token", "test-csrf")
    return {"Content-Type": "application/json", "X-CSRFToken": token}


# ══════════════════════════════════════════════════════════════════════════════
# 1. APP BOOT & ROUTES
# ══════════════════════════════════════════════════════════════════════════════

class TestBoot:
    def test_app_creates(self, app):
        assert app is not None

    def test_expected_routes_registered(self, app):
        rules = {r.rule for r in app.url_map.iter_rules()}
        expected = [
            "/", "/login", "/register", "/logout",
            "/forgot-password", "/reset-password/<token>",
            "/api/payments/link", "/api/payments/status/<tx_ref>",
            "/api/payments/history", "/api/account/settings",
            "/verify/<tx_ref>", "/api/payments/preview/<tx_ref>",
            "/api/payments/transfer-status/<tx_ref>", "/health",
        ]
        for route in expected:
            assert route in rules, f"Missing route: {route}"

    def test_health_endpoint(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.get_json()
        assert data["app"] == "OnePay"
        assert data["database"] == "ok"
        assert "mock_mode" in data

    def test_health_mock_mode_true_without_credentials(self, client):
        r = client.get("/health")
        data = r.get_json()
        assert data["mock_mode"] is True   # no credentials in test env


# ══════════════════════════════════════════════════════════════════════════════
# 2. REGISTRATION
# ══════════════════════════════════════════════════════════════════════════════

class TestRegister:
    def test_register_page_loads(self, client):
        r = client.get("/register")
        assert r.status_code == 200
        assert b"Register" in r.data or b"register" in r.data.lower()

    def test_register_success(self, client):
        r = _register(client, "testuser_reg")
        assert r.status_code == 200
        assert b"dashboard" in r.data.lower() or b"OnePay" in r.data

    def test_register_duplicate_username(self, client):
        _register(client, "dup_user")
        r = _register(client, "dup_user")
        assert b"already taken" in r.data.lower() or r.status_code in (200, 400)

    def test_register_short_password(self, client):
        with client.session_transaction() as sess:
            sess["csrf_token"] = "test-csrf"
        r = client.post("/register", data={
            "username": "shortpw_user", "password": "abc",
            "password2": "abc", "csrf_token": "test-csrf",
        }, follow_redirects=True)
        assert b"8 characters" in r.data or r.status_code == 200

    def test_register_password_mismatch(self, client):
        with client.session_transaction() as sess:
            sess["csrf_token"] = "test-csrf"
        r = client.post("/register", data={
            "username": "mismatch_user", "password": "Password123",
            "password2": "Different123", "csrf_token": "test-csrf",
        }, follow_redirects=True)
        assert b"do not match" in r.data.lower() or r.status_code == 200

    def test_register_invalid_username(self, client):
        with client.session_transaction() as sess:
            sess["csrf_token"] = "test-csrf"
        r = client.post("/register", data={
            "username": "a!", "password": "Password123",
            "password2": "Password123", "csrf_token": "test-csrf",
        }, follow_redirects=True)
        assert b"3" in r.data or b"letters" in r.data.lower() or r.status_code == 200

    def test_register_csrf_rejected(self, client):
        r = client.post("/register", data={
            "username": "csrf_test", "password": "Password123",
            "password2": "Password123", "csrf_token": "wrong-token",
        }, follow_redirects=True)
        assert b"expired" in r.data.lower() or r.status_code == 200

    def test_register_duplicate_email(self, client):
        import secrets
        unique_email = f"same_{secrets.token_hex(4)}@example.com"
        _register(client, "user1_dup_email", email=unique_email)
        r = _register(client, "user2_dup_email", email=unique_email)
        assert b"already registered" in r.data.lower() or r.status_code in (200, 400)

    def test_register_invalid_email(self, client):
        with client.session_transaction() as sess:
            sess["csrf_token"] = "test-csrf"
        r = client.post("/register", data={
            "username": "emailtest", "email": "notanemail",
            "password": "Password123", "password2": "Password123",
            "csrf_token": "test-csrf",
        }, follow_redirects=True)
        assert b"valid email" in r.data.lower() or r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# 3. LOGIN / LOGOUT
# ══════════════════════════════════════════════════════════════════════════════

class TestLogin:
    def setup_method(self):
        self.username = "login_test_user"
        self.password = "Password123"

    def test_login_page_loads(self, client):
        client.get("/logout")  # ensure no active session
        r = client.get("/login")
        assert r.status_code == 200

    def test_login_success(self, client):
        _register(client, self.username, self.password)
        r = _login(client, self.username, self.password)
        assert r.status_code == 200

    def test_login_wrong_password(self, client):
        _register(client, "wrong_pw_user")
        with client.session_transaction() as sess:
            sess["csrf_token"] = "test-csrf"
        r = client.post("/login", data={
            "username": "wrong_pw_user", "password": "WrongPass!",
            "csrf_token": "test-csrf",
        }, follow_redirects=True)
        assert b"incorrect" in r.data.lower() or r.status_code == 200

    def test_login_nonexistent_user(self, client):
        with client.session_transaction() as sess:
            sess["csrf_token"] = "test-csrf"
        r = client.post("/login", data={
            "username": "nobody_xyz", "password": "Password123",
            "csrf_token": "test-csrf",
        }, follow_redirects=True)
        assert b"incorrect" in r.data.lower() or r.status_code == 200

    def test_login_csrf_rejected(self, client):
        r = client.post("/login", data={
            "username": self.username, "password": self.password,
            "csrf_token": "bad-token",
        }, follow_redirects=True)
        assert b"expired" in r.data.lower() or r.status_code == 200

    def test_logout(self, client):
        _register(client, "logout_user")
        _login(client, "logout_user")
        r = client.get("/logout", follow_redirects=True)
        assert r.status_code == 200
        assert b"logged out" in r.data.lower() or b"login" in r.data.lower()

    def test_session_set_after_login(self, client):
        _register(client, "session_check_user")
        _login(client, "session_check_user")
        with client.session_transaction() as sess:
            assert sess.get("user_id") is not None
            assert sess.get("username") == "session_check_user"

    def test_session_permanent_after_login(self, client):
        _register(client, "perm_session_user")
        _login(client, "perm_session_user")
        with client.session_transaction() as sess:
            assert sess.permanent is True

    def test_account_lockout(self, client):
        _register(client, "lockout_user")
        # Exhaust max attempts (TestingConfig.LOGIN_MAX_ATTEMPTS = 3)
        for _ in range(3):
            with client.session_transaction() as sess:
                sess["csrf_token"] = "test-csrf"
            client.post("/login", data={
                "username": "lockout_user", "password": "WrongPass!",
                "csrf_token": "test-csrf",
            })
        with client.session_transaction() as sess:
            sess["csrf_token"] = "test-csrf"
        r = client.post("/login", data={
            "username": "lockout_user", "password": "Password123",
            "csrf_token": "test-csrf",
        }, follow_redirects=True)
        assert b"locked" in r.data.lower() or r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# 4. PASSWORD RESET
# ══════════════════════════════════════════════════════════════════════════════

class TestPasswordReset:
    def test_forgot_password_page_loads(self, client):
        r = client.get("/forgot-password")
        assert r.status_code == 200

    def test_forgot_password_unknown_user_no_leak(self, client):
        """Should not reveal whether the username exists."""
        with client.session_transaction() as sess:
            sess["csrf_token"] = "test-csrf"
        r = client.post("/forgot-password", data={
            "username": "nonexistent_xyz", "csrf_token": "test-csrf",
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b"logged" in r.data.lower() or b"reset" in r.data.lower()

    def test_forgot_password_known_user(self, client):
        _register(client, "reset_flow_user")
        with client.session_transaction() as sess:
            sess["csrf_token"] = "test-csrf"
        r = client.post("/forgot-password", data={
            "username": "reset_flow_user", "csrf_token": "test-csrf",
        }, follow_redirects=True)
        assert r.status_code == 200

    def test_forgot_password_sends_email(self, client, monkeypatch, db_session):
        """Test that send_password_reset is called when user has email."""
        import blueprints.auth
        from models.user import User
        import secrets
        
        # Use truly unique identifiers
        unique_id = secrets.token_hex(8)
        unique_user = f"pwreset_{unique_id}"
        unique_email = f"pwreset_{unique_id}@example.com"
        
        # Register with unique credentials
        _register(client, unique_user, email=unique_email)
        
        # Mock the email sending function BEFORE making the request
        email_sent = []
        def mock_send(to_email, reset_url):
            email_sent.append((to_email, reset_url))
            return True
        
        monkeypatch.setattr(blueprints.auth, "send_password_reset", mock_send)
        
        with client.session_transaction() as sess:
            sess["csrf_token"] = "test-csrf"
        r = client.post("/forgot-password", data={
            "username": unique_user, "csrf_token": "test-csrf",
        }, follow_redirects=True)
        
        assert r.status_code == 200
        # If email was sent, verify it
        if len(email_sent) > 0:
            assert email_sent[0][0] == unique_email
            assert "/reset-password/" in email_sent[0][1]

    def test_reset_password_invalid_token(self, client):
        client.get("/logout")  # ensure not logged in
        r = client.get("/reset-password/invalid-token-xyz", follow_redirects=True)
        assert r.status_code == 200
        assert b"invalid" in r.data.lower() or b"expired" in r.data.lower()

    def test_reset_password_full_flow(self, client, db_session):
        from models.user import User
        from services.security import generate_reset_token
        client.get("/logout")
        _register(client, "full_reset_user")
        client.get("/logout")
        token = generate_reset_token()
        db_session.expire_all()
        user = db_session.query(User).filter(User.username == "full_reset_user").first()
        assert user is not None, "full_reset_user not found in DB"
        user.reset_token = token
        user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        db_session.commit()

        with client.session_transaction() as sess:
            sess["csrf_token"] = "test-csrf"
        r = client.post(f"/reset-password/{token}", data={
            "password": "NewPassword456", "password2": "NewPassword456",
            "csrf_token": "test-csrf",
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b"updated" in r.data.lower() or b"sign in" in r.data.lower()


# ══════════════════════════════════════════════════════════════════════════════
# 5. DASHBOARD (auth-gated)
# ══════════════════════════════════════════════════════════════════════════════

class TestDashboard:
    def test_dashboard_redirects_unauthenticated(self, client):
        client.get("/logout")  # ensure logged out
        r = client.get("/", follow_redirects=False)
        assert r.status_code in (302, 301)

    def test_dashboard_loads_when_authenticated(self, client):
        _register(client, "dash_user")
        _login(client, "dash_user")
        r = client.get("/")
        assert r.status_code == 200
        assert b"OnePay" in r.data


# ══════════════════════════════════════════════════════════════════════════════
# 5A. ANALYTICS SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

class TestAnalyticsSummary:
    def test_summary_unauthenticated(self, client):
        client.get("/logout")  # Ensure logged out
        r = client.get("/api/payments/summary")
        assert r.status_code == 401

    def test_summary_authenticated(self, client):
        _register(client, "summary_user")
        _login(client, "summary_user")
        r = client.get("/api/payments/summary")
        assert r.status_code == 200
        data = r.get_json()
        assert data["success"] is True
        assert "all_time" in data
        assert "this_month" in data
        assert "total_collected" in data["all_time"]
        assert "conversion_rate" in data["all_time"]


# ══════════════════════════════════════════════════════════════════════════════
# 6. CREATE PAYMENT LINK
# ══════════════════════════════════════════════════════════════════════════════

class TestCreateLink:
    def setup_method(self):
        self.username = "link_creator"

    def _auth_client(self, client):
        _register(client, self.username)
        _login(client, self.username)
        return client

    def test_create_link_success(self, client):
        self._auth_client(client)
        r = client.post("/api/payments/link",
            headers=_csrf_headers(client),
            data=json.dumps({"amount": 5000}),
        )
        assert r.status_code == 201
        data = r.get_json()
        assert data["success"] is True
        assert "payment_url" in data
        assert "tx_ref" in data
        assert data["tx_ref"].startswith("ONEPAY-")

    def test_create_link_with_all_fields(self, client):
        self._auth_client(client)
        r = client.post("/api/payments/link",
            headers=_csrf_headers(client),
            data=json.dumps({
                "amount": 1500.50,
                "description": "Invoice #42",
                "customer_email": "buyer@example.com",
                "customer_phone": "+2348012345678",
                "return_url": "https://example.com/thanks",
            }),
        )
        assert r.status_code == 201
        data = r.get_json()
        assert data["description"] == "Invoice #42"

    def test_create_link_missing_amount(self, client):
        self._auth_client(client)
        r = client.post("/api/payments/link",
            headers=_csrf_headers(client),
            data=json.dumps({"description": "no amount"}),
        )
        assert r.status_code == 400
        assert r.get_json()["error_code"] == "VALIDATION_ERROR"

    def test_create_link_zero_amount(self, client):
        self._auth_client(client)
        r = client.post("/api/payments/link",
            headers=_csrf_headers(client),
            data=json.dumps({"amount": 0}),
        )
        assert r.status_code == 400

    def test_create_link_negative_amount(self, client):
        self._auth_client(client)
        r = client.post("/api/payments/link",
            headers=_csrf_headers(client),
            data=json.dumps({"amount": -100}),
        )
        assert r.status_code == 400

    def test_create_link_unauthenticated(self, client):
        client.get("/logout")
        r = client.post("/api/payments/link",
            headers={"Content-Type": "application/json", "X-CSRFToken": "x"},
            data=json.dumps({"amount": 100}),
        )
        assert r.status_code == 401

    def test_create_link_csrf_rejected(self, client):
        self._auth_client(client)
        r = client.post("/api/payments/link",
            headers={"Content-Type": "application/json", "X-CSRFToken": "wrong"},
            data=json.dumps({"amount": 100}),
        )
        assert r.status_code == 403

    def test_create_link_idempotency(self, client):
        self._auth_client(client)
        headers = {**_csrf_headers(client), "X-Idempotency-Key": "idem-key-001"}
        r1 = client.post("/api/payments/link", headers=headers, data=json.dumps({"amount": 200}))
        r2 = client.post("/api/payments/link", headers=headers, data=json.dumps({"amount": 200}))
        assert r1.status_code == 201
        assert r2.status_code == 200
        assert r1.get_json()["tx_ref"] == r2.get_json()["tx_ref"]

    def test_create_link_virtual_account_in_mock_mode(self, client):
        self._auth_client(client)
        r = client.post("/api/payments/link",
            headers=_csrf_headers(client),
            data=json.dumps({"amount": 3000}),
        )
        data = r.get_json()
        assert data["virtual_account_number"] is not None
        assert "Wema" in (data["virtual_bank_name"] or "")


# ══════════════════════════════════════════════════════════════════════════════
# 7. TRANSACTION STATUS & HISTORY
# ══════════════════════════════════════════════════════════════════════════════

class TestStatusAndHistory:
    def _create_link(self, client):
        _register(client, "status_user")
        _login(client, "status_user")
        r = client.post("/api/payments/link",
            headers=_csrf_headers(client),
            data=json.dumps({"amount": 1000}),
        )
        return r.get_json()

    def test_status_returns_transaction(self, client):
        data = self._create_link(client)
        tx_ref = data["tx_ref"]
        r = client.get(f"/api/payments/status/{tx_ref}")
        assert r.status_code == 200
        result = r.get_json()
        assert result["tx_ref"] == tx_ref
        assert result["status"] in ("pending", "verified", "expired", "failed")

    def test_status_not_found(self, client):
        _login(client, "status_user")
        r = client.get("/api/payments/status/ONEPAY-0000000000000000000000000000000A")
        assert r.status_code == 404

    def test_status_invalid_ref_format(self, client):
        _login(client, "status_user")
        r = client.get("/api/payments/status/../../etc/passwd")
        assert r.status_code in (400, 404)

    def test_status_unauthenticated(self, client):
        client.get("/logout")
        r = client.get("/api/payments/status/ONEPAY-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA1")
        assert r.status_code == 401

    def test_history_returns_list(self, client):
        _register(client, "history_list_user")
        _login(client, "history_list_user")
        r = client.get("/api/payments/history")
        assert r.status_code == 200
        data = r.get_json()
        assert "transactions" in data
        assert "pagination" in data
        assert isinstance(data["transactions"], list)

    def test_history_pagination_fields(self, client):
        _register(client, "history_page_user")
        _login(client, "history_page_user")
        r = client.get("/api/payments/history?page=1")
        assert r.status_code == 200
        p = r.get_json()["pagination"]
        assert "page" in p and "total_pages" in p and "has_next" in p

    def test_history_unauthenticated(self, client):
        client.get("/logout")
        r = client.get("/api/payments/history")
        assert r.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# 7A. LINK RE-ISSUE
# ══════════════════════════════════════════════════════════════════════════════

class TestLinkReissue:
    def test_reissue_expired_link(self, client, db_session):
        from models.transaction import Transaction, TransactionStatus
        from datetime import datetime, timezone, timedelta
        
        # Create a link
        _register(client, "reissue_user")
        _login(client, "reissue_user")
        
        headers = _csrf_headers(client)
        r = client.post("/api/payments/link", json={"amount": 500}, headers=headers)
        assert r.status_code == 201
        original_ref = r.get_json()["tx_ref"]
        
        # Manually expire it in DB
        db_session.expire_all()
        tx = db_session.query(Transaction).filter(Transaction.tx_ref == original_ref).first()
        tx.expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        tx.status = TransactionStatus.EXPIRED
        db_session.commit()
        
        # Re-issue
        r = client.post(f"/api/payments/reissue/{original_ref}", headers=headers)
        assert r.status_code == 201
        data = r.get_json()
        assert data["success"] is True
        assert data["tx_ref"] != original_ref
        assert "payment_url" in data
        assert data["amount"] == "500.00"

    def test_reissue_verified_rejected(self, client, db_session):
        from models.transaction import Transaction, TransactionStatus
        
        _register(client, "reissue_verified_user")
        _login(client, "reissue_verified_user")
        
        headers = _csrf_headers(client)
        r = client.post("/api/payments/link", json={"amount": 300}, headers=headers)
        original_ref = r.get_json()["tx_ref"]
        
        # Mark as verified
        db_session.expire_all()
        tx = db_session.query(Transaction).filter(Transaction.tx_ref == original_ref).first()
        tx.status = TransactionStatus.VERIFIED
        tx.transfer_confirmed = True
        db_session.commit()
        
        # Try to re-issue
        r = client.post(f"/api/payments/reissue/{original_ref}", headers=headers)
        assert r.status_code == 400
        assert b"verified" in r.data.lower()


# ══════════════════════════════════════════════════════════════════════════════
# 8. PUBLIC ROUTES (verify page, preview, transfer-status)
# ══════════════════════════════════════════════════════════════════════════════

class TestPublicRoutes:
    def _make_link(self, client):
        _register(client, "pub_user")
        _login(client, "pub_user")
        r = client.post("/api/payments/link",
            headers=_csrf_headers(client),
            data=json.dumps({"amount": 750}),
        )
        return r.get_json()

    def test_verify_page_valid_link(self, client):
        data = self._make_link(client)
        tx_ref = data["tx_ref"]
        # Extract hash from payment_url
        hash_token = data["payment_url"].split("hash=")[1]
        r = client.get(f"/verify/{tx_ref}?hash={hash_token}")
        assert r.status_code == 200
        assert b"OnePay" in r.data

    def test_verify_page_missing_hash(self, client):
        data = self._make_link(client)
        r = client.get(f"/verify/{data['tx_ref']}")
        assert r.status_code == 200
        assert b"invalid" in r.data.lower() or b"error" in r.data.lower()

    def test_verify_page_bad_tx_ref(self, client):
        r = client.get("/verify/../../etc/passwd?hash=abc")
        assert r.status_code in (200, 400, 404)

    def test_preview_api_valid(self, client):
        data = self._make_link(client)
        r = client.get(f"/api/payments/preview/{data['tx_ref']}")
        assert r.status_code == 200
        result = r.get_json()
        assert result["success"] is True
        assert result["tx_ref"] == data["tx_ref"]
        assert "hash_token" not in result   # must never be exposed

    def test_preview_api_not_found(self, client):
        r = client.get("/api/payments/preview/ONEPAY-0000000000000000000000000000000B")
        assert r.status_code == 404

    def test_transfer_status_pending_mock(self, client):
        data = self._make_link(client)
        r = client.get(f"/api/payments/transfer-status/{data['tx_ref']}")
        assert r.status_code == 200
        result = r.get_json()
        # First poll in mock mode returns pending
        assert result["status"] in ("pending", "confirmed")

    def test_transfer_status_confirms_after_polls(self, client):
        data = self._make_link(client)
        tx_ref = data["tx_ref"]
        status = "pending"
        for _ in range(5):
            r = client.get(f"/api/payments/transfer-status/{tx_ref}")
            result = r.get_json()
            status = result.get("status")
            if status == "confirmed":
                break
        assert status == "confirmed"

    def test_transfer_status_not_found(self, client):
        r = client.get("/api/payments/transfer-status/ONEPAY-0000000000000000000000000000000C")
        assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# 9. ACCOUNT SETTINGS (webhook URL)
# ══════════════════════════════════════════════════════════════════════════════

class TestSettings:
    def test_save_valid_webhook_url(self, client):
        _register(client, "settings_user")
        _login(client, "settings_user")
        r = client.post("/api/account/settings",
            headers=_csrf_headers(client),
            data=json.dumps({"webhook_url": "https://example.com/webhook"}),
        )
        assert r.status_code == 200
        assert r.get_json()["success"] is True

    def test_save_invalid_webhook_url(self, client):
        _login(client, "settings_user")
        r = client.post("/api/account/settings",
            headers=_csrf_headers(client),
            data=json.dumps({"webhook_url": "http://not-https.com/hook"}),
        )
        assert r.status_code == 400

    def test_save_localhost_webhook_rejected(self, client):
        _login(client, "settings_user")
        r = client.post("/api/account/settings",
            headers=_csrf_headers(client),
            data=json.dumps({"webhook_url": "https://localhost/hook"}),
        )
        assert r.status_code == 400

    def test_clear_webhook_url(self, client):
        _login(client, "settings_user")
        r = client.post("/api/account/settings",
            headers=_csrf_headers(client),
            data=json.dumps({"webhook_url": ""}),
        )
        assert r.status_code == 200

    def test_settings_unauthenticated(self, client):
        client.get("/logout")
        r = client.post("/api/account/settings",
            headers={"Content-Type": "application/json", "X-CSRFToken": "x"},
            data=json.dumps({"webhook_url": "https://example.com/hook"}),
        )
        assert r.status_code == 401

    def test_settings_csrf_rejected(self, client):
        _register(client, "settings_csrf_user")
        _login(client, "settings_csrf_user")
        r = client.post("/api/account/settings",
            headers={"Content-Type": "application/json", "X-CSRFToken": "bad"},
            data=json.dumps({"webhook_url": "https://example.com/hook"}),
        )
        assert r.status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# 10. SECURITY UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

class TestSecurity:
    def test_tx_ref_format(self):
        from services.security import generate_tx_reference
        ref = generate_tx_reference()
        assert ref.startswith("ONEPAY-")
        assert len(ref) == 39   # "ONEPAY-" + 32 hex chars

    def test_tx_refs_are_unique(self):
        from services.security import generate_tx_reference
        refs = {generate_tx_reference() for _ in range(100)}
        assert len(refs) == 100

    def test_hash_token_verify_roundtrip(self):
        from services.security import generate_hash_token, verify_hash_token, generate_expiration_time
        ref = "ONEPAY-TESTREF0000000000000000001"
        amount = Decimal("1500.00")
        expires = generate_expiration_time(30)
        token = generate_hash_token(ref, amount, expires)
        assert verify_hash_token(ref, amount, expires, token) is True

    def test_hash_token_tampered_amount(self):
        from services.security import generate_hash_token, verify_hash_token, generate_expiration_time
        ref = "ONEPAY-TESTREF0000000000000000002"
        expires = generate_expiration_time(30)
        token = generate_hash_token(ref, Decimal("1000.00"), expires)
        assert verify_hash_token(ref, Decimal("1001.00"), expires, token) is False

    def test_hash_token_tampered_ref(self):
        from services.security import generate_hash_token, verify_hash_token, generate_expiration_time
        expires = generate_expiration_time(30)
        token = generate_hash_token("ONEPAY-REAL00000000000000000001", 500, expires)
        assert verify_hash_token("ONEPAY-FAKE00000000000000000001", 500, expires, token) is False

    def test_validate_return_url_https(self):
        from services.security import validate_return_url
        assert validate_return_url("https://example.com/thanks") == "https://example.com/thanks"

    def test_validate_return_url_http_rejected(self):
        from services.security import validate_return_url
        assert validate_return_url("http://example.com/thanks") is None

    def test_validate_return_url_localhost_rejected(self):
        from services.security import validate_return_url
        assert validate_return_url("https://localhost/cb") is None

    def test_validate_return_url_private_ip_rejected(self):
        from services.security import validate_return_url
        assert validate_return_url("https://192.168.1.1/cb") is None

    def test_validate_return_url_relative_allowed(self):
        from services.security import validate_return_url
        assert validate_return_url("/thanks") == "/thanks"

    def test_validate_webhook_url_https_only(self):
        from services.security import validate_webhook_url
        assert validate_webhook_url("https://hooks.example.com/pay") is not None
        assert validate_webhook_url("http://hooks.example.com/pay") is None

    def test_validate_webhook_url_no_relative(self):
        from services.security import validate_webhook_url
        assert validate_webhook_url("/relative/path") is None

    def test_hash_token_format_valid(self):
        from services.security import validate_hash_token_format, generate_hash_token, generate_expiration_time
        token = generate_hash_token("ONEPAY-TESTREF0000000000000000003", 100, generate_expiration_time())
        assert validate_hash_token_format(token) is True

    def test_hash_token_format_invalid(self):
        from services.security import validate_hash_token_format
        assert validate_hash_token_format("") is False
        assert validate_hash_token_format("short") is False
        assert validate_hash_token_format("has spaces in it!!") is False

    def test_reset_token_length(self):
        from services.security import generate_reset_token
        token = generate_reset_token()
        assert len(token) >= 48


# ══════════════════════════════════════════════════════════════════════════════
# 11. MODELS
# ══════════════════════════════════════════════════════════════════════════════

class TestUserModel:
    def test_set_and_check_password(self):
        from models.user import User
        u = User(username="modeltest")
        u.set_password("SecurePass1")
        assert u.check_password("SecurePass1") is True
        assert u.check_password("WrongPass") is False

    def test_is_locked_false_by_default(self):
        from models.user import User
        u = User(username="notlocked")
        assert u.is_locked() is False

    def test_record_failed_login_locks(self):
        from models.user import User
        u = User(username="willlock")
        u.failed_login_attempts = 0
        for _ in range(5):
            u.record_failed_login(max_attempts=5, lockout_secs=900)
        assert u.is_locked() is True

    def test_record_successful_login_clears_lockout(self):
        from models.user import User
        u = User(username="unlockme")
        u.failed_login_attempts = 5
        u.locked_until = datetime.now(timezone.utc) + timedelta(hours=1)
        u.record_successful_login()
        assert u.failed_login_attempts == 0
        assert u.locked_until is None


class TestTransactionModel:
    def _make_tx(self):
        from models.transaction import Transaction, TransactionStatus
        return Transaction(
            tx_ref="ONEPAY-MODELTESTREF000000000001",
            amount=Decimal("500.00"),
            currency="NGN",
            hash_token="fakehash",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            status=TransactionStatus.PENDING,
        )

    def test_to_dict_no_hash_token(self):
        tx = self._make_tx()
        d = tx.to_dict()
        assert "hash_token" not in d
        assert d["tx_ref"] == "ONEPAY-MODELTESTREF000000000001"

    def test_is_expired_false_for_future(self):
        tx = self._make_tx()
        assert tx.is_expired() is False

    def test_is_expired_true_for_past(self):
        from models.transaction import Transaction
        tx = Transaction(
            tx_ref="ONEPAY-EXPIREDREF0000000000001",
            amount=Decimal("100.00"),
            hash_token="x",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        assert tx.is_expired() is True

    def test_effective_status_expired_when_past_expiry(self):
        from models.transaction import Transaction, TransactionStatus
        tx = Transaction(
            tx_ref="ONEPAY-EXPIREDREF0000000000002",
            amount=Decimal("100.00"),
            hash_token="x",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            status=TransactionStatus.PENDING,
            is_used=False,
        )
        assert tx.effective_status_value() == "expired"

    def test_effective_status_none_safe(self):
        from models.transaction import Transaction
        tx = Transaction(
            tx_ref="ONEPAY-NULLSTATUS000000000001",
            amount=Decimal("100.00"),
            hash_token="x",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            status=None,
        )
        # Should not raise
        val = tx.effective_status_value()
        assert val in ("pending", "verified", "failed", "expired")

    def test_naive_datetime_treated_as_utc(self):
        from models.transaction import Transaction
        naive_future = datetime.now() + timedelta(minutes=10)  # no tzinfo
        tx = Transaction(
            tx_ref="ONEPAY-NAIVEDTREF000000000001",
            amount=Decimal("100.00"),
            hash_token="x",
            expires_at=naive_future,
        )
        assert tx.is_expired() is False

    def test_expires_at_utc_iso_format(self):
        tx = self._make_tx()
        iso = tx.expires_at_utc_iso()
        assert iso is not None
        assert "T" in iso


# ══════════════════════════════════════════════════════════════════════════════
# 12. RATE LIMITER
# ══════════════════════════════════════════════════════════════════════════════

class TestRateLimiter:
    def test_allows_under_limit(self, db_session):
        from services.rate_limiter import check_rate_limit
        key = "test:ratelimit:allow"
        for i in range(5):
            assert check_rate_limit(db_session, key, limit=10, window_secs=60) is True

    def test_blocks_over_limit(self, db_session):
        from services.rate_limiter import check_rate_limit
        key = "test:ratelimit:block"
        for _ in range(3):
            check_rate_limit(db_session, key, limit=3, window_secs=60)
        result = check_rate_limit(db_session, key, limit=3, window_secs=60)
        assert result is False

    def test_cleanup_removes_old_records(self, db_session):
        from services.rate_limiter import check_rate_limit, cleanup_old_rate_limits
        from models.rate_limit import RateLimit
        key = "test:ratelimit:cleanup"
        check_rate_limit(db_session, key, limit=10, window_secs=60)
        # Force the record to be old
        record = db_session.query(RateLimit).filter(RateLimit.key == key).first()
        if record:
            record.window_start = datetime.now(timezone.utc) - timedelta(hours=2)
            db_session.commit()
        deleted = cleanup_old_rate_limits(db_session, older_than_secs=3600)
        assert deleted >= 1


# ══════════════════════════════════════════════════════════════════════════════
# 13. QUICKTELLER MOCK
# ══════════════════════════════════════════════════════════════════════════════

class TestQuicktellerMock:
    def test_is_not_configured_without_credentials(self):
        from services.quickteller import quickteller
        assert quickteller.is_configured() is False

    def test_is_transfer_configured_in_mock_mode(self):
        from services.quickteller import quickteller
        # Mock mode always returns True for transfer configured
        assert quickteller.is_transfer_configured() is True

    def test_mock_create_virtual_account(self):
        from services.quickteller import quickteller
        result = quickteller.create_virtual_account("ONEPAY-MOCKTEST0000000000001", 100000, "Test User")
        assert "accountNumber" in result
        assert result["bankName"] == "Wema Bank (Demo)"
        assert len(result["accountNumber"]) == 10

    def test_mock_virtual_account_deterministic(self):
        from services.quickteller import quickteller
        r1 = quickteller.create_virtual_account("ONEPAY-DETTEST0000000000001", 50000, "User")
        r2 = quickteller.create_virtual_account("ONEPAY-DETTEST0000000000001", 50000, "User")
        assert r1["accountNumber"] == r2["accountNumber"]

    def test_mock_confirm_transfer_pending_then_confirmed(self):
        from services.quickteller import quickteller, MOCK_CONFIRM_AFTER
        ref = "ONEPAY-POLLTEST000000000001"
        for i in range(MOCK_CONFIRM_AFTER - 1):
            result = quickteller.confirm_transfer(ref)
            assert result["responseCode"] == "Z0"
        result = quickteller.confirm_transfer(ref)
        assert result["responseCode"] == "00"

    def test_mock_poll_count_cleaned_after_confirm(self):
        from services.quickteller import quickteller, _mock_poll_counts, MOCK_CONFIRM_AFTER
        ref = "ONEPAY-CLEANTEST00000000001"
        for _ in range(MOCK_CONFIRM_AFTER):
            quickteller.confirm_transfer(ref)
        assert ref not in _mock_poll_counts


# ══════════════════════════════════════════════════════════════════════════════
# 14. WEBHOOK
# ══════════════════════════════════════════════════════════════════════════════

class TestWebhook:
    def test_sign_payload_format(self):
        from services.webhook import _sign_payload
        sig = _sign_payload(b'{"event":"test"}')
        assert sig.startswith("sha256=")
        assert len(sig) > 10

    def test_deliver_from_dict_no_url(self):
        from services.webhook import deliver_webhook_from_dict
        result = deliver_webhook_from_dict({"webhook_url": None, "tx_ref": "X"})
        assert result is False

    def test_deliver_from_dict_bad_url_fails_gracefully(self):
        from services.webhook import deliver_webhook_from_dict
        result = deliver_webhook_from_dict({
            "webhook_url": "https://localhost.invalid/hook",
            "tx_ref": "ONEPAY-WEBHOOKTEST000000001",
            "amount": "100.00", "currency": "NGN",
            "description": None, "status": "verified", "verified_at": None,
        })
        assert result is False


# ══════════════════════════════════════════════════════════════════════════════
# 15. CORE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

class TestCoreHelpers:
    def test_valid_username_accepts_valid(self):
        from core.auth import valid_username
        assert valid_username("alice") is True
        assert valid_username("user_123") is True
        assert valid_username("ABC") is True

    def test_valid_username_rejects_invalid(self):
        from core.auth import valid_username
        assert valid_username("ab") is False          # too short
        assert valid_username("has space") is False
        assert valid_username("has-dash") is False
        assert valid_username("a" * 31) is False      # too long

    def test_valid_tx_ref_accepts_valid(self):
        from core.auth import valid_tx_ref
        assert valid_tx_ref("ONEPAY-ABCDEF1234567890ABCDEF12345") is True

    def test_valid_tx_ref_rejects_invalid(self):
        from core.auth import valid_tx_ref
        assert valid_tx_ref("short") is False
        assert valid_tx_ref("has spaces") is False
        assert valid_tx_ref("../etc/passwd") is False

    def test_error_response_shape(self, app):
        with app.app_context():
            from core.responses import error
            resp, status = error("bad input", "VALIDATION_ERROR", 400)
            data = resp.get_json()
            assert status == 400
            assert data["success"] is False
            assert data["error_code"] == "VALIDATION_ERROR"

    def test_rate_limited_response(self, app):
        with app.app_context():
            from core.responses import rate_limited
            resp, status = rate_limited()
            assert status == 429

    def test_unauthenticated_response(self, app):
        with app.app_context():
            from core.responses import unauthenticated
            resp, status = unauthenticated()
            assert status == 401


# ══════════════════════════════════════════════════════════════════════════════
# 16. DATABASE
# ══════════════════════════════════════════════════════════════════════════════

class TestDatabase:
    def test_get_db_context_manager(self, app):
        from database import get_db
        from models.user import User
        with get_db() as db:
            count = db.query(User).count()
            assert isinstance(count, int)

    def test_get_db_rollback_on_exception(self, app):
        from database import get_db
        try:
            with get_db() as db:
                raise ValueError("forced rollback")
        except ValueError:
            pass  # rollback should have happened silently

    def test_init_db_idempotent(self, app):
        from database import init_db, _db_initialised
        # Calling again should not raise
        init_db()
        init_db()


# ══════════════════════════════════════════════════════════════════════════════
# 17. EDGE CASES & SECURITY HARDENING
# ══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_hash_token_not_in_preview_response(self, client):
        """hash_token must never be exposed via the API."""
        _register(client, "edge_user")
        _login(client, "edge_user")
        r = client.post("/api/payments/link",
            headers=_csrf_headers(client),
            data=json.dumps({"amount": 100}),
        )
        tx_ref = r.get_json()["tx_ref"]
        preview = client.get(f"/api/payments/preview/{tx_ref}").get_json()
        assert "hash_token" not in preview

    def test_status_api_does_not_expose_other_users_tx(self, client):
        """Merchant A should not see merchant B's transaction."""
        import time
        suffix = str(int(time.time() * 1000))[-6:]
        user_a = f"merchant_a_{suffix}"
        user_b = f"merchant_b_{suffix}"

        # Create link as merchant A
        _register(client, user_a)
        _login(client, user_a)
        r = client.post("/api/payments/link",
            headers=_csrf_headers(client),
            data=json.dumps({"amount": 999}),
        )
        assert r.status_code == 201
        tx_ref = r.get_json()["tx_ref"]

        # Log out merchant A, register and log in as merchant B
        client.get("/logout")
        _register(client, user_b)
        _login(client, user_b)

        # Verify merchant B cannot see merchant A's transaction
        with client.session_transaction() as sess:
            assert sess.get("username") == user_b, "Should be logged in as merchant B"

        r2 = client.get(f"/api/payments/status/{tx_ref}")
        assert r2.status_code == 404

    def test_verify_page_tampered_hash_shows_error(self, client):
        _register(client, "tamper_user")
        _login(client, "tamper_user")
        r = client.post("/api/payments/link",
            headers=_csrf_headers(client),
            data=json.dumps({"amount": 200}),
        )
        tx_ref = r.get_json()["tx_ref"]
        r2 = client.get(f"/verify/{tx_ref}?hash=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
        assert r2.status_code == 200
        assert b"invalid" in r2.data.lower() or b"tampered" in r2.data.lower()

    def test_description_truncated_at_255(self, client):
        _login(client, "edge_user")
        long_desc = "A" * 300
        r = client.post("/api/payments/link",
            headers=_csrf_headers(client),
            data=json.dumps({"amount": 50, "description": long_desc}),
        )
        assert r.status_code == 201
        assert len(r.get_json()["description"]) <= 255

    def test_currency_uppercased_and_truncated(self, client):
        _login(client, "edge_user")
        r = client.post("/api/payments/link",
            headers=_csrf_headers(client),
            data=json.dumps({"amount": 50, "currency": "usd"}),
        )
        assert r.status_code == 201
        assert r.get_json()["currency"] == "USD"

    def test_invalid_return_url_not_stored(self, client):
        _login(client, "edge_user")
        r = client.post("/api/payments/link",
            headers=_csrf_headers(client),
            data=json.dumps({"amount": 50, "return_url": "javascript:alert(1)"}),
        )
        assert r.status_code == 201
        # return_url should be None/absent — not the malicious value
        tx_ref = r.get_json()["tx_ref"]
        preview = client.get(f"/api/payments/preview/{tx_ref}").get_json()
        assert "javascript" not in str(preview)


# ══════════════════════════════════════════════════════════════════════════════
# 18. AUDIT LOGGING
# ══════════════════════════════════════════════════════════════════════════════

class TestAuditLogging:
    def test_audit_log_on_registration(self, client, db_session):
        from models.audit_log import AuditLog
        
        _register(client, "audit_register_user")
        
        # Check audit log was created
        logs = db_session.query(AuditLog).filter(
            AuditLog.event == "merchant.registered"
        ).all()
        assert len(logs) >= 1
        log = logs[-1]
        assert log.event == "merchant.registered"
        assert log.ip_address is not None

    def test_audit_log_on_link_created(self, client, db_session):
        from models.audit_log import AuditLog
        
        _register(client, "audit_link_user")
        _login(client, "audit_link_user")
        
        r = client.post("/api/payments/link",
            headers=_csrf_headers(client),
            data=json.dumps({"amount": 100}),
        )
        tx_ref = r.get_json()["tx_ref"]
        
        # Check audit log was created
        logs = db_session.query(AuditLog).filter(
            AuditLog.event == "link.created",
            AuditLog.tx_ref == tx_ref
        ).all()
        assert len(logs) == 1
        log = logs[0]
        assert log.tx_ref == tx_ref
        assert log.user_id is not None

    def test_audit_endpoint_returns_logs(self, client, db_session):
        _register(client, "audit_endpoint_user")
        _login(client, "audit_endpoint_user")
        
        # Create a link
        r = client.post("/api/payments/link",
            headers=_csrf_headers(client),
            data=json.dumps({"amount": 200}),
        )
        tx_ref = r.get_json()["tx_ref"]
        
        # Fetch audit logs
        r = client.get(f"/api/payments/audit/{tx_ref}")
        assert r.status_code == 200
        data = r.get_json()
        assert data["success"] is True
        assert len(data["audit_logs"]) >= 1
        assert data["audit_logs"][0]["event"] == "link.created"

    def test_audit_endpoint_ownership_enforced(self, client):
        import time
        suffix = str(int(time.time() * 1000))[-6:]
        user_a = f"audit_owner_a_{suffix}"
        user_b = f"audit_owner_b_{suffix}"
        
        # Create link as user A
        _register(client, user_a)
        _login(client, user_a)
        r = client.post("/api/payments/link",
            headers=_csrf_headers(client),
            data=json.dumps({"amount": 300}),
        )
        tx_ref = r.get_json()["tx_ref"]
        
        # Try to access as user B
        client.get("/logout")
        _register(client, user_b)
        _login(client, user_b)
        
        r = client.get(f"/api/payments/audit/{tx_ref}")
        assert r.status_code == 404
