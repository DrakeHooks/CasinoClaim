# Drake Hooks
# Stake API
# Requires Google Account linked to Stake.us. Other auth methods are in development.



import re
import os
import asyncio
from dotenv import load_dotenv  # Import load_dotenv to load environment variables
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import discord

# Load environment variables from the .env file
load_dotenv()

async def stake_auth(ctx, driver, channel):
    try:
        # Get the URL and allow page to load
        driver.get("https://stake.us/casino/home")
        await asyncio.sleep(20)
        signInBtn = WebDriverWait(driver, 90).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div[2]/div[1]/div[2]/div/div/div/section/div/button[1]"))
        )
        signInBtn.click()
        await asyncio.sleep(15)
        googleLogoBtn = WebDriverWait(driver, 90).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div[1]/div[2]/div[2]/div/div/div[2]/div[2]/div[2]/button")))
        googleLogoBtn.click()
        await asyncio.sleep(5)
    except:
        screenshot_path = "stake_auth_error.png"
        driver.save_screenshot(screenshot_path)
        await channel.send("Stake authentication failed",
                           file=discord.File(screenshot_path))
        os.remove(screenshot_path)
        return

async def stake_claim(ctx, driver, channel):
    try:
        await stake_auth(ctx, driver, channel)
    except:
        print("Error in stake_auth")
    try:
        # Open the initial website
        driver.get("https://stake.us/casino/home?tab=dailyBonus&currency=btc&modal=wallet")
        await asyncio.sleep(10)
        try:
            await asyncio.sleep(20)
            claimBtn = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div[1]/div[2]/div[2]/div/div[1]/div/form/button")))
            claimBtn.click()
            await channel.send("Stake Daily Bonus Available!")
        except:
            print("Stake Daily Bonus Unavailable!")
    finally:
            hours_xpath = "/html/body/div[1]/div[1]/div[2]/div[2]/div/div[1]/div/form/div[3]/div/div[2]/span[1]/span"
            hours_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, hours_xpath)))
            hours = hours_element.text.zfill(2)

            minutes_xpath = "/html/body/div[1]/div[1]/div[2]/div[2]/div/div[1]/div/form/div[3]/div/div[3]/span[1]/span"
            minutes_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, minutes_xpath)))
            minutes = minutes_element.text.zfill(2)

            seconds_xpath = "/html/body/div[1]/div[1]/div[2]/div[2]/div/div[1]/div/form/div[3]/div/div[4]/span[1]/span"
            seconds_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, seconds_xpath)))
            seconds = seconds_element.text.zfill(2)

            countdown_message = f"Next Stake Bonus Available in: {hours}:{minutes}:{seconds}"
            await channel.send(countdown_message)
        