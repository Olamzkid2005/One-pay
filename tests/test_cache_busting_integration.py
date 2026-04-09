"""
Integration test for cache busting in rendered templates.
"""

import pytest
import re
from flask import render_template_string


def test_hashed_url_in_template(app):
    """Test that hashed_url() works in templates."""
    with app.test_request_context():
        # Render a simple template using hashed_url
        template = """
        <link rel="stylesheet" href="{{ hashed_url('css/output.css') }}">
        <script src="{{ hashed_url('js/login.js') }}"></script>
        """
        rendered = render_template_string(template)
        
        # Check that hashed URLs are present
        assert "/static/css/output." in rendered
        assert ".css" in rendered
        assert "/static/js/login." in rendered
        assert ".js" in rendered
        
        # Verify hash format (8 hex chars)
        css_match = re.search(r'/static/css/output\.([a-f0-9]{8})\.css', rendered)
        assert css_match is not None, "CSS hash not found in rendered template"
        
        js_match = re.search(r'/static/js/login\.([a-f0-9]{8})\.js', rendered)
        assert js_match is not None, "JS hash not found in rendered template"


def test_base_template_uses_hashed_urls(app):
    """Test that base.html uses hashed URLs."""
    with app.test_request_context():
        with open("templates/base.html") as f:
            content = f.read()
        
        # Verify base.html uses hashed_url helper
        assert "hashed_url('css/output.css')" in content
        assert "hashed_url('js/loading-states.js')" in content


@pytest.fixture
def app():
    """Create Flask app for testing."""
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    yield app
    
    # Cleanup: Signal background threads to stop
    if hasattr(app, '_shutdown_event'):
        app._shutdown_event.set()
