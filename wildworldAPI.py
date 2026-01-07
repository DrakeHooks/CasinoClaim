# Drake Hooks + WaterTrooper
# Casino Claim 2
# Wild World API
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
WILDWORLD_CRED = os.getenv("WILDWORLD")  # format "username:password"
SITE_URL = "https://wildworldcasino.com"
LOGIN_URL = "https://wildworldcasino.com/login"
PROMOTIONS_URL = "https://wildworldcasino.com/promotions"

EMAIL_INPUT_XPATH = ("/html/body/div[1]/div/main/div/div/div/div[2]/div/div/form/div[1]/input")
PASSWORD_INPUT_XPATH = ("/html/body/div[1]/div/main/div/div/div/div[2]/div/div/form/div[2]/input")
LOGIN_SUBMIT_XPATH = ("/html/body/div[1]/div/main/div/div/div/div[2]/div/div/form/div[3]/button")

CLAIM_BUTTON_XPATH = ("//button[@class='swal2-confirm swal2-styled']")

# ───────────────────────────────────────────────────────────
# 0) Wild World Casino Helpers
# ───────────────────────────────────────────────────────────
def _is_logged_in(driver) -> bool:
    """Detect if already logged in."""
    try:
        driver.find_element(By.XPATH, "//div[@class='currency-bar hud__primary-currency-bar currency-bar--goldBar']")
        return True
    except NoSuchElementException:
        pass
    try:
        driver.find_element(By.XPATH, "//a[@class='notification_btn notify-bell']")
        return True
    except NoSuchElementException:
        return False

# ───────────────────────────────────────────────────────────
# 1) Login & then hand off to claim
# ───────────────────────────────────────────────────────────
async def wildworld_casino(ctx, driver, channel):
    if not WILDWORLD_CRED:
        await channel.send("❌ Missing `WILDWORLD` as 'email:password' in your .env.")
        return

    username, password = WILDWORLD_CRED.split(":", 1)

    # 1a) Navigate to site
    print("[Wild World Casino] Navigating to site…")
    driver.get(SITE_URL)
    await asyncio.sleep(10)

    if _is_logged_in(driver):
        print("[Wild World Casino] Already logged in, skipping login.")
        await claim_wildworld_bonus(ctx, driver, channel)
        return       

    # 1b) Login to site
    print("[Wild World Casino] Attempting to login...")
    try:
        try:
            driver.get(LOGIN_URL)
            await asyncio.sleep(10)
        except Exception:
            print("[Wild World Casino] Unable to load login url.")

        try:
            email = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, EMAIL_INPUT_XPATH)))
            email.send_keys(username)
            await asyncio.sleep(10)
        except Exception:
            print("[Wild World Casino] Unable to enter email.")

        try:
            pw = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By. XPATH, PASSWORD_INPUT_XPATH)))
            pw.send_keys(password)
            await asyncio.sleep(10)
        except Exception:
            print("[Wild World Casino] Unable to enter password.")

        try:
            empw_ln_btn = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, LOGIN_SUBMIT_XPATH)))
            empw_ln_btn.click()
            print("[Wild World Casino] Submitted credentials.")
            await asyncio.sleep(10)
        except Exception:
            print("[Wild World Casino] Unable to click login submit button.")

        # Now that we're logged in, try claiming
        await claim_wildworld_bonus(ctx, driver, channel)

    except TimeoutException as e:
        screenshot = "wildworld_login_error.png"
        driver.save_screenshot(screenshot)
        await channel.send("Wild World Casino login timed out, will retry later.",file=discord.File(screenshot))
        os.remove(screenshot)
        print("Login timeout:", e)

# ───────────────────────────────────────────────────────────
# 2) Click Claim Bonus Button -> Click OK Button
# ───────────────────────────────────────────────────────────
async def claim_wildworld_bonus(ctx, driver, channel):
    # 2a) Click the “Claim Bonus” button
    print("[Wild World Casino] Attempting to click Claim Bonus button...")
    try:
        claim = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, CLAIM_BUTTON_XPATH)))
        claim.click()
        await channel.send("Wild World Casino Daily Bonus Claimed!")
    except TimeoutException:
        print("[Wild World Casino] Unable to click daily bonus button.")
        return