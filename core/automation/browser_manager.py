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
        launch_kwargs = {
            "user_data_dir": self.profile_dir,
            "headless": self.headless,
            "viewport": {"width": 1280, "height": 800},
            "locale": "de-DE",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                "--no-sandbox"
            ]
        }
        try:
            self._context = self._playwright.chromium.launch_persistent_context(channel="chrome", **launch_kwargs)
        except Exception:
            try:
                self._context = self._playwright.chromium.launch_persistent_context(channel="msedge", **launch_kwargs)
            except Exception:
                self._context = self._playwright.chromium.launch_persistent_context(**launch_kwargs)
        cookie_file = os.path.join(self.profile_dir, "cookies.json")
        if os.path.exists(cookie_file):
            try:
                import json
                with open(cookie_file, "r", encoding="utf-8") as f:
                    cookies = json.load(f)
                if cookies and isinstance(cookies, list):
                    valid_cookies = []
                    for c in cookies:
                        if c.get("name") and c.get("value"):
                            entry = {
                                "name": c["name"],
                                "value": c["value"],
                                "path": c.get("path", "/")
                            }
                            if c.get("domain"):
                                entry["domain"] = c["domain"]
                            else:
                                entry["url"] = "https://de.indeed.com"
                            if "secure" in c: entry["secure"] = c["secure"]
                            if "httpOnly" in c: entry["httpOnly"] = c["httpOnly"]
                            valid_cookies.append(entry)
                    if valid_cookies:
                        self._context.add_cookies(valid_cookies)
            except Exception:
                pass

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
