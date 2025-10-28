# Drake Hooks + WaterTrooper
# Casino Claim 2
# Smiles Casino API
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
SMILESCASINO_CRED = os.getenv("SMILESCASINO")  # format "username:password"
SITE_URL = "https://smilescasino.com"
LOBBY_URL = "https://smilescasino.com/lobby"

LOGIN_BUTTON_XPATH = ("/html/body/div[2]/div[2]/div/div/header/div/div[3]/div[1]/div/button[1]")
EMAIL_INPUT_XPATH = ("/html/body/div[2]/div[2]/div/div/div/div[2]/div/div[2]/form/div[3]/input")
PASSWORD_INPUT_XPATH = ("/html/body/div[2]/div[2]/div/div/div/div[2]/div/div[2]/form/div[4]/input")
LOGIN_SUBMIT_XPATH = ("/html/body/div[2]/div[2]/div/div/div/div[2]/div/div[2]/form/div[6]/button")

GET_COINS_BUTTON_XPATH = ("/html/body/div[2]/div[2]/div/div/header/div/div[3]/div[1]/div[2]/div[1]/button")
DAILY_BONUS_BUTTON_XPATH = ("/html/body/div[2]/div[2]/div/div/div/div[2]/div/div[2]/div/div[1]/div[2]/button")

# The Claim button(s) XPATH
CLAIM_BUTTON_XPATHS = [
    "/html/body/div[2]/div[2]/div/div/div/div[2]/div/div[2]/div/div[2]/div/div/div/div[3]/div[2]/div[1]/div[2]/div[2]/button",
    "/html/body/div[2]/div[2]/div/div/div/div[2]/div/div[2]/div/div[2]/div/div/div/div[3]/div[2]/div[2]/div[2]/div[2]/button",
    "/html/body/div[2]/div[2]/div/div/div/div[2]/div/div[2]/div/div[2]/div/div/div/div[3]/div[2]/div[3]/div[2]/div[2]/button",
    "/html/body/div[2]/div[2]/div/div/div/div[2]/div/div[2]/div/div[2]/div/div/div/div[3]/div[2]/div[4]/div[2]/div[2]/button",
    "/html/body/div[2]/div[2]/div/div/div/div[2]/div/div[2]/div/div[2]/div/div/div/div[3]/div[2]/div[5]/div[2]/div[2]/button",
    "/html/body/div[2]/div[2]/div/div/div/div[2]/div/div[2]/div/div[2]/div/div/div/div[3]/div[2]/div[6]/div[2]/div[2]/button",
    "/html/body/div[2]/div[2]/div/div/div/div[2]/div/div[2]/div/div[2]/div/div/div/div[3]/div[2]/div[7]/div[3]/button"
]

# ───────────────────────────────────────────────────────────
# 1) Smiles Casino Helpers
# ───────────────────────────────────────────────────────────
def _is_logged_in(driver) -> bool:
    """Detect if already logged in."""
    try:
        driver.find_element(By.CLASS_NAME, "toggle-coin")
        return True
    except NoSuchElementException:
        pass
    try:
        driver.find_element(By.CLASS_NAME, "header-top__balance")
        return True
    except NoSuchElementException:
        return False

# ───────────────────────────────────────────────────────────
# 2) Login & then hand off to claim
# ───────────────────────────────────────────────────────────
async def smilescasino_casino(ctx, driver, channel):
    if not SMILESCASINO_CRED:
        await channel.send("Smiles Casino credentials not found in environment variables.")
        return

    username, password = SMILESCASINO_CRED.split(":")

    # 2a) Navigate to site
    print("[Smiles Casino] Navigating to site…")
    driver.get(SITE_URL)
    await asyncio.sleep(10)

    if _is_logged_in(driver):
        print("[Smiles Casino] Already logged in, skipping login.")
        await claim_smilescasino_bonus(ctx, driver, channel)
        return

    # 2b) Login to site
    print("[Smiles Casino] Attempting to log in...")
    try:
        login_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, LOGIN_BUTTON_XPATH)))
        login_btn.click()
        await asyncio.sleep(10)

        email = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, EMAIL_INPUT_XPATH)))
        email.send_keys(username)
        await asyncio.sleep(10)

        pw = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By. XPATH, PASSWORD_INPUT_XPATH)))
        pw.send_keys(password)
        await asyncio.sleep(10)

        empw_ln_btn = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, LOGIN_SUBMIT_XPATH)))
        empw_ln_btn.click()
        print("[Smiles Casino] Submitted credentials.")
        await asyncio.sleep(10)

        # Now that we're logged in, try claiming
        await claim_smilescasino_bonus(ctx, driver, channel)

    except TimeoutException as e:
        screenshot = "smilescasino_login_error.png"
        driver.save_screenshot(screenshot)
        await channel.send("Smiles Casino login timed out, will retry later.",file=discord.File(screenshot))
        os.remove(screenshot)
        print("Login timeout:", e)

# ───────────────────────────────────────────────────────────
# 3) Click Get Coins -> Click Daily Bonus -> Claim
# ───────────────────────────────────────────────────────────
async def claim_smilescasino_bonus(ctx, driver, channel):
    try:
        # 3a) Navigate to store
        print("[Smiles Casino] Reloading lobby.")
        driver.get(LOBBY_URL)
        await asyncio.sleep(10)
    except Exception as e:
        print(f"Error: {e}")
        pass

    # 3b) Click the “Get Coins” button
    print("[Smiles Casino] Opening Get Coins menu...")
    try:
        get_coins_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, GET_COINS_BUTTON_XPATH)))
        get_coins_btn.click()
        await asyncio.sleep(10)
    except TimeoutException:
        pass

    # 3c) Click the "Daily Bonus" button
    print("[Smiles Casino] Opening Daily Bonus tab...")
    try:
        daily_bonus_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, DAILY_BONUS_BUTTON_XPATH)))
        daily_bonus_btn.click()
        await asyncio.sleep(10)
    except TimeoutException:
        pass

    # 3d) Click the "Claim" button(s)
    print("[Smiles Casino] Attempting to click Claim button(s)...")
    for xp in CLAIM_BUTTON_XPATHS:
        try:
            claim = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, xp)))
            claim.click()
            await channel.send("Smiles Casino Daily Bonus Claimed!")
        except TimeoutException:
        # might not be logged in yet
            continue