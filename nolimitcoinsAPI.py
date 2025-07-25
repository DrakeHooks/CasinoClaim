# Drake Hooks + WaterTrooper
# Casino Claim 2
# NoLimitCoins API

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
NOLIMITCOINS_CRED = os.getenv("NOLIMITCOINS")  # format "username:password"
STORE_URL     = "https://nolimitcoins.com/promotions"

# The “Daily Bonus” card you click first
CLAIM_CARD_XPATH = (
    "/html/body/div[1]/div/main/div/div[3]/div[5]/div[2]/div/button"
)

# All possible XPaths for the enabled “Claim” button (Day 1–7)
# You probably don't need all these xpaths, if you can get this to click the button
CLAIM_XPATHS = [
            "/html/body/div[3]/div/div/div/button",
            "/html/body/div[3]/div/div/div/div[1]/div[1]/div",
            "/html/body/div[3]/div/div/div/div[1]/div[2]/div",
            "/html/body/div[3]/div/div/div/div[1]/div[3]/div",
            "/html/body/div[3]/div/div/div/div[1]/div[4]/div",
            "/html/body/div[3]/div/div/div/div[1]/div[5]/div",
            "/html/body/div[3]/div/div/div/div[1]/div[6]/div",
            "/html/body/div[3]/div/div/div/div[1]/div[7]/div/div[2]"
]

# XPath for the disabled countdown button
XPATH_COUNTDOWN = "//button[@disabled and contains(normalize-space(.), ':')]"

# ───────────────────────────────────────────────────────────
# 1) Unified flow: claim → countdown → login & claim
# ───────────────────────────────────────────────────────────
async def nolimitcoins_flow(ctx, driver, channel):
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
            await channel.send("NoLimitCoins Daily Bonus Claimed!")
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
        await channel.send(f"Next NoLimitCoins bonus Available in: {countdown}")
        return
    except TimeoutException:
        pass

    # 4) Fallback: not logged in (or weird page) → login + claim
    print("logging into NoLimitCoins and claiming…")
    await nolimitcoins_casino(ctx, driver, channel)

# ───────────────────────────────────────────────────────────
# 2) Login & then hand off to claim
# ───────────────────────────────────────────────────────────
async def nolimitcoins_casino(ctx, driver, channel):
    if not NOLIMITCOINS_CRED:
        await channel.send("NoLimitCoins credentials not found in environment variables.")
        return

    username, password = NOLIMITCOINS_CRED.split(":")

    driver.get("https://nolimitcoins.com")
    await asyncio.sleep(5)

    try:
        login_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((
                By.XPATH,
                "/html/body/div[1]/div/div[1]/header/div[2]/button[1]"
            ))
        )
        login_btn.click()

        await asyncio.sleep(5)
        email = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div/div[1]/div/form/label[1]/div/div[2]/input"))
        )
        email.send_keys(username)
        await asyncio.sleep(5)
        pw = driver.find_element(By.XPATH, "/html/body/div[1]/div/div[1]/div/form/label[2]/div[1]/input")
        pw.send_keys(password, Keys.ENTER)
        await asyncio.sleep(5)

        # Now that we're logged in, try claiming
        await claim_nolimitcoins_bonus(ctx, driver, channel)

    except TimeoutException as e:
        screenshot = "nolimitcoins_login_error.png"
        driver.save_screenshot(screenshot)
        await channel.send(
            "NoLimitCoins login timed out, will retry later.",
            file=discord.File(screenshot)
        )
        os.remove(screenshot)
        print("Login timeout:", e)

# ───────────────────────────────────────────────────────────
# 3) After login: click the daily card + claim buttons
# ───────────────────────────────────────────────────────────
async def claim_nolimitcoins_bonus(ctx, driver, channel):
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
            await channel.send("NoLimitCoins Daily Bonus Claimed!")
            return
        except TimeoutException:
            continue

    # if still nothing, read countdown instead
    await nolimitcoins_flow(ctx, driver, channel)

# ───────────────────────────────────────────────────────────
# 4) (Optional) standalone countdown reader
# ───────────────────────────────────────────────────────────
async def check_nolimitcoins_countdown(ctx, driver, channel):
    # you can call this directly if you ever just want the timer
    driver.get(STORE_URL)
    await asyncio.sleep(5)

    countdown_btn = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, XPATH_COUNTDOWN))
    )
    raw       = countdown_btn.text.strip()
    countdown = re.sub(r"\s+", "", raw)
    await channel.send(f"Next NoLimitCoins Bonus Available in: {countdown}")