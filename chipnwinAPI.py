# Drake Hooks + WaterTrooper
# Casino Claim 2
# Chipnwin API

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
CHIPNWIN_CRED = os.getenv("CHIPNWIN")  # format "username:password"
SITE_URL = "https://chipnwin.com"
STORE_URL = "https://chipnwin.com/store/features"

# The accept cookie button XPATH
COOKIE_BUTTON = (
    "/html/body/div[1]/div[7]/div/div[2]/button"
)

# The login button XPATH
LOGIN_BUTTON = (
    "/html/body/div[1]/div[3]/div[1]/div[2]/div[1]/button"
)

# The Email Input ID
EMAIL_INPUT = (
    "input_customemail"
)

# The Password Input ID
PASSWORD_INPUT = (
    "input_custompassword"
)

# The Login Submit XPATH
LOGIN_SUBMIT = (
    "/html/body/div[1]/div[7]/div/div[2]/div[2]/div[5]/div[1]/button"
)

# Close the popup
CLOSE_POPUP = (
    "/html/body/div[1]/div[7]/div/div[1]/div[2]/svg"
)

# The claim button XPATH
CLAIM_BUTTON = (
    "/html/body/div[1]/div[4]/div/div[1]/div[3]/div[2]/div[3]/div[4]/div[2]/button"
)

# The collect button XPATH
COLLECT_BUTTON = [
    "/html/body/div[1]/div[6]/div/div[2]/div[3]/button",
    "/html/body/div[1]/div[7]/div/div[2]/div[3]/button",
    "/html/body/div[1]/div[8]/div/div[2]/div[3]/button"
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
async def chipnwin_flow(ctx, driver, channel):
    # 1a) Navigate to site
    driver.get(STORE_URL)
    await asyncio.sleep(10)

    # 1b) Click the accept cookie button
    try:
        cookie = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, COOKIE_BUTTON))
        )
        cookie.click()
        await asyncio.sleep(10)
    except TimeoutException:
        pass    

    # 1c) Click the “Claim Now” Button
    try:
        claim = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, CLAIM_BUTTON))
        )
        claim.click()
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
            await channel.send("Chipnwin Daily Bonus Claimed!")
            return
        except TimeoutException:
        # might not be logged in yet
            continue

    # 1e) If no claim, try to read the countdown
    try:
        countdown_btn = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.XPATH, XPATH_COUNTDOWN))
        )
        raw       = countdown_btn.text.strip()               # e.g. "22 : 27 : 06"
        countdown = re.sub(r"\s+", "", raw)           # => "22:27:06"
        await channel.send(f"Next Chipnwin bonus Available in: {countdown}")
        return
    except TimeoutException:
        pass

    # 1f) Fallback: not logged in (or weird page) → login + claim
    print("logging into Chipnwin and claiming…")
    await chipnwin_casino(ctx, driver, channel)

# ───────────────────────────────────────────────────────────
# 2) Login & then hand off to claim
# ───────────────────────────────────────────────────────────
async def chipnwin_casino(ctx, driver, channel):
    if not CHIPNWIN_CRED:
        await channel.send("Chipnwin credentials not found in environment variables.")
        return

    username, password = CHIPNWIN_CRED.split(":")

    driver.get(SITE_URL)
    await asyncio.sleep(10)

    try:
        login_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, LOGIN_BUTTON))
        )
        login_btn.click()

        await asyncio.sleep(10)
        email = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, EMAIL_INPUT))
        )
        email.send_keys(username)
        await asyncio.sleep(5)
        pw = driver.find_element(By.ID, PASSWORD_INPUT)
        pw.send_keys(password)
        await asyncio.sleep(5)
        empw_ln_btn = driver.find_element(By.XPATH, LOGIN_SUBMIT)
        empw_ln_btn.click()
        await asyncio.sleep(10)

        # Refresh the page to deal with popup
        driver.refresh()
        await asyncio.sleep(5)

        # Now that we're logged in, try claiming
        await claim_chipnwin_bonus(ctx, driver, channel)

    except TimeoutException as e:
        screenshot = "chipnwin_login_error.png"
        driver.save_screenshot(screenshot)
        await channel.send(
            "Chipnwin login timed out, will retry later.",
            file=discord.File(screenshot)
        )
        os.remove(screenshot)
        print("Login timeout:", e)

# ───────────────────────────────────────────────────────────
# 3) After login: click the daily card + claim buttons
# ───────────────────────────────────────────────────────────
async def claim_chipnwin_bonus(ctx, driver, channel):
    driver.get(STORE_URL)
    await asyncio.sleep(5)

    # Close the Popup
    try:
        popup = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, CLOSE_POPUP))
        )
        popup.click()
        await asyncio.sleep(10)
    except TimeoutException:
        pass    

    # Click the “Claim Now” Button
    try:
        claim = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, CLAIM_BUTTON))
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
            await channel.send("Chipnwin Daily Bonus Claimed!")
            return
        except TimeoutException:
            pass

    # if still nothing, read countdown instead
    await chipnwin_flow(ctx, driver, channel)

# ───────────────────────────────────────────────────────────
# 4) (Optional) standalone countdown reader
# ───────────────────────────────────────────────────────────
async def check_chipnwin_countdown(ctx, driver, channel):
    # you can call this directly if you ever just want the timer
    driver.get(STORE_URL)
    await asyncio.sleep(10)

    countdown_btn = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, XPATH_COUNTDOWN))
    )
    raw       = countdown_btn.text.strip()
    countdown = re.sub(r"\s+", "", raw)
    await channel.send(f"Next Chipnwin Bonus Available in: {countdown}")

# ───────────────────────────────────────────────────────────
# 5) (Optional) Daily Spin Wheel
# ───────────────────────────────────────────────────────────
async def claim_chipnwin_wheel(ctx, driver, channel):
    driver.get(STORE_URL)
    await asyncio.sleep(10)

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
        await channel.send("Chipnwin Daily Wheel Claimed!")
    except TimeoutException:
        pass