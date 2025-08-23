# Drake Hooks
# Casino Claim 2
# Helper API

"""Utility helpers used across the bot."""

import asyncio


async def open_captcha_solver_page(driver):
    """Open the captcha solver extension page."""
    try:
        # Open the extensions page first so the extension context is loaded
        driver.get("chrome://extensions")
        await asyncio.sleep(2)
        # Navigate directly to the captcha solver popup
        driver.get(
            "chrome-extension://hlifkpholllijblknnmbfagnkjneagid/popup/popup.html#/"
        )
        await asyncio.sleep(5)
        return True
    except Exception as e:  # pragma: no cover - best effort
        print(f"Failed to open captcha solver page: {e}")
        return False

