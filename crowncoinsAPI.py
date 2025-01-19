# Drake Hooks
# Casino Claim
# CrownCoinsCasino API



import re
import os
import asyncio
import requests
import json
from datetime import timedelta
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Load environment variables from the .env file
load_dotenv()

# Function to authenticate into Crown Coins via google. Run !googleauth before running this function.
async def auth_crown_google(driver, bot, ctx, channel):
    try:
        web = "https://crowncoinscasino.com/"
        driver.get(web)
        await asyncio.sleep(5)  # Give time for page to load

        try:
            login_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div/div[1]/div[1]/div[2]/button[2]"))
            )
            login_btn.click()

            google_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div[2]/div[2]/div/div/div[1]/div[2]/div[1]/button"))
            )
            google_btn.click()

            await asyncio.sleep(5)
            await channel.send("Authenticated into Crown Coins Casino!")
        except:
            await channel.send("Crown Coins login with google failed. Perhaps you need to run !googleauth.")
    except:
        print("Error in authenticate_crowncoins")
        return

# Function to authenticate into Crown Coins via .env creds.
async def auth_crown_env(driver, bot, ctx, channel):
    try:
        web = "https://crowncoinscasino.com/"
        driver.get(web)
        await asyncio.sleep(5)  # Give time for page to load

        try:
            login_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div/div[1]/div[1]/div[2]/button[2]"))
            )
            login_btn.click()

            # If found, proceed with login
            username = os.getenv("CROWNCOINS").split(":")[0]
            password = os.getenv("CROWNCOINS").split(":")[1]
            
            username_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "/html/body/div[2]/div[2]/div[2]/div/div/div[1]/div[2]/form/div[1]/input"))
            )

            password_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "/html/body/div[2]/div[2]/div[2]/div/div/div[1]/div[2]/form/div[2]/div/input"))
            )

            # Input the username and password
            username_field.send_keys(username)
            password_field.send_keys(password)
            await asyncio.sleep(2)

            login_btn2 = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div[2]/div[2]/div/div/div[1]/div[2]/form/div[3]/button"))
            )
            login_btn2.click()

            await asyncio.sleep(5)
            await channel.send("Authenticated into Crown Coins Casino!")
        except:
            await channel.send("Crown Coins login button not found.")
    except:
        print("Error in authenticate_crowncoins")
        return


# Function to get the countdown timer
async def get_countdown(driver, bot, ctx, channel):
    try:
        # Enable network logging via CDP
        driver.execute_cdp_cmd("Network.enable", {})
        await asyncio.sleep(20)  # Allow time for requests to be captured

        # Fetch network logs
        logs = driver.get_log("performance")
        request_id = None

        for entry in logs:
            log = json.loads(entry["message"])

            # Capture responses for daily-bonus
            if log["message"]["method"] == "Network.responseReceived":
                response = log["message"]["params"]["response"]
                url = response.get("url", "")
                status = response.get("status", "")

                if "daily-bonus" in url and status == 200:
                    request_id = log["message"]["params"]["requestId"]
                    break

        if not request_id:
            await channel.send("Failed to capture the daily-bonus request ID. Retrying...")
            return

        # Wait briefly to ensure the response body is available
        await asyncio.sleep(10)

        # Retrieve and process the response body
        try:
            response_body = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": request_id})
            response_json = json.loads(response_body.get("body", "{}"))

            # Extract the `timeUntilNextBonusMS` value
            time_until_next_bonus_ms = response_json.get("data", {}).get("data", {}).get("timeUntilNextBonusMS")
            if time_until_next_bonus_ms is not None:
                # Convert milliseconds to HH:MM:SS format
                time_until_next_bonus = str(timedelta(milliseconds=time_until_next_bonus_ms)).split(".")[0]
                await channel.send(f"Next Crown Coins Bonus Available in: {time_until_next_bonus}")
            else:
                await channel.send("Key 'timeUntilNextBonusMS' not found in response.")
        except Exception as e:
            await channel.send(f"Failed to retrieve Daily-Bonus response body: {e}")
    except Exception as e:
        await channel.send(f"An error occurred while retrieving the countdown: {e}")


# Function to claim the daily bonus
async def claim_crown_bonus(driver, bot, ctx, channel):
    try:
        day1_btn_xpath = "/html/body/div[2]/div[5]/div[2]/div/div[3]/div"
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, day1_btn_xpath))).click()
        await asyncio.sleep(2)
        await channel.send("Crown Coins Daily Bonus Claimed!")
        return True
    except:
        try:
            day7_btn_xpath = "/html/body/div[2]/div[5]/div[2]/div/div[3]/div[7]"
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, day7_btn_xpath))).click()
            await asyncio.sleep(2)
            await channel.send("Crown Coins Daily Bonus Claimed!")
            return True
        except:
            print("Failed to click bonus buttons.")
            return False

# Main function for CrownCoinsCasino bonus claiming
async def crowncoins_casino(driver, bot, ctx, channel):
    try:
        # Navigate to the website
        driver.get("https://crowncoinscasino.com/")
        await asyncio.sleep(10)  # Wait for page to load

        # Attempt to claim the daily bonus
        bonus_claimed = await claim_crown_bonus(driver, bot, ctx, channel)

        # If bonus cannot be claimed, get the countdown timer
        if not bonus_claimed:
            await get_countdown(driver, bot, ctx, channel)
    except Exception as e:
        await channel.send(f"An error occurred: {e}")
