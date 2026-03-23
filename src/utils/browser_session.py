from dataclasses import dataclass
from enum import StrEnum

from playwright.async_api import async_playwright


@dataclass
class NavigationCommand(StrEnum):
    """Command usable for navigation"""

    TAB = "Tab"
    SHIFT_TAB = "Shift+Tab"
    SPACE = "Space"
    ENTER = "Enter"
    ESCAPE = "Escape"


class BrowserSession:
    def __init__(self) -> None:
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def is_initialized(self) -> bool:
        """Return True when browser and current page are ready to use."""
        if self.browser is None or not self.browser.is_connected():
            return False
        if self.page is None or self.page.is_closed():
            if not self._rebind_page_from_browser():
                return False
        if self.page is None or self.page.is_closed():
            return False
        return True

    async def create_session(self) -> None:
        """Create a fresh Playwright browser/context/page session."""
        await self.close_session()
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-setuid-sandbox"],
        )
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()
        await self.goto("about:blank")

    async def press_key(
        self, key: NavigationCommand, tab_delay_ms: int = 50, expand_delay_ms: int = 1000
    ) -> None:
        """Press a keyboard key on the active page and wait for UI updates."""
        if not self.is_initialized():
            raise RuntimeError("Browser session not initialized")
        await self.page.keyboard.press(key)
        if tab_delay_ms > 0 and "Tab" in key:
            await self.page.wait_for_timeout(tab_delay_ms)
        elif expand_delay_ms > 0:
            await self.page.wait_for_timeout(expand_delay_ms)

    async def goto(self, url: str) -> None:
        """Navigate the active page to the given URL."""
        if not self.is_initialized():
            raise RuntimeError("Browser session not initialized")
        await self.page.goto(url, wait_until="networkidle")

    async def refresh_page(self) -> None:
        """Reload the active page and wait for network idle."""
        if not self.is_initialized():
            raise RuntimeError("Browser session not initialized")
        await self.page.reload(wait_until="networkidle")
        self._rebind_page_from_browser()

    async def close_session(self) -> None:
        """Close page/context/browser/playwright and clear local references."""
        try:
            if self.page is not None:
                try:
                    await self.page.close()
                except Exception:
                    pass

            if self.context is not None:
                try:
                    await self.context.close()
                except Exception:
                    pass

            if self.browser is not None:
                try:
                    await self.browser.close()
                except Exception:
                    pass

            if self.playwright is not None:
                try:
                    await self.playwright.stop()
                except Exception:
                    pass
        finally:
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None

    def _rebind_page_from_browser(self) -> bool:
        """Try to rebind to an existing open page from browser contexts."""
        if self.context is not None and self.context in self.browser.contexts:
            if self.context.pages:
                self.page = self.context.pages[0]
                return True

        for context in self.browser.contexts:
            if context.pages:
                self.context = context
                self.page = context.pages[0]
                return True

        return False


BROWSER_SESSION = BrowserSession()
