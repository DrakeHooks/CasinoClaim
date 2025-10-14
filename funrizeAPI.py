# Drake Hooks + WaterTrooper
# Casino Claim 2
# Funrize API — claim-first + reliable countdown, with login fallback

import os
import re
import asyncio
import discord
from typing import Optional, Iterable
from dotenv import load_dotenv

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException

# ───────────────────────────────────────────────────────────
# Config & constants
# ───────────────────────────────────────────────────────────
load_dotenv()
FUNRIZE_CRED = os.getenv("FUNRIZE")  # "username:password"
SITE_URL  = "https://funrize.com"
STORE_URL = "https://funrize.com/promotions"

# Login button (class)
LOGIN_BUTTON_CLASS = "login-btn"

# Store page “Claim Now”
CLAIM_CARD_CLASS      = "daily-login-prize"  # friend’s working selector
CLAIM_NOW_TEXT_XPATH  = "//button[normalize-space()='Claim Now']"  # fallback by visible text

# Modal “COLLECT” buttons (several layers for safety)
COLLECT_XPATHS = [
    "/html/body/div[3]/div/div/div[2]/div[2]/button",
    "/html/body/div[4]/div/div/div[2]/div[2]/button",
    "/html/body/div[5]/div/div/div[2]/div[2]/button",
    "/html/body/div[6]/div/div/div[2]/div[2]/button",
    # text fallback
    "//div[contains(@class,'modal') or contains(@class,'Dialog')]//button[normalize-space()='Collect' or normalize-space()='COLLECT']",
]

# Countdown on the store page (disabled button that shows “HH : MM : SS”)
COUNTDOWN_DISABLED_BTN_XPATH = "//button[@disabled and contains(normalize-space(.), ':')]"

# ───────────────────────────────────────────────────────────
# Small helpers
# ───────────────────────────────────────────────────────────
def wait_clickable(driver, by, sel, timeout=10):
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, sel)))

def wait_present(driver, by, sel, timeout=10):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, sel)))

def safe_click(driver, el):
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    except Exception:
        pass
    try:
        el.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", el)

def try_click_any_xpath(driver, xpaths: Iterable[str], timeout_each=6) -> bool:
    for xp in xpaths:
        try:
            el = wait_clickable(driver, By.XPATH, xp, timeout_each)
            safe_click(driver, el)
            return True
        except Exception:
            continue
    return False

def read_store_countdown(driver, timeout=4) -> Optional[str]:
    """Read the disabled countdown button and normalize to HH:MM:SS."""
    try:
        node = wait_present(driver, By.XPATH, COUNTDOWN_DISABLED_BTN_XPATH, timeout)
        raw = (node.text or "").strip()              # e.g. "22 : 27 : 06"
        # remove all whitespace around colons → "22:27:06"
        compact = re.sub(r"\s+", "", raw)
        # sanity normalize like H:MM:SS -> HH:MM:SS
        m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", compact)
        if m:
            h = int(m.group(1))
            mm = int(m.group(2))
            ss = int(m.group(3) or 0)
            return f"{h:02d}:{mm:02d}:{ss:02d}"
        return compact  # fallback: whatever we saw
    except TimeoutException:
        return None

# ───────────────────────────────────────────────────────────
# Main unified flow
# ───────────────────────────────────────────────────────────
async def funrize_flow(ctx, driver, channel):
    """
    Go to store → try to claim (Claim Now → COLLECT).
    If claim not possible, read & report countdown.
    If we look logged out / nothing works, login and retry claim.
    """
    driver.get(STORE_URL)
    await asyncio.sleep(3)

    # 1) Click the “Claim Now”/daily card (class first → text fallback)
    clicked_card = False
    try:
        card = wait_clickable(driver, By.CLASS_NAME, CLAIM_CARD_CLASS, 8)
        safe_click(driver, card)
        clicked_card = True
        await asyncio.sleep(1.2)
    except TimeoutException:
        # text fallback
        try:
            btn = wait_clickable(driver, By.XPATH, CLAIM_NOW_TEXT_XPATH, 4)
            safe_click(driver, btn)
            clicked_card = True
            await asyncio.sleep(1.0)
        except TimeoutException:
            pass

    # 2) If modal is up, try to click “COLLECT”
    if clicked_card:
        if try_click_any_xpath(driver, COLLECT_XPATHS, timeout_each=8):
            await channel.send("Funrize Daily Bonus Claimed!")
            return
        # Not claimable (button disabled / not found) → read store-page countdown
        cd = read_store_countdown(driver, timeout=4)
        if cd:
            await channel.send(f"Next Funrize Bonus Available in: {cd}")
            return

    # 3) If we didn’t click card (or nothing actionable), try reading the store countdown directly
    cd = read_store_countdown(driver, timeout=3)
    if cd:
        await channel.send(f"Next Funrize Bonus Available in: {cd}")
        return

    # 4) Fallback: probably logged out → login then try to claim again
    await funrize_casino(ctx, driver, channel)

# ───────────────────────────────────────────────────────────
# Login & retry claim
# ───────────────────────────────────────────────────────────
async def funrize_casino(ctx, driver, channel):
    if not FUNRIZE_CRED:
        await channel.send("Funrize credentials not found in environment variables.")
        return

    username, password = FUNRIZE_CRED.split(":", 1)

    driver.get(SITE_URL)
    await asyncio.sleep(3)

    try:
        # Open login modal
        login_btn = wait_clickable(driver, By.CLASS_NAME, LOGIN_BUTTON_CLASS, 12)
        safe_click(driver, login_btn)
        await asyncio.sleep(0.8)

        email = wait_present(driver, By.XPATH,
            "/html/body/div[1]/div/div[1]/div/div/div/div[1]/div/div[2]/form/label[1]/div[2]/input", 10)
        email.clear(); email.send_keys(username)
        await asyncio.sleep(0.3)

        pw = wait_present(driver, By.XPATH,
            "/html/body/div[1]/div/div[1]/div/div/div/div[1]/div/div[2]/form/label[2]/div[2]/input", 10)
        pw.clear(); pw.send_keys(password, Keys.ENTER)

        await asyncio.sleep(2.5)
        # Now logged in → try to claim again
        await claim_funrize_bonus(ctx, driver, channel)

    except TimeoutException:
        await channel.send("Funrize login timed out, will retry later.")

# ───────────────────────────────────────────────────────────
# Post-login claim attempt (reuses the same claim + collect steps)
# ───────────────────────────────────────────────────────────
async def claim_funrize_bonus(ctx, driver, channel):
    driver.get(STORE_URL)
    await asyncio.sleep(2)

    # Try the daily card / Claim Now
    clicked_card = False
    try:
        card = wait_clickable(driver, By.CLASS_NAME, CLAIM_CARD_CLASS, 8)
        safe_click(driver, card)
        clicked_card = True
        await asyncio.sleep(1.0)
    except TimeoutException:
        try:
            btn = wait_clickable(driver, By.XPATH, CLAIM_NOW_TEXT_XPATH, 4)
            safe_click(driver, btn)
            clicked_card = True
            await asyncio.sleep(1.0)
        except TimeoutException:
            pass

    if clicked_card and try_click_any_xpath(driver, COLLECT_XPATHS, timeout_each=8):
        await channel.send("Funrize Daily Bonus Claimed!")
        return

    # Otherwise, report the store countdown (persistent when unavailable)
    cd = read_store_countdown(driver, timeout=4)
    if cd:
        await channel.send(f"Next Funrize Bonus Available in: {cd}")
    else:
        await channel.send("Funrize: No countdown found.")

# ───────────────────────────────────────────────────────────
# Optional: standalone countdown
# ───────────────────────────────────────────────────────────
async def check_funrize_countdown(ctx, driver, channel):
    driver.get(STORE_URL)
    await asyncio.sleep(2)
    cd = read_store_countdown(driver, timeout=6)
    if cd:
        await channel.send(f"Next Funrize Bonus Available in: {cd}")
    else:
        await channel.send("Funrize: No countdown found.")
