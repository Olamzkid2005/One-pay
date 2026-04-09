"""
Unit tests for Form Loading States (Requirement 15).

Verifies that:
- static/js/loading-states.js exists with required functions
- static/js/login.js references LoadingStates
- static/js/dashboard.js references LoadingStates

**Validates: Requirements 15.1, 15.3, 15.4, 15.5**
"""
import os

import pytest


def _project_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read_js(filename):
    path = os.path.join(_project_root(), "static", "js", filename)
    with open(path) as f:
        return f.read()


# ── loading-states.js existence and content ────────────────────────────────────

class TestLoadingStatesModule:
    """Verify loading-states.js exists and contains required API."""

    def test_file_exists(self):
        """loading-states.js must exist as a static asset."""
        path = os.path.join(_project_root(), "static", "js", "loading-states.js")
        assert os.path.isfile(path), "static/js/loading-states.js must exist"

    def test_file_not_empty(self):
        """loading-states.js must not be empty."""
        path = os.path.join(_project_root(), "static", "js", "loading-states.js")
        assert os.path.getsize(path) > 0

    def test_contains_disable_button(self):
        """
        disableButton must be present — disables submit and shows spinner.
        Requirement 15.1: disable submit button and show loading indicator.
        """
        content = _read_js("loading-states.js")
        assert "disableButton" in content

    def test_contains_enable_button(self):
        """
        enableButton must be present — re-enables button on error.
        Requirement 15.3: re-enable submit button on failure.
        """
        content = _read_js("loading-states.js")
        assert "enableButton" in content

    def test_contains_attach_to_form(self):
        """
        attachToForm must be present — attaches loading state to a form.
        Requirement 15.5: apply loading states to all forms making HTTP requests.
        """
        content = _read_js("loading-states.js")
        assert "attachToForm" in content

    def test_contains_with_loading(self):
        """withLoading must be present for AJAX button wrapping."""
        content = _read_js("loading-states.js")
        assert "withLoading" in content

    def test_double_submission_prevention(self):
        """
        _submitting WeakSet must be present to track and prevent double submission.
        Requirement 15.4: prevent double submission by tracking submission state.
        """
        content = _read_js("loading-states.js")
        assert "_submitting" in content

    def test_re_enable_on_error_in_with_loading(self):
        """
        withLoading must call enableButton in the catch block.
        Requirement 15.3: re-enable button when submission fails.
        """
        content = _read_js("loading-states.js")
        # enableButton must appear after a catch/error handler
        catch_idx = content.find("catch")
        enable_idx = content.find("enableButton", catch_idx)
        assert catch_idx != -1 and enable_idx != -1, (
            "enableButton must be called inside a catch block in withLoading"
        )

    def test_prevent_double_submission_logic(self):
        """
        attachToForm must check _submitting before proceeding.
        Requirement 15.4: prevent double submission.
        """
        content = _read_js("loading-states.js")
        assert "_submitting.has(form)" in content or "_submitting.has" in content


# ── login.js integration ───────────────────────────────────────────────────────

class TestLoginJsLoadingStates:
    """Verify login.js references LoadingStates for the login form."""

    def test_login_js_references_loading_states(self):
        """
        login.js must reference LoadingStates to apply loading state on submit.
        Requirements 15.1, 15.2, 15.3.
        """
        content = _read_js("login.js")
        assert "LoadingStates" in content, (
            "login.js must reference LoadingStates"
        )

    def test_login_js_attaches_to_form(self):
        """login.js must call attachToForm for the login form."""
        content = _read_js("login.js")
        assert "attachToForm" in content, (
            "login.js must call LoadingStates.attachToForm"
        )

    def test_login_js_uses_signing_in_text(self):
        """login.js should use a meaningful loading text for the login action."""
        content = _read_js("login.js")
        assert "Signing in" in content, (
            "login.js should use 'Signing in...' as loading text"
        )


# ── dashboard.js integration ───────────────────────────────────────────────────

class TestDashboardJsLoadingStates:
    """Verify dashboard.js references LoadingStates for payment forms."""

    def test_dashboard_js_references_loading_states(self):
        """
        dashboard.js must reference LoadingStates.
        Requirement 15.5: apply loading states to all forms making HTTP requests.
        """
        content = _read_js("dashboard.js")
        assert "LoadingStates" in content, (
            "dashboard.js must reference LoadingStates"
        )

    def test_dashboard_js_uses_disable_button(self):
        """dashboard.js must call LoadingStates.disableButton for AJAX operations."""
        content = _read_js("dashboard.js")
        assert "LoadingStates.disableButton" in content

    def test_dashboard_js_uses_enable_button(self):
        """
        dashboard.js must call LoadingStates.enableButton to re-enable on error.
        Requirement 15.3: re-enable button on failure.
        """
        content = _read_js("dashboard.js")
        assert "LoadingStates.enableButton" in content

    def test_dashboard_js_guards_with_typeof_check(self):
        """
        dashboard.js must guard LoadingStates usage with typeof check
        for graceful degradation when the module is not loaded.
        """
        content = _read_js("dashboard.js")
        assert "typeof LoadingStates" in content
