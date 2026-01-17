# Drake Hooks + WaterTrooper
# Casino Claim 2
# LoneStar Casino API
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
LONESTAR_CRED = os.getenv("LONESTAR")  # format "username:password"

SITE_URL = "https://lonestarcasino.com"
LOGIN_URL = "https://lonestarcasino.com/#!login"

LOGIN_EMAIL_ID = ("logemailnbtn")

EMAIL_INPUT_ID = ("poplogin_email")
PASSWORD_INPUT_ID = ("poplogin_password")
LOGIN_SUBMIT_ID = ("poploginbtn")

CLAIM_BUTTON_ID = ("daily_button")

# ───────────────────────────────────────────────────────────
# 0) LoneStar Casino Helpers
# ───────────────────────────────────────────────────────────
def _is_logged_in(driver) -> bool:
    """Detect if already logged in."""
    try:
        driver.find_element(By.XPATH, "//div[@class='gc coinswitcher']")
        return True
    except NoSuchElementException:
        pass
    try:
        driver.find_element(By.XPATH, "//div[@class='coinsloc gc']")
        return True
    except NoSuchElementException:
        return False

# ───────────────────────────────────────────────────────────
# 1) Login & then hand off to claim
# ───────────────────────────────────────────────────────────
async def lonestar_casino(ctx, driver, channel):
    if not LONESTAR_CRED:
        await channel.send("❌ Missing `LONESTAR` as 'email:password' in your .env.")
        return

    username, password = LONESTAR_CRED.split(":", 1)

    # 1a) Navigate to site
    print("[LoneStar Casino] Navigating to site…")
    driver.get(SITE_URL)
    await asyncio.sleep(10)

    if _is_logged_in(driver):
        print("[LoneStar Casino] Already logged in, skipping login.")
        await claim_lonestar_bonus(ctx, driver, channel)
        return

    # 1b) Navigate to login
    print("[LoneStar Casino] Navigating to login...")
    driver.get(LOGIN_URL)
    await asyncio.sleep(10)

    # 1c) Login to site
    print("[LoneStar Casino] Attempting to login...")
    try:
        try:
            login_email = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, LOGIN_EMAIL_ID)))
            login_email.click()
            await asyncio.sleep(10)
        except Exception:
            print("[LoneStar Casino] Unable to click login with email button.")

        try:
            email = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, EMAIL_INPUT_ID)))
            email.send_keys(username)
            await asyncio.sleep(5)
        except Exception:
            print("[LoneStar Casino] Unable to enter email.")

        try:
            pw = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By. ID, PASSWORD_INPUT_ID)))
            pw.send_keys(password)
            await asyncio.sleep(5)
        except Exception:
            print("[LoneStar Casino] Unable to enter password.")

        try:
            empw_ln_btn = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, LOGIN_SUBMIT_ID)))
            empw_ln_btn.click()
            print("[LoneStar Casino] Submitted credentials.")
            await asyncio.sleep(10)
        except Exception:
            print("[LoneStar Casino] Unable to click login submit button.")

        # Now that we're logged in, try claiming
        await claim_lonestar_bonus(ctx, driver, channel)

    except TimeoutException as e:
        screenshot = "lonestar_login_error.png"
        driver.save_screenshot(screenshot)
        await channel.send("LoneStar Casino login timed out, will retry later.",file=discord.File(screenshot))
        os.remove(screenshot)
        print("Login timeout:", e)

# ───────────────────────────────────────────────────────────
# 2) Claim Daily Bonus
# ───────────────────────────────────────────────────────────
async def claim_lonestar_bonus(ctx, driver, channel):
        # 2a) Click the “Collect” button
        print("[LoneStar Casino] Attempting to claim daily bonus...")
        try:
            claim = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, CLAIM_BUTTON_ID)))
            claim.click()
            await channel.send("LoneStar Casino Daily Bonus Claimed!")
        except Exception:
            print("[LoneStar Casino] Unable to claim daily bonus.")