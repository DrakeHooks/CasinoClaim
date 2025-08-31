# Drake Hooks + WaterTrooper
# Casino Claim 2
# SpinQuest API

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
SITE_URL = "https://spinquest.com/"
STORE_URL = "https://spinquest.com/casino/lobby"

# The “Daily Bonus” card you click first
CLAIM_BUTTON = (
    "/html/body/div[1]/div[1]/div[2]/div/main/div/div[1]/div/div/div[1]/div[2]/div[4]/button"
)

# The login button XPATH
LOGIN_BUTTON = (
    "/html/body/div[1]/div[1]/div[2]/div/nav/div[2]/div/button[1]"
)

# XPath for the disabled countdown button
XPATH_COUNTDOWN = "//button[@disabled and contains(normalize-space(.), ':')]"

# ───────────────────────────────────────────────────────────
# 1) Unified flow: claim → countdown → login & claim
# ───────────────────────────────────────────────────────────
async def spinquest_flow(ctx, driver, channel):
    # 1a) Navigate to site
    driver.get(STORE_URL)
    await asyncio.sleep(5)

    # 1a) Click the “Daily Bonus” card
    try:
        if driver.current_url == SITE_URL:
            await spinquest_casino(ctx, driver, channel)
        else:

            print("SpinQuest 1a")
            claim = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, CLAIM_BUTTON))
            )
            claim.click()
            await channel.send("SpinQuest Daily Bonus Claimed!")
            await asyncio.sleep(5)
    except TimeoutException:
        # might not be logged in yet
        pass

    # 1b) If no claim, try to read the countdown
    try:
        print("SpinQuest 1b")
        countdown_btn = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.XPATH, XPATH_COUNTDOWN))
        )
        raw       = countdown_btn.text.strip()               # e.g. "22 : 27 : 06"
        countdown = re.sub(r"\s+", "", raw)           # => "22:27:06"
        await channel.send(f"Next SpinQuest bonus Available in: {countdown}")
        return
    except TimeoutException:
        pass

    # 1c) Fallback: not logged in (or weird page) → login + claim
    print("logging into SpinQuest and claiming…")
    await spinquest_casino(ctx, driver, channel)

# ───────────────────────────────────────────────────────────
# 2) Login & then hand off to claim
# ───────────────────────────────────────────────────────────
async def spinquest_casino(ctx, driver, channel):
    if not SPINQUEST_CRED:
        await channel.send("SpinQuest credentials not found in environment variables.")
        return

    username, password = SPINQUEST_CRED.split(":")

    driver.get("https://spinquest.com")
    await asyncio.sleep(5)

    try:
        print("SpinQuest Login Button")
        login_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, LOGIN_BUTTON))
        )
        login_btn.click()

        await asyncio.sleep(5)
        print("SpinQuest Email Input")
        email = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, ":r6:-form-item"))
        )
        email.send_keys(username)
        print("SpinQuest Password Input")
        pw = driver.find_element(By.ID, ":r7:-form-item")
        await asyncio.sleep(5)
        pw.send_keys(password, Keys.ENTER)
        await asyncio.sleep(5)

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
    driver.get(STORE_URL)
    await asyncio.sleep(5)

    # click the “Daily Bonus” card again
    try:
        claim = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, CLAIM_BUTTON))
        )
        claim.click()
        await channel.send("SpinQuest Daily Bonus Claimed!")
        await asyncio.sleep(5)
    except TimeoutException:
        pass

    # if still nothing, read countdown instead
    await spinquest_flow(ctx, driver, channel)

# ───────────────────────────────────────────────────────────
# 4) (Optional) standalone countdown reader
# ───────────────────────────────────────────────────────────
async def check_spinquest_countdown(ctx, driver, channel):
    # you can call this directly if you ever just want the timer
    driver.get(STORE_URL)
    await asyncio.sleep(5)

    countdown_btn = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, XPATH_COUNTDOWN))
    )
    raw       = countdown_btn.text.strip()
    countdown = re.sub(r"\s+", "", raw)
    await channel.send(f"Next SpinQuest Bonus Available in: {countdown}")