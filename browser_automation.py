import os
import subprocess
import time
import asyncio
import urllib.request
import json
import shutil
from playwright.async_api import async_playwright
from browser_helpers import BrowserHelpers


# Configuration
DEBUGGING_PORT = 9222
CHROME_USER_DATA = r"C:\Users\Admin\AppData\Local\Google\Chrome\User Data"
DEBUG_DIR = r"C:\temp\chrome_debug"
PROFILE_DIR = "Profile 3"
DEFAULT_URL = "https://valiant.trade"
NIGHTLY_PASSWORD = "den10161610"


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
        print("Killing Chrome...")
        subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], capture_output=True, shell=True)
        time.sleep(3)

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

    def setup_debug_profile(self) -> None:
        """Copy user profile to debug directory."""
        source = os.path.join(CHROME_USER_DATA, self.profile_dir)
        dest = os.path.join(DEBUG_DIR, self.profile_dir)

        # Create debug dir
        os.makedirs(DEBUG_DIR, exist_ok=True)

        # Copy profile if source exists and dest doesn't
        if os.path.exists(source):
            if os.path.exists(dest):
                print(f"Debug profile exists: {dest}")
            else:
                print(f"Copying profile to debug directory...")
                shutil.copytree(source, dest)
                print(f"Profile copied")
        else:
            print(f"Source profile not found: {source}")

    def spawn_chrome(self) -> None:
        """Spawn Chrome with debugging enabled."""
        chrome_path = self.find_chrome()

        # Setup debug profile
        self.setup_debug_profile()

        args = [
            chrome_path,
            f"--remote-debugging-port={DEBUGGING_PORT}",
            f"--user-data-dir={DEBUG_DIR}",
            f"--profile-directory={self.profile_dir}",
            "--start-maximized",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-session-crashed-bubble",
        ]

        if self.default_url:
            args.append(self.default_url)

        print(f"Spawning Chrome with debug directory...")

        self.chrome_process = subprocess.Popen(args)

        print(f"Chrome spawned (PID: {self.chrome_process.pid})")

    async def launch(self) -> None:
        """Main launch function - spawns Chrome and connects via CDP."""
        # Step 1: Kill existing Chrome
        self.kill_chrome()

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

    async def unlock_nightly_wallet(self) -> bool:
        """
        Unlock Nightly wallet and connect.

        Flow:
        1. Click "Connect" on valiant.trade
        2. Wait for Nightly tab
        3. Enter password
        4. Click "Unlock"
        5. Click "Connect" in Nightly
        6. Return to valiant.trade
        """
        print("\n=== Unlocking Nightly Wallet ===\n")

        try:
            # Step 1: Click "Connect" on valiant.trade
            print("Step 1: Click 'Connect' on valiant.trade")
            helpers = BrowserHelpers(self.page)
            await asyncio.sleep(2)

            if not await helpers.click_button("Connect"):
                print("ERROR: 'Connect' button not found")
                return False

            # Step 2: Wait for Nightly tab
            print("\nStep 2: Waiting for Nightly tab...")
            nightly_page = None
            for i in range(20):
                await asyncio.sleep(1)
                for ctx in self.browser.contexts:
                    for p in ctx.pages:
                        if "nightly" in p.url.lower() or "chrome-extension" in p.url.lower():
                            nightly_page = p
                            break
                    if nightly_page:
                        break
                if nightly_page:
                    break
                print(f"  Waiting... ({i+1}/20)")

            if not nightly_page:
                print("ERROR: Nightly tab not found")
                return False

            print(f"Found Nightly: {nightly_page.url}")

            # Step 3: Enter password
            print("\nStep 3: Enter password")
            await nightly_page.bring_to_front()
            await asyncio.sleep(2)

            nightly = BrowserHelpers(nightly_page)
            if not await nightly.type_text("input[type='password']", NIGHTLY_PASSWORD):
                print("ERROR: Password field not found")
                return False

            # Step 4: Click Unlock
            print("\nStep 4: Click 'Unlock'")
            await asyncio.sleep(0.5)
            if not await nightly.click_button("Unlock"):
                print("ERROR: 'Unlock' button not found")
                return False

            await asyncio.sleep(3)

            # Step 5: Click Connect in Nightly
            print("\nStep 5: Click 'Connect' in Nightly")
            if not await nightly.click_button("Connect"):
                print("ERROR: 'Connect' button not found in Nightly")
                return False

            await asyncio.sleep(2)

            # Step 6: Return to valiant.trade
            print("\nStep 6: Return to valiant.trade")
            for ctx in self.browser.contexts:
                for p in ctx.pages:
                    if "valiant" in p.url.lower():
                        await p.bring_to_front()
                        self.page = p
                        break

            # Step 7: Refresh page to complete connection
            print("\nStep 7: Refreshing page...")
            await asyncio.sleep(1)
            await self.page.reload(wait_until="domcontentloaded")
            await asyncio.sleep(2)

            print(f"\nConnected on: {self.page.url}")
            print("\n=== Wallet Connected! ===\n")
            return True

        except Exception as e:
            print(f"ERROR: {e}")
            return False


async def main():
    bot = BrowserAutomation(
        profile_dir="Profile 3",
        default_url="https://valiant.trade"
    )

    try:
        await bot.launch()

        print(f"\nPage: {bot.page.url}")
        await asyncio.sleep(3)

        # Unlock wallet
        await bot.unlock_nightly_wallet()

        input("Press Enter to close...")

    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
