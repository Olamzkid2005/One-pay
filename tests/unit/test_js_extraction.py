"""
Unit tests for JavaScript extraction (Requirement 14).

Verifies that:
- static/js/login.js exists as an external file
- templates/login.html references login.js and does not contain inline script logic
- The login page renders correctly via the Flask test client

**Validates: Requirements 14.2, 14.4, 14.5**
"""
import os
import pytest


# ── File existence tests ───────────────────────────────────────────────────────

class TestLoginJsFile:
    """Verify the extracted login.js file exists and is referenced correctly."""

    def test_login_js_file_exists(self):
        """
        Test that static/js/login.js exists as an external file.

        Requirement 14.1: THE System SHALL extract inline JavaScript from
        login.html to a separate static/js/login.js file.
        """
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        js_path = os.path.join(project_root, "static", "js", "login.js")
        assert os.path.isfile(js_path), "static/js/login.js must exist"

    def test_login_js_is_not_empty(self):
        """
        Test that login.js contains actual JavaScript content.

        Requirement 14.4: THE System SHALL maintain functionality after extraction.
        """
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        js_path = os.path.join(project_root, "static", "js", "login.js")
        assert os.path.getsize(js_path) > 0, "static/js/login.js must not be empty"

    def test_login_js_contains_toggle_password(self):
        """
        Test that login.js contains the togglePassword function.

        Requirement 14.4: Core functionality must be preserved after extraction.
        """
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        js_path = os.path.join(project_root, "static", "js", "login.js")
        with open(js_path) as f:
            content = f.read()
        assert "togglePassword" in content, "login.js must contain togglePassword function"


# ── Template reference tests ───────────────────────────────────────────────────

class TestLoginHtmlReferences:
    """Verify login.html references the external JS file correctly."""

    def _read_login_html(self):
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        html_path = os.path.join(project_root, "templates", "login.html")
        with open(html_path) as f:
            return f.read()

    def test_login_html_references_login_js(self):
        """
        Test that login.html has a script tag referencing login.js.

        Requirement 14.1: The extracted file must be referenced in the template.
        """
        content = self._read_login_html()
        assert "login.js" in content, "login.html must reference login.js"

    def test_login_html_uses_defer_attribute(self):
        """
        Test that the login.js script tag uses the defer attribute.

        Requirement 14.1: Script tag should use defer for performance.
        """
        content = self._read_login_html()
        assert "defer" in content, "login.js script tag must use defer attribute"

    def test_login_html_has_no_inline_toggle_password(self):
        """
        Test that login.html does not contain inline togglePassword definition.

        Requirement 14.1: JavaScript logic must be in the external file, not inline.
        """
        content = self._read_login_html()
        assert "function togglePassword" not in content, (
            "togglePassword must not be defined inline in login.html"
        )


# ── Flask integration tests ────────────────────────────────────────────────────

class TestLoginPageRenders:
    """Verify the login page renders correctly using the Flask test client."""

    @pytest.fixture
    def client(self):
        """Create a Flask test client."""
        import sys
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        from app import create_app
        flask_app = create_app()
        flask_app.config["TESTING"] = True
        flask_app.config["WTF_CSRF_ENABLED"] = False
        with flask_app.test_client() as c:
            yield c

    def test_login_page_returns_200(self, client):
        """
        Test that the login page loads with HTTP 200.

        Requirement 14.4: THE System SHALL maintain functionality after extraction.
        """
        response = client.get("/api/v1/login")
        assert response.status_code == 200

    def test_login_page_contains_login_js_reference(self, client):
        """
        Test that the rendered login page includes a reference to login.js.

        Requirement 14.4: The rendered page must load the external JS file.
        """
        response = client.get("/api/v1/login")
        assert b"login.js" in response.data

    def test_login_page_contains_csp_nonce(self, client):
        """
        Test that the rendered login page includes a nonce in inline scripts.

        Requirement 14.5: THE System SHALL use nonce-based CSP for inline handlers.
        """
        response = client.get("/api/v1/login")
        assert b"nonce=" in response.data

    def test_login_page_csp_header_contains_nonce(self, client):
        """
        Test that the CSP response header includes a nonce directive.

        Requirement 14.5: The CSP header must include the nonce for inline scripts.
        """
        response = client.get("/api/v1/login")
        csp = response.headers.get("Content-Security-Policy", "")
        assert "nonce-" in csp, "CSP header must contain a nonce directive"
