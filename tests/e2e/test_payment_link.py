from playwright.sync_api import Page, expect


def test_create_payment_link(page: Page):
    """Test payment link creation flow."""
    page.goto("/login")
    page.fill("input[name='username']", "testuser")
    page.fill("input[name='password']", "TestPassword123!")
    page.click("button[type='submit']")

    page.goto("/payments/create")
    page.fill("input[name='amount']", "1000.00")
    page.select_option("select[name='currency']", "NGN")
    page.fill("input[name='description']", "Test payment")
    page.click("button[type='submit']")

    expect(page).to_have_url("/payments/success")
