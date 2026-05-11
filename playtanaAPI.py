# Drake Hooks + WaterTrooper
# Casino Claim 3
# Playtana API
# Version 3.3
# Updated 2026.05.11

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
PLAYTANA_CRED = os.getenv("PLAYTANA")  # format "username:password"

SITE_URL = "https://playtana.com"
LOGIN_URL = "https://playtana.com/signin"
LOBBY_URL = "https://playtana.com/lobby"
PROMOTIONS_URL = "https://playtana.com/promotions"

LOGIN_BUTTON_XPATH = "//a[@class='button sign-in']"
EMAIL_INPUT_XPATH = "//input[@data-tid='login-email-input']"
PASSWORD_INPUT_XPATH = "//input[@data-tid='login-password-input']"
LOGIN_SUBMIT_XPATH = "//button[@data-tid='login-btn']"

REWARD_BUTTON_XPATH = "//button[@data-tid='promotion-card-log-in-every-day-for-guaranteed-rewards-btn']"
CLAIM_BUTTON_XPATH = "//button[@data-tid='daily-login-action-button']"

# ───────────────────────────────────────────────────────────
# 0) Helpers
# ───────────────────────────────────────────────────────────

def _is_logged_in(driver) -> bool:
    """Detect if already logged in."""
    try:
        driver.find_element(By.XPATH, "//div[@class='prize coins']")
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

async def playtana_casino(ctx, driver, channel):
    if not PLAYTANA_CRED:
        await channel.send("❌ Missing `PLAYTANA` as 'email:password' in your .env.")
        return

    username, password = PLAYTANA_CRED.split(":", 1)

    print("[Playtana] Navigating to lobby...")
    driver.get(LOBBY_URL)
    await asyncio.sleep(10)

    if _is_logged_in(driver):
        print("[Playtana] Already logged in.")
        await claim_playtana_bonus(ctx, driver, channel)
        return

    print("[Playtana] Attempting to login...")
    try:
        try:
            login = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, LOGIN_BUTTON_XPATH)))
            login.click()
            await asyncio.sleep(10)
        except Exception:
            print("[Playtana] Login button failed.")

        try:
            email = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, EMAIL_INPUT_XPATH)))
            email.send_keys(username)
            await asyncio.sleep(5)
        except Exception:
            print("[Playtana] Email input failed.")

        try:
            pw = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, PASSWORD_INPUT_XPATH)))
            pw.send_keys(password)
            await asyncio.sleep(5)
        except Exception:
            print("[Playtana] Password input failed.")

        try:
            submit = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, LOGIN_SUBMIT_XPATH)))
            submit.click()
            print("[Playtana] Submitted credentials.")
            await asyncio.sleep(10)
        except Exception:
            print("[Playtana] Submit failed.")

        await claim_playtana_bonus(ctx, driver, channel)

    except TimeoutException as e:
        screenshot = "playtana_login_error.png"
        driver.save_screenshot(screenshot)
        await channel.send("Playtana login timed out.",file=discord.File(screenshot))
        os.remove(screenshot)
        print("Login timeout:", e)

# ───────────────────────────────────────────────────────────
# 2) Claim Bonus
# ───────────────────────────────────────────────────────────

async def claim_playtana_bonus(ctx, driver, channel):
    
    print("[Playtana] Navigating to promotions...")
    try:
        driver.get(PROMOTIONS_URL)
        await asyncio.sleep(10)
    except Exception as e:
        print(f"Error: {e}")

    print("[Playtana] Attempting to click claim reward button...")
    try:
        reward = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, REWARD_BUTTON_XPATH)))
        reward.click()
        await asyncio.sleep(10)
    except Exception:
        print("[Playtana] Reward failed.")

    print("[Playtant] Attempting to claim daily bonus...")
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
        screenshot = "playtana_claim.png"
        driver.save_screenshot(screenshot)

        await channel.send("Playtana Daily Bonus Claimed!",file=discord.File(screenshot))

        os.remove(screenshot)

    except Exception as e:
        print("[Playtana] Claim failed:", e)

        # 📸 error screenshot
        screenshot = "playtana_claim_error.png"
        driver.save_screenshot(screenshot)

        await channel.send("Playtana Daily Bonus Unavailable.",file=discord.File(screenshot))

        os.remove(screenshot)        