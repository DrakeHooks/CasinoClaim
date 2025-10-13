# Drake Hooks + WaterTrooper
# Casino Claim 2
# Funrize API (countdown-first; modal-aware; no false “claimed”)

import os
import re
import asyncio
import discord
from dotenv import load_dotenv
from typing import Optional, Iterable

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException

# ───────────────────────────────────────────────────────────
# Config & Constants
# ───────────────────────────────────────────────────────────
load_dotenv()
FUNRIZE_CRED = os.getenv("FUNRIZE")  # "username:password"

SITE_URL  = "https://funrize.com"
STORE_URL = "https://funrize.com/promotions"

# Buttons / controls
CLAIM_CARD_CLASS = "daily-login-prize"  # opens daily reward modal

# Collect buttons inside modal (a few indices for safety)
COLLECT_XPATHS = [
    "/html/body/div[3]/div/div/div[2]/div[2]/button",
    "/html/body/div[4]/div/div/div[2]/div[2]/button",
    "/html/body/div[5]/div/div/div[2]/div[2]/button",
    "/html/body/div[6]/div/div/div[2]/div[2]/button",
]

# Countdown on promotions page (wrapper DIV) – corrected
COUNTDOWN_PAGE_XPATH = "/html/body/div[1]/div/div[1]/main/div/div/div[2]/div[6]/div/div[2]/div[1]/div[1]/div"

# Countdown inside the modal (your provided xpath)
COUNTDOWN_MODAL_XPATH = "/html/body/div[3]/div/div/div[2]/div[2]/div/span[2]/span"

# Modal root to wait for close
MODAL_ROOT_XPATHS = [
    "/html/body/div[3]/div",
    "/html/body/div[4]/div",
    "/html/body/div[5]/div",
    "/html/body/div[6]/div",
]

# ───────────────────────────────────────────────────────────
# Small helpers
# ───────────────────────────────────────────────────────────
def wait_clickable(driver, by, sel, timeout=10):
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, sel)))

def wait_present(driver, by, sel, timeout=10):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, sel)))

def is_present(driver, by, sel, timeout=0.5) -> bool:
    try:
        WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, sel)))
        return True
    except TimeoutException:
        return False

def wait_invisible_any(driver, xpaths: Iterable[str], timeout=6) -> bool:
    """True if any of the given nodes becomes invisible (modal closed)."""
    for xp in xpaths:
        try:
            if WebDriverWait(driver, timeout).until(EC.invisibility_of_element_located((By.XPATH, xp))):
                return True
        except TimeoutException:
            continue
    return False

def safe_click(driver, el):
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    except Exception:
        pass
    try:
        el.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", el)

def try_click_any(driver, selectors: Iterable[tuple], timeout_each=4) -> bool:
    for by, sel in selectors:
        try:
            el = wait_clickable(driver, by, sel, timeout_each)
            safe_click(driver, el)
            return True
        except Exception:
            continue
    return False

def try_click_any_xpath(driver, xpaths: Iterable[str], timeout_each=4) -> bool:
    return try_click_any(driver, [(By.XPATH, xp) for xp in xpaths], timeout_each)

def _normalize_hms_from_text(text: str) -> Optional[str]:
    """
    Accepts '07 H 11 M 7 S', '12 H 11 M', '23 : 55 : 33', etc.
    Returns HH:MM:SS (seconds default to 00 if missing).
    """
    if not text:
        return None
    t = " ".join(text.split())

    m = re.search(r"(\d{1,2})\s*[:]\s*(\d{1,2})(?:\s*[:]\s*(\d{1,2}))?", t)
    if m:
        h, mm, ss = m.group(1), m.group(2), m.group(3) or "00"
        return f"{int(h):02d}:{int(mm):02d}:{int(ss):02d}"

    m = re.search(r"(?:(\d{1,2})\s*[Hh])?(?:\s*(\d{1,2})\s*[Mm])?(?:\s*(\d{1,2})\s*[Ss])?", t)
    if m:
        h = m.group(1) if m.group(1) else "0"
        mm = m.group(2) if m.group(2) else "0"
        ss = m.group(3) if m.group(3) else "0"
        if h == "0" and mm == "0" and ss == "0":
            return None
        return f"{int(h):02d}:{int(mm):02d}:{int(ss):02d}"
    return None

def read_countdown_by_xpath(driver, xpath: str, timeout=3) -> Optional[str]:
    try:
        node = wait_present(driver, By.XPATH, xpath, timeout)
        return _normalize_hms_from_text(node.text)
    except TimeoutException:
        return None

def read_funrize_page_countdown(driver) -> Optional[str]:
    return read_countdown_by_xpath(driver, COUNTDOWN_PAGE_XPATH, timeout=4)

def read_funrize_modal_countdown(driver) -> Optional[str]:
    # The countdown spans may be split; text() should still concatenate.
    return read_countdown_by_xpath(driver, COUNTDOWN_MODAL_XPATH, timeout=1.5)

async def send_screenshot(channel: discord.TextChannel, driver, name="funrize.png"):
    driver.save_screenshot(name)
    await channel.send(file=discord.File(name))
    try:
        os.remove(name)
    except OSError:
        pass

# ───────────────────────────────────────────────────────────
# Flow: countdown first → open card → modal timer? → try collect
# ───────────────────────────────────────────────────────────
async def funrize_flow(ctx, driver, channel):
    driver.get(STORE_URL)
    await asyncio.sleep(2)

    # 1) Report PAGE countdown first if present
    cd = read_funrize_page_countdown(driver)
    if cd:
        await channel.send(f"Next Funrize Bonus Available in: {cd}")
        return

    # 2) No page timer → open the daily card (modal)
    opened = False
    try:
        card = wait_clickable(driver, By.CLASS_NAME, CLAIM_CARD_CLASS, timeout=7)
        safe_click(driver, card)
        opened = True
        await asyncio.sleep(1)
    except TimeoutException:
        pass

    # 3) If modal shows a countdown, report it and stop
    if opened:
        modal_cd = read_funrize_modal_countdown(driver)
        if modal_cd:
            await channel.send(f"Next Funrize Bonus Available in: {modal_cd}")
            return

    # 4) Try to find & click a Collect button in the modal
    if opened:
        clicked = try_click_any_xpath(driver, COLLECT_XPATHS, timeout_each=4)
        if clicked:
            # Confirm claim by modal closing OR absence of any timers
            closed = wait_invisible_any(driver, MODAL_ROOT_XPATHS, timeout=6)
            if not closed:
                # If modal didn't close, check again if a timer is present (means NOT claimable)
                modal_cd = read_funrize_modal_countdown(driver)
                if modal_cd:
                    await channel.send(f"Next Funrize Bonus Available in: {modal_cd}")
                    return

            # As a final sanity check, refresh page timer: if still no timer → assume claimed
            await asyncio.sleep(0.5)
            page_cd = read_funrize_page_countdown(driver)
            if not page_cd:
                await channel.send("Funrize Daily Bonus Claimed!")
                await send_screenshot(channel, driver)
                return
            else:
                await channel.send(f"Next Funrize Bonus Available in: {page_cd}")
                return

    # 5) Nothing actionable → likely logged out; do login flow
    await funrize_casino(ctx, driver, channel)

# ───────────────────────────────────────────────────────────
# Login then retry (countdown-first again)
# ───────────────────────────────────────────────────────────
async def funrize_casino(ctx, driver, channel):
    if not FUNRIZE_CRED:
        await channel.send("Funrize credentials not found in environment variables.")
        return

    username, password = FUNRIZE_CRED.split(":", 1)

    driver.get(SITE_URL)
    await asyncio.sleep(2)

    try:
        # Open login modal
        login_btn = wait_clickable(driver, By.CLASS_NAME, "login-btn", timeout=10)
        safe_click(driver, login_btn)
        await asyncio.sleep(0.6)

        email = wait_present(driver, By.XPATH,
            "/html/body/div[1]/div/div[1]/div/div/div/div[1]/div/div[2]/form/label[1]/div[2]/input", 10)
        email.send_keys(username)
        await asyncio.sleep(0.2)

        pw = wait_present(driver, By.XPATH,
            "/html/body/div[1]/div/div[1]/div/div/div/div[1]/div/div[2]/form/label[2]/div[2]/input", 10)
        pw.send_keys(password, Keys.ENTER)

        await asyncio.sleep(2.5)
        await funrize_flow(ctx, driver, channel)

    except TimeoutException:
        await channel.send("Funrize login timed out, will retry later.")
        await send_screenshot(channel, driver, "funrize_login_error.png")

# ───────────────────────────────────────────────────────────
# Standalone countdown reader
# ───────────────────────────────────────────────────────────
async def check_funrize_countdown(ctx, driver, channel):
    driver.get(STORE_URL)
    await asyncio.sleep(2)
    cd = read_funrize_page_countdown(driver)
    if cd:
        await channel.send(f"Next Funrize Bonus Available in: {cd}")
    else:
        # Open modal and try modal timer as a backup
        try:
            card = wait_clickable(driver, By.CLASS_NAME, CLAIM_CARD_CLASS, timeout=5)
            safe_click(driver, card)
            await asyncio.sleep(0.6)
            modal_cd = read_funrize_modal_countdown(driver)
            if modal_cd:
                await channel.send(f"Next Funrize Bonus Available in: {modal_cd}")
                return
        except TimeoutException:
            pass
        await channel.send("Funrize: No countdown found.")
        await send_screenshot(channel, driver)
