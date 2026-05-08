# Drake Hooks + WaterTrooper
# Casino Claim 3
# Scarlet Sands API
# Version 3.3
# Updated 2026.05.08

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
SCARLETSANDS_CRED = os.getenv("SCARLETSANDS")  # format "username:password"

SITE_URL = "https://scarletsands.com"
LOGIN_URL = "https://scarletsands.com/signin"
LOBBY_URL = "https://scarletsands.com/lobby"
PROMOTIONS_URL = "https://scarletsands.com/promotions"

LOGIN_BUTTON_XPATH = "//button[@data-tid='header-login-btn']"
EMAIL_INPUT_XPATH = "//input[@data-tid='login-email-input']"
PASSWORD_INPUT_XPATH = "//input[@data-tid='login-password-input']"
LOGIN_SUBMIT_XPATH = "//button[@data-tid='login-btn']"

REWARD_BUTTON_XPATH = "//button[@data-tid='promo-daily-login-button']"
CLAIM_BUTTON_XPATH = "//button[@class='a-button primary size-lg wide']"

# ───────────────────────────────────────────────────────────
# 0) Helpers
# ───────────────────────────────────────────────────────────

def _is_logged_in(driver) -> bool:
    """Detect if already logged in."""
    try:
        driver.find_element(By.XPATH, "//div[@class='balance-switcher']")
        return True
    except NoSuchElementException:
        pass
    try:
        driver.find_element(By.XPATH, "//button[@data-tid='header-buy-btn']")
        return True
    except NoSuchElementException:
        return False

# ───────────────────────────────────────────────────────────
# 1) Login Flow
# ───────────────────────────────────────────────────────────

async def scarletsands_casino(ctx, driver, channel):
    if not SCARLETSANDS_CRED:
        await channel.send("❌ Missing `SCARLETSANDS` as 'email:password' in your .env.")
        return

    username, password = SCARLETSANDS_CRED.split(":", 1)

    print("[Scarlet Sands] Navigating to lobby...")
    driver.get(LOBBY_URL)
    await asyncio.sleep(10)

    if _is_logged_in(driver):
        print("[Scarlet Sands] Already logged in.")
        await claim_scarletsands_bonus(ctx, driver, channel)
        return

    print("[Scarlet Sands] Attempting to login...")
    try:
        try:
            login = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, LOGIN_BUTTON_XPATH)))
            login.click()
            await asyncio.sleep(10)
        except Exception:
            print("[Scarlet Sands] Login button failed.")

        try:
            email = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, EMAIL_INPUT_XPATH)))
            email.send_keys(username)
            await asyncio.sleep(5)
        except Exception:
            print("[Scarlet Sands] Email input failed.")

        try:
            pw = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, PASSWORD_INPUT_XPATH)))
            pw.send_keys(password)
            await asyncio.sleep(5)
        except Exception:
            print("[Scarlet Sands] Password input failed.")

        try:
            submit = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, LOGIN_SUBMIT_XPATH)))
            submit.click()
            print("[Scarlet Sands] Submitted credentials.")
            await asyncio.sleep(10)
        except Exception:
            print("[Scarlet Sands] Submit failed.")

        await claim_scarletsands_bonus(ctx, driver, channel)

    except TimeoutException as e:
        screenshot = "scarletsands_login_error.png"
        driver.save_screenshot(screenshot)
        await channel.send("Scarlet Sands login timed out.",file=discord.File(screenshot))
        os.remove(screenshot)
        print("Login timeout:", e)

# ───────────────────────────────────────────────────────────
# 2) Claim Bonus
# ───────────────────────────────────────────────────────────

async def claim_scarletsands_bonus(ctx, driver, channel):
    print("[Scarlet Sands] Navigating to promotions...")
    try:
        driver.get(PROMOTIONS_URL)
        await asyncio.sleep(10)
    except Exception as e:
        print(f"Error: {e}")

    print("[Scarlet Sands] Refreashing promotions once...")
    driver.refresh()
    await asyncio.sleep(10)

    print("[Scarlet Sands] Refreashing promotions twice...")
    driver.refresh()
    await asyncio.sleep(10)

    print("[Scarlet Sands] Refreashing promotions thrice...")
    driver.refresh()
    await asyncio.sleep(10)

    print("[Scarlet Sands] Refreashing promotions quarce...")
    driver.refresh()
    await asyncio.sleep(10)

    print("[Scarlet Sands] Attempting to click claim reward button...")
    try:
        reward = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, REWARD_BUTTON_XPATH)))
        reward.click()
        await asyncio.sleep(10)
    except Exception:
        print("[Scarlet Sands] Reward failed.")

    print("[Scarlet Sands] Attempting to claim bonus...")
    try:
        claim = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, CLAIM_BUTTON_XPATH)))
        # normal click
        try:
            claim.click()
        except Exception:
            # fallback JS click (very important for these sites)
            driver.execute_script("arguments[0].click();", claim)

        await asyncio.sleep(5)

        # 📸 success screenshot
        screenshot = "scarletsands_claim.png"
        driver.save_screenshot(screenshot)

        await channel.send("Scarlet Sands Daily Bonus Claimed!",file=discord.File(screenshot))

        os.remove(screenshot)

    except Exception as e:
        print("[Scarlet Sands] Claim failed:", e)

        # 📸 error screenshot
        screenshot = "scarletsands_claim_error.png"
        driver.save_screenshot(screenshot)

        await channel.send("Scarlet Sands Daily Bonus Unavailable.",file=discord.File(screenshot))

        os.remove(screenshot)           