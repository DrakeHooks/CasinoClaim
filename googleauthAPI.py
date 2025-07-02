# Drake Hooks
# Casino Claim
# Google Authentication API
# This API is used to authenticate a Google account using the provided credentials for casinos that require Google authentication.


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


async def google_auth(ctx, driver, channel, credentials):
    try:
        if credentials and all(credentials):
            email, password = credentials
        else:
            google_login = os.getenv("GOOGLE_LOGIN")
            if google_login:
                email, password = google_login.split(":")
            else:
                await channel.send("Google credentials not found")
                return
        if email and password:
            driver.get("https://myaccount.google.com/?utm_source=chrome-profile-chooser&pli=1")
            await asyncio.sleep(5)
            driver.get("https://accounts.google.com/o/oauth2/v2/auth/oauthchooseaccount?redirect_uri=https%3A%2F%2Fdevelopers.google.com%2Foauthplayground&prompt=consent&response_type=code&client_id=407408718192.apps.googleusercontent.com&scope=email&access_type=offline&flowName=GeneralOAuthFlow")
            await asyncio.sleep(5)
        # Locate and fill the email field
            identifierID = driver.find_element(By.ID, "identifierId")
            await asyncio.sleep(5)
            identifierID.send_keys(email)
            await asyncio.sleep(5)
        # Click 'Next' button
            nextBTN = driver.find_element(By.XPATH, "/html/body/div[1]/div[1]/div[2]/c-wiz/div/div[3]/div/div[1]/div/div/button")
            nextBTN.click()
            await asyncio.sleep(5)
        # Locate and fill the password field
            password_field = driver.find_element(By.NAME, "Passwd")
            await asyncio.sleep(5)
            password_field.send_keys(password)
            await asyncio.sleep(5)
        # Click 'Next' button after password
            nextBTN_2 = driver.find_element(By.ID, "passwordNext")
            nextBTN_2.click()
        # Prompt for 2FA approval
            await channel.send("Approve 2FA to authenticate Google Account within 60 seconds.")
            await asyncio.sleep(60)
        # Final success message
            driver.get("https://myaccount.google.com/")
            await asyncio.sleep(5)
            await channel.send("Google Auth Successful!")
        else:
             await channel.send("Google credentials not found")
    except:
            screenshot_path = "google_auth_error.png"
            driver.save_screenshot(screenshot_path)
            await channel.send("Google authentication failed",
                           file=discord.File(screenshot_path))
            os.remove(screenshot_path)
            return
    return
