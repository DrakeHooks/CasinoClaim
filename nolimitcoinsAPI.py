# Drake Hooks + WaterTrooper
# Casino Claim 2
# NoLimitCoins API (claim → collect; countdown fallback; robust Google chooser tab-scan)

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
COUNTDOWN_DIV_XPATH = "/html/body/div[1]/div/main/div/div[3]/div[4]/div[2]/div"

# Optional overlay that can block clicks.
OVERLAY_LOCATOR = (By.ID, "ModalDailyLogin")

# Your exact Google chooser row (first account)
GOOGLE_CHOOSER_PRIMARY_XPATH = "/html/body/div[2]/div[1]/div[1]/div[2]/c-wiz/main/div[2]/div/div/div[1]/form/span/section/div/div/div/div/ul/li[1]/div"

# Backup candidate XPaths for Google account row (handles minor A/B DOM shifts)
GOOGLE_ACCOUNT_XPATHS = [
    GOOGLE_CHOOSER_PRIMARY_XPATH,
    "/html/body/div[1]/div[1]/div[2]/div/div/div[2]/div/div/div[1]/form/span/section/div/div/div/div/ul/li[1]/div",
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
        if WebDriverWait(driver, 10).until(EC.visibility_of_element_located(OVERLAY_LOCATOR)):
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

def scan_windows_and_click_xpath(driver, target_xpath: str, timeout: int = 30) -> bool:
    """
    Keep switching among all open windows/tabs until we find an element matching target_xpath,
    click it, and return True. Returns False if not found within timeout.
    """
    end = time.monotonic() + timeout
    seen = set()
    while time.monotonic() < end:
        # refresh the handle set each pass (chooser can appear late)
        for handle in driver.window_handles:
            if handle in seen and len(driver.window_handles) > 1:
                # still try again, but prioritize unseen handles first
                continue
            try:
                driver.switch_to.window(handle)
            except Exception:
                continue
            seen.add(handle)

            try:
                el = WebDriverWait(driver, 2.5).until(
                    EC.element_to_be_clickable((By.XPATH, target_xpath))
                )
                safe_click(driver, el)
                return True
            except TimeoutException:
                # try the next handle
                pass

        time.sleep(0.3)
    return False

# ───────────────────────────────────────────────────────────
# Claim flow: claim → collect; countdown fallback
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

    # Step 1: Claim/Claim Reward button on store
    if not try_click_any(driver, CLAIM_REWARD_SELECTORS, timeout_each=5):
        cd = read_countdown_from_div(driver)
        if cd:
            await channel.send(f"Next No Limit Coins Bonus Available in: {cd}")
        else:
            await channel.send("[NoLimitCoins] Timed Out. Perhaps you need to authenticate?")
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
        await channel.send("[NoLimitCoins] Could not access countdown. Perhaps the x-path has changed?")
        await send_screenshot(channel, driver)

async def claim_nolimitcoins_bonus(ctx, driver, channel):
    """Same as nolimitcoins_flow but used post-login."""
    await nolimitcoins_flow(ctx, driver, channel)

# ───────────────────────────────────────────────────────────
# Auth (.env) → then claim
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
# Google OAuth with tab scan for chooser → click → back to main
# ───────────────────────────────────────────────────────────
async def auth_nolimit_google(driver, channel, ctx):
    """
    Opens NLC sign-in, clicks the 'Continue with Google' button,
    then iterates through all open windows/tabs until it finds the chooser
    element at GOOGLE_CHOOSER_PRIMARY_XPATH, clicks it, and finally returns
    to the original tab.
    """
    try:
        driver.get(SIGNIN_URL)
        await asyncio.sleep(5)

        # Click "Continue with Google" on NLC
        google_btn = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div[1]/div/form/div[1]/button[2]"))
        )
        safe_click(driver, google_btn)

        main_handle = driver.current_window_handle

        # Keep scanning tabs for the chooser element and click it
        clicked = scan_windows_and_click_xpath(driver, GOOGLE_CHOOSER_PRIMARY_XPATH, timeout=30)

        if not clicked:
            # Try the backups if the primary failed (A/B markup differences)
            for xp in GOOGLE_ACCOUNT_XPATHS[1:]:
                if scan_windows_and_click_xpath(driver, xp, timeout=12):
                    clicked = True
                    break

        if not clicked:
            raise TimeoutException("Account chooser element not found/clickable in any tab")

        # Return to main tab and wait to land back on nolimitcoins
        driver.switch_to.window(main_handle)
        WebDriverWait(driver, 30).until(lambda d: "nolimitcoins.com" in (d.current_url or "").lower())
        await asyncio.sleep(2)

        await channel.send("Authenticated into NoLimitCoins!")
    except Exception:
        await channel.send("NoLimitCoins login with Google failed. Perhaps you need to run !auth google again or try .env auth.")
