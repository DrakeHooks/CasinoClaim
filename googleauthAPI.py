# Drake Hooks
# Casino Claim 2
# Google Auth API

import re
import os
import discord
import asyncio
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# Load environment variables from the .env file
load_dotenv()

# Retrieve the single login string from environment variables
google_login = os.getenv("GOOGLE_LOGIN")

# Initialize email/password safely
email, password = None, None
if google_login and ":" in google_login:
    email, password = google_login.split(":", 1)  # split once in case password has ":"

async def google_auth(ctx, driver, channel, credentials):
    try:
        if credentials:
            username, password = credentials
        else:
            username = email or os.getenv("GOOGLE_USERNAME")
            password = password or os.getenv("GOOGLE_PASSWORD")

        # If no credentials, notify and exit
        if not username or not password:
            await channel.send("No Google credentials found in `.env`")
            return

        # Start login process
        driver.get("https://myaccount.google.com/?utm_source=chrome-profile-chooser&pli=1")
        await asyncio.sleep(5)
        driver.get("https://accounts.google.com/o/oauth2/v2/auth/oauthchooseaccount?redirect_uri=https%3A%2F%2Fdevelopers.google.com%2Foauthplayground&prompt=consent&response_type=code&client_id=407408718192.apps.googleusercontent.com&scope=email&access_type=offline&flowName=GeneralOAuthFlow")
        await asyncio.sleep(5)

        # Locate and fill the email field
        identifierID = driver.find_element(By.ID, "identifierId")
        await asyncio.sleep(5)
        identifierID.send_keys(username)
        identifierID.send_keys(Keys.ENTER)
        await asyncio.sleep(5)

        # Locate and fill the password field
        password_field = driver.find_element(By.NAME, "Passwd")
        await asyncio.sleep(5)
        password_field.send_keys(password)
        password_field.send_keys(Keys.ENTER)
        await asyncio.sleep(5)

        # Screenshot after login attempt
        screenshot1_path = "1google_screenshot.png"
        driver.save_screenshot(screenshot1_path)
        await channel.send(file=discord.File(screenshot1_path))
        os.remove(screenshot1_path)

        await channel.send("Approve 2FA to authenticate Google Account within 60 seconds.")
        await asyncio.sleep(60)

        # Final success message
        driver.get("https://myaccount.google.com/")
        await asyncio.sleep(5)
        await channel.send("Google Auth Successful!")

        google_screenshot_path = "google_screenshot.png"
        driver.save_screenshot(google_screenshot_path)
        await channel.send(file=discord.File(google_screenshot_path))
        os.remove(google_screenshot_path)

    except Exception as e:
        await channel.send(f"Error in google_auth: {str(e)}")
    return
