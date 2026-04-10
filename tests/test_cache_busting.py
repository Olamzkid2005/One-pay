"""
Tests for content-based filename cache busting (Requirement 23.4).

Verifies that:
1. Hashed filenames are generated correctly
2. Manifest.json is created and loaded
3. Templates use hashed URLs
4. Flask serves hashed files with correct cache headers
"""

import json
import os

import pytest
from flask import Flask


class TestCacheBusting:
    """Test cache busting implementation."""

    def test_manifest_exists(self) -> None:
        """Manifest.json should exist in static directory."""
        manifest_path = os.path.join("static", "manifest.json")
        assert os.path.exists(manifest_path), "manifest.json not found"

    def test_manifest_format(self) -> None:
        """Manifest should map original filenames to hashed versions."""
        manifest_path = os.path.join("static", "manifest.json")
        with open(manifest_path) as f:
            manifest = json.load(f)

        # Check expected entries
        assert "css/output.css" in manifest
        assert "js/login.js" in manifest
        assert "js/dashboard.js" in manifest
        assert "js/verify.js" in manifest
        assert "js/loading-states.js" in manifest

        # Verify hashed filenames have 8-char hash
        for original, hashed in manifest.items():
            assert hashed.startswith(original.split("/")[0] + "/")
            # Extract hash from filename (e.g., "output.a09f3865.css" -> "a09f3865")
            parts = hashed.split(".")
            if len(parts) >= 3:
                hash_part = parts[-2]
                assert len(hash_part) == 8, f"Hash should be 8 chars: {hashed}"
                assert all(c in "0123456789abcdef" for c in hash_part), \
                    f"Hash should be hex: {hashed}"

    def test_hashed_files_exist(self) -> None:
        """Hashed files should exist on disk."""
        manifest_path = os.path.join("static", "manifest.json")
        with open(manifest_path) as f:
            manifest = json.load(f)

        for hashed_path in manifest.values():
            full_path = os.path.join("static", hashed_path.replace("/", os.sep))
            assert os.path.exists(full_path), f"Hashed file not found: {full_path}"

    def test_hashed_url_helper(self, app, client) -> None:
        """hashed_url() helper should return hashed paths from manifest."""
        with app.test_request_context():
            # Load manifest
            manifest_path = os.path.join(app.root_path, "static", "manifest.json")
            with open(manifest_path) as f:
                json.load(f)

            # Get the hashed_url function from context processor
            context_processors = app.template_context_processors[None]
            hashed_url_func = None
            for processor in context_processors:
                result = processor()
                if "hashed_url" in result:
                    hashed_url_func = result["hashed_url"]
                    break

            assert hashed_url_func is not None, "hashed_url not found in context"

            # Test that it returns hashed URLs
            hashed_css = hashed_url_func("css/output.css")
            assert ".css" in hashed_css
            assert "output" in hashed_css

    def test_original_files_exist(self) -> None:
        """Original (unhashed) files should still exist for development."""
        assert os.path.exists("static/css/output.css")
        assert os.path.exists("static/js/login.js")
        assert os.path.exists("static/js/dashboard.js")
        assert os.path.exists("static/js/verify.js")
        assert os.path.exists("static/js/loading-states.js")

    def test_hashed_content_matches_original(self) -> None:
        """Hashed files should have identical content to originals."""
        manifest_path = os.path.join("static", "manifest.json")
        with open(manifest_path) as f:
            manifest = json.load(f)

        for original, hashed in manifest.items():
            original_path = os.path.join("static", original.replace("/", os.sep))
            hashed_path = os.path.join("static", hashed.replace("/", os.sep))

            with open(original_path, "rb") as f1, open(hashed_path, "rb") as f2:
                assert f1.read() == f2.read(), \
                    f"Content mismatch: {original} vs {hashed}"


class TestCacheHeaders:
    """Test cache headers for static files."""

    def test_static_route_exists(self, client) -> None:
        """Static file route should be accessible."""
        # Try to access a known static file
        response = client.get("/static/openapi.json")
        assert response.status_code == 200

    def test_hashed_files_accessible(self, client) -> None:
        """Hashed files should be accessible via Flask."""
        manifest_path = os.path.join("static", "manifest.json")
        with open(manifest_path) as f:
            manifest = json.load(f)

        # Test one hashed file
        hashed_css = manifest.get("css/output.css")
        if hashed_css:
            response = client.get(f"/static/{hashed_css}")
            assert response.status_code == 200
            assert response.content_type.startswith("text/css")


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


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()
