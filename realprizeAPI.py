# Drake Hooks + WaterTrooper
# Casino Claim 2
# Real Prize API
# Version 3.1
# Updated 2026.04.18
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
REALPRIZE_CRED = os.getenv("REALPRIZE")  # format "username:password"

SITE_URL = "https://realprize.com"

LOGIN_BUTTON_XPATH = ("//a[@class='site-header__login-btn btn-login']")

LOGIN_EMAIL_ID = ("logemailnbtn")
EMAIL_INPUT_XPATH = ("//input[@id='poplogin_email']")
PASSWORD_INPUT_XPATH = ("//input[@id='poplogin_password']")
LOGIN_SUBMIT_XPATH = ("//button[@id='poploginbtn']")

DAILYBONUS_BUTTON_XPATH = ("//div[@class='daily_button']")

# ───────────────────────────────────────────────────────────
# 0) Real Prize Helpers
# ───────────────────────────────────────────────────────────
def _is_logged_in(driver) -> bool:
    """Detect if already logged in."""
    try:
        driver.find_element(By.XPATH, "//div[@class='gcnum']")
        return True
    except NoSuchElementException:
        pass
    try:
        driver.find_element(By.XPATH, "//div[@class='myviptitle']")
        return True
    except NoSuchElementException:
        return False

# ───────────────────────────────────────────────────────────
# 1) Login & then hand off to claim
# ───────────────────────────────────────────────────────────
async def realprize_casino(ctx, driver, channel):
    if not REALPRIZE_CRED:
        await channel.send("❌ Missing `REALPRIZE` as 'email:password' in your .env.")
        return

    username, password = REALPRIZE_CRED.split(":", 1)

    # 1a) Navigate to site
    print("[Real Prize] Navigating to site...")
    driver.get(SITE_URL)
    await asyncio.sleep(10)

    if _is_logged_in(driver):
        print("[Real Prize] Already logged in, skipping login.")
        await claim_realprize_bonus(ctx, driver, channel)
        return

    # 1b) Login to site
    print("[Real Prize] Attempting to login...")
    try:
        try:
            login = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, LOGIN_BUTTON_XPATH)))
            login.click()
            await asyncio.sleep(10)
        except Exception:
            print("[Real Prize] Unable to click login button.")

        try:
            login_email = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, LOGIN_EMAIL_ID)))
            login_email.click()
            await asyncio.sleep(5)
        except Exception:
            print("[Real Prize] Unable to click login with email button.")

        try:
            email = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, EMAIL_INPUT_XPATH)))
            email.send_keys(username)
            await asyncio.sleep(5)
        except Exception:
            print("[Real Prize] Unable to enter email.")

        try:
            pw = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, PASSWORD_INPUT_XPATH)))
            pw.send_keys(password)
            await asyncio.sleep(5)
        except Exception:
            print("[Real Prize] Unable to enter password.")

        try:
            empw_ln_btn = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, LOGIN_SUBMIT_XPATH)))
            empw_ln_btn.click()
            print("[Real Prize] Submitted credentials.")
            await asyncio.sleep(10)
        except Exception:
            print("[Real Prize] Unable to click login submit button.")

        # Now that we're logged in, try claiming
        await claim_realprize_bonus(ctx, driver, channel)

    except TimeoutException as e:
        screenshot = "realprize_login_error.png"
        driver.save_screenshot(screenshot)
        await channel.send("Real Prize login timed out, will retry later.",file=discord.File(screenshot))
        os.remove(screenshot)
        print("Login timeout:", e)

# ───────────────────────────────────────────────────────────
# 2) Click Claim Button
# ───────────────────────────────────────────────────────────
async def claim_realprize_bonus(ctx, driver, channel):
        # 2a) Click the “Collect” button
        print("[Real Prize] Attempting to claim daily bonus...")
        try:
            claim = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, DAILYBONUS_BUTTON_XPATH)))
            claim.click()
            await asyncio.sleep(5)
            await channel.send("Real Prize Daily Bonus Claimed!")
        except Exception:
            print("[Real Prize] Unable to claim daily bonus.")