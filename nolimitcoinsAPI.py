# Drake Hooks + WaterTrooper
# Casino Claim 2
# NoLimitCoins API (with countdown-from-::before support)

import os
import re
import asyncio
import discord
from typing import Iterable, Optional

from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ───────────────────────────────────────────────────────────
# Config & Constants
# ───────────────────────────────────────────────────────────
load_dotenv()
NOLIMITCOINS_CRED = os.getenv("NOLIMITCOINS")  # "username:password"
STORE_URL  = "https://nolimitcoins.com/promotions"
SIGNIN_URL = "https://nolimitcoins.com/signin/"

# The Daily Login card button. We'll read its text / ::before to detect countdowns.
CLAIM_CARD_COUNTDOWN_XPATH = "/html/body/div[1]/div/main/div/div[3]/div[5]/div[2]/div/button"

# Keep both observed locations for the card Click (site moves these)
CLAIM_CARD_XPATHS = [
    "/html/body/div[1]/div/main/div/div[3]/div[4]/div[2]/div/button",
    "/html/body/div[1]/div/main/div/div[3]/div[5]/div[2]/div/button",
]

# Enabled “Claim” targets: modal close + day tabs + day7 claim button, etc.
CLAIM_XPATHS = [
    "/html/body/div[4]/div/div/div/button",
    "/html/body/div[3]/div/div/div/button",
    "/html/body/div[3]/div/div/div/div[1]/div[1]/div",
    "/html/body/div[3]/div/div/div/div[1]/div[2]/div",
    "/html/body/div[3]/div/div/div/div[1]/div[3]/div",
    "/html/body/div[3]/div/div/div/div[1]/div[4]/div",
    "/html/body/div[3]/div/div/div/div[1]/div[5]/div",
    "/html/body/div[3]/div/div/div/div[1]/div[6]/div",
    "/html/body/div[3]/div/div/div/div[1]/div[7]/div/div[2]",
]

# The green “Claim Reward” button often has text via ::before; prefer classes over text.
CLAIM_REWARD_SELECTORS = [
    (By.CSS_SELECTOR, "button.a-button.primary.size-md.btn"),
    # fallback using Vue attr if needed
    (By.CSS_SELECTOR, "button[data-v-895f4e2b]"),
]

# Disabled countdown button (generic fallback, separate from the card)
XPATH_COUNTDOWN_GENERIC = "//button[@disabled and contains(normalize-space(.), ':')]"

# ───────────────────────────────────────────────────────────
# Small helpers
# ───────────────────────────────────────────────────────────
def wait_clickable(driver, by, sel, timeout=10):
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, sel)))

def wait_present(driver, by, sel, timeout=10):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, sel)))

def try_click_any(driver, selectors: Iterable[tuple], timeout_each=3) -> bool:
    for by, sel in selectors:
        try:
            el = wait_clickable(driver, by, sel, timeout_each)
            el.click()
            return True
        except TimeoutException:
            continue
    return False

def try_click_any_xpath(driver, xpaths: Iterable[str], timeout_each=3) -> bool:
    return try_click_any(driver, [(By.XPATH, xp) for xp in xpaths], timeout_each)

async def send_screenshot(channel: discord.TextChannel, driver, name="nlc_screenshot.png"):
    driver.save_screenshot(name)
    await channel.send(file=discord.File(name))
    try:
        os.remove(name)
    except OSError:
        pass

def _normalize_hms(hms: str) -> str:
    # "7 : 3 : 9" -> "07:03:09"
    parts = re.split(r"\s*:\s*", hms.strip())
    if len(parts) != 3:
        return hms.replace(" ", "")
    h, m, s = parts
    return f"{h.zfill(2)}:{m.zfill(2)}:{s.zfill(2)}"

def read_claim_card_countdown(driver, xpath: str) -> Optional[str]:
    """
    Return 'HH:MM:SS' if the Daily Login card shows a countdown, else None.
    Works even when the label is rendered via CSS ::before.
    """
    try:
        btn = wait_present(driver, By.XPATH, xpath, timeout=6)
    except TimeoutException:
        return None

    # Check disabled state via attribute or class
    cls = (btn.get_attribute("class") or "").lower()
    is_disabled = btn.get_attribute("disabled") is not None or "disabled" in cls
    if not is_disabled:
        return None

    # 1) Try visible text
    txt = (btn.text or "").strip()
    m = re.search(r"(\d{1,2}\s*:\s*\d{2}\s*:\s*\d{2})", txt)
    if m:
        return _normalize_hms(m.group(1))

    # 2) Fallback to ::before content
    css_text = driver.execute_script("""
        const el = arguments[0];
        const s = window.getComputedStyle(el, '::before').getPropertyValue('content');
        return s ? s.replace(/^["']|["']$/g, '') : '';
    """, btn) or ""
    m = re.search(r"(\d{1,2}\s*:\s*\d{2}\s*:\s*\d{2})", css_text)
    if m:
        return _normalize_hms(m.group(1))

    return None

# ───────────────────────────────────────────────────────────
# Main flows
# ───────────────────────────────────────────────────────────
async def nolimitcoins_flow(ctx, driver, channel):
    """
    Open store → if card has countdown, report HH:MM:SS.
    Else attempt claim; if nothing to claim, read generic countdown; else login+claim.
    """
    driver.get(STORE_URL)
    await asyncio.sleep(3)

    # 🔎 Card-specific countdown (preferred)
    cd = read_claim_card_countdown(driver, CLAIM_CARD_COUNTDOWN_XPATH)
    if cd:
        await channel.send(f"Next No Limit Coins Bonus Available in: {cd}")
        return

    # Optional screenshot for debugging
    # await send_screenshot(channel, driver)

    # Try clicking the Daily card (site shuffles index sometimes)
    try_click_any_xpath(driver, CLAIM_CARD_XPATHS, timeout_each=5)
    await asyncio.sleep(1)

    # Prefer the “Claim Reward” button by class, then try our XPath set
    if try_click_any(driver, CLAIM_REWARD_SELECTORS, timeout_each=3) or \
       try_click_any_xpath(driver, CLAIM_XPATHS, timeout_each=3):
        screenshot = "claim.png"
            driver.save_screenshot(screenshot)
            await channel.send(
            file=discord.File(screenshot))
            os.remove(screenshot)
        await channel.send("NoLimitCoins Daily Bonus Claimed!")
        return

    # Generic disabled countdown fallback anywhere on the page
    try:
        countdown_btn = wait_present(driver, By.XPATH, XPATH_COUNTDOWN_GENERIC, timeout=4)
        await channel.send(
            f"Next No Limit Coins Bonus Available in: {_normalize_hms(countdown_btn.text)}"
        )
        return
    except TimeoutException:
        pass

    # Not logged in or page odd → login and try again
    await nolimitcoins_casino(ctx, driver, channel)

async def nolimitcoins_casino(ctx, driver, channel):
    """Login with .env credentials, then proceed to claim."""
    if not NOLIMITCOINS_CRED:
        await channel.send("NoLimitCoins credentials not found in environment variables.")
        return
    username, password = NOLIMITCOINS_CRED.split(":", 1)

    driver.get(SIGNIN_URL)
    await asyncio.sleep(2)

    try:
        # Open form if hidden under header button
        try:
            btn = wait_clickable(driver, By.XPATH, "/html/body/div[1]/div/div[1]/header/div[2]/button[1]", 6)
            btn.click()
            await asyncio.sleep(1)
        except TimeoutException:
            pass

        email = wait_present(driver, By.XPATH, "/html/body/div[1]/div/div[1]/div/form/label[1]/div/div[2]/input", 10)
        email.send_keys(username)
        await asyncio.sleep(0.5)

        pw = wait_present(driver, By.XPATH, "/html/body/div[1]/div/div[1]/div/form/label[2]/div[1]/input", 10)
        pw.send_keys(password, Keys.ENTER)
        await asyncio.sleep(3)

        await claim_nolimitcoins_bonus(ctx, driver, channel)

    except TimeoutException as e:
        await send_screenshot(channel, driver, "nolimitcoins_login_error.png")
        await channel.send("NoLimitCoins login timed out, will retry later.")
        print("Login timeout:", e)

async def claim_nolimitcoins_bonus(ctx, driver, channel):
    """After login: open store → try claim; else report countdown via card/generic."""
    driver.get(STORE_URL)
    await asyncio.sleep(2)

    # If card shows countdown, report and stop early
    cd = read_claim_card_countdown(driver, CLAIM_CARD_COUNTDOWN_XPATH)
    if cd:
        await channel.send(f"Next No Limit Coins Bonus Available in: {cd}")
        return

    try_click_any_xpath(driver, CLAIM_CARD_XPATHS, timeout_each=6)
    await asyncio.sleep(1)

    if try_click_any(driver, CLAIM_REWARD_SELECTORS, timeout_each=5) or \
       try_click_any_xpath(driver, CLAIM_XPATHS, timeout_each=5):
        await channel.send("NoLimitCoins Daily Bonus Claimed!")

        screenshot = "nlc_bonus_claim.png"
        driver.save_screenshot(screenshot)
        await channel.send(
        file=discord.File(screenshot))
        os.remove(screenshot)
        return

    # Fall back to generic countdown once more
    try:
        countdown_btn = wait_present(driver, By.XPATH, XPATH_COUNTDOWN_GENERIC, timeout=6)
        await channel.send(
            f"Next No Limit Coins Bonus Available in: {_normalize_hms(countdown_btn.text)}"
        )
    except TimeoutException:
        # As a last resort, re-run the unified flow (for robustness)
        await nolimitcoins_flow(ctx, driver, channel)

async def check_nolimitcoins_countdown(ctx, driver, channel):
    """Standalone timer fetch."""
    driver.get(STORE_URL)
    await asyncio.sleep(2)
    cd = read_claim_card_countdown(driver, CLAIM_CARD_COUNTDOWN_XPATH)
    if not cd:
        # fallback to generic disabled button if card lookup fails
        btn = wait_present(driver, By.XPATH, XPATH_COUNTDOWN_GENERIC, timeout=10)
        cd = _normalize_hms(btn.text)
    await channel.send(f"Next No Limit Coins Bonus Available in: {cd}")

# ───────────────────────────────────────────────────────────
# Auth helpers
# ───────────────────────────────────────────────────────────
async def auth_nolimit_env(driver, channel, ctx):
    try:
        driver.get(SIGNIN_URL)
        await asyncio.sleep(2)

        creds = os.getenv("NOLIMITCOINS")
        if not creds:
            await channel.send("NoLimitCoins credentials not found in environment variables.")
            return
        username, password = creds.split(":", 1)

        email_input = wait_present(driver, By.NAME, "email", 8)
        email_input.send_keys(username)
        await asyncio.sleep(0.5)

        password_input = wait_present(driver, By.NAME, "password", 8)
        password_input.send_keys(password)
        password_input.send_keys(Keys.ENTER)

        await asyncio.sleep(3)
        await send_screenshot(channel, driver)
        await channel.send("Authenticated into NoLimitCoins!")
    except Exception:
        await channel.send("NoLimitCoins login with env creds failed. Perhaps you need to run !googleauth.")

async def auth_nolimit_google(driver, channel, ctx):
    try:
        driver.get(SIGNIN_URL)
        await asyncio.sleep(2)

        google_btn = wait_clickable(driver, By.XPATH, "/html/body/div[1]/div/div[1]/div/form/div[1]/button[2]", 10)
        google_btn.click()

        WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) > 1)
        driver.switch_to.window(driver.window_handles[1])

        await send_screenshot(channel, driver)

        acct_btn = wait_clickable(
            driver,
            By.XPATH,
            "/html/body/div[1]/div[1]/div[2]/div/div/div[2]/div/div/div[1]/form/span/section/div/div/div/div/ul/li[1]/div",
            10,
        )
        acct_btn.click()

        driver.switch_to.window(driver.window_handles[0])
        await asyncio.sleep(3)

        await channel.send("Authenticated into NoLimitCoins!")
    except Exception:
        await channel.send("NoLimitCoins login with Google failed. Perhaps you need to run !googleauth.")
