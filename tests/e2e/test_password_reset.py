from playwright.sync_api import Page, expect


def test_password_reset(page: Page):
    """Test password reset flow."""
    page.goto("/reset-password")
    page.fill("input[name='email']", "test@example.com")
    page.click("button[type='submit']")

    # Check for success message
    expect(page.locator(".alert-success")).to_be_visible()
