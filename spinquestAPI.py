# Drake Hooks + WaterTrooper
# Casino Claim 2
# SpinQuest API
# Version 2
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
SPINQUEST_CRED = os.getenv("SPINQUEST")  # format "username:password"
SITE_URL = "https://spinquest.com"
LOBBY_URL = "https://spinquest.com/casino/lobby"

LOGIN_BUTTON_XPATH = ("/html/body/div[1]/div[1]/div[2]/div/nav/div[2]/div/button[1]")
EMAIL_INPUT_ID = (":r6:-form-item")
PASSWORD_INPUT_ID = (":r7:-form-item")
LOGIN_SUBMIT_ID = (":r8:")

CLAIM_BUTTON_XPATHS = [
    "/html/body/div[1]/div[1]/div[2]/div/main/div/div[1]/div/div/div[1]/div[2]/div[3]/button",
    "/html/body/div[1]/div[1]/div[2]/div/main/div/div[1]/div/div/div[1]/div[2]/div[4]/button"
]

# XPath for the disabled countdown button
XPATH_COUNTDOWN = "//button[@disabled and contains(normalize-space(.), ':')]"

# ───────────────────────────────────────────────────────────
# 1) Unified flow: claim → countdown → login & claim
# ───────────────────────────────────────────────────────────
async def spinquest_flow(ctx, driver, channel):
    # 1a) Navigate to lobby
    print("[SpinQuest] Navigating to lobby...")
    driver.get(LOBBY_URL)
    await asyncio.sleep(10)

    # 1b) Click the “Daily Bonus” card
    print("[SpinQuest] Attempting to click Claim Now button...")
    for xp in CLAIM_BUTTON_XPATHS:
        try:
            claim = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, xp)))
            claim.click()
            await channel.send("SpinQuest Daily Bonus Claimed!")
            await asyncio.sleep(10)
        except TimeoutException:
            # might not be logged in yet
            pass

    # 1c) If no claim, try to read the countdown
    print("[SpinQuest] Checking for countdown...")
    try:
        countdown_btn = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, XPATH_COUNTDOWN)))
        raw       = countdown_btn.text.strip()               # e.g. "22 : 27 : 06"
        countdown = re.sub(r"\s+", "", raw)           # => "22:27:06"
        await channel.send(f"Next SpinQuest bonus Available in: {countdown}")
        return
    except TimeoutException:
        pass

    # 1d) Fallback: not logged in (or weird page) → login + claim
    print("Logging into SpinQuest and claiming…")
    await spinquest_casino(ctx, driver, channel)

# ───────────────────────────────────────────────────────────
# 2) Login & then hand off to claim
# ───────────────────────────────────────────────────────────
async def spinquest_casino(ctx, driver, channel):
    if not SPINQUEST_CRED:
        await channel.send("SpinQuest credentials not found in environment variables.")
        return

    username, password = SPINQUEST_CRED.split(":")

    # 2a) Navigate to site
    print("[SpinQuest] Navigating to site...")
    driver.get("https://spinquest.com")
    await asyncio.sleep(10)

    # 2b) Login to site
    print("[SpinQuest] Attempting to login...")
    try:
        login_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, LOGIN_BUTTON_XPATH)))
        login_btn.click()
        email = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, EMAIL_INPUT_ID)))
        email.send_keys(username)
        await asyncio.sleep(5)
        pw = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, PASSWORD_INPUT_ID)))
        pw.send_keys(password)
        await asyncio.sleep(5)
        empw_ln_btn = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, LOGIN_SUBMIT_ID)))
        empw_ln_btn.click()
        print("[SpinQuest] Submitted credentials.")
        await asyncio.sleep(10)

        # Now that we're logged in, try claiming
        await claim_spinquest_bonus(ctx, driver, channel)

    except TimeoutException as e:
        screenshot = "spinquest_login_error.png"
        driver.save_screenshot(screenshot)
        await channel.send(
            "SpinQuest login timed out, will retry later.",
            file=discord.File(screenshot)
        )
        os.remove(screenshot)
        print("Login timeout:", e)

# ───────────────────────────────────────────────────────────
# 3) After login: click the daily card + claim buttons
# ───────────────────────────────────────────────────────────
async def claim_spinquest_bonus(ctx, driver, channel):
    # 3a) Navigate to lobby
    print("[SpinQuest] Navigating to lobby...")
    driver.get(LOBBY_URL)
    await asyncio.sleep(10)

    # 3b) Click the "Claim Now" button
    print("[SpinQuest] Attempting to click Claim Now button...")
    for xp in CLAIM_BUTTON_XPATHS:
        try:
            claim = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, xp)))
            claim.click()
            await channel.send("SpinQuest Daily Bonus Claimed!")
            await asyncio.sleep(10)
        except TimeoutException:
            pass

    # 3b) If no claim, read the countdown
    await spinquest_flow(ctx, driver, channel)

# ───────────────────────────────────────────────────────────
# 4) (Optional) standalone countdown reader
# ───────────────────────────────────────────────────────────
async def check_spinquest_countdown(ctx, driver, channel):
    # you can call this directly if you ever just want the timer
    print("[SpinQuest] Checking for countdown...")
    driver.get(LOBBY_URL)
    await asyncio.sleep(10)

    countdown_btn = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, XPATH_COUNTDOWN)))
    raw       = countdown_btn.text.strip()
    countdown = re.sub(r"\s+", "", raw)
    await channel.send(f"Next SpinQuest Bonus Available in: {countdown}")