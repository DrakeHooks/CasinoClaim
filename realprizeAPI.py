# Drake Hooks + WaterTrooper
# Casino Claim 2
# Real Prize API
# Version 3.2
# Updated 2026.04.19

import re
import os
import asyncio
import discord
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# ───────────────────────────────────────────────────────────
# Config & Constants
# ───────────────────────────────────────────────────────────
load_dotenv()
REALPRIZE_CRED = os.getenv("REALPRIZE")  # format "username:password"

SITE_URL = "https://realprize.com"

LOGIN_BUTTON_XPATH = "//a[@class='site-header__login-btn btn-login']"
LOGIN_EMAIL_ID = "logemailnbtn"
EMAIL_INPUT_XPATH = "//input[@id='poplogin_email']"
PASSWORD_INPUT_XPATH = "//input[@id='poplogin_password']"
LOGIN_SUBMIT_XPATH = "//button[@id='poploginbtn']"

DAILYBONUS_BUTTON_XPATH = "//div[@class='daily_button']"

# ───────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────
def _is_logged_in(driver) -> bool:
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
# Login Flow
# ───────────────────────────────────────────────────────────
async def realprize_casino(ctx, driver, channel):
    if not REALPRIZE_CRED:
        await channel.send("❌ Missing `REALPRIZE` as 'email:password' in your .env.")
        return

    username, password = REALPRIZE_CRED.split(":", 1)

    print("[Real Prize] Navigating to site...")
    driver.get(SITE_URL)
    await asyncio.sleep(10)

    if _is_logged_in(driver):
        print("[Real Prize] Already logged in.")
        await claim_realprize_bonus(ctx, driver, channel)
        return

    print("[Real Prize] Attempting login...")

    try:
        try:
            login = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, LOGIN_BUTTON_XPATH))
            )
            login.click()
            await asyncio.sleep(5)
        except Exception:
            print("[Real Prize] Login button failed")

        try:
            login_email = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, LOGIN_EMAIL_ID))
            )
            login_email.click()
            await asyncio.sleep(3)
        except Exception:
            print("[Real Prize] Email login button failed")

        try:
            email = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, EMAIL_INPUT_XPATH))
            )
            email.send_keys(username)
        except Exception:
            print("[Real Prize] Email input failed")

        try:
            pw = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, PASSWORD_INPUT_XPATH))
            )
            pw.send_keys(password)
        except Exception:
            print("[Real Prize] Password input failed")

        try:
            submit = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, LOGIN_SUBMIT_XPATH))
            )
            submit.click()
            await asyncio.sleep(10)
        except Exception:
            print("[Real Prize] Submit failed")

        await claim_realprize_bonus(ctx, driver, channel)

    except TimeoutException as e:
        screenshot = "realprize_login_error.png"
        driver.save_screenshot(screenshot)

        await channel.send(
            "❌ Real Prize login timed out.",
            file=discord.File(screenshot)
        )

        os.remove(screenshot)
        print("Login timeout:", e)

# ───────────────────────────────────────────────────────────
# Claim Bonus
# ───────────────────────────────────────────────────────────
async def claim_realprize_bonus(ctx, driver, channel):
    print("[Real Prize] Attempting claim...")

    try:
        claim = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, DAILYBONUS_BUTTON_XPATH))
        )

        # normal click
        try:
            claim.click()
        except Exception:
            # fallback JS click (very important for these sites)
            driver.execute_script("arguments[0].click();", claim)

        await asyncio.sleep(5)

        # 📸 success screenshot
        screenshot = "realprize_claim.png"
        driver.save_screenshot(screenshot)

        await channel.send(
            "Real Prize Daily Bonus Claimed!",
            file=discord.File(screenshot)
        )

        os.remove(screenshot)

    except Exception as e:
        print("[Real Prize] Claim failed:", e)

        # 📸 error screenshot
        screenshot = "realprize_claim_error.png"
        driver.save_screenshot(screenshot)

        await channel.send(
            "[Real Prize] daily bonus unavailable.",
            file=discord.File(screenshot)
        )

        os.remove(screenshot)