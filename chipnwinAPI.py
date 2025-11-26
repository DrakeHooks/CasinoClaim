# Drake Hooks + WaterTrooper
# Casino Claim 2
# Chipnwin API
# Version 3
# Notes:

import re
import os
import asyncio
import discord
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

# ───────────────────────────────────────────────────────────
# Config & Constants
# ───────────────────────────────────────────────────────────
load_dotenv()
CHIPNWIN_CRED = os.getenv("CHIPNWIN")  # format "username:password"
SITE_URL = "https://chipnwin.com"
STORE_URL = "https://chipnwin.com/store/features"

COOKIE_BUTTON_XPATHS = [
    "/html/body/div[1]/div[6]/div/div[2]/button",
    "/html/body/div[1]/div[7]/div/div[2]/button"
]

LOGIN_BUTTON_XPATH = ("/html/body/div[1]/div[3]/div[1]/div[2]/div[1]/button")

EMAIL_INPUT_ID = ("input_customemail")
PASSWORD_INPUT_ID = ("input_custompassword")
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
    "/html/body/div[1]/div[8]/div/div[2]/div[3]/button"
]

SPINWIN_BUTTON_XPATHS = [
    "/html/body/div[1]/div[3]/div/div[1]/div[3]/div[2]/div[2]/div[4]/div[2]/button",
    "/html/body/div[1]/div[4]/div/div[1]/div[3]/div[2]/div[2]/div[4]/div[2]/button",
]

SPIN_BUTTON_XPATHS = [
    "/html/body/div[1]/div[6]/div/div[3]/div/button",
    "/html/body/div[1]/div[7]/div/div[3]/div/button",
]

COUNTDOWN_XPATH = ("//p[starts-with(@class, 's14__w500__h22') and contains(normalize-space(.), ':')]")

# ───────────────────────────────────────────────────────────
# Chipnwin Helpers
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

# ───────────────────────────────────────────────────────────
# 1) Login & then hand off to claim
# ───────────────────────────────────────────────────────────
async def chipnwin_casino(ctx, driver, channel):
    if not CHIPNWIN_CRED:
        await channel.send("❌ Missing `CHIPNWIN` as 'email:password' in your .env.")
        return

    username, password = CHIPNWIN_CRED.split(":")

    # 1a) Navigate to site
    print("[Chipnwin] Navigating to site…")
    driver.get(SITE_URL)
    await asyncio.sleep(10)

    # 1b) Click the accept cookie button
    print("[Chipnwin] Attempting to accept cookie...")
    for cb in COOKIE_BUTTON_XPATHS:
        try:
            cookie = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, cb)))
            cookie.click()
            await asyncio.sleep(10)
        except TimeoutException:
            pass

    if _is_logged_in(driver):
        print("[Chipnwin] Already logged in, skipping login.")
        await claim_chipnwin_bonus(ctx, driver, channel)
        return

    # 1c) Login to site
    print("[Chipnwin] Attempting to login...")
    try:
        try:
            login_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, LOGIN_BUTTON_XPATH)))
            login_btn.click()
            await asyncio.sleep(10)
        except Exception:
            print("[Chipnwin] Unable to click login button.")

        try:
            email = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, EMAIL_INPUT_ID)))
            email.send_keys(username)
            await asyncio.sleep(5)
        except Exception:
            print("[Chipnwin] Unable to enter email.")

        try:
            pw = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, PASSWORD_INPUT_ID)))
            pw.send_keys(password)
            await asyncio.sleep(5)
        except Exception:
            print("[Chipnwin] Unable to enter password.")

        for ls in LOGIN_SUBMIT_XPATHS:
            try:
                empw_ln_btn = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, ls)))
                empw_ln_btn.click()
                print("[Chipnwin] Submitted credentials.")
                await asyncio.sleep(10)
            except Exception:
                print("[Chipnwin] Unable to submit login.")

        # Refresh the page to deal with popup
        print("[Chipnwin] Reloading page.")
        driver.refresh()
        await asyncio.sleep(5)

        # Now that we're logged in, try claiming
        await claim_chipnwin_bonus(ctx, driver, channel)

    except TimeoutException as e:
        screenshot = "chipnwin_login_error.png"
        driver.save_screenshot(screenshot)
        await channel.send(
            "Chipnwin login timed out, will retry later.",
            file=discord.File(screenshot)
        )
        os.remove(screenshot)
        print("Login timeout:", e)

# ───────────────────────────────────────────────────────────
# 2) After login: click the daily card + claim buttons
# ───────────────────────────────────────────────────────────
async def claim_chipnwin_bonus(ctx, driver, channel):
    # 2a) Navigate to store
    print("[Chipnwin] Navigating to store…")
    driver.get(STORE_URL)
    await asyncio.sleep(5)

    # 2b) Open daily login menu
    print("[Chipnwin] Opening daily login menu...")
    for sb in START_BUTTON_XPATHS:
        try:
            start_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, sb)))
            start_btn.click()
            await asyncio.sleep(10)
        except Exception:
            print("[Chipnwin] Unable to click start button.")

    # 2c) Claim daily bonus
    print("[Chipnwin] Attempting to click Claim button...")
    for cb in CLAIM_BUTTON_XPATHS:
        try:    
            claim_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, cb)))
            claim_btn.click()
            await channel.send("Chipnwin Daily Bonus Claimed!")
        except TimeoutException:
            pass

    # 2d) If no claim, try to read the countdown
    try:
        countdown_btn = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, COUNTDOWN_XPATH)))
        raw       = countdown_btn.text.strip()               # e.g. "22 : 27 : 06"
        countdown = re.sub(r"\s+", "", raw)           # => "22:27:06"
        await channel.send(f"Next Chipnwin bonus Available in: {countdown}")
        return
    except TimeoutException:
        pass

# ───────────────────────────────────────────────────────────
# 3) (Optional) standalone countdown reader
# ───────────────────────────────────────────────────────────
async def check_chipnwin_countdown(ctx, driver, channel):
    print("[Chipnwin] Navigating to site…")
    driver.get(STORE_URL)
    await asyncio.sleep(10)

    print("[Chipnwin] Checking for countdown timer…")
    countdown_btn = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, XPATH_COUNTDOWN)))
    raw       = countdown_btn.text.strip()
    countdown = re.sub(r"\s+", "", raw)
    await channel.send(f"Next Chipnwin Bonus Available in: {countdown}")

# ───────────────────────────────────────────────────────────
# 4) (Optional) Daily Spin Wheel
# ───────────────────────────────────────────────────────────
async def spin_chipnwin_wheel(ctx, driver, channel):
    # 4a) Navigate to store
    print ("[Chipnwin] Navigating to store…")
    driver.get(STORE_URL)
    await asyncio.sleep(10)

    # 4b) Click the "Spin & Win" Card
    print("[Chipnwin] Opening Spin & Win...")
    for sw in SPINWIN_BUTTON_XPATHS:
        try:
            spinwin_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, sw)))
            spinwin_btn.click()
            await asyncio.sleep(10)
        except TimeoutException:
            pass

    # 4c) Click the "Spin" button
    print("[Chipnwin] Attempting to spin the wheel...")
    for spb in SPIN_BUTTON_XPATHS:
        try:
            spin_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, spb)))
            spin_btn.click()
            await channel.send("Chipnwin Wheel Spun!")
        except TimeoutException:
            pass