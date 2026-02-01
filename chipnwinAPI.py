# Drake Hooks + WaterTrooper
# Casino Claim 2
# Chipnwin API
# Version 4 (fix: only announce "claimed" when it actually claims)
# Notes:
# - Chipnwin appears to always show a countdown. So:
#   - We ONLY send "Chipnwin Daily Bonus Claimed!" if we click Claim AND we see evidence the claim succeeded.
#   - Otherwise, we ONLY send the countdown message.
# - Also fixes: check_chipnwin_countdown() used a bad constant name (XPATH_COUNTDOWN).

import re
import os
import asyncio
import discord
from dotenv import load_dotenv

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
)

# ───────────────────────────────────────────────────────────
# Config & Constants
# ───────────────────────────────────────────────────────────
load_dotenv()
CHIPNWIN_CRED = os.getenv("CHIPNWIN")  # format "username:password"
SITE_URL = "https://chipnwin.com"
STORE_URL = "https://chipnwin.com/store/features"

COOKIE_BUTTON_XPATHS = [
    "/html/body/div[1]/div[6]/div/div[2]/button",
    "/html/body/div[1]/div[7]/div/div[2]/button",
]

LOGIN_BUTTON_XPATH = "/html/body/div[1]/div[3]/div[1]/div[2]/div[1]/button"

EMAIL_INPUT_ID = "input_customemail"
PASSWORD_INPUT_ID = "input_custompassword"

LOGIN_SUBMIT_XPATHS = [
    "/html/body/div[1]/div[6]/div/div[2]/div[2]/div[5]/div/button",
    "/html/body/div[1]/div[7]/div/div[2]/div[2]/div[5]/div/button",
]

START_BUTTON_XPATHS = [
    "/html/body/div[1]/div[3]/div/div[1]/div[3]/div[2]/div[3]/div[4]/div[2]/button",
    "/html/body/div[1]/div[4]/div/div[1]/div[3]/div[2]/div[3]/div[4]/div[2]/button",
]

CLAIM_BUTTON_XPATHS = [
    "/html/body/div[1]/div[6]/div/div[2]/div[3]/button",
    "/html/body/div[1]/div[7]/div/div[2]/div[3]/button",
    "/html/body/div[1]/div[8]/div/div[2]/div[3]/button",
]

SPINWIN_BUTTON_XPATHS = [
    "/html/body/div[1]/div[3]/div/div[1]/div[3]/div[2]/div[2]/div[4]/div[2]/button",
    "/html/body/div[1]/div[4]/div/div[1]/div[3]/div[2]/div[2]/div[4]/div[2]/button",
]

SPIN_BUTTON_XPATHS = [
    "/html/body/div[1]/div[6]/div/div[3]/div/button",
    "/html/body/div[1]/div[7]/div/div[3]/div/button",
]

# Countdown element (has ":" in it like "22 : 27 : 06")
COUNTDOWN_XPATH = "//p[starts-with(@class, 's14__w500__h22') and contains(normalize-space(.), ':')]"

# ───────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────
def _is_logged_in(driver) -> bool:
    """Detect if already logged in."""
    try:
        driver.find_element(By.XPATH, "//p[@class='s12__w500__h18 color_1BB83D line_height_normal_important']")
        return True
    except NoSuchElementException:
        pass

    try:
        driver.find_element(By.XPATH, "//span[@data-test='balance']")
        return True
    except NoSuchElementException:
        return False


def _clean_countdown(raw: str) -> str:
    # "22 : 27 : 06" -> "22:27:06"
    return re.sub(r"\s+", "", raw.strip())


def _scroll_into_view(driver, el) -> None:
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", el)
    except Exception:
        pass


def _safe_click(driver, el) -> bool:
    """
    Try normal click, then JS click.
    Returns True if it *appears* clicked (no exception), False otherwise.
    """
    try:
        _scroll_into_view(driver, el)
        el.click()
        return True
    except (ElementClickInterceptedException, Exception):
        try:
            _scroll_into_view(driver, el)
            driver.execute_script("arguments[0].click();", el)
            return True
        except Exception:
            return False


def _first_clickable(driver, xpaths, timeout=6):
    """
    Returns (xpath, element) for the first xpath that becomes clickable, else (None, None).
    """
    for xp in xpaths:
        try:
            el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xp)))
            return xp, el
        except TimeoutException:
            continue
        except Exception:
            continue
    return None, None


def _read_countdown(driver, timeout=10) -> str | None:
    """
    Reads countdown text if present, returns cleaned countdown "HH:MM:SS", else None.
    """
    try:
        el = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, COUNTDOWN_XPATH)))
        raw = el.text
        return _clean_countdown(raw)
    except TimeoutException:
        return None
    except Exception:
        return None


def _confirm_claim_succeeded(driver, clicked_element, timeout=8) -> bool:
    """
    We only want to announce 'claimed' if the click actually triggered a state change.

    Confirmation strategy (fast + resilient):
    - If the clicked claim button becomes stale (modal re-render), treat as success.
    - OR if the clicked button text changes away from "Claim" (e.g., "Claimed") within timeout.
    - OR if a visible element anywhere contains "claimed"/"success"/"congrat" (toast/modal copy).

    This avoids the old behavior where we announce claim just because a button existed.
    """
    # 1) Stale element -> UI re-render -> likely success
    try:
        WebDriverWait(driver, timeout).until(EC.staleness_of(clicked_element))
        return True
    except TimeoutException:
        pass
    except Exception:
        pass

    # 2) Button text changes away from "Claim"
    try:
        before = (clicked_element.text or "").strip().lower()
        # If it already wasn't "claim", this doesn't help much; still try other checks.
        def _btn_changed(_driver):
            try:
                txt = (clicked_element.text or "").strip().lower()
                # text changed (or now includes "claimed")
                if "claimed" in txt:
                    return True
                if before and txt and txt != before and ("claim" not in txt):
                    return True
                return False
            except Exception:
                return False

        if WebDriverWait(driver, timeout).until(_btn_changed):
            return True
    except TimeoutException:
        pass
    except Exception:
        pass

    # 3) Generic success text anywhere visible (toast/modal)
    # Keep this broad but not too expensive.
    success_xpaths = [
        "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'claimed')]",
        "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'success')]",
        "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'congrat')]",
        "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'reward')]",
    ]
    for xp in success_xpaths:
        try:
            WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.XPATH, xp)))
            # Presence alone can be noisy; prefer visible if possible.
            try:
                el = driver.find_element(By.XPATH, xp)
                if el and el.is_displayed():
                    return True
            except Exception:
                return True
        except TimeoutException:
            continue
        except Exception:
            continue

    return False


# ───────────────────────────────────────────────────────────
# 1) Login & then hand off to claim
# ───────────────────────────────────────────────────────────
async def chipnwin_casino(ctx, driver, channel):
    if not CHIPNWIN_CRED:
        await channel.send("❌ Missing `CHIPNWIN` as 'email:password' in your .env.")
        return

    username, password = CHIPNWIN_CRED.split(":", 1)

    print("[Chipnwin] Navigating to site…")
    driver.get(SITE_URL)
    await asyncio.sleep(6)

    # Accept cookies (best-effort)
    print("[Chipnwin] Attempting to accept cookie...")
    for cb in COOKIE_BUTTON_XPATHS:
        try:
            cookie = WebDriverWait(driver, 4).until(EC.element_to_be_clickable((By.XPATH, cb)))
            if _safe_click(driver, cookie):
                await asyncio.sleep(2)
                break
        except TimeoutException:
            pass
        except Exception:
            pass

    if _is_logged_in(driver):
        print("[Chipnwin] Already logged in, skipping login.")
        await claim_chipnwin_bonus(ctx, driver, channel)
        return

    print("[Chipnwin] Attempting to login...")
    try:
        # Open login modal
        try:
            login_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, LOGIN_BUTTON_XPATH)))
            _safe_click(driver, login_btn)
            await asyncio.sleep(3)
        except Exception:
            print("[Chipnwin] Unable to click login button.")

        # Fill credentials
        try:
            email = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, EMAIL_INPUT_ID)))
            email.clear()
            email.send_keys(username)
            await asyncio.sleep(1)
        except Exception:
            print("[Chipnwin] Unable to enter email.")

        try:
            pw = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, PASSWORD_INPUT_ID)))
            pw.clear()
            pw.send_keys(password)
            await asyncio.sleep(1)
        except Exception:
            print("[Chipnwin] Unable to enter password.")

        # Submit
        submitted = False
        for ls in LOGIN_SUBMIT_XPATHS:
            try:
                btn = WebDriverWait(driver, 6).until(EC.element_to_be_clickable((By.XPATH, ls)))
                if _safe_click(driver, btn):
                    submitted = True
                    print("[Chipnwin] Submitted credentials.")
                    await asyncio.sleep(6)
                    break
            except Exception:
                continue

        if not submitted:
            print("[Chipnwin] Unable to submit login (no submit button clicked).")

        # Refresh to deal with popups / ensure session state
        print("[Chipnwin] Reloading page.")
        driver.refresh()
        await asyncio.sleep(4)

        await claim_chipnwin_bonus(ctx, driver, channel)

    except TimeoutException as e:
        screenshot = "chipnwin_login_error.png"
        driver.save_screenshot(screenshot)
        await channel.send(
            "Chipnwin login timed out, will retry later.",
            file=discord.File(screenshot),
        )
        os.remove(screenshot)
        print("Login timeout:", e)


# ───────────────────────────────────────────────────────────
# 2) After login: click the daily card + claim buttons
# ───────────────────────────────────────────────────────────
async def claim_chipnwin_bonus(ctx, driver, channel):
    print("[Chipnwin] Navigating to store…")
    driver.get(STORE_URL)
    await asyncio.sleep(5)

    # Open daily login menu (best-effort)
    print("[Chipnwin] Opening daily login menu...")
    _, start_btn = _first_clickable(driver, START_BUTTON_XPATHS, timeout=8)
    if start_btn:
        _safe_click(driver, start_btn)
        await asyncio.sleep(4)
    else:
        print("[Chipnwin] Start button not found/clickable.")

    # IMPORTANT FIX:
    # Only announce "claimed" if click happens AND we can confirm a post-click success state.
    print("[Chipnwin] Attempting to click Claim button...")
    claimed = False

    claim_xpath, claim_btn = _first_clickable(driver, CLAIM_BUTTON_XPATHS, timeout=6)
    if claim_btn:
        # Attempt click
        clicked = _safe_click(driver, claim_btn)
        if clicked:
            await asyncio.sleep(1.5)
            # Confirm it actually claimed (not just "button existed")
            if _confirm_claim_succeeded(driver, claim_btn, timeout=8):
                claimed = True

    if claimed:
        await channel.send("Chipnwin Daily Bonus Claimed!")
        return

    # If not claimed, report countdown (since it should always exist)
    countdown = _read_countdown(driver, timeout=12)
    if countdown:
        await channel.send(f"Next Chipnwin bonus available in: {countdown}")
    else:
        # fallback message if their UI changes
        await channel.send("Chipnwin: claim not available (could not read countdown).")


# ───────────────────────────────────────────────────────────
# 3) Standalone countdown reader
# ───────────────────────────────────────────────────────────
async def check_chipnwin_countdown(ctx, driver, channel):
    print("[Chipnwin] Navigating to store…")
    driver.get(STORE_URL)
    await asyncio.sleep(6)

    print("[Chipnwin] Checking for countdown timer…")
    countdown = _read_countdown(driver, timeout=12)
    if countdown:
        await channel.send(f"Next Chipnwin bonus available in: {countdown}")
    else:
        await channel.send("Chipnwin: could not read countdown.")


# ───────────────────────────────────────────────────────────
# 4) Daily Spin Wheel
# ───────────────────────────────────────────────────────────
async def spin_chipnwin_wheel(ctx, driver, channel):
    print("[Chipnwin] Navigating to store…")
    driver.get(STORE_URL)
    await asyncio.sleep(6)

    print("[Chipnwin] Opening Spin & Win...")
    _, spinwin_btn = _first_clickable(driver, SPINWIN_BUTTON_XPATHS, timeout=8)
    if spinwin_btn:
        _safe_click(driver, spinwin_btn)
        await asyncio.sleep(4)
    else:
        print("[Chipnwin] Spin & Win card not found/clickable.")

    print("[Chipnwin] Attempting to spin the wheel...")
    _, spin_btn = _first_clickable(driver, SPIN_BUTTON_XPATHS, timeout=8)
    if spin_btn and _safe_click(driver, spin_btn):
        await channel.send("Chipnwin Wheel Spun!")
    else:
        await channel.send("Chipnwin: spin not available (or could not click).")
