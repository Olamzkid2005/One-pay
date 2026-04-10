from playwright.sync_api import Page, expect


def test_user_registration(page: Page):
    """Test user registration flow."""
    page.goto("/register")
    page.fill("input[name='username']", "testuser")
    page.fill("input[name='email']", "test@example.com")
    page.fill("input[name='password']", "TestPassword123!")
    page.click("button[type='submit']")
    expect(page).to_have_url("/dashboard")
