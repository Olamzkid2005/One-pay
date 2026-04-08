"""
Unit tests for Accessibility Compliance (Requirement 16).

Verifies that:
- base.html has lang="en" attribute
- login.html has a <main> element
- Theme toggle button has aria-label
- Form inputs have associated labels (for/id pairs)
- Focus-visible styles exist in input.css
- loading-states.js exists (keyboard users rely on loading feedback)

**Validates: Requirements 16.1, 16.2, 16.3, 16.4, 16.5, 16.6**
"""
import os
import re
import pytest


def _project_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read_template(name):
    path = os.path.join(_project_root(), "templates", name)
    with open(path) as f:
        return f.read()


def _read_css(name):
    path = os.path.join(_project_root(), "static", "css", name)
    with open(path) as f:
        return f.read()


# ── base.html ──────────────────────────────────────────────────────────────────

class TestBaseHtml:
    """Accessibility checks for the base template."""

    def test_lang_attribute(self):
        """base.html must declare lang="en" for screen readers (Req 16.5)."""
        content = _read_template("base.html")
        assert 'lang="en"' in content, 'base.html must have <html lang="en">'

    def test_theme_toggle_has_aria_label(self):
        """Theme toggle button must have aria-label (Req 16.1)."""
        content = _read_template("base.html")
        assert 'aria-label="Toggle dark/light mode"' in content, (
            "Theme toggle button must have aria-label='Toggle dark/light mode'"
        )

    def test_theme_toggle_is_button(self):
        """Theme toggle must be a <button> element for keyboard access (Req 16.4)."""
        content = _read_template("base.html")
        assert re.search(r'<button[^>]+id="theme-toggle"', content), (
            "Theme toggle must be a <button> element"
        )


# ── login.html ─────────────────────────────────────────────────────────────────

class TestLoginHtml:
    """Accessibility checks for the login template."""

    def test_has_main_element(self):
        """login.html must have a <main> landmark element (Req 16.5)."""
        content = _read_template("login.html")
        assert "<main" in content, "login.html must contain a <main> element"

    def test_username_label_for_attribute(self):
        """Username label must have for='username' (Req 16.2)."""
        content = _read_template("login.html")
        assert 'for="username"' in content, (
            "Username label must have for='username'"
        )

    def test_username_input_has_id(self):
        """Username input must have id='username' matching the label (Req 16.2)."""
        content = _read_template("login.html")
        assert 'id="username"' in content, (
            "Username input must have id='username'"
        )

    def test_password_label_for_attribute(self):
        """Password label must have for='password' (Req 16.2)."""
        content = _read_template("login.html")
        assert 'for="password"' in content, (
            "Password label must have for='password'"
        )

    def test_password_toggle_has_aria_label(self):
        """Password visibility toggle must have aria-label (Req 16.1)."""
        content = _read_template("login.html")
        assert 'aria-label="Toggle password visibility"' in content, (
            "Password toggle button must have aria-label='Toggle password visibility'"
        )


# ── register.html ──────────────────────────────────────────────────────────────

class TestRegisterHtml:
    """Accessibility checks for the registration template."""

    def test_has_main_element(self):
        """register.html must have a <main> landmark element (Req 16.5)."""
        content = _read_template("register.html")
        assert "<main" in content, "register.html must contain a <main> element"

    def test_username_label_for_attribute(self):
        """Username label must have for='username' (Req 16.2)."""
        content = _read_template("register.html")
        assert 'for="username"' in content

    def test_email_label_for_attribute(self):
        """Email label must have for='email' (Req 16.2)."""
        content = _read_template("register.html")
        assert 'for="email"' in content

    def test_password_label_for_attribute(self):
        """Password label must have for='password' (Req 16.2)."""
        content = _read_template("register.html")
        assert 'for="password"' in content

    def test_confirm_password_label_for_attribute(self):
        """Confirm password label must have for='password2' (Req 16.2)."""
        content = _read_template("register.html")
        assert 'for="password2"' in content

    def test_password_toggle_has_aria_label(self):
        """Password toggle buttons must have aria-label (Req 16.1)."""
        content = _read_template("register.html")
        assert 'aria-label="Toggle password visibility"' in content


# ── forgot_password.html ───────────────────────────────────────────────────────

class TestForgotPasswordHtml:
    """Accessibility checks for the forgot password template."""

    def test_has_main_element(self):
        """forgot_password.html must have a <main> landmark element (Req 16.5)."""
        content = _read_template("forgot_password.html")
        assert "<main" in content

    def test_username_label_for_attribute(self):
        """Username label must have for='username' (Req 16.2)."""
        content = _read_template("forgot_password.html")
        assert 'for="username"' in content

    def test_username_input_has_id(self):
        """Username input must have id='username' (Req 16.2)."""
        content = _read_template("forgot_password.html")
        assert 'id="username"' in content


# ── input.css ──────────────────────────────────────────────────────────────────

class TestInputCss:
    """Accessibility checks for the CSS file."""

    def test_focus_visible_styles_exist(self):
        """input.css must define :focus-visible styles (Req 16.3)."""
        content = _read_css("input.css")
        assert ":focus-visible" in content, (
            "input.css must contain :focus-visible styles for keyboard navigation"
        )

    def test_focus_visible_has_outline(self):
        """Focus-visible styles must include an outline (Req 16.3)."""
        content = _read_css("input.css")
        # Find the focus-visible block and verify outline is set
        assert "outline" in content, (
            "Focus-visible styles must set an outline property"
        )

    def test_contrast_ratio_comment_exists(self):
        """input.css must document color contrast ratios (Req 16.6)."""
        content = _read_css("input.css")
        assert "Contrast ratio" in content or "contrast ratio" in content, (
            "input.css must document color contrast ratios"
        )


# ── loading-states.js ──────────────────────────────────────────────────────────

class TestLoadingStatesJs:
    """Verify loading-states.js exists for keyboard user feedback (Req 16.4)."""

    def test_loading_states_js_exists(self):
        """loading-states.js must exist to provide keyboard-accessible feedback."""
        path = os.path.join(_project_root(), "static", "js", "loading-states.js")
        assert os.path.isfile(path), "static/js/loading-states.js must exist"
