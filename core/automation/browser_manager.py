import os
from typing import Optional, Any
from playwright.sync_api import sync_playwright, BrowserContext, Page, Playwright

PROFILE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "browser_session")
os.makedirs(PROFILE_DIR, exist_ok=True)

class BrowserSessionManager:
    """
    Manages a persistent Chromium browser profile so that active logins
    (BMW, Siemens, Mercedes-Benz, LinkedIn, Personio) are retained across runs.
    """
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.profile_dir = PROFILE_DIR
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None

    def start(self) -> tuple:
        self._playwright = sync_playwright().start()
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=self.profile_dir,
            headless=self.headless,
            viewport={"width": 1280, "height": 800},
            slow_mo=100,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ]
        )
        page = self._context.pages[0] if self._context.pages else self._context.new_page()
        return self._playwright, self._context, page

    def open_portal_for_login(self, portal_url: str):
        """Opens the portal URL in a headed browser window so user can log in or handle 2FA."""
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=self.profile_dir,
                headless=False,
                viewport={"width": 1280, "height": 800},
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(portal_url)
            print(f"[Session Helper] Please log in to {portal_url} in the opened window.")
            print("[Session Helper] Your cookies and session will be saved automatically.")

            page.wait_for_timeout(30000)
            context.close()

    def close(self):
        if self._context:
            self._context.close()
        if self._playwright:
            self._playwright.stop()

Tuple_BrowserObjects = Any
