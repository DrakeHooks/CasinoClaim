# Drake Hooks + WaterTrooper
# Casino Claim 2
# SpinPals API

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
SPINPALS_CRED = os.getenv("SPINPALS")  # format "username:password"
STORE_URL     = "https://www.spinpals.com/user/store"

# The “Daily Bonus” card you click first
CLAIM_CARD_XPATH = (
    "/html/body/div[2]/div[2]/div/div/div/div[2]/div[2]/div/div/div[1]/div/div/div/div/div[3]/div/div/a"
)

# All possible XPaths for the enabled “Claim” button (Day 1–7)
CLAIM_XPATHS = [
            "/html/body/div[2]/div[2]/div/div/div/div[2]/div[2]/div/div/div[2]/div/div/div/div[2]/div[1]/div/div/button",
            "/html/body/div[2]/div[2]/div/div/div/div[2]/div[2]/div/div/div[2]/div/div/div/div[2]/div[2]/div/div/button",
            "/html/body/div[2]/div[2]/div/div/div/div[2]/div[2]/div/div/div[2]/div/div/div/div[2]/div[3]/div/div/button",
            "/html/body/div[2]/div[2]/div/div/div/div[2]/div[2]/div/div/div[2]/div/div/div/div[2]/div[4]/div/div/button",
            "/html/body/div[2]/div[2]/div/div/div/div[2]/div[2]/div/div/div[2]/div/div/div/div[2]/div[5]/div/div/button",
            "/html/body/div[2]/div[2]/div/div/div/div[2]/div[2]/div/div/div[2]/div/div/div/div[2]/div[6]/div/div/button",
            "/html/body/div[2]/div[2]/div/div/div/div[2]/div[2]/div/div/div[2]/div/div/div/div[2]/div[7]/div/div/button"
]

# XPath for the disabled countdown button
XPATH_COUNTDOWN = "//button[@disabled and contains(normalize-space(.), ':')]"

# ───────────────────────────────────────────────────────────
# 1) Unified flow: claim → countdown → login & claim
# ───────────────────────────────────────────────────────────
async def spinpals_flow(ctx, driver, channel):
    # 1a) Navigate to store
    driver.get(STORE_URL)
    await asyncio.sleep(5)

    # 1b) Click the “Daily Bonus” card
    try:
        card = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, CLAIM_CARD_XPATH))
        )
        card.click()
        await asyncio.sleep(2)
    except TimeoutException:
        # might not be logged in yet
        pass

    # 2) Try to click any enabled “Claim” button
    for xp in CLAIM_XPATHS:
        try:
            claim_btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            claim_btn.click()
            await channel.send("SpinPals Daily Bonus Claimed!")
            return
        except TimeoutException:
            continue

    # 3) If no claim, try to read the countdown
    try:
        countdown_btn = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.XPATH, XPATH_COUNTDOWN))
        )
        raw       = countdown_btn.text.strip()               # e.g. "22 : 27 : 06"
        countdown = re.sub(r"\s+", "", raw)           # => "22:27:06"
        await channel.send(f"Next SpinPals bonus Available in: {countdown}")
        return
    except TimeoutException:
        pass

    # 4) Fallback: not logged in (or weird page) → login + claim
    print("logging into SpinPals and claiming…")
    await spinpals_casino(ctx, driver, channel)

# ───────────────────────────────────────────────────────────
# 2) Login & then hand off to claim
# ───────────────────────────────────────────────────────────
async def spinpals_casino(ctx, driver, channel):
    if not SPINPALS_CRED:
        await channel.send("SpinPals credentials not found in environment variables.")
        return

    username, password = SPINPALS_CRED.split(":")

    driver.get("https://www.spinpals.com")
    await asyncio.sleep(5)

    try:
        login_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((
                By.XPATH,
                "/html/body/div[2]/div[2]/div/div/div/div[1]/div[2]/div/button[1]"
            ))
        )
        login_btn.click()

        await asyncio.sleep(5)
        email = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "email"))
        )
        email.send_keys(username)

        pw = driver.find_element(By.NAME, "password")
        pw.send_keys(password, Keys.ENTER)
        await asyncio.sleep(5)

        # Now that we're logged in, try claiming
        await claim_spinpals_bonus(ctx, driver, channel)

    except TimeoutException as e:
        screenshot = "spinpals_login_error.png"
        driver.save_screenshot(screenshot)
        await channel.send(
            "SpinPals login timed out, will retry later.",
            file=discord.File(screenshot)
        )
        os.remove(screenshot)
        print("Login timeout:", e)

# ───────────────────────────────────────────────────────────
# 3) After login: click the daily card + claim buttons
# ───────────────────────────────────────────────────────────
async def claim_spinpals_bonus(ctx, driver, channel):
    driver.get(STORE_URL)
    await asyncio.sleep(5)

    # click the “Daily Bonus” card again
    try:
        card = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, CLAIM_CARD_XPATH))
        )
        card.click()
        await asyncio.sleep(2)
    except TimeoutException:
        pass

    # then reuse the same loop we had above
    for xp in CLAIM_XPATHS:
        try:
            claim_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            claim_btn.click()
            await channel.send("SpinPals Daily Bonus Claimed!")
            return
        except TimeoutException:
            continue

    # if still nothing, read countdown instead
    await spinpals_flow(ctx, driver, channel)

# ───────────────────────────────────────────────────────────
# 4) (Optional) standalone countdown reader
# ───────────────────────────────────────────────────────────
async def check_spinpals_countdown(ctx, driver, channel):
    # you can call this directly if you ever just want the timer
    driver.get(STORE_URL)
    await asyncio.sleep(5)

    countdown_btn = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, XPATH_COUNTDOWN))
    )
    raw       = countdown_btn.text.strip()
    countdown = re.sub(r"\s+", "", raw)
    await channel.send(f"Next SpinPals bonus Available in: {countdown}")
