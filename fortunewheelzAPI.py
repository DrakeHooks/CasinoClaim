# Drake Hooks + WaterTrooper
# Casino Claim 2
# Fortune Wheelz API

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
FORTUNEWHEELZ_CRED = os.getenv("FORTUNEWHEELZ")  # format "username:password"
SITE_URL = "https://fortunewheelz.com"
STORE_URL = "https://fortunewheelz.com/promotions"

# The login button XPATH
LOGIN_BUTTON = (
    "/html/body/div[1]/div/div/div[1]/header/div[2]/button[1]"
)

# The email input XPATH
EMAIL_INPUT = (
    "/html/body/div[1]/div/div/div[2]/form/label[1]/div[2]/div[2]/input"
)

# The password input XPATH
PASSWORD_INPUT = (
    "/html/body/div[1]/div/div/div[2]/form/label[2]/div[2]/input"
)

# The submit login XPATH
LOGIN_INPUT = (
    "/html/body/div[1]/div/div/div[2]/form/div/button"
)

# The claim button XPATH
CLAIM_BUTTON = (
    "promo-daily-login-button"
)

# The collect button XPATH
COLLECT_BUTTON = [
    "/html/body/div[5]/div/div[2]/div[3]/button",
    "/html/body/div[8]/div/div[2]/div[3]/button",
    "/html/body/div[9]/div/div[2]/div[3]/button"
]

# Spin & Win XPATH
PROMOTIONS_SPIN = (
    "card-dailyWheel"
)

# Daily Wheel Spin XPATH
SPIN_BUTTON = (
    "wheel-button"
)

# XPath for the disabled countdown button
XPATH_COUNTDOWN = "//button[@disabled and contains(normalize-space(.), ':')]"

# ───────────────────────────────────────────────────────────
# 1) Unified flow: claim → countdown → login & claim
# ───────────────────────────────────────────────────────────
async def fortunewheelz_flow(ctx, driver, channel):
    # 1a) Navigate to site
    driver.get(STORE_URL)
    await asyncio.sleep(10)

    # 1b) Click the “Claim Now” Button
    try:
        claim = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, CLAIM_BUTTON))
        )
        claim.click()
        await asyncio.sleep(10)
    except TimeoutException:
        pass

    # 1c) Click the "Collect" Button
    for xp in COLLECT_BUTTON:
        try:
            collect = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, xp))
            )
            collect.click()
            await channel.send("Fortune Wheelz Daily Bonus Claimed!")
            return
        except TimeoutException:
        # might not be logged in yet
            continue

    # 1d) If no claim, try to read the countdown
    try:
        countdown_btn = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.XPATH, XPATH_COUNTDOWN))
        )
        raw       = countdown_btn.text.strip()               # e.g. "22 : 27 : 06"
        countdown = re.sub(r"\s+", "", raw)           # => "22:27:06"
        await channel.send(f"Next Fortune Wheelz bonus Available in: {countdown}")
        return
    except TimeoutException:
        pass

    # 1e) Fallback: not logged in (or weird page) → login + claim
    print("Logging into Fortune Wheelz and claiming…")
    await fortunewheelz_casino(ctx, driver, channel)

# ───────────────────────────────────────────────────────────
# 2) Login & then hand off to claim
# ───────────────────────────────────────────────────────────
async def fortunewheelz_casino(ctx, driver, channel):
    if not FORTUNEWHEELZ_CRED:
        await channel.send("Fortune Wheelz credentials not found in environment variables.")
        return

    username, password = FORTUNEWHEELZ_CRED.split(":")

    driver.get(SITE_URL)
    await asyncio.sleep(10)

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
        pw = driver.find_element(By.XPATH, PASSWORD_INPUT)
        await asyncio.sleep(10)
        pw.send_keys(password)
        await asyncio.sleep(10)
        empw_ln_btn = driver.find_element(By.XPATH, LOGIN_INPUT)
        empw_ln_btn.click()
        await asyncio.sleep(10)

        # Now that we're logged in, try claiming
        await claim_fortunewheelz_bonus(ctx, driver, channel)

    except TimeoutException as e:
        screenshot = "fortunewheelz_login_error.png"
        driver.save_screenshot(screenshot)
        await channel.send(
            "Fortune Wheelz login timed out, will retry later.",
            file=discord.File(screenshot)
        )
        os.remove(screenshot)
        print("Login timeout:", e)

# ───────────────────────────────────────────────────────────
# 3) After login: click the daily card + claim buttons
# ───────────────────────────────────────────────────────────
async def claim_fortunewheelz_bonus(ctx, driver, channel):
    driver.get(STORE_URL)
    await asyncio.sleep(10)

    # Click the “Claim Now” Button
    try:
        claim = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, CLAIM_BUTTON))
        )
        claim.click()
        await asyncio.sleep(10)
    except TimeoutException:
        pass    

        # then reuse the same loop we had above
    for xp in COLLECT_BUTTON:
        try:    
            collect = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            collect.click()
            await channel.send("Fortune Wheelz Daily Bonus Claimed!")
            return
        except TimeoutException:
            pass

    # if still nothing, read countdown instead
    await fortunewheelz_flow(ctx, driver, channel)

# ───────────────────────────────────────────────────────────
# 4) (Optional) standalone countdown reader
# ───────────────────────────────────────────────────────────
async def check_fortunewheelz_countdown(ctx, driver, channel):
    # you can call this directly if you ever just want the timer
    driver.get(STORE_URL)
    await asyncio.sleep(10)

    countdown_btn = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, XPATH_COUNTDOWN))
    )
    raw       = countdown_btn.text.strip()
    countdown = re.sub(r"\s+", "", raw)
    await channel.send(f"Next Fortune Wheelz Bonus Available in: {countdown}")

# ───────────────────────────────────────────────────────────
# 5) (Optional) Daily Spin Wheel
# ───────────────────────────────────────────────────────────
async def claim_fortunewheelz_wheel(ctx, driver, channel):
    driver.get(STORE_URL)
    await asyncio.sleep(10)

    # Click the "Spin & Win" Card
    try:
        spinwin_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, PROMOTIONS_SPIN))
        )
        spinwin_btn.click()
        await asyncio.sleep(10)
    except TimeoutException:
        pass

    # Click the "Spin" button
    try:
        spin_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, SPIN_BUTTON))
        )
        spin_btn.click()
        await channel.send("Fortune Wheelz Daily Wheel Claimed!")
    except TimeoutException:
        pass