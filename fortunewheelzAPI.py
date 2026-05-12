# Drake Hooks + WaterTrooper
# Casino Claim 3
# Fortune Wheelz API
# Version 3.3
# Updated 2026.05.12

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
FORTUNEWHEELZ_CRED = os.getenv("FORTUNEWHEELZ")  # format "username:password"

SITE_URL = "https://fortunewheelz.com"
LOGIN_URL = "https://fortunewheelz.com/signin"
LOBBY_URL = "https://fortunewheelz.com/lobby"
PROMOTIONS_URL = "https://fortunewheelz.com/promotions"

LOGIN_BUTTON_XPATH = "//button[@data-tid='header-login-btn']"
EMAIL_INPUT_XPATH = "//input[@data-tid='login-email-input']"
PASSWORD_INPUT_XPATH = "//input[@data-tid='login-password-input']"
LOGIN_SUBMIT_XPATH = "//button[@data-tid='login-btn']"

CLAIM_REWARD_XPATH = "//button[@data-tid='promo-daily-login-button']"
CLAIM_BUTTON_XPATH = "//button[@data-tid='daily-login-btn']"

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

async def fortunewheelz_casino(ctx, driver, channel):
    if not FORTUNEWHEELZ_CRED:
        await channel.send("❌ Missing `FORTUNEWHEELZ` as 'email:password' in your .env.")
        return

    username, password = FORTUNEWHEELZ_CRED.split(":", 1)

    print("[Fortune Wheelz] Navigating to site...")
    driver.get(SITE_URL)
    await asyncio.sleep(10)

    if _is_logged_in(driver):
        print("[Fortune Wheelz] Already logged in.")
        await claim_fortunewheelz_bonus(ctx, driver, channel)
        return

    print("[Fortune Wheelz] Attempting to login...")
    try:
        try:
            login = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, LOGIN_BUTTON_XPATH)))
            login.click()
            await asyncio.sleep(10)
        except Exception:
            print("[Fortune Wheelz] Login button failed.")

        try:
            email = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, EMAIL_INPUT_XPATH)))
            email.send_keys(username)
            await asyncio.sleep(5)
        except Exception:
            print("[Fortune Wheelz] Email input failed.")

        try:
            pw = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, PASSWORD_INPUT_XPATH)))
            pw.send_keys(password)
            await asyncio.sleep(5)
        except Exception:
            print("[Fortune Wheelz] Password input failed.")

        try:
            submit = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, LOGIN_SUBMIT_XPATH)))
            submit.click()
            print("[Fortune Wheelz] Submitted credentials.")
            await asyncio.sleep(10)
        except Exception:
            print("[Fortune Wheelz] Submit failed.")

        await claim_fortunewheelz_bonus(ctx, driver, channel)

    except TimeoutException as e:
        screenshot = "fortunewheelz_login_error.png"
        driver.save_screenshot(screenshot)
        await channel.send("Fortune Wheelz login timed out.",file=discord.File(screenshot))
        os.remove(screenshot)
        print("Login timeout:", e)

# ───────────────────────────────────────────────────────────
# 2) Claim Bonus
# ───────────────────────────────────────────────────────────

async def claim_fortunewheelz_bonus(ctx, driver, channel):

    print("[Fortune Wheelz] Navigating to promotions...")
    try:
        driver.get(PROMOTIONS_URL)
        await asyncio.sleep(10)
    except Exception as e:
        print(f"Error: {e}")

    print("[Fortune Wheelz] Refreashing promotions once...")
    driver.refresh()
    await asyncio.sleep(10)

    print("[Fortune Wheelz] Refreashing promotions twice...")
    driver.refresh()
    await asyncio.sleep(10)

    print("[Fortune Wheelz] Refreashing promotions thrice...")
    driver.refresh()
    await asyncio.sleep(10)

    print("[Fortune Wheelz] Attempting to click claim reward button...")
    try:
        reward = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, CLAIM_REWARD_XPATH)))
        reward.click()
        await asyncio.sleep(10)
    except Exception:
        print("[Fortune Wheelz] Reward failed.")

    print("[Fortune Wheelz] Attempting to claim daily bonus...")
    try:
        claim = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, CLAIM_BUTTON_XPATH)))
        try:
            claim.click()
        except Exception:
            # fallback JS click (very important for these sites)
            driver.execute_script("arguments[0].click();", claim)

        await asyncio.sleep(5)

        # 📸 success screenshot
        screenshot = "fortunewheelz_claim.png"
        driver.save_screenshot(screenshot)

        await channel.send("Fortune Wheelz Daily Bonus Claimed!",file=discord.File(screenshot))

        os.remove(screenshot)

    except Exception as e:
        print("[Fortune Wheelz] Claim failed:", e)

        # 📸 error screenshot
        screenshot = "fortunewheelz_claim_error.png"
        driver.save_screenshot(screenshot)

        await channel.send("Fortune Wheelz Daily Bonus Unavailable.",file=discord.File(screenshot))

        os.remove(screenshot)