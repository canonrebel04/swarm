from playwright.sync_api import sync_playwright
import time
import os

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # Mock window.WebSocket to avoid connection errors
    page.add_init_script("window.WebSocket = function() { this.onopen = null; this.onmessage = null; this.onclose = null; this.send = function() {}; };")

    # Setup dialog handler to mock swarm_api_key prompt
    page.on("dialog", lambda dialog: dialog.accept("mock-api-key"))

    page.goto("http://localhost:3000")
    time.sleep(2)  # Wait for render

    page.screenshot(path="screenshot.png")
    print("Screenshot saved to screenshot.png")

    browser.close()
