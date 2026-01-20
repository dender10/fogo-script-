"""
Browser Helpers for Playwright automation.
"""

import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class BrowserHelpers:
    """Helper class for browser automation with Playwright."""

    def __init__(self, page):
        self.page = page

    async def sleep(self, seconds: float) -> None:
        """Async sleep."""
        await asyncio.sleep(seconds)

    async def find_button(self, text: str, timeout: int = 10000):
        """
        Find button by text using multiple strategies.
        Returns locator or None.
        """
        strategies = [
            f"button:has-text('{text}')",
            f"input[value='{text}']",
            f"a:has-text('{text}')",
            f"[role='button']:has-text('{text}')",
            f"button >> text='{text}'",
        ]

        for selector in strategies:
            try:
                locator = self.page.locator(selector).first
                await locator.wait_for(timeout=min(timeout // len(strategies), 3000), state="visible")
                logger.info(f"Found button '{text}' with: {selector}")
                return locator
            except Exception:
                continue

        logger.warning(f"Button not found: {text}")
        return None

    async def click_button(self, text: str, timeout: int = 10000) -> bool:
        """Find button by text and click it."""
        button = await self.find_button(text, timeout)
        if button:
            try:
                await button.click(timeout=timeout)
                logger.info(f"Clicked button: {text}")
                return True
            except Exception as e:
                logger.error(f"Failed to click button '{text}': {e}")
                return False
        return False

    async def type_text(self, selector: str, text: str, delay: int = 50) -> bool:
        """Type text into input field."""
        try:
            locator = self.page.locator(selector).first
            await locator.wait_for(state="visible", timeout=10000)
            await locator.fill("")  # Clear first
            await locator.type(text, delay=delay)
            logger.info(f"Typed text into: {selector}")
            return True
        except Exception as e:
            logger.error(f"Failed to type in '{selector}': {e}")
            return False

    async def wait_for_element(self, selector: str, timeout: int = 30000) -> bool:
        """Wait for element to be visible."""
        try:
            locator = self.page.locator(selector).first
            await locator.wait_for(timeout=timeout, state="visible")
            logger.info(f"Element visible: {selector}")
            return True
        except Exception as e:
            logger.warning(f"Element not found: {selector} - {e}")
            return False

    async def wait_for_load(self, state: str = "domcontentloaded", timeout: int = 30000) -> bool:
        """Wait for page to load."""
        try:
            await self.page.wait_for_load_state(state, timeout=timeout)
            logger.info(f"Page loaded: {state}")
            return True
        except Exception as e:
            logger.warning(f"Page load timeout: {e}")
            return False
