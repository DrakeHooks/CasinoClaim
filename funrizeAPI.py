# Drake Hooks + WaterTrooper
# Casino Claim 2
# Funrize API

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
FUNRIZE_CRED = os.getenv("FUNRIZE")  # format "username:password"
SITE_URL = "https://funrize.com"
STORE_URL = "https://funrize.com/promotions"

# The login button XPATH
LOGIN_BUTTON = (
    "login-btn"
)

# The claim button XPATH
CLAIM_BUTTON = (
    "daily-login-prize"
)

# The collect button XPATH
COLLECT_BUTTON = [
    "/html/body/div[3]/div/div/div[2]/div[2]/button",
    "/html/body/div[4]/div/div/div[2]/div[2]/button",
    "/html/body/div[6]/div/div/div[2]/div[2]/button"
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
async def funrize_flow(ctx, driver, channel):
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
            await channel.send("Funrize Daily Bonus Claimed!")
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
        await channel.send(f"Next Funrize bonus Available in: {countdown}")
        return
    except TimeoutException:
        pass

    # 1e) Fallback: not logged in (or weird page) → login + claim
    print("logging into Funrize and claiming…")
    await funrize_casino(ctx, driver, channel)

# ───────────────────────────────────────────────────────────
# 2) Login & then hand off to claim
# ───────────────────────────────────────────────────────────
async def funrize_casino(ctx, driver, channel):
    if not FUNRIZE_CRED:
        await channel.send("Funrize credentials not found in environment variables.")
        return

    username, password = FUNRIZE_CRED.split(":")

    driver.get("https://funrize.com")
    await asyncio.sleep(5)

    try:
        login_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, LOGIN_BUTTON))
        )
        login_btn.click()

        await asyncio.sleep(5)
        email = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div/div[1]/div/div/div/div[1]/div/div[2]/form/label[1]/div[2]/input"))
        )
        email.send_keys(username)
        pw = driver.find_element(By.XPATH, "/html/body/div[1]/div/div[1]/div/div/div/div[1]/div/div[2]/form/label[2]/div[2]/input")
        await asyncio.sleep(5)
        pw.send_keys(password, Keys.ENTER)
        await asyncio.sleep(5)

        # Now that we're logged in, try claiming
        await claim_funrize_bonus(ctx, driver, channel)

    except TimeoutException as e:
        screenshot = "funrize_login_error.png"
        driver.save_screenshot(screenshot)
        await channel.send(
            "Funrize login timed out, will retry later.",
            file=discord.File(screenshot)
        )
        os.remove(screenshot)
        print("Login timeout:", e)

# ───────────────────────────────────────────────────────────
# 3) After login: click the daily card + claim buttons
# ───────────────────────────────────────────────────────────
async def claim_funrize_bonus(ctx, driver, channel):
    driver.get(STORE_URL)
    await asyncio.sleep(5)

    # Click the “Claim Now” Button
    try:
        claim = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, CLAIM_BUTTON))
        )
        claim.click()
        await asyncio.sleep(5)
    except TimeoutException:
        pass    

        # then reuse the same loop we had above
    for xp in COLLECT_BUTTON:
        try:    
            collect = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            collect.click()
            await channel.send("Funrize Daily Bonus Claimed!")
            return
        except TimeoutException:
            pass

    # if still nothing, read countdown instead
    await funrize_flow(ctx, driver, channel)

# ───────────────────────────────────────────────────────────
# 4) (Optional) standalone countdown reader
# ───────────────────────────────────────────────────────────
async def check_funrize_countdown(ctx, driver, channel):
    # you can call this directly if you ever just want the timer
    driver.get(STORE_URL)
    await asyncio.sleep(5)

    countdown_btn = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, XPATH_COUNTDOWN))
    )
    raw       = countdown_btn.text.strip()
    countdown = re.sub(r"\s+", "", raw)
    await channel.send(f"Next Funrize Bonus Available in: {countdown}")

# ───────────────────────────────────────────────────────────
# 5) (Optional) Daily Spin Wheel
# ───────────────────────────────────────────────────────────
async def claim_funrize_wheel(ctx, driver, channel):
    driver.get(STORE_URL)
    await asyncio.sleep(5)

    # Click the "Spin & Win" Card
    try:
        spinwin_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, PROMOTIONS_SPIN))
        )
        spinwin_btn.click()
        await asyncio.sleep(5)
    except TimeoutException:
        pass

    # Click the "Spin" button
    try:
        spin_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, SPIN_BUTTON))
        )
        spin_btn.click()
        await channel.send("Funrize Daily Wheel Claimed!")
    except TimeoutException:
        pass