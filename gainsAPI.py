# Drake Hooks + WaterTrooper
# Casino Claim 2
# Gains API
# Version 3.2
# Updated 2026.04.26

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
GAINS_CRED = os.getenv("GAINS")  # format "username:password"

SITE_URL = "https://gains.com"
PROMOTIONS_URL = "https://gains.com/promotions"

LOGIN_BUTTON_XPATH = ("//button[@class='mdc-button mat-mdc-button-base ac-neutral mdc-button--unelevated mat-mdc-unelevated-button mat-unthemed']")

EMAIL_INPUT_XPATH = ("//input[@formcontrolname='email']")
PASSWORD_INPUT_XPATH = ("//input[@formcontrolname='password']")

WALLET_BUTTON_XPATH = ("//button[@class='mdc-button mat-mdc-button-base wallet-btn mdc-button--unelevated mat-mdc-unelevated-button mat-unthemed']")
DAILYBONUS_BUTTON_XPATH = ("//mat-icon[@data-mat-icon-name='gift_circle']")
CLAIM_BUTTON_XPATH = ("//button[@class='mdc-button mat-mdc-button-base daily-claim ac-width-full ac-btn-lg mdc-button--unelevated mat-mdc-unelevated-button mat-unthemed']")

# ───────────────────────────────────────────────────────────
# 0) Helpers
# ───────────────────────────────────────────────────────────

def _is_logged_in(driver) -> bool:
    """Detect if already logged in."""
    try:
        driver.find_element(By.XPATH, "//button[@class='mdc-icon-button mat-mdc-icon-button mat-mdc-button-base search-btn mat-unthemed']")
        return True
    except NoSuchElementException:
        pass
    try:
        driver.find_element(By.XPATH, "//button[@class='mdc-icon-button mat-mdc-icon-button mat-mdc-button-base mat-mdc-menu-trigger menu-btn avatar-menu mat-unthemed']")
        return True
    except NoSuchElementException:
        return False

# ───────────────────────────────────────────────────────────
# 1) Login Flow
# ───────────────────────────────────────────────────────────

async def gains_casino(ctx, driver, channel):
    if not GAINS_CRED:
        await channel.send("❌ Missing `GAINS` as 'email:password' in your .env.")
        return

    username, password = GAINS_CRED.split(":", 1)

    print("[Gains] Navigating to site...")
    driver.get(SITE_URL)
    await asyncio.sleep(10)

    if _is_logged_in(driver):
        print("[Gains] Already logged in.")
        await claim_gains_bonus(ctx, driver, channel)
        return

    print("[Gains] Attempting to login...")
    try:
        try:
            login_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, LOGIN_BUTTON_XPATH)))
            login_button.click()
            await asyncio.sleep(10)
        except Exception:
            print("[Gains] Login button failed.")

        try:
            email_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, EMAIL_INPUT_XPATH)))
            email_input.send_keys(username)
            await asyncio.sleep(5)
        except Exception:
            print("[Gains] Email input failed.")

        try:
            password_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, PASSWORD_INPUT_XPATH)))
            password_input.send_keys(password, Keys.ENTER)
            print("[Gains] Submitted credentials.")
            await asyncio.sleep(10)
        except Exception:
            print("[Gains] Password input failed.")

        await claim_gains_bonus(ctx, driver, channel)

    except TimeoutException as e:
        screenshot = "gains_login_error.png"
        driver.save_screenshot(screenshot)
        await channel.send("Gains login timed out, will retry later.",file=discord.File(screenshot))
        os.remove(screenshot)
        print("Login timeout:", e)

# ───────────────────────────────────────────────────────────
# 2) Claim Bonus
# ───────────────────────────────────────────────────────────
async def claim_gains_bonus(ctx, driver, channel):
    # 2a) Navigate to promotions
    print("[Gains] Navigating to promotions...")
    try:
        driver.get(PROMOTIONS_URL)
        await asyncio.sleep(10)
    except Exception as e:
        print(f"Error: {e}")

    print("[Gains] Attempting to click wallet button...")
    try:
        wallet = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, WALLET_BUTTON_XPATH)))
        wallet.click()
        await asyncio.sleep(10)
    except Exception:
        print("[Gains] Wallet button failed.")

    print("[Gains] Attempting to click daily bonus button...")
    try:
        dailybonus = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, DAILYBONUS_BUTTON_XPATH)))
        dailybonus.click()
        await asyncio.sleep(10)
    except Exception:
        print("[Gains] Daily bonus button failed.")

    print("[Gains] Attempting to claim daily bonus...")
    try:
        claim = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, CLAIM_BUTTON_XPATH)))
        try:
            claim.click()
        except Exception:
            # fallback JS click (very important for these sites)
            driver.execute_script("arguments[0].click();", claim)

        await asyncio.sleep(5)

        # 📸 success screenshot
        screenshot = "gains_claim.png"
        driver.save_screenshot(screenshot)

        await channel.send("💰 Gains Daily Bonus Claimed!",file=discord.File(screenshot))

        os.remove(screenshot)

    except Exception as e:
        print("[Gains] Claim failed:", e)

        # 📸 error screenshot
        screenshot = "gains_claim_error.png"
        driver.save_screenshot(screenshot)

        await channel.send("⏳ Gains daily bonus unavailable.",file=discord.File(screenshot))

        os.remove(screenshot)        