# Drake Hooks + WaterTrooper
# Casino Claim 2 — Fortune Wheelz API (de-recursed + guarded)

import os
import re
import asyncio
import discord
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

load_dotenv()

FORTUNEWHEELZ_CRED = os.getenv("FORTUNEWHEELZ")  # "email:password"
SITE_URL  = "https://fortunewheelz.com"
STORE_URL = "https://fortunewheelz.com/promotions"

# Locators
LOGIN_BUTTON  = "/html/body/div[1]/div/div/div[1]/header/div[2]/button[1]"
EMAIL_INPUT   = "/html/body/div[1]/div/div/div[2]/form/label[1]/div[2]/div[2]/input"
PASSWORD_INPUT= "/html/body/div[1]/div/div/div[2]/form/label[2]/div[2]/input"
LOGIN_SUBMIT  = "/html/body/div[1]/div/div/div[2]/form/div/button"

CLAIM_CARD_CLASS   = "promo-daily-login-button"   # "Claim now" card on /promotions
COLLECT_XPATHS     = [
    "/html/body/div[5]/div/div[2]/div[3]/button",
    "/html/body/div[8]/div/div[2]/div[3]/button",
    "/html/body/div[9]/div/div[2]/div[3]/button",
]
COUNTDOWN_DISABLED_BTN = "//button[@disabled and contains(normalize-space(.), ':')]"

COUNTDOWN_XPATH = "/html/body/div[4]/div/div[2]/div[3]/p"
# Generic helper
def _wait_clickable(driver, by, value, timeout=8):
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, value)))

def _wait_present(driver, by, value, timeout=8):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))

# ───────────────────────────────────────────────────────────
# Public entry: one pass that never recurses
# ───────────────────────────────────────────────────────────
async def fortunewheelz_flow(ctx, driver, channel):
    """
    Try in this order:
      1) If claim dialog is reachable → claim
      2) Else show countdown if present
      3) Else login once, then try claim once
    Never recurse; never loop forever.
    """
    # Step 1: try claim directly
    driver.get(STORE_URL)
    await asyncio.sleep(5)

    claimed = await _try_claim(driver, channel)
    if claimed:
        return

    # Step 2: try a countdown read
    countdown = _read_countdown(driver)
    if countdown:
        await channel.send(f"Next Fortune Wheelz bonus Available in: {countdown}")
        return

    # Step 3: login once, then attempt one claim pass
    if not FORTUNEWHEELZ_CRED:
        await channel.send("Fortune Wheelz credentials not found in environment variables.")
        return

    try:
        driver.get(SITE_URL)
        await asyncio.sleep(3)
        _wait_clickable(driver, By.XPATH, LOGIN_BUTTON, timeout=10).click()
        await asyncio.sleep(1)

        email = _wait_present(driver, By.XPATH, EMAIL_INPUT, timeout=10)
        pw    = _wait_present(driver, By.XPATH, PASSWORD_INPUT, timeout=10)
        user, passw = FORTUNEWHEELZ_CRED.split(":", 1)
        email.send_keys(user)
        pw.send_keys(passw)
        _wait_clickable(driver, By.XPATH, LOGIN_SUBMIT, timeout=10).click()
        await asyncio.sleep(3)
    except TimeoutException:
        await _shoot(channel, driver, "fortunewheelz_login_timeout.png",
                     "Fortune Wheelz login timed out. Will try again next loop.")
        return

    # After login, one more single attempt:
    driver.get(STORE_URL)
    await asyncio.sleep(3)
    claimed = await _try_claim(driver, channel)
    if claimed:
        return

    countdown = _read_countdown(driver)
    if countdown:
        await channel.send(f"Next Fortune Wheelz bonus Available in: {countdown}")
    # If neither was found, we silently return; the main loop will revisit later.

# ───────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────
async def _try_claim(driver, channel) -> bool:
    """Return True if we successfully claimed; False otherwise."""
    try:
        _wait_clickable(driver, By.CLASS_NAME, CLAIM_CARD_CLASS, timeout=6).click()
        await asyncio.sleep(2)
    except TimeoutException:
        # card not visible/clickable — might still have a collect modal from earlier
        pass

    for xp in COLLECT_XPATHS:
        try:
            _wait_clickable(driver, By.XPATH, xp, timeout=4).click()
            await channel.send("Fortune Wheelz Daily Bonus Claimed!")
            return True
        except TimeoutException:
            continue
    return False

def _read_countdown(driver) -> str | None:
    try:
        btn = _wait_present(driver, By.XPATH, COUNTDOWN_XPATH, timeout=10)
        raw = btn.text.strip()              # e.g. "22 : 27 : 06"
        return re.sub(r"\s+", "", raw)      # → "22:27:06"
    except TimeoutException:
        return None

async def _shoot(channel, driver, path, msg):
    try:
        driver.save_screenshot(path)
        await channel.send(msg, file=discord.File(path))
    except Exception:
        await channel.send(msg)
    finally:
        try: os.remove(path)
        except Exception: pass
