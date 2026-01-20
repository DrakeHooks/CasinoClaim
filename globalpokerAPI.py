# Drake Hooks
# Casino Claim 2
# Global Poker API (hardened)
#
# Goals:
# - Stop relying on brittle absolute XPaths where possible
# - Add “debug-like” pacing without screenshots (settle delays + retries)
# - Make login detection more robust (already-logged-in vs login form)
# - Make Get Coins + daily bonus flow more resilient
# - Add clear Discord error messages (instead of silent failures)

import os
import re
import time
import asyncio
from dotenv import load_dotenv

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
    ElementNotInteractableException,
    WebDriverException,
)

load_dotenv()

# ───────────────────────────────────────────────────────────
# Config knobs (set in .env if you want)
# ───────────────────────────────────────────────────────────
GP_PAGELOAD_TIMEOUT = int(os.getenv("GP_PAGELOAD_TIMEOUT", "25"))
GP_WAIT_TIMEOUT = int(os.getenv("GP_WAIT_TIMEOUT", "18"))

# These are the “debug-mode magic” delays (tunable)
GP_POST_NAV_SETTLE = float(os.getenv("GP_POST_NAV_SETTLE", "6"))          # after driver.get()
GP_POST_LOGIN_SETTLE = float(os.getenv("GP_POST_LOGIN_SETTLE", "6"))      # after clicking login
GP_AFTER_GET_COINS_SETTLE = float(os.getenv("GP_AFTER_GET_COINS_SETTLE", "4"))
GP_RETRY_ON_FAILURE = int(os.getenv("GP_RETRY_ON_FAILURE", "1"))          # 0/1/2
GP_RETRY_SETTLE = float(os.getenv("GP_RETRY_SETTLE", "10"))              # wait before retrying

GP_URL = "https://play.globalpoker.com/"


# ───────────────────────────────────────────────────────────
# Small async sleep helper (cancel friendly)
# ───────────────────────────────────────────────────────────
async def _sleep(seconds: float):
    end = time.monotonic() + max(0.0, float(seconds))
    while True:
        rem = end - time.monotonic()
        if rem <= 0:
            return
        await asyncio.sleep(min(0.5, rem))


# ───────────────────────────────────────────────────────────
# Selenium helpers
# ───────────────────────────────────────────────────────────
def _wait(driver, timeout=GP_WAIT_TIMEOUT):
    return WebDriverWait(driver, timeout)

def _is_cloudflare_or_interstitial(driver) -> bool:
    """Detect common bot-check/interstitial states."""
    try:
        url = (driver.current_url or "").lower()
    except Exception:
        url = ""
    try:
        title = (driver.title or "").lower()
    except Exception:
        title = ""

    if "challenge" in url or "captcha" in url:
        return True
    if "cloudflare" in title or "just a moment" in title:
        return True

    # Text sniff (cheap)
    try:
        body = driver.page_source.lower()
        if "just a moment" in body or "checking your browser" in body or "cf-browser-verification" in body:
            return True
    except Exception:
        pass

    return False

def _safe_click(driver, by, sel, timeout=GP_WAIT_TIMEOUT) -> bool:
    """Wait clickable → click. Returns True if clicked."""
    try:
        el = _wait(driver, timeout).until(EC.element_to_be_clickable((by, sel)))
        try:
            el.click()
        except (ElementClickInterceptedException, ElementNotInteractableException):
            driver.execute_script("arguments[0].click();", el)
        return True
    except TimeoutException:
        return False
    except StaleElementReferenceException:
        return False

def _safe_send_keys(driver, by, sel, text: str, timeout=GP_WAIT_TIMEOUT) -> bool:
    try:
        el = _wait(driver, timeout).until(EC.presence_of_element_located((by, sel)))
        el.clear()
        el.send_keys(text)
        return True
    except TimeoutException:
        return False
    except Exception:
        return False

def _any_present(driver, locators, timeout=6):
    """Return first element found, else None."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        for by, sel in locators:
            try:
                els = driver.find_elements(by, sel)
                if els:
                    return els[0]
            except Exception:
                pass
        time.sleep(0.2)
    return None

def _text_of(driver, by, sel) -> str:
    try:
        el = driver.find_element(by, sel)
        return (el.text or "").strip()
    except Exception:
        return ""

def _countdown_from_dom(driver) -> str:
    """
    Try multiple strategies:
    1) Your obfuscated class pattern span
    2) Generic time-looking text like 12:34:56
    3) Any element that contains 'Next' + ':' etc
    Return countdown text or "".
    """
    # 1) Your existing obfuscated class logic
    try:
        letters = "abcdefghijklmnopqrstuvwxyz"
        classes = [f"{char * 6}_e" for char in letters]
        xpath = "//span[" + " or ".join(f"contains(@class, '{cls}')" for cls in classes) + "]"
        el = _wait(driver, 4).until(EC.presence_of_element_located((By.XPATH, xpath)))
        txt = (el.text or "").strip()
        if txt:
            return txt
    except TimeoutException:
        pass
    except Exception:
        pass

    # 2) Time-looking text anywhere
    # Common patterns: H:MM:SS, HH:MM:SS, MM:SS
    patterns = [
        re.compile(r"\b\d{1,2}:\d{2}:\d{2}\b"),
        re.compile(r"\b\d{1,2}:\d{2}\b"),
    ]
    try:
        # sample a reasonable set of elements
        candidates = driver.find_elements(By.XPATH, "//*[normalize-space(text())!='']")
        for el in candidates[:250]:
            try:
                t = (el.text or "").strip()
                if not t or len(t) > 40:
                    continue
                for p in patterns:
                    if p.search(t):
                        return t
            except Exception:
                continue
    except Exception:
        pass

    return ""


# ───────────────────────────────────────────────────────────
# Login (robust)
# ───────────────────────────────────────────────────────────
async def login_to_global_poker(driver, channel) -> bool:
    """
    Attempts to ensure we're logged in.
    - Navigates to GP_URL
    - If login form appears, uses GLOBAL_POKER=user:pass and submits
    - If already logged in, returns True
    """
    try:
        driver.set_page_load_timeout(GP_PAGELOAD_TIMEOUT)
    except Exception:
        pass

    try:
        driver.get(GP_URL)
    except WebDriverException as e:
        await channel.send(f"[GlobalPoker] Failed to load site: `{e}`")
        return False

    await _sleep(GP_POST_NAV_SETTLE)

    # If Cloudflare / interstitial, wait a bit longer
    if _is_cloudflare_or_interstitial(driver):
        await channel.send("[GlobalPoker] Interstitial detected (bot-check). Waiting…")
        await _sleep(10)
        if _is_cloudflare_or_interstitial(driver):
            await channel.send("[GlobalPoker] Still on interstitial. Try again later or check extension/CAPTCHA solver.")
            return False

    # Detect login form in a resilient way
    login_locators = [
        # common input types
        (By.CSS_SELECTOR, "input[type='email']"),
        (By.CSS_SELECTOR, "input[type='text']"),
        (By.CSS_SELECTOR, "input[type='password']"),
        # your original absolute XPaths (fallback)
        (By.XPATH, "/html/body/main/div/div[2]/form//input"),
    ]

    # Heuristic: if we see a password field, we’re likely on login
    pw = _any_present(driver, [(By.CSS_SELECTOR, "input[type='password']")], timeout=3)

    if not pw:
        # no password field → likely already logged in
        print("[GlobalPoker] Already logged in (no password field detected).")
        return True

    creds = os.getenv("GLOBAL_POKER", "").strip()
    if not creds or ":" not in creds:
        await channel.send("[GlobalPoker] GLOBAL_POKER credentials missing or invalid. Use `GLOBAL_POKER=email:password`.")
        return False

    username, password = creds.split(":", 1)

    # Try to target fields
    # Username/email: prefer email; fallback to first visible text input
    user_ok = False
    for sel in ("input[type='email']", "input[name*='email' i]", "input[name*='user' i]", "input[type='text']"):
        if _safe_send_keys(driver, By.CSS_SELECTOR, sel, username, timeout=6):
            user_ok = True
            break

    pass_ok = _safe_send_keys(driver, By.CSS_SELECTOR, "input[type='password']", password, timeout=6)

    if not (user_ok and pass_ok):
        # last resort: your old absolute paths (kept)
        try:
            uel = _wait(driver, 5).until(EC.presence_of_element_located((
                By.XPATH,
                "/html/body/main/div/div[2]/form/div/div/div/div/div[2]/div[2]/span/div/div/div/div/div/div/div/div/div[2]/div[3]/div[1]/div/input"
            )))
            pel = _wait(driver, 5).until(EC.presence_of_element_located((
                By.XPATH,
                "/html/body/main/div/div[2]/form/div/div/div/div/div[2]/div[2]/span/div/div/div/div/div/div/div/div/div[2]/div[3]/div[2]/div/div/input"
            )))
            uel.clear(); uel.send_keys(username)
            pel.clear(); pel.send_keys(password)
            user_ok = pass_ok = True
        except Exception:
            await channel.send("[GlobalPoker] Could not locate login fields.")
            return False

    await _sleep(0.8)

    # Click submit: prefer a visible button with submit, else press Enter
    clicked = _safe_click(driver, By.CSS_SELECTOR, "button[type='submit']", timeout=6)
    if not clicked:
        clicked = _safe_click(driver, By.NAME, "submit", timeout=4)

    if not clicked:
        try:
            # press Enter in password field
            driver.switch_to.active_element.send_keys(Keys.ENTER)
            clicked = True
        except Exception:
            pass

    if not clicked:
        await channel.send("[GlobalPoker] Login submit button not found.")
        return False

    await _sleep(GP_POST_LOGIN_SETTLE)

    # If we’re still on a login-like page with password visible, consider it failed
    if _any_present(driver, [(By.CSS_SELECTOR, "input[type='password']")], timeout=2):
        await channel.send("[GlobalPoker] Login may have failed (still seeing password field).")
        return False

    print("[GlobalPoker] Logged in successfully.")
    return True


# ───────────────────────────────────────────────────────────
# Get Coins button (robust)
# ───────────────────────────────────────────────────────────
async def click_get_coins_button(driver, channel) -> bool:
    """
    Open the daily bonus / store modal.
    Try multiple selectors:
    - Text contains "Get Coins"
    - Button in header
    - Your original XPath fallback
    """
    # Give the UI time to hydrate
    await _sleep(1.0)

    selectors = [
        (By.XPATH, "//button[contains(., 'Get Coins') or contains(., 'GET COINS')]"),
        (By.XPATH, "//*[self::button or self::a][contains(., 'Get Coins') or contains(., 'GET COINS')]"),
        # sometimes it's an icon button; look for aria-label
        (By.CSS_SELECTOR, "button[aria-label*='coin' i]"),
        # your original absolute XPath fallback
        (By.XPATH, "/html/body/div[2]/div/div[1]/div/div[4]/button"),
    ]

    for by, sel in selectors:
        if _safe_click(driver, by, sel, timeout=6):
            print("[GlobalPoker] 'Get Coins' clicked.")
            await _sleep(GP_AFTER_GET_COINS_SETTLE)
            return True

    await channel.send("[GlobalPoker] 'Get Coins' button not found.")
    return False


# ───────────────────────────────────────────────────────────
# Claim bonus (robust-ish with fallbacks)
# ───────────────────────────────────────────────────────────
async def claim_global_poker_bonus(ctx, driver, channel) -> bool:
    """
    Attempt to click daily claim items after Get Coins modal is open.
    Your original list used very brittle /html/body/div[8]… XPaths.
    We'll:
    - try “Claim/Collect/Free” buttons by text first
    - then fall back to your known XPaths
    """
    # 1) Text-based claim buttons (preferred)
    claim_text_xpaths = [
        "//*[self::button or self::div or self::a][contains(., 'Claim') or contains(., 'CLAIM')]",
        "//*[self::button or self::div or self::a][contains(., 'Collect') or contains(., 'COLLECT')]",
        "//*[self::button or self::div or self::a][contains(., 'Free') or contains(., 'FREE')]",
    ]
    for xp in claim_text_xpaths:
        try:
            el = _wait(driver, 4).until(EC.element_to_be_clickable((By.XPATH, xp)))
            try:
                el.click()
            except Exception:
                driver.execute_script("arguments[0].click();", el)
            await _sleep(2)
            await channel.send("Global Poker Daily Bonus Claimed!")
            return True
        except TimeoutException:
            pass
        except Exception:
            pass

    # 2) Fallback: your original XPaths
    button_xpaths = [
        "/html/body/div[8]/div/div/div[2]/div[2]/div[2]/div/div[2]/div[2]/div[1]",
        "/html/body/div[8]/div/div/div[2]/div[2]/div[2]/div/div[2]/div[2]/div[2]",
        "/html/body/div[8]/div/div/div[2]/div[2]/div[2]/div/div[2]/div[2]/div[3]",
        "/html/body/div[8]/div/div/div[2]/div[2]/div[2]/div/div[2]/div[2]/div[4]",
        "/html/body/div[8]/div/div/div[2]/div[2]/div[2]/div/div[2]/div[2]/div[5]",
        "/html/body/div[8]/div/div/div[2]/div[2]/div[2]/div/div[2]/div[2]/div[6]",
        "/html/body/div[8]/div/div/div[2]/div[2]/div[2]/div/div[2]/div[2]/div[7]",
    ]

    bonus_claimed = False
    for button_xpath in button_xpaths:
        try:
            claim_button = _wait(driver, 4).until(EC.element_to_be_clickable((By.XPATH, button_xpath)))
            try:
                claim_button.click()
            except Exception:
                driver.execute_script("arguments[0].click();", claim_button)
            bonus_claimed = True
            print(f"[GlobalPoker] Clicked bonus button: {button_xpath}")
            await _sleep(1.5)
            break
        except TimeoutException:
            continue
        except Exception:
            continue

    if bonus_claimed:
        await channel.send("Global Poker Daily Bonus Claimed!")
        return True

    print("[GlobalPoker] No claim button clickable.")
    return False


# ───────────────────────────────────────────────────────────
# Main flow
# ───────────────────────────────────────────────────────────
async def global_poker(ctx, driver, channel):
    """
    Behavior:
    - Ensure logged in
    - Open Get Coins modal
    - If countdown found → report it
    - Else attempt claim
    - On failure → one retry with refresh + longer settle (debug-like)
    """
    last_err = None

    for attempt in range(0, max(0, GP_RETRY_ON_FAILURE) + 1):
        try:
            if attempt > 0:
                await channel.send(f"[GlobalPoker] Retrying… (attempt {attempt+1})")
                try:
                    driver.refresh()
                except Exception:
                    pass
                await _sleep(GP_RETRY_SETTLE)

            ok = await login_to_global_poker(driver, channel)
            if not ok:
                return

            # Extra settle to mimic debug-mode delays
            await _sleep(2.0)

            opened = await click_get_coins_button(driver, channel)
            if not opened:
                return

            # Check countdown first
            countdown_value = _countdown_from_dom(driver)
            if countdown_value:
                await channel.send(f"Next Global Poker Bonus Available in: {countdown_value}")
                return

            # No countdown found → attempt claim
            claimed = await claim_global_poker_bonus(ctx, driver, channel)
            if claimed:
                # After claiming, countdown usually becomes visible; try to report it
                await _sleep(2.5)
                cd2 = _countdown_from_dom(driver)
                if cd2:
                    await channel.send(f"Next Global Poker Bonus Available in: {cd2}")
                return

            # If neither countdown nor claim worked, one more settle then re-check countdown
            await _sleep(3.0)
            countdown_value = _countdown_from_dom(driver)
            if countdown_value:
                await channel.send(f"Next Global Poker Bonus Available in: {countdown_value}")
                return

            # If still nothing, treat as failure to allow retry
            raise TimeoutException("Neither countdown nor claim button detected in Get Coins modal.")

        except Exception as e:
            last_err = e
            # if no retries left, report
            if attempt >= GP_RETRY_ON_FAILURE:
                try:
                    url = driver.current_url
                except Exception:
                    url = "unknown"
                await channel.send(f"[GlobalPoker] Failed: `{type(e).__name__}: {e}` (url: `{url}`)")
                return

    # safety
    if last_err:
        await channel.send(f"[GlobalPoker] Failed: `{type(last_err).__name__}: {last_err}`")
