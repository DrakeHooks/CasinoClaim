# Drake Hooks + WaterTrooper
# Casino Claim 2
# Jumbo API
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
JUMBO_CRED = os.getenv("JUMBO")  # format "username:password"

SITE_URL = "https://www.jumbo88.com"
LOGIN_URL = "https://www.jumbo88.com/login"
LOBBY_URL = "https://www.jumbo88.com/lobby"
REWARDS_URL = "https://www.jumbo88.com/daily-rewards"

EMAIL_INPUT_XPATH = ("/html/body/div[2]/div/main/form/div[1]/label/input")
PASSWORD_INPUT_XPATH = ("html/body/div[2]/div/main/form/div[2]/div/label/input")
LOGIN_SUBMIT_XPATH =("/html/body/div[2]/div/main/form/button")

CLAIM_BUTTON_XPATH = ("/html/body/div[2]/div[2]/main/div/div/div/div/div/div[1]/div[2]/button")
SPIN_BUTTON_XPATH = ("/html/body/div[2]/div[2]/main/div/div/div/div[2]/div/button[2]")
SPINWIN_BUTTON_XPATH = ("/html/body/div[3]/div/div/div[2]/div/button")
CLAIM_FREE_BUTTON_XPATH = ("/html/body/div[3]/div/div/div[2]/div/div/div/div[3]/div/div/div/div[10]/div/div[3]/form/div/button")

COUNTDOWN_XPATH = "//button[@disabled and contains(normalize-space(.), ':')]"

# ───────────────────────────────────────────────────────────
# 1) Jumbo Helpers
# ───────────────────────────────────────────────────────────
def _is_logged_in(driver) -> bool:
    """Detect if already logged in."""
    try:
        driver.find_element(By.XPATH, "//button[@data-test='currency-switcher']")
        return True
    except NoSuchElementException:
        pass
    try:
        driver.find_element(By.XPATH, "//span[@data-test='balance']")
        return True
    except NoSuchElementException:
        return False

# ───────────────────────────────────────────────────────────
# 2) Login & then hand off to claim
# ───────────────────────────────────────────────────────────
async def jumbo_casino(ctx, driver, channel):
    if not JUMBO_CRED:
        await channel.send("Jumbo credentials not found in environment variables.")
        return

    username, password = JUMBO_CRED.split(":", 1)

    # 2a) Navigate to site
    print("[Jumbo] Navigating to site…")
    driver.get(LOBBY_URL)
    await asyncio.sleep(10)

    if _is_logged_in(driver):
        print("[Jumbo] Already logged in, skipping login.")
        await claim_jumbo_bonus(ctx, driver, channel)
        return

    # 2b) Login to site
    print("[Jumbo] Attempting to login...")
    try:
        try:
            driver.get(LOGIN_URL)
            await asyncio.sleep(10)
        except Exception:
            print("[Jumbo] Unable to load login url.")    

        try:
            email_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, EMAIL_INPUT_XPATH)))
            email_input.send_keys(username)
            await asyncio.sleep(5)
        except Exception:
            print("[Jumbo] Unable to enter email.")

        try:
            password_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, PASSWORD_INPUT_XPATH)))
            password_input.send_keys(password)
            await asyncio.sleep(5)
        except Exception:
            print("[Jumbo] Unable to enter password.")    

        try:
            login_submit = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, LOGIN_SUBMIT_XPATH)))
            login_submit.click()
            print("[Jumbo] Submitted credentials.")
            await asyncio.sleep(10)
        except Exception:
            print("[Jumbo] Unable to click login button.")

        # Now that we're logged in, try claiming
        await claim_jumbo_bonus(ctx, driver, channel)    

    except TimeoutException as e:
        screenshot = "jumbo_login_error.png"
        driver.save_screenshot(screenshot)
        await channel.send("Jumbo login timed out, will retry later.",file=discord.File(screenshot))
        os.remove(screenshot)
        print("Login timeout:", e)

# ───────────────────────────────────────────────────────────
# 3) Click Daily Reward Button -> Click Claim Now Button(s)
# ───────────────────────────────────────────────────────────
async def claim_jumbo_bonus(ctx, driver, channel):
    # 3a) Navigate to daily rewards
    print("[Jumbo] Navigating to daily rewards...")   
    try:
        driver.get(REWARDS_URL)
        await asyncio.sleep(10)
    except Exception as e:
        print(f"Error: {e}")

    # 3b) Click the “Claim Day X Spin” button
    print("[Jumbo] Attempting to click daily spin button...")
    try:
        claim_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, CLAIM_BUTTON_XPATH)))
        claim_button.click()
        await asyncio.sleep(10)
    except Exception:
        print("[Jumbo] Unable to click daily spin button.") 

    # 3c) Click the "Spin" button
    print("[Jumbo] Attempting to click spin button...")
    try:
        spin_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, SPIN_BUTTON_XPATH)))
        spin_button.click()
        await asyncio.sleep(10)
    except Exception:
        print("[Jumbo] Unable to click spin button.")

    # 3d) Click the "Spin to Win" button
    print("[Jumbo] Attempting to click spin to win button...")
    try:
        spinwin_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, SPINWIN_BUTTON_XPATH)))
        spinwin_button.click()
        await asyncio.sleep(10)
    except Exception:
        print("[Jumbo] Unable to click spin to win button.")

    # 3e) Click the "Claim Free" button
    print("[Jumbo] Attempting to click claim free button...")
    try:
        claimfree_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, CLAIM_FREE_BUTTON_XPATH)))
        claimfree_button.click()
        await channel.send("Jumbo Daily Bonus Claimed!")
    except Exception:
        print("[Jumbo] Unable to claim daily bonus.")

    # 3f) If no claim, try to read the countdown
    print("[Jumbo] Checking for countdown...")
    try:
        countdown_btn = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, COUNTDOWN_XPATH)))
        raw       = countdown_btn.text.strip()               # e.g. "22 : 27 : 06"
        countdown = re.sub(r"Available\s+", "", raw)           # => "22:27:06"
        await channel.send(f"Next Jumbo Bonus Available in: {countdown}")
        return
    except:
        print("[Jumbo] Unable to read countdown.")
        screenshot = "jumbo_countdown_error.png"
        driver.save_screenshot(screenshot)
        await channel.send("Jumbo: unable to read countdown.",file=discord.File(screenshot))
        os.remove(screenshot)
# ───────────────────────────────────────────────────────────
# 4) (Optional) Standalone Countdown Reader
# ───────────────────────────────────────────────────────────
async def check_jumbo_countdown(ctx, driver, channel):
    # you can call this directly if you ever just want the timer
    print("[Jumbo] Checking for countdown...")
    driver.get(REWARDS_URL)
    await asyncio.sleep(10)

    countdown_btn = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, COUNTDOWN_XPATH)))
    raw       = countdown_btn.text.strip()
    countdown = re.sub(r"\s+", "", raw)
    await channel.send(f"Next Jumbo Bonus Available in: {countdown}")        