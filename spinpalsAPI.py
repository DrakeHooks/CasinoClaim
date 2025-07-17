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
from seleniumbase import BaseCase


# Load environment variables from the .env file
load_dotenv()


# Function to log in and claim SpinPals bonus
async def spinpals_casino(ctx, driver, channel):
    try:
        # Get the SPINPALS credentials from the .env file
        spinpals_credentials = os.getenv("SPINPALS")


        if spinpals_credentials:
            # Split the credentials into username and password using the ':' delimiter
            username, password = spinpals_credentials.split(':')
        else:
            await channel.send("SpinPals credentials not found in environment variables.")
            return
        # Get the URL and allow page to load
        driver.get("https://www.spinpals.com")
        await asyncio.sleep(10)
        login_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div[2]/div/div/div/div[1]/div[2]/div/button[1]"))
        )
        login_button.click()


        await asyncio.sleep(90)
        email_input = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.NAME, "email"))
            )
        email_input.send_keys(username)
        await asyncio.sleep(5)  # Wait for email
        password_input = driver.find_element(By.NAME, "password")
        password_input.send_keys(password)
        password_input.send_keys(Keys.ENTER)
        await asyncio.sleep(40)  # Wait for login process to complete
        # Now proceed with claiming the bonus
        await claim_spinpals_bonus(ctx, driver, channel)
    except TimeoutException as e:
        screenshot_path = "1sp_screenshot.png"
        driver.save_screenshot(screenshot_path)
        await channel.send("SpinPals Authentication timed out, will try again later.", 
                       file=discord.File(screenshot_path))
        os.remove(screenshot_path)
        print(f"Login timeout: {e}")
        await channel.send("Login to SpinPals failed.")
    except Exception as e:
        print(f"Error in spinpals_casino")










# Function to claim the 24-hour bonus
async def claim_spinpals_bonus(ctx, driver, channel):
    try:

        # Get the URL and allow page to load
        driver.get("https://www.spinpals.com/user/store")
        await asyncio.sleep(10)

        # Navigate to the store page to claim the bonus
        if driver.current_url == "https://www.spinpals.com/user/store":
            await channel.send("Authenticated into SpinPals successfully!")
            await asyncio.sleep(5)

        # Click the daily bonus button
        daily_bonus = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div[2]/div/div/div/div[2]/div[2]/div/div/div[1]/div/div/div/div/div[3]/div/div/a"))
        )
        daily_bonus.click()


        # Try multiple possible XPaths for the claim button
        xpaths = [
            "/html/body/div[2]/div[2]/div/div/div/div[2]/div[2]/div/div/div[2]/div/div/div/div[2]/div[1]/div/div/button",
            "/html/body/div[2]/div[2]/div/div/div/div[2]/div[2]/div/div/div[2]/div/div/div/div[2]/div[2]/div/div/button",
            "/html/body/div[2]/div[2]/div/div/div/div[2]/div[2]/div/div/div[2]/div/div/div/div[2]/div[3]/div/div/button",
            "/html/body/div[2]/div[2]/div/div/div/div[2]/div[2]/div/div/div[2]/div/div/div/div[2]/div[4]/div/div/button",
            "/html/body/div[2]/div[2]/div/div/div/div[2]/div[2]/div/div/div[2]/div/div/div/div[2]/div[5]/div/div/button",
            "/html/body/div[2]/div[2]/div/div/div/div[2]/div[2]/div/div/div[2]/div/div/div/div[2]/div[6]/div/div/button",
            "/html/body/div[2]/div[2]/div/div/div/div[2]/div[2]/div/div/div[2]/div/div/div/div[2]/div[7]/div/div/button"
        ]

        button_found = False
        for xpath in xpaths:
            try:
                claim_button = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                claim_button.click()
                await channel.send("SpinPals Daily Bonus Claimed!")
                button_found = True
                break
            except TimeoutException:
                continue

        # Check countdown if button was not found
        if not button_found:
            print("No 'Claim' button found. Checking countdown timer...")
            await check_spinpals_countdown(ctx, driver, channel)

    except Exception as e:
        print(f"Error while claiming SpinPals bonus: {str(e)}")
        return False




async def check_spinpals_countdown(ctx, driver, channel):
    try:
        # 1) Wait for the disabled button with a colon in its text
        btn = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((
                By.XPATH,
                "//button[@disabled and contains(normalize-space(.), ':')]"
            ))
        )

        # 2) Collapse out any whitespace
        raw = btn.text.strip()                  # e.g. "22 : 27 : 06"
        countdown = re.sub(r"\s+", "", raw)     # becomes "22:27:06"

        # 3) Validate format
        if not re.match(r"^\d{1,2}:\d{1,2}:\d{1,2}$", countdown):
            raise ValueError(f"Unexpected format: {raw!r}")

        # 4) Send to Discord
        await channel.send(f"Next SpinPals Bonus in: {countdown}")

    except (TimeoutException, ValueError) as e:
        print(f"[SpinPals] countdown error: {e}")
        await channel.send("Error retrieving SpinPals countdown timer.")