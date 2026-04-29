from playwright.sync_api import sync_playwright

def run_cuj(page):
    page.goto("http://localhost:3000")
    page.wait_for_timeout(500)

    # Mock WebSocket to prevent continuous 404 connection attempts in the background
    page.add_init_script("""
        window.WebSocket = function(url) {
            this.url = url;
            this.readyState = 1;
            this.send = function() {};
            this.close = function() {};
            setTimeout(() => { if (this.onopen) this.onopen(); }, 100);
        };
        window.WebSocket.OPEN = 1;
        window.WebSocket.CONNECTING = 0;
    """)

    # Click Fleet Dashboard to ensure aria-current="page" is present
    page.locator('li', has_text="Fleet Dashboard").click()
    page.wait_for_timeout(500)

    # Focus objective input, enter an objective and deploy
    page.get_by_role("textbox").fill("Test Accessibility")
    page.wait_for_timeout(500)

    page.get_by_role("button", name="Deploy Swarm").click()
    page.wait_for_timeout(500)

    # Take screenshot at the key moment showing the loading spinner and button state
    page.screenshot(path="/home/jules/verification/screenshots/verification.png")
    page.wait_for_timeout(1000)

if __name__ == "__main__":
    import os
    os.makedirs("/home/jules/verification/screenshots", exist_ok=True)
    os.makedirs("/home/jules/verification/videos", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir="/home/jules/verification/videos"
        )
        page = context.new_page()
        try:
            run_cuj(page)
        finally:
            context.close()  # MUST close context to save the video
            browser.close()
