# Drake Hooks
# Casino Claim
# Global Poker API



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

# Helper function to retrieve the countdown element
def get_countdown_element(driver):
    try:
        letters = "abcdefghijklmnopqrstuvwxyz"
        classes = [f"{char * 6}_e" for char in letters]
        xpath = "//span[" + " or ".join(f"contains(@class, '{cls}')" for cls in classes) + "]"
        
        countdown_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        return countdown_element
    except TimeoutException:
        return None



# Function to log in to Global Poker, handling the case where the session is already active
async def login_to_global_poker(driver, channel):
    try:
        driver.get("https://play.globalpoker.com/")
        await asyncio.sleep(5)
        
        # Check if login page is present by looking for the username field
        try:
            username_field = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "/html/body/main/div/div[2]/form/div/div/div/div/div[2]/div[2]/span/div/div/div/div/div/div/div/div/div[2]/div[3]/div[1]/div/input"))
            )
            # If found, proceed with login
            creds = os.getenv("GLOBAL_POKER")
            if not creds:
                await channel.send("GLOBAL_POKER credentials not found in environment variables.")
                return False
            username, password = creds.split(":")
            
            password_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "/html/body/main/div/div[2]/form/div/div/div/div/div[2]/div[2]/span/div/div/div/div/div/div/div/div/div[2]/div[3]/div[2]/div/div/input"))
            )

            # Input the username and password
            username_field.send_keys(username)
            password_field.send_keys(password)
            await asyncio.sleep(2)

            # Click the login button
            login_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.NAME, "submit"))
            )
            login_button.click()
            
            await asyncio.sleep(5)  # Give it some time to log in
            print("Logged in to Global Poker successfully!")
        except TimeoutException:
            # If username field is not found, we assume the user is already logged in
            print("Already logged in to Global Poker.")
        
    except TimeoutException:
        await channel.send("Login to Global Poker failed. Please check the XPATHs or credentials.")
        return False

    return True

# Function to claim Global Poker bonus after clicking "Get Coins" button
async def claim_global_poker_bonus(ctx, driver, channel):
    try:
        # List of possible claim button XPaths
        button_xpaths = [
            "/html/body/div[8]/div/div/div[2]/div[2]/div[2]/div/div[2]/div[2]/div[1]",
            "/html/body/div[8]/div/div/div[2]/div[2]/div[2]/div/div[2]/div[2]/div[2]",
            "/html/body/div[8]/div/div/div[2]/div[2]/div[2]/div/div[2]/div[2]/div[3]",
            "/html/body/div[8]/div/div/div[2]/div[2]/div[2]/div/div[2]/div[2]/div[4]",
            "/html/body/div[8]/div/div/div[2]/div[2]/div[2]/div/div[2]/div[2]/div[5]",
            "/html/body/div[8]/div/div/div[2]/div[2]/div[2]/div/div[2]/div[2]/div[6]",
            "/html/body/div[8]/div/div/div[2]/div[2]/div[2]/div/div[2]/div[2]/div[7]"
        ]

        # Loop through the possible claim buttons and attempt to click each one
        bonus_claimed = False
        for button_xpath in button_xpaths:
            try:
                # Wait for the claim button to become clickable
                claim_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, button_xpath))
                )
                claim_button.click()  # Click the button to claim the bonus
                bonus_claimed = True
                print(f"Clicked bonus button: {button_xpath}")
                await asyncio.sleep(2)
            except TimeoutException:
                print(f"Bonus button not found: {button_xpath}")
                continue  # If the current button is not found, move to the next

        if bonus_claimed:
            await channel.send("Global Poker Daily Bonus Claimed!")
        else:
            await channel.send("(Global Poker) No bonus was claimed. All buttons were attempted, but none were clickable.")
            
    except Exception as e:
        await channel.send(f"Error claiming Global Poker bonus: {str(e)}")

# Function to click the "Get Coins" button before claiming the bonus
async def click_get_coins_button(driver, channel):
    try:
        first_button_xpath = "/html/body/div[2]/div/div[1]/div/div[4]/button"
        first_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, first_button_xpath))
        )
        first_button.click()
        print("GlobalPoker.com 'Get Coins' button clicked!")
        await asyncio.sleep(3)  # Wait for any UI transitions

    except TimeoutException:
        await channel.send("Get Coins button not found! Check TOS or button XPATHS!")

# Main function to check the countdown first, then claim the bonus if not found
async def global_poker(ctx, driver, channel):
    # First, attempt login or check if already logged in
    logged_in = await login_to_global_poker(driver, channel)
    if not logged_in:
        return

    # After login, click "Get Coins" button to proceed
    await click_get_coins_button(driver, channel)

    # After clicking "Get Coins", check if a countdown exists
    countdown_element = get_countdown_element(driver)
    if countdown_element:
        countdown_value = countdown_element.text
        await channel.send(f"Next Global Poker Bonus Available in: {countdown_value}")
    else:
        # If countdown is not found, proceed to claim the bonus
        await claim_global_poker_bonus(ctx, driver, channel)
