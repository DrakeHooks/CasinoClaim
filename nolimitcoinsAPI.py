# Drake Hooks + WaterTrooper
# Casino Claim 2
# NoLimitCoins API (simple: Claim -> Collect; timer from countdown DIV; resilient Google chooser switch)

import os
import re
import time
import asyncio
import discord
from typing import Iterable, Optional

from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException

# ───────────────────────────────────────────────────────────
# Config & Constants
# ───────────────────────────────────────────────────────────
load_dotenv()
NOLIMITCOINS_CRED = os.getenv("NOLIMITCOINS")  # "username:password"
STORE_URL  = "https://nolimitcoins.com/promotions"
SIGNIN_URL = "https://nolimitcoins.com/signin/"

# After opening the store: first click a "Claim / Claim Reward" styled button…
CLAIM_REWARD_SELECTORS = [
    (By.CSS_SELECTOR, "button.a-button.primary.size-md.btn:not(.disabled)"),
    (By.CSS_SELECTOR, "button[data-v-895f4e2b]:not(.disabled)"),
]

# …then click one of these "Collect" buttons in the modal.
CLAIM_XPATHS = [
    "/html/body/div[3]/div/div/div/button",
    "/html/body/div[4]/div/div/div/button",
]

# Read countdown from this DIV (provided path)
COUNTDOWN_DIV_XPATH = "/html/body/div[1]/div/main/div/div[3]/div[5]/div[2]/div"

# Optional overlay that can block clicks.
OVERLAY_LOCATOR = (By.ID, "ModalDailyLogin")

# Candidate XPaths for Google account row (handles minor A/B DOM shifts)
GOOGLE_ACCOUNT_XPATHS = [
    # Your updated path with c-wiz
    "/html/body/div[2]/div[1]/div[2]/c-wiz/main/div[2]/div/div/div[1]/form/span/section/div/div/div/div/ul/li[1]/div",
    # Common v3 chooser path
    "/html/body/div[1]/div[1]/div[2]/div/div/div[2]/div/div/div[1]/form/span/section/div/div/div/div/ul/li[1]/div",
    # Fallback: any li in the account list
    "//ul/li[1]/div[contains(@class,'qk0lee') or contains(@role,'button') or @role='button']",
]

# ───────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────
def wait_clickable(driver, by, sel, timeout=10):
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, sel)))

def wait_present(driver, by, sel, timeout=10):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, sel)))

def safe_click(driver, el):
    """Scroll into view and click; fallback to JS click if intercepted."""
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    except Exception:
        pass
    try:
        el.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", el)

def try_click_any(driver, selectors: Iterable[tuple], timeout_each=3) -> bool:
    for by, sel in selectors:
        try:
            el = wait_clickable(driver, by, sel, timeout_each)
            safe_click(driver, el)
            return True
        except (TimeoutException, ElementClickInterceptedException):
            continue
    return False

def try_click_any_xpath(driver, xpaths: Iterable[str], timeout_each=3) -> bool:
    return try_click_any(driver, [(By.XPATH, xp) for xp in xpaths], timeout_each)

def dismiss_overlay(driver, timeout=4):
    """Best-effort overlay close; no error if it isn't there."""
    try:
        if WebDriverWait(driver, 1).until(EC.visibility_of_element_located(OVERLAY_LOCATOR)):
            try_click_any_xpath(driver, CLAIM_XPATHS, timeout_each=2)
            WebDriverWait(driver, timeout).until(EC.invisibility_of_element_located(OVERLAY_LOCATOR))
    except Exception:
        pass

async def send_screenshot(channel: discord.TextChannel, driver, name="nlc.png"):
    driver.save_screenshot(name)
    await channel.send(file=discord.File(name))
    try:
        os.remove(name)
    except OSError:
        pass

def _normalize_hms(hms: str) -> str:
    parts = re.split(r"\s*:\s*", hms.strip())
    if len(parts) != 3:
        return hms.replace(" ", "")
    h, m, s = parts
    return f"{h.zfill(2)}:{m.zfill(2)}:{s.zfill(2)}"

def read_countdown_from_div(driver) -> Optional[str]:
    """Return HH:MM:SS from the countdown DIV, or None if not present/parseable."""
    try:
        node = wait_present(driver, By.XPATH, COUNTDOWN_DIV_XPATH, timeout=4)
        text = (node.text or "").strip()
        m = re.search(r"(\d{1,2}\s*:\s*\d{2}\s*:\s*\d{2})", text)
        if m:
            return _normalize_hms(m.group(1))
        return None
    except TimeoutException:
        return None

# ---------- Google popup switching (promo-safe; waits for chooser) ----------
def is_google_account_chooser_now(driver) -> bool:
    """Detect the chooser by domain and hallmark text — tolerant of A/B markup."""
    url = (driver.current_url or "").lower()
    if "accounts.google.com" not in url:
        return False
    # Positive URL hints
    if not any(k in url for k in ("accountchooser", "signin", "servicelogin", "/v3/")):
        return False
    # Either headline or sub-copy present
    try:
        WebDriverWait(driver, 1.2).until(EC.presence_of_element_located((By.XPATH, "//*[contains(., 'Choose an account')]")))
        return True
    except TimeoutException:
        pass
    try:
        WebDriverWait(driver, 1.2).until(EC.presence_of_element_located((By.XPATH, "//*[contains(., 'to continue to')]")))
        return True
    except TimeoutException:
        return False

def is_chrome_promo_now(driver) -> bool:
    """Heuristic to recognize the Chrome promo/welcome page."""
    u = (driver.current_url or "").lower()
    t = (driver.title or "").lower()
    if "chrome" in u and "accounts.google.com" in u:
        return True
    return any(s in t for s in ("make chrome your own", "sign in to chrome", "get your passwords"))

def switch_to_accounts_google_popup(driver, timeout=20):
    """
    Look across ALL popups (even if the promo opens first) and switch to the real
    Google account chooser as soon as it exists.
    Returns (main_handle, chooser_handle).
    """
    main = driver.current_window_handle
    WebDriverWait(driver, timeout).until(lambda d: len(d.window_handles) > 1)

    end = time.time() + timeout
    seen = set([main])
    chooser = None

    while time.time() < end:
        # New handles might appear after the promo — keep checking the full set
        for h in driver.window_handles:
            if h in seen:
                continue
            seen.add(h)
            try:
                driver.switch_to.window(h)
            except Exception:
                continue

            if is_google_account_chooser_now(driver):
                chooser = h
                break
            # Ignore promo and any other random windows; do not close them
            # so we don't accidentally kill the OAuth flow.

        if chooser:
            break
        time.sleep(0.25)

    if not chooser:
        # One last pass over all existing handles before giving up
        for h in driver.window_handles:
            if h == main:
                continue
            try:
                driver.switch_to.window(h)
            except Exception:
                continue
            if is_google_account_chooser_now(driver):
                chooser = h
                break

    if not chooser:
        raise TimeoutException("Google account chooser window not found")

    return main, chooser

def click_first_google_account(driver, timeout=12):
    """Try several known XPaths to click the first account in the chooser."""
    for xp in GOOGLE_ACCOUNT_XPATHS:
        try:
            el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xp)))
            safe_click(driver, el)
            return True
        except TimeoutException:
            continue
    return False

# ───────────────────────────────────────────────────────────
# Simple two-step claim flow
# ───────────────────────────────────────────────────────────
async def nolimitcoins_flow(ctx, driver, channel):
    """
    1) Open Store
    2) Click Claim/Claim Reward (by class)
    3) Click Collect (modal)
    Else → read countdown from COUNTDOWN_DIV_XPATH and report it.
    """
    driver.get(STORE_URL)
    await asyncio.sleep(2)
    dismiss_overlay(driver)

    # Step 1: Claim/Claim Reward
    if not try_click_any(driver, CLAIM_REWARD_SELECTORS, timeout_each=5):
        cd = read_countdown_from_div(driver)
        if cd:
            await channel.send(f"Next No Limit Coins Bonus Available in: {cd}")
        else:
            await channel.send("NoLimitCoins: Claim button not found.")
            await send_screenshot(channel, driver)
        return

    await asyncio.sleep(1)
    dismiss_overlay(driver)

    # Step 2: Collect (modal)
    if try_click_any_xpath(driver, CLAIM_XPATHS, timeout_each=5):
        await channel.send("NoLimitCoins Daily Bonus Claimed!")
        await send_screenshot(channel, driver)
        return

    # If Collect wasn't found, show timer from the DIV if possible
    cd = read_countdown_from_div(driver)
    if cd:
        await channel.send(f"Next No Limit Coins Bonus Available in: {cd}")
    else:
        await channel.send("NoLimitCoins: Couldn't find 'Collect' after clicking claim. Perhaps you need to authenticate?")
        await send_screenshot(channel, driver)

async def claim_nolimitcoins_bonus(ctx, driver, channel):
    """Same as nolimitcoins_flow but used post-login."""
    await nolimitcoins_flow(ctx, driver, channel)

# ───────────────────────────────────────────────────────────
# Login with .env, then claim
# ───────────────────────────────────────────────────────────
async def nolimitcoins_casino(ctx, driver, channel):
    if not NOLIMITCOINS_CRED:
        await channel.send("NoLimitCoins credentials not found in environment variables.")
        return
    username, password = NOLIMITCOINS_CRED.split(":", 1)

    driver.get(SIGNIN_URL)
    await asyncio.sleep(2)

    try:
        # If form hidden under header button, open it
        try:
            btn = wait_clickable(driver, By.XPATH, "/html/body/div[1]/div/div[1]/header/div[2]/button[1]", 6)
            safe_click(driver, btn)
            await asyncio.sleep(1)
        except TimeoutException:
            pass

        email = wait_present(driver, By.NAME, "email", 10)
        email.send_keys(username)
        await asyncio.sleep(0.3)

        pw = wait_present(driver, By.NAME, "password", 10)
        pw.send_keys(password)
        pw.send_keys(Keys.ENTER)
        await asyncio.sleep(2)

        await claim_nolimitcoins_bonus(ctx, driver, channel)
    except TimeoutException:
        await send_screenshot(channel, driver, "nolimitcoins_login_error.png")
        await channel.send("NoLimitCoins login timed out, will retry later.")

# ───────────────────────────────────────────────────────────
# Countdown only (reads from the provided DIV)
# ───────────────────────────────────────────────────────────
async def check_nolimitcoins_countdown(ctx, driver, channel):
    driver.get(STORE_URL)
    await asyncio.sleep(2)
    cd = read_countdown_from_div(driver)
    if cd:
        await channel.send(f"Next No Limit Coins Bonus Available in: {cd}")
    else:
        await channel.send("NoLimitCoins: No countdown found.")
        await send_screenshot(channel, driver)

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
        await asyncio.sleep(0.2)

        password_input = wait_present(driver, By.NAME, "password", 8)
        password_input.send_keys(password)
        password_input.send_keys(Keys.ENTER)

        await asyncio.sleep(2)
        await send_screenshot(channel, driver)
        await channel.send("Authenticated into NoLimitCoins!")
    except Exception:
        await channel.send("NoLimitCoins login with env creds failed. Perhaps you need to run !auth google.")

async def auth_nolimit_google(driver, channel, ctx):
    """
    Handle Google popup where *two* windows can open:
    - Chrome promo (ignore)
    - Actual account chooser (target)
    We keep scanning until the chooser appears, then click the first account.
    """
    try:
        driver.get(SIGNIN_URL)
        await asyncio.sleep(2)

        google_btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div[1]/div/form/div[1]/button[2]"))
        )
        safe_click(driver, google_btn)

        # Switch to the true chooser (wait even if promo shows first)
        main_handle, chooser_handle = switch_to_accounts_google_popup(driver, timeout=22)
        driver.switch_to.window(chooser_handle)

        if not click_first_google_account(driver, timeout=12):
            raise TimeoutException("Could not click first Google account")

        # Back to main; wait for return to nolimitcoins
        driver.switch_to.window(main_handle)
        WebDriverWait(driver, 25).until(lambda d: "nolimitcoins.com" in (d.current_url or "").lower())
        await asyncio.sleep(5)

        await channel.send("Authenticated into NoLimitCoins!")
    except Exception:
        await channel.send("NoLimitCoins login with Google failed. Perhaps you need to run !auth google.")
