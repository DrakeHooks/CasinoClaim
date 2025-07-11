# Drake Hooks
# Casino Claim 2
# Rolling Riches API

import re
import os
import asyncio
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Load environment variables from the .env file
load_dotenv()

# Function to log in and claim Rolling Riches bonus
async def rolling_riches_casino(ctx, driver, channel):
    try:
        # Get the ROLLING_RICHES credentials from the .env file
        rolling_riches_credentials = os.getenv("ROLLING_RICHES")

        if rolling_riches_credentials:
            # Split the credentials into username and password using the ':' delimiter
            username, password = rolling_riches_credentials.split(':')
        else:
            await channel.send("Rolling Riches credentials not found in environment variables.")
            return

        # Get the URL and allow page to load
        driver.get("https://rollingriches.com/login")
        await asyncio.sleep(10)
        try:
            email_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            login_button_present = True
        except TimeoutException:
            login_button_present = False

        # If login button is found, perform login with credentials
        if login_button_present:
            email_input.send_keys(username)
            password_input = driver.find_element(By.ID, "password")
            password_input.send_keys(password)
            password_input.send_keys(Keys.ENTER)
            await asyncio.sleep(5)  # Wait for login process to complete
        else:
            # If no login button is found, assume already logged in
            await channel.send("Rolling Riches unable to login.")

        # Now proceed with claiming the bonus
        await claim_rolling_riches_bonus(ctx, driver, channel)

    except TimeoutException as e:
        print(f"Login timeout: {e}")
        await channel.send("Login to Rolling Riches failed.")
    except Exception as e:
        print(f"Error in rolling_riches_casino")


# Function to claim the 6-hour bonus
async def claim_rolling_riches_bonus(ctx, driver, channel):
    try:
        # Navigate to the main page to claim the bonus
        driver.get("https://www.rollingriches.com/get-coins")
        await asyncio.sleep(5)
        
        # Click the daily bonus label
        daily_bonus_label = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/app-root/app-get-coin/div/div[1]/div/label[2]"))
        )
        daily_bonus_label.click()

        # Click the claim button
        claim_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/app-root/app-get-coin/div/div[2]/div/app-hourly-bonus/div/div/div[4]/button"))
        )
        claim_btn.click()
        await channel.send("Rolling Riches 6-Hour Bonus Claimed!")

    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        await asyncio.sleep(10)
        print("Checking for countdown element.")
        
        # List of possible XPaths for the countdown element
        countdown_xpaths = [
            "/html/body/app-root/app-get-coin/div/div[2]/div/app-hourly-bonus/div/div/div[4]/div/label",
            "/html/body/app-root/app-get-coin/div/div[2]/div/app-hourly-bonus/div/div/div[5]/div/label"
        ]
        countdown_element = None
        for xpath in countdown_xpaths:
            try:
                countdown_element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, xpath)))
                if countdown_element:
                    break
            except:
                continue
        
        if countdown_element:
            countdown_value = countdown_element.text.strip()

            # Replace spaces with colons to format it correctly as HH:MM:SS
            countdown_value = countdown_value.replace(" ", ":")
            
            # In case the value has fewer than 6 characters, prepend zeros to maintain the format
            time_parts = countdown_value.split(":")
            while len(time_parts) < 3:  # Ensure we have 3 parts (HH:MM:SS)
                time_parts.insert(0, "00")
            formatted_countdown = ":".join(time_parts)

            await channel.send(f"Next Rolling Riches Bonus Available in: {formatted_countdown}")
        else:
            print("Unable to retrieve Rolling Riches countdown value.")



