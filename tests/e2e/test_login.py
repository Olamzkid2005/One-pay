from playwright.sync_api import Page, expect


def test_user_login(page: Page):
    """Test user login flow."""
    page.goto("/login")
    page.fill("input[name='username']", "testuser")
    page.fill("input[name='password']", "TestPassword123!")
    page.click("button[type='submit']")
    expect(page).to_have_url("/dashboard")
