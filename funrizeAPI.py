# Drake Hooks + WaterTrooper
# Casino Claim 2
# Funrize — claim-first (Claim Now → COLLECT), then report store-page countdown

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

load_dotenv()
FUNRIZE_CRED = os.getenv("FUNRIZE")  # "username:password"

SITE_URL  = "https://funrize.com"
STORE_URL = "https://funrize.com/promotions"

# Store page “Claim Now”
X_CLAIM_NOW_PRIMARY = (By.XPATH, "/html/body/div[1]/div/div[1]/main/div/div/div[2]/div[6]/div/div[2]/div[2]/button")
X_CLAIM_NOW_BY_TEXT = (By.XPATH, "//button[normalize-space()='Claim Now']")

# Modal “COLLECT” button (primary + a few fallbacks)
COLLECT_XPATHS = [
    "/html/body/div[3]/div/div/div[2]/div[2]/button",
    "/html/body/div[4]/div/div/div[2]/div[2]/button",
    "/html/body/div[5]/div/div/div[2]/div[2]/button",
    "/html/body/div[6]/div/div/div[2]/div[2]/button",
    # text fallback
    "//div[contains(@class,'modal') or contains(@class,'Dialog')]//button[normalize-space()='Collect' or normalize-space()='COLLECT']",
]

# Countdown (store page + modal)
COUNTDOWN_PAGE_XPATH  = "/html/body/div[1]/div/div[1]/main/div/div/div[2]/div[6]/div/div[2]/div[1]/div[1]/div"
COUNTDOWN_MODAL_XPATH = "/html/body/div[3]/div/div/div[2]/div[2]/div/span[2]/span"

# Modal roots (to detect close)
MODAL_ROOT_XPATHS = [
    "/html/body/div[3]/div",
    "/html/body/div[4]/div",
    "/html/body/div[5]/div",
    "/html/body/div[6]/div",
]

# ── helpers ────────────────────────────────────────────────
def wait_clickable(driver, by, sel, timeout=8):
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, sel)))

def wait_present(driver, by, sel, timeout=8):
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

def try_click_any_xpath(driver, xpaths: Iterable[str], timeout_each=5) -> bool:
    for xp in xpaths:
        try:
            el = wait_clickable(driver, By.XPATH, xp, timeout_each)
            safe_click(driver, el)
            return True
        except Exception:
            continue
    return False

def wait_invisible_any(driver, xpaths: Iterable[str], timeout=6) -> bool:
    for xp in xpaths:
        try:
            if WebDriverWait(driver, timeout).until(EC.invisibility_of_element_located((By.XPATH, xp))):
                return True
        except TimeoutException:
            continue
    return False

def _normalize_hms_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    t = " ".join(text.split())
    m = re.search(r"(\d{1,2})\s*:\s*(\d{1,2})(?:\s*:\s*(\d{1,2}))?", t)
    if m:
        h, mm, ss = m.group(1), m.group(2), m.group(3) or "00"
        return f"{int(h):02d}:{int(mm):02d}:{int(ss):02d}"
    m = re.search(r"(?:(\d{1,2})\s*[Hh])?(?:\s*(\d{1,2})\s*[Mm])?(?:\s*(\d{1,2})\s*[Ss])?", t)
    if m:
        h = m.group(1) or "0"
        mm = m.group(2) or "0"
        ss = m.group(3) or "0"
        if h == "0" and mm == "0" and ss == "0":
            return None
        return f"{int(h):02d}:{int(mm):02d}:{int(ss):02d}"
    return None

def read_text_timer(driver, xpath: str, timeout=3) -> Optional[str]:
    try:
        node = wait_present(driver, By.XPATH, xpath, timeout)
        return _normalize_hms_from_text(node.text)
    except TimeoutException:
        return None

def page_countdown(driver) -> Optional[str]:
    return read_text_timer(driver, COUNTDOWN_PAGE_XPATH, timeout=4)

def modal_countdown(driver) -> Optional[str]:
    return read_text_timer(driver, COUNTDOWN_MODAL_XPATH, timeout=2)

# ── main flow ──────────────────────────────────────────────
async def funrize_flow(ctx, driver, channel):
    driver.get(STORE_URL)
    await asyncio.sleep(2)

    # 1) Click “Claim Now” on the store page (primary → text fallback)
    claim_now_clicked = False
    for locator in (X_CLAIM_NOW_PRIMARY, X_CLAIM_NOW_BY_TEXT):
        try:
            btn = wait_clickable(driver, *locator, timeout=4)
            safe_click(driver, btn)
            claim_now_clicked = True
            break
        except TimeoutException:
            continue

    if claim_now_clicked:
        # 2) In the modal: if COLLECT is clickable → click it
        if try_click_any_xpath(driver, COLLECT_XPATHS, timeout_each=6):
            # Wait for modal to close (or just settle), then read the store timer
            wait_invisible_any(driver, MODAL_ROOT_XPATHS, timeout=6)
            await asyncio.sleep(2)
            cd = page_countdown(driver)
            await channel.send("Funrize Daily Bonus Claimed!")
            if cd:
                await channel.send(f"Next Funrize Bonus Available in: {cd}")
            return

        # 3) If COLLECT wasn’t clickable, report the modal’s countdown (not claimable yet)
        cdm = modal_countdown(driver)
        if cdm:
            await channel.send(f"Next Funrize Bonus Available in: {cdm}")
            return
        # Fallback: store countdown
        cds = page_countdown(driver)
        if cds:
            await channel.send(f"Next Funrize Bonus Available in: {cds}")
            return
        # If neither visible, you might be logged out; fall through to login
    else:
        # 4) If “Claim Now” isn’t available, just show the store-page countdown
        cds = page_countdown(driver)
        if cds:
            await channel.send(f"Next Funrize Bonus Available in: {cds}")
            return

    # 5) If we get here, likely logged out → login and retry
    await funrize_casino(ctx, driver, channel)

# ── login then retry ───────────────────────────────────────
async def funrize_casino(ctx, driver, channel):
    if not FUNRIZE_CRED:
        await channel.send("Funrize credentials not found in environment variables.")
        return

    username, password = FUNRIZE_CRED.split(":", 1)

    driver.get(SITE_URL)
    await asyncio.sleep(2)

    try:
        login_btn = wait_clickable(driver, By.CLASS_NAME, "login-btn", timeout=10)
        safe_click(driver, login_btn)
        await asyncio.sleep(2)

        email = wait_present(driver, By.XPATH,
            "/html/body/div[1]/div/div[1]/div/div/div/div[1]/div/div[2]/form/label[1]/div[2]/input", 10)
        email.send_keys(username)
        await asyncio.sleep(2)

        pw = wait_present(driver, By.XPATH,
            "/html/body/div[1]/div/div[1]/div/div/div/div[1]/div/div[2]/form/label[2]/div[2]/input", 10)
        pw.send_keys(password, Keys.ENTER)

        await asyncio.sleep(2.5)
        # Retry claim-first flow
        await funrize_flow(ctx, driver, channel)

    except TimeoutException:
        await channel.send("Funrize login timed out, will retry later.")

# Optional: standalone countdown reader
async def check_funrize_countdown(ctx, driver, channel):
    driver.get(STORE_URL)
    await asyncio.sleep(2)
    cds = page_countdown(driver)
    if cds:
        await channel.send(f"Next Funrize Bonus Available in: {cds}")
        return
    # Try modal as a backup
    try:
        card = wait_clickable(driver, By.CLASS_NAME, "daily-login-prize", timeout=5)
        safe_click(driver, card)
        await asyncio.sleep(5)
        cdm = modal_countdown(driver)
        if cdm:
            await channel.send(f"Next Funrize Bonus Available in: {cdm}")
            return
    except TimeoutException:
        pass
    await channel.send("Funrize: No countdown found.")
