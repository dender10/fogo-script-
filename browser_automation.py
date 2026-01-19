import os
import subprocess
import time
import asyncio
import urllib.request
import json
from playwright.async_api import async_playwright


# Configuration
DEBUGGING_PORT = 9222
CHROME_USER_DATA = r"C:\Users\Admin\AppData\Local\Google\Chrome\User Data"
PROFILE_DIR = "Profile 3"
DEFAULT_URL = "https://valiant.trade"


class BrowserAutomation:
    def __init__(self, profile_dir: str = PROFILE_DIR, default_url: str = DEFAULT_URL):
        self.profile_dir = profile_dir
        self.default_url = default_url
        self.browser = None
        self.page = None
        self.chrome_process = None
        self.playwright = None

    def find_chrome(self) -> str:
        """Search common Windows paths for chrome.exe."""
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]

        for path in paths:
            if os.path.exists(path):
                print(f"Found Chrome at: {path}")
                return path

        raise FileNotFoundError("Chrome not found in common locations")

    def kill_chrome(self) -> None:
        """Kill all Chrome processes."""
        print("Killing existing Chrome processes...")
        subprocess.run(
            ["taskkill", "/F", "/IM", "chrome.exe", "/T"],
            capture_output=True,
            shell=True
        )

    def get_ws_endpoint(self, port: int = DEBUGGING_PORT, max_retries: int = 60) -> str:
        """Poll debugging endpoint until Chrome responds."""
        url = f"http://127.0.0.1:{port}/json/version"

        for attempt in range(1, max_retries + 1):
            try:
                print(f"Waiting for Chrome... ({attempt}/{max_retries})")
                with urllib.request.urlopen(url, timeout=1) as response:
                    data = json.loads(response.read().decode())
                    ws_url = data.get("webSocketDebuggerUrl")
                    if ws_url:
                        print(f"Chrome ready! WebSocket: {ws_url}")
                        return ws_url
            except Exception:
                time.sleep(1)

        raise TimeoutError(f"Chrome did not respond after {max_retries} seconds")

    def spawn_chrome(self) -> None:
        """Spawn Chrome with debugging enabled."""
        chrome_path = self.find_chrome()

        args = [
            chrome_path,
            f"--remote-debugging-port={DEBUGGING_PORT}",
            f"--user-data-dir={CHROME_USER_DATA}",
            f"--profile-directory={self.profile_dir}",
            "--start-maximized",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-session-crashed-bubble",
        ]

        if self.default_url:
            args.append(self.default_url)

        print(f"Spawning Chrome with profile: {self.profile_dir}")

        # Windows-specific: hide console window
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        self.chrome_process = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            startupinfo=startupinfo,
        )

        print(f"Chrome spawned (PID: {self.chrome_process.pid})")

    async def launch(self) -> None:
        """Main launch function - spawns Chrome and connects via CDP."""
        # Step 1: Kill existing Chrome
        self.kill_chrome()
        time.sleep(2)

        # Step 2: Spawn Chrome
        self.spawn_chrome()

        # Step 3: Get WebSocket endpoint (polls until ready)
        ws_endpoint = self.get_ws_endpoint()

        # Step 4: Connect Playwright via CDP
        print("Connecting Playwright via CDP...")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.connect_over_cdp(ws_endpoint)

        # Step 5: Get existing page
        contexts = self.browser.contexts
        if contexts and contexts[0].pages:
            self.page = contexts[0].pages[0]
            print(f"Connected to existing page: {self.page.url}")
        else:
            self.page = await self.browser.new_page()
            if self.default_url:
                await self.page.goto(self.default_url)
            print("Created new page")

        print("Browser automation ready!")

    async def close(self) -> None:
        """Disconnect and cleanup."""
        print("Closing browser automation...")

        if self.browser:
            await self.browser.close()

        if self.playwright:
            await self.playwright.stop()

        if self.chrome_process:
            self.chrome_process.terminate()

        print("Browser closed.")

    # Helper functions for automation

    async def goto(self, url: str, wait_until: str = "domcontentloaded") -> None:
        """Navigate to URL."""
        await self.page.goto(url, wait_until=wait_until)
        print(f"Navigated to: {url}")

    async def click(self, selector: str, timeout: int = 10000) -> None:
        """Click element by selector."""
        await self.page.click(selector, timeout=timeout)
        print(f"Clicked: {selector}")

    async def type_text(self, selector: str, text: str, delay: int = 50) -> None:
        """Type text into element."""
        await self.page.fill(selector, "")  # Clear first
        await self.page.type(selector, text, delay=delay)
        print(f"Typed into: {selector}")

    async def wait_for(self, selector: str, timeout: int = 30000) -> None:
        """Wait for element to appear."""
        await self.page.wait_for_selector(selector, timeout=timeout)
        print(f"Found: {selector}")

    async def get_text(self, selector: str) -> str:
        """Get text content of element."""
        return await self.page.text_content(selector)


async def main():
    bot = BrowserAutomation(
        profile_dir="Profile 3",
        default_url="https://valiant.trade"
    )

    try:
        await bot.launch()

        # Page is already on valiant.trade with user logged in
        print(f"Current URL: {bot.page.url}")
        print(f"Page title: {await bot.page.title()}")

        # Keep browser open
        input("Press Enter to close browser...")

    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
