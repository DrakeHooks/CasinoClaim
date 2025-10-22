# Drake Hooks + WaterTrooper
# Casino Claim 2
# TaoFortune API

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
TAOFORTUNE_CRED = os.getenv("TAOFORTUNE")  # format "username:password"
SITE_URL = "https://taofortune.com"
STORE_URL = "https://taofortune.com/promotions"

# The login button XPATH
LOGIN_BUTTON = (
    "/html/body/div[1]/div/div[1]/div[1]/header/div/button[1]"
)

# The Email Input XPATH
EMAIL_INPUT = (
    "/html/body/div[1]/div/div[1]/main/div/div/form/div/label[1]/div[2]/div[2]/input"
)

# The Password Input XPATH
PASSWORD_INPUT = (
    "/html/body/div[1]/div/div[1]/main/div/div/form/div/label[2]/div[2]/input"
)

# The Login Input XPATH
LOGIN_INPUT = (
    "/html/body/div[1]/div/div[1]/main/div/div/form/button"
)

# The Card Button Class Name
CARD_BUTTON = (
    "card-magicBox"
)

# The Box XPATH
BOX_BUTTON = (
    "/html/body/div[4]/div/div[3]/div[1]/div[3]/img"
)

# The collect button XPATH
COLLECT_BUTTON = [
    "/html/body/div[4]/div/div[3]/div[2]/button"
]

# XPath for the disabled countdown button
XPATH_COUNTDOWN = "//button[@disabled and contains(normalize-space(.), ':')]"

# ───────────────────────────────────────────────────────────
# 1) Unified flow: claim → countdown → login & claim
# ───────────────────────────────────────────────────────────
async def taofortune_flow(ctx, driver, channel):
    # 1a) Navigate to site
    driver.get(STORE_URL)
    await asyncio.sleep(10)

    # 1b) Click the “Magic Box” Card
    try:
        card = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, CARD_BUTTON))
        )
        card.click()
        await asyncio.sleep(10)
    except TimeoutException:
        pass
    #1c) Click the "Prize Box"
    try:
        box = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, BOX_BUTTON))
        )
        box.click()
        await asyncio.sleep(10)
    except TimeoutException:
        pass

    # 1d) Click the "Collect" Button
    for xp in COLLECT_BUTTON:
        try:
            collect = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, xp))
            )
            collect.click()
            await channel.send("TaoFortune Daily Bonus Claimed!")
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
        await channel.send(f"Next TaoFortune bonus Available in: {countdown}")
        return
    except TimeoutException:
        pass

    # 1e) Fallback: not logged in (or weird page) → login + claim
    print("logging into TaoFortune and claiming…")
    await taofortune_casino(ctx, driver, channel)

# ───────────────────────────────────────────────────────────
# 2) Login & then hand off to claim
# ───────────────────────────────────────────────────────────
async def taofortune_casino(ctx, driver, channel):
    if not TAOFORTUNE_CRED:
        await channel.send("TaoFortune credentials not found in environment variables.")
        return

    username, password = TAOFORTUNE_CRED.split(":")

    driver.get(SITE_URL)
    await asyncio.sleep(5)

    try:
        login_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, LOGIN_BUTTON))
        )
        login_btn.click()

        await asyncio.sleep(5)
        email = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, EMAIL_INPUT))
        )
        email.send_keys(username)
        pw = driver.find_element(By.XPATH, PASSWORD_INPUT)
        await asyncio.sleep(5)
        pw.send_keys(password)
        await asyncio.sleep(5)
        empw_ln_btn = driver.find_element(By.XPATH, LOGIN_INPUT)
        empw_ln_btn.click()
        await asyncio.sleep(5)

        # Now that we're logged in, try claiming
        await claim_taofortune_bonus(ctx, driver, channel)

    except TimeoutException as e:
        screenshot = "taofortune_login_error.png"
        driver.save_screenshot(screenshot)
        await channel.send(
            "TaoFortune login timed out, will retry later.",
            file=discord.File(screenshot)
        )
        os.remove(screenshot)
        print("Login timeout:", e)

# ───────────────────────────────────────────────────────────
# 3) After login: click the daily card + claim buttons
# ───────────────────────────────────────────────────────────
async def claim_taofortune_bonus(ctx, driver, channel):
    # 3a) Nagivate to site
    driver.get(STORE_URL)
    await asyncio.sleep(5)

    # 3b Click the “Magic Box” Card
    try:
        card = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, CARD_BUTTON))
        )
        card.click()
        await asyncio.sleep(5)
    except TimeoutException:
        pass

    # 3c) Click the "Prize Box"
    try:
        box = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, BOX_BUTTON))
        )
        box.click()
        await asyncio.sleep(10)
    except TimeoutException:
        pass

    # 3d) Click the "Collect" Button
    for xp in COLLECT_BUTTON:
        try:    
            collect = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            collect.click()
            await channel.send("TaoFortune Daily Bonus Claimed!")
            return
        except TimeoutException:
            pass

    # if still nothing, read countdown instead
    await taofortune_flow(ctx, driver, channel)

# ───────────────────────────────────────────────────────────
# 4) (Optional) standalone countdown reader
# ───────────────────────────────────────────────────────────
async def check_taofortune_countdown(ctx, driver, channel):
    # you can call this directly if you ever just want the timer
    driver.get(STORE_URL)
    await asyncio.sleep(5)

    countdown_btn = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, XPATH_COUNTDOWN))
    )
    raw       = countdown_btn.text.strip()
    countdown = re.sub(r"\s+", "", raw)
    await channel.send(f"Next TaoFortune Bonus Available in: {countdown}")