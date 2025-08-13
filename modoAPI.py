# Drake Hooks
# Casino Claim 2
# Modo API


import os
import asyncio
import discord
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import re
from helperAPI import open_captcha_solver_page

# Load environment variables from the .env file
load_dotenv()

# ───────────────────────────────────────────────────────────
# Authentication for Modo. 5 Attempts to login
# ───────────────────────────────────────────────────────────
async def authenticate_modo(driver, bot, ctx, channel):
    channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL")))

    creds = os.getenv("MODO")
    if not creds:
        await channel.send("MODO credentials not found in environment variables.")
        return False

    email, password = creds.split(":")

    for attempt in range(5):
        try:
            await open_captcha_solver_page(driver)
            driver.maximize_window()

            web = "https://login.modo.us/login"
            driver.get(web)
            await asyncio.sleep(10)

            try:
                email_field = WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.XPATH, "/html/body/main/div/div[2]/form/div/div/div/div/div[2]/div[2]/span/div/div/div/div/div/div/div[2]/div[3]/div[1]/div/input"))
                )
                email_field.send_keys(email)

                password_field = WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.XPATH, "/html/body/main/div/div[2]/form/div/div/div/div/div[2]/div[2]/span/div/div/div/div/div/div/div[2]/div[3]/div[2]/div/div/input"))
                )
                password_field.send_keys(password)
                screenshot_path = "modo_login_screenshot.png"
                driver.save_screenshot(screenshot_path)
                await channel.send("Modo user/pass entered. Solving captcha...", file=discord.File(screenshot_path))
                os.remove(screenshot_path)
                await asyncio.sleep(120)
            except Exception:
                await channel.send("Unable to auth Modo! Retrying...")
                await asyncio.sleep(5)
                continue

            try:
                login_btn = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((By.XPATH, "/html/body/main/div/div[2]/form/div/div/div/button"))
                )
                login_btn.click()
                await asyncio.sleep(10)
            except Exception:
                await channel.send("Unable to solve Modo captcha! Retrying...")
                await asyncio.sleep(5)
                continue

            await asyncio.sleep(10)
            driver.refresh()
            getCoins_xpath = "/html/body/div[1]/div[2]/div[2]/main/main/header/div/div/div[2]/button"
            try:
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.XPATH, getCoins_xpath))
                )
                await channel.send("Authenticated into modo successfully!")
                return True
            except TimeoutException:
                await channel.send(f"Authentication failed. Get Coins element not found. Attempt {attempt + 1} of 5.")
        except TimeoutException:
            await channel.send(f"Authentication timeout on attempt {attempt + 1}. Retrying...")

        await asyncio.sleep(5)

    await channel.send("Authentication failed after 5 attempts.")
    return False

# ───────────────────────────────────────────────────────────
# Bonus Claim Function
# ───────────────────────────────────────────────────────────
async def claim_modo_bonus(driver, bot, ctx, channel):
    try:
        channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL")))

        driver.get("https://modo.us/lobby/")
        await asyncio.sleep(10)

        # Try multiple possible XPaths for the claim button
        xpaths = [
            "/html/body/div[6]/div[3]/div/div[2]/button",
            "/html/body/div[6]/div[3]/div/div[3]/div/button",
            "/html/body/div[4]/div[3]/div/div[3]/button",
            "/html/body/div[8]/div[3]/div/div[3]/div/button",
            "/html/body/div[5]/div[3]/div[3]/button",
            "/html/body/div[5]/div[3]/div/div[3]/div/button",
            "/html/body/div[6]/div[3]/div/div[3]/div/button",
            "/html/body/div[7]/div[3]/div/div[3]/div/button"
        ]

        button_found = False
        for xpath in xpaths:
            try:
                claim_button = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                claim_button.click()
                await channel.send("Modo Daily Bonus Claimed!")
                button_found = True
                break
            except TimeoutException:
                continue

        # Check countdown if button was not found
        if not button_found:
            print("No 'Claim Now' button found. Checking countdown timer...")
            await check_modo_countdown(driver, bot, ctx, channel)

    except Exception as e:
        print(f"Error while claiming Modo bonus: {str(e)}")
        return False

    return True


# ───────────────────────────────────────────────────────────
# Countdown reader function
# ───────────────────────────────────────────────────────────
async def check_modo_countdown(driver, bot, ctx, channel):
    try:
        channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL")))

        driver.get("https://modo.us/lobby/")
        await asyncio.sleep(10)

        # Wait for countdown timer element using updated class
        countdown_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div[1]/div/div[3]/div/div[1]/div/div[1]/button/div/div[2]/div[1]/div/span"))
        )

        # Extract countdown text
        countdown_text = countdown_element.text.strip()

        # Use regex to extract time format (HH:MM:SS)
        match = re.match(r"(\d{2}):(\d{2}):(\d{2})", countdown_text)
        if match:
            countdown_time = countdown_text
        else:
            countdown_time = "Unknown format"

        # Send formatted countdown message
        countdown_message = f"Next Modo Bonus Available in: {countdown_time}"
        await channel.send(countdown_message)

    except TimeoutException:
        await channel.send("Failed to retrieve Modo countdown timer.")
        return False

    return True


# ───────────────────────────────────────────────────────────
# Main function
# ───────────────────────────────────────────────────────────
async def modo_casino(driver, bot, ctx, channel):
    channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL")))

    # Authenticate first
    await channel.send("Authenticating into Modo...")
    authenticated = await authenticate_modo(driver, bot, ctx, channel)

    if authenticated:
        try:
            await claim_modo_bonus(driver, bot, ctx, channel)
            await asyncio.sleep(5)
        except:
            print("Failed to claim Modo bonus.")
        await check_modo_countdown(driver, bot, ctx, channel)
    else:
        await channel.send("Failed to authenticate into Modo.")
