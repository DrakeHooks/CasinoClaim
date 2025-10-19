# Drake Hooks + WaterTrooper
# Casino Claim 2
# Fortune Wheelz API (non-recursive; one-shot actions)

import os
import re
import asyncio
import discord
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ───────────────────────────────────────────────────────────
# Config & Constants
# ───────────────────────────────────────────────────────────
load_dotenv()
FORTUNEWHEELZ_CRED = os.getenv("FORTUNEWHEELZ")  # format "email:password"

SITE_URL  = "https://fortunewheelz.com"
STORE_URL = "https://fortunewheelz.com/promotions"

# XPaths / selectors (keep your working ones)
LOGIN_BUTTON   = "/html/body/div[1]/div/div/div[1]/header/div[2]/button[1]"
EMAIL_INPUT    = "/html/body/div[1]/div/div/div[2]/form/label[1]/div[2]/div[2]/input"
PASSWORD_INPUT = "/html/body/div[1]/div/div/div[2]/form/label[2]/div[2]/input"
LOGIN_SUBMIT   = "/html/body/div[1]/div/div/div[2]/form/div/button"

CLAIM_BUTTON_CLASS = "promo-daily-login-button"  # "Claim Now" on promotions
COLLECT_BUTTON_XP  = [
    "/html/body/div[5]/div/div[2]/div[3]/button",
    "/html/body/div[8]/div/div[2]/div[3]/button",
    "/html/body/div[9]/div/div[2]/div[3]/button",
]

XPATH_COUNTDOWN = "//button[@disabled and contains(normalize-space(.), ':')]"

# ───────────────────────────────────────────────────────────
# Helpers (short, bounded waits)
# ───────────────────────────────────────────────────────────
def _wait_clickable(driver, by, sel, timeout=10):
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, sel)))

def _wait_present(driver, by, sel, timeout=10):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, sel)))

# ───────────────────────────────────────────────────────────
# Public one-shot flow the loop/command will call
# ───────────────────────────────────────────────────────────
async def fortunewheelz_flow(ctx, driver, channel):
    """
    One run:
      1) Try claim directly on /promotions.
      2) If nothing to claim, report countdown.
      3) If likely logged out, login once and try claim once more.
    Always returns.
    """
    # Try direct claim
    driver.get(STORE_URL)
    await asyncio.sleep(3)

    claimed = await _try_claim(driver, channel)
    if claimed:
        return

    # Try to read countdown
    read = await _report_countdown(driver, channel)
    if read:
        return

    # Probably logged out; login once and try claim once more
    await _login_if_needed(driver, channel)
    driver.get(STORE_URL)
    await asyncio.sleep(2)
    claimed = await _try_claim(driver, channel)
    if not claimed:
        await _report_countdown(driver, channel)

# ───────────────────────────────────────────────────────────
# Login
# ───────────────────────────────────────────────────────────
async def _login_if_needed(driver, channel):
    if not FORTUNEWHEELZ_CRED:
        try:
            await channel.send("⚠️ Fortune Wheelz credentials not found in environment (FORTUNEWHEELZ).")
        except Exception:
            pass
        return

    username, password = FORTUNEWHEELZ_CRED.split(":", 1)

    driver.get(SITE_URL)
    await asyncio.sleep(3)

    try:
        btn = _wait_clickable(driver, By.XPATH, LOGIN_BUTTON, timeout=10)
        btn.click()
        await asyncio.sleep(1.5)

        email_el = _wait_present(driver, By.XPATH, EMAIL_INPUT, timeout=10)
        email_el.clear()
        email_el.send_keys(username)

        pw_el = _wait_present(driver, By.XPATH, PASSWORD_INPUT, timeout=10)
        pw_el.clear()
        pw_el.send_keys(password)

        submit = _wait_clickable(driver, By.XPATH, LOGIN_SUBMIT, timeout=10)
        submit.click()
        await asyncio.sleep(4)
    except TimeoutException:
        # If anything times out, just return; the loop timeout will protect us.
        pass

# ───────────────────────────────────────────────────────────
# Claim helpers
# ───────────────────────────────────────────────────────────
async def _try_claim(driver, channel) -> bool:
    """Return True if we successfully claimed."""
    try:
        claim = _wait_clickable(driver, By.CLASS_NAME, CLAIM_BUTTON_CLASS, timeout=10)
        claim.click()
        await asyncio.sleep(2)
    except TimeoutException:
        # Claim button not present
        return False

    # Try each possible "Collect" xpath once
    for xp in COLLECT_BUTTON_XP:
        try:
            collect = _wait_clickable(driver, By.XPATH, xp, timeout=10)
            collect.click()
            await channel.send("✅ Fortune Wheelz daily bonus collected.")
            return True
        except TimeoutException:
            continue
    return False

async def _report_countdown(driver, channel) -> bool:
    """Return True if we found and reported a timer."""
    try:
        btn = _wait_present(driver, By.XPATH, XPATH_COUNTDOWN, timeout=5)
        raw = (btn.text or "").strip()      # e.g. "22 : 27 : 06"
        countdown = re.sub(r"\s+", "", raw) # => "22:27:06"
        await channel.send(f"Next Fortune Wheelz bonus Available in: {countdown}")
        return True
    except TimeoutException:
        return False

# ───────────────────────────────────────────────────────────
# Optional explicit helpers if you call them elsewhere
# ───────────────────────────────────────────────────────────
async def fortunewheelz_casino(ctx, driver, channel):
    """Kept for compatibility: just do a one-shot login, then try claim."""
    await _login_if_needed(driver, channel)
    driver.get(STORE_URL)
    await asyncio.sleep(2)
    if not await _try_claim(driver, channel):
        await _report_countdown(driver, channel)

async def claim_fortunewheelz_bonus(ctx, driver, channel):
    """One-shot claim attempt. No recursion."""
    driver.get(STORE_URL)
    await asyncio.sleep(2)
    if not await _try_claim(driver, channel):
        await _report_countdown(driver, channel)

async def check_fortunewheelz_countdown(ctx, driver, channel):
    """One-shot timer read."""
    driver.get(STORE_URL)
    await asyncio.sleep(2)
    if not await _report_countdown(driver, channel):
        await channel.send("Could not find Fortune Wheelz timer; maybe available now.")
