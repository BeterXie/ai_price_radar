"""Run inside the production image with its read-only, non-root restrictions."""
from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch_persistent_context('/data/browser_profile', headless=False)
    page = browser.new_page()
    page.goto('data:text/html,<title>collector-smoke</title><p>ready</p>')
    assert page.title() == 'collector-smoke'
    browser.add_cookies([{'name':'collector-smoke','value':'ready','domain':'example.com','path':'/','expires':2000000000}])
    browser.close()
    browser = playwright.chromium.launch_persistent_context('/data/browser_profile', headless=False)
    assert any(cookie['name'] == 'collector-smoke' for cookie in browser.cookies())
    browser.close()
print('Headed Chromium works in isolated read-only collector')
