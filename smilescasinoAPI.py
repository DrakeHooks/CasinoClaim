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
from selenium.common.exceptions import TimeoutException

# ───────────────────────────────────────────────────────────
# Config & Constants
# ───────────────────────────────────────────────────────────
load_dotenv()
SMILESCASINO_CRED = os.getenv("SMILESCASINO")  # format "username:password"
SITE_URL = "https://smilescasino.com"
STORE_URL = "https://smilescasino.com/lobby"

# The login button XPATH
LOGIN_BUTTON = (
    "/html/body/div[2]/div[2]/div/div/header/div/div[3]/div[1]/div/button[1]"
)

# The email input XPATH
EMAIL_INPUT = (
    "/html/body/div[2]/div[2]/div/div/div/div[2]/div/div[2]/form/div[3]/input"
)

# The password input XPATH
PASSWORD_INPUT = (
    "/html/body/div[2]/div[2]/div/div/div/div[2]/div/div[2]/form/div[4]/input"
)

# The login input XPATH
LOGIN_INPUT = (
    "/html/body/div[2]/div[2]/div/div/div/div[2]/div/div[2]/form/div[6]/button"
)

# The claim button XPATH
GET_COINS_BUTTON = (
    "/html/body/div[2]/div[2]/div/div/header/div/div[3]/div[1]/div[2]/div[1]/button"
)

# The Daily Bonus button XPATH
DAILY_BONUS_BUTTON = (
    "/html/body/div[2]/div[2]/div/div/div/div[2]/div/div[2]/div/div[1]/div[2]/button"
)

# The Claim button(s) XPATH
CLAIM_BUTTON = [
    "/html/body/div[2]/div[2]/div/div/div/div[2]/div/div[2]/div/div[2]/div/div/div/div[3]/div[2]/div[1]/div[2]/div[2]/button",
    "/html/body/div[2]/div[2]/div/div/div/div[2]/div/div[2]/div/div[2]/div/div/div/div[3]/div[2]/div[2]/div[2]/div[2]/button",
    "/html/body/div[2]/div[2]/div/div/div/div[2]/div/div[2]/div/div[2]/div/div/div/div[3]/div[2]/div[3]/div[2]/div[2]/button",
    "/html/body/div[2]/div[2]/div/div/div/div[2]/div/div[2]/div/div[2]/div/div/div/div[3]/div[2]/div[4]/div[2]/div[2]/button",
    "/html/body/div[2]/div[2]/div/div/div/div[2]/div/div[2]/div/div[2]/div/div/div/div[3]/div[2]/div[5]/div[2]/div[2]/button",
    "/html/body/div[2]/div[2]/div/div/div/div[2]/div/div[2]/div/div[2]/div/div/div/div[3]/div[2]/div[6]/div[2]/div[2]/button",
    "/html/body/div[2]/div[2]/div/div/div/div[2]/div/div[2]/div/div[2]/div/div/div/div[3]/div[2]/div[7]/div[2]/div[2]/button"
]

# XPath for the disabled countdown button
XPATH_COUNTDOWN = "//button[@disabled and contains(normalize-space(.), ':')]"

# ───────────────────────────────────────────────────────────
# 1) Unified flow: claim → countdown → login & claim
# ───────────────────────────────────────────────────────────
async def smilescasino_flow(ctx, driver, channel):
    # 1a) Navigate to site
    driver.get(STORE_URL)
    await asyncio.sleep(10)

    # 1b) Click the “Get Coins” button
    try:
        get_coins_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, GET_COINS_BUTTON))
        )
        get_coins_btn.click()
        await asyncio.sleep(10)
    except TimeoutException:
        pass

    # 1c) Click the "Daily Bonus" button
    try:
        daily_bonus_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, DAILY_BONUS_BUTTON))
        )
        daily_bonus_btn.click()
        await asyncio.sleep(10)
    except TimeoutException:
        pass

    # 1d) Click the "Claim" button(s)
    for xp in CLAIM_BUTTON:
        try:
            claim = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            claim.click()
            await channel.send("Smiles Casino Daily Bonus Claimed!")
            return
        except TimeoutException:
        # might not be logged in yet
            continue

    # 1e) If no claim, try to read the countdown
    try:
        countdown_btn = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, XPATH_COUNTDOWN))
        )
        raw       = countdown_btn.text.strip()               # e.g. "22 : 27 : 06"
        countdown = re.sub(r"\s+", "", raw)           # => "22:27:06"
        await channel.send(f"Next Smiles Casino bonus Available in: {countdown}")
        return
    except TimeoutException:
        pass

    # 1f) Fallback: not logged in (or weird page) → login + claim
    print("logging into Smiles Casino and claiming…")
    await smilescasino_casino(ctx, driver, channel)

# ───────────────────────────────────────────────────────────
# 2) Login & then hand off to claim
# ───────────────────────────────────────────────────────────
async def smilescasino_casino(ctx, driver, channel):
    if not SMILESCASINO_CRED:
        await channel.send("Smiles Casino credentials not found in environment variables.")
        return

    username, password = SMILESCASINO_CRED.split(":")

    # 2a) Navigate to site
    driver.get(SITE_URL)
    await asyncio.sleep(10)

    # 2b) Login to site
    try:
        login_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, LOGIN_BUTTON))
        )
        login_btn.click()
        await asyncio.sleep(10)

        email = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, EMAIL_INPUT))
        )
        email.send_keys(username)
        await asyncio.sleep(10)

        pw = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By. XPATH, PASSWORD_INPUT))
        )
        pw.send_keys(password)
        await asyncio.sleep(10)

        empw_ln_btn = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, LOGIN_INPUT))
        )
        empw_ln_btn.click()
        await asyncio.sleep(10)

        # Now that we're logged in, try claiming
        await claim_smilescasino_bonus(ctx, driver, channel)

    except TimeoutException as e:
        screenshot = "smilescasino_login_error.png"
        driver.save_screenshot(screenshot)
        await channel.send(
            "Smiles Casino login timed out, will retry later.",
            file=discord.File(screenshot)
        )
        os.remove(screenshot)
        print("Login timeout:", e)

# ───────────────────────────────────────────────────────────
# 3) After login: click the daily card + claim buttons
# ───────────────────────────────────────────────────────────
async def claim_smilescasino_bonus(ctx, driver, channel):
    # 3a) Navigate to store
    driver.get(STORE_URL)
    await asyncio.sleep(10)

    # 3b) Click the “Get Coins” button
    try:
        get_coins_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, GET_COINS_BUTTON))
        )
        get_coins_btn.click()
        await asyncio.sleep(10)
    except TimeoutException:
        pass

    # 3c) Click the "Daily Bonus" button
    try:
        daily_bonus_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, DAILY_BONUS_BUTTON))
        )
        daily_bonus_btn.click()
        await asyncio.sleep(10)
    except TimeoutException:
        pass

    # 3d) Click the "Claim" button(s)
    for xp in CLAIM_BUTTON:
        try:
            claim = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            claim.click()
            await channel.send("Smiles Casino Daily Bonus Claimed!")
            return
        except TimeoutException:
        # might not be logged in yet
            continue

    # if still nothing, read countdown instead
    await smilescasino_flow(ctx, driver, channel)

# ───────────────────────────────────────────────────────────
# 4) (Optional) standalone countdown reader
# ───────────────────────────────────────────────────────────
async def check_smilescasino_countdown(ctx, driver, channel):
    # you can call this directly if you ever just want the timer
    driver.get(STORE_URL)
    await asyncio.sleep(10)

    countdown_btn = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, XPATH_COUNTDOWN))
    )
    raw       = countdown_btn.text.strip()
    countdown = re.sub(r"\s+", "", raw)
    await channel.send(f"Next Smiles Casino Bonus Available in: {countdown}")