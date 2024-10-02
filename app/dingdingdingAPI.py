import os
import asyncio
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Load environment variables from the .env file
load_dotenv()

# Global variable to track authentication status
authenticated = False

# Function to authenticate into DingDingDing
async def authenticate_dingdingding(driver, bot, ctx):
    global authenticated
    try:
        web = "https://www.dingdingding.com/login"
        driver.get(web)
        await asyncio.sleep(50)

        # Wait for email and password fields, enter credentials from environment variables
        email_field = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div/div/div[1]/div[1]/div/div/div[2]/form/input[1]"))
        )
        email_field.send_keys(os.getenv("DINGDINGDING").split(":")[0])

        password_field = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div/div/div[1]/div[1]/div/div/div[2]/form/input[2]"))
        )
        password_field.send_keys(os.getenv("DINGDINGDING").split(":")[1])
        
        await asyncio.sleep(3)

        # Click login button
        login_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div/div[1]/div[1]/div/div/div[2]/form/button[2]"))
        )
        login_btn.click()

        await asyncio.sleep(5)

        # Check if login was successful
        if driver.current_url == "https://dingdingding.com/lobby/":
            await ctx.send("Authenticated into DingDingDing successfully!")
            authenticated = True
        else:
            await ctx.send("Authentication failed. Did not reach the lobby.")
            authenticated = False

    except TimeoutException:
        authenticated = False
        await ctx.send("Authentication timeout. Please check your credentials or XPaths.")
        return False

    return True

# Function to claim DingDingDing daily bonus
async def claim_dingdingding_bonus(driver, ctx):
    try:
        # Click the bonus button in the lobby
        bonus_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#__nuxt > div > div:nth-child(1) > aside.sidenav > div.sidenav__cont > div > div.sidenav__actions > button.btn.btn--nav.btn--rewards > span.btn__label"))
        )
        bonus_button.click()
        print("DingDingDing Daily Bonus Button Found!")

        # Click the collect button
        collect_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div[1]/div[6]/div/div[2]/div/div/button[2]"))
        )
        collect_button.click()

        await ctx.send("DingDingDing Daily Bonus Claimed!")

    except TimeoutException:
        print("COLLECT button not found! Check XPATH of claim button!")
        return False

    return True

# Function to check the countdown for the next bonus
async def check_dingdingding_countdown(driver, ctx):
    try:
        # Retrieve countdown elements
        hours_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div/div[1]/div[6]/div/div[2]/div/div/div/span/div[1]/span"))
        )
        minutes_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div/div[1]/div[6]/div/div[2]/div/div/div/span/div[2]"))
        )
        seconds_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div/div[1]/div[6]/div/div[2]/div/div/div/span/div[3]"))
        )

        # Format countdown time
        countdown_message = f"Next DingDingDing Bonus Available in: {hours_element.text.zfill(2)}:{minutes_element.text.zfill(2)}:{seconds_element.text.zfill(2)}"
        await ctx.send(countdown_message)

    except TimeoutException:
        await ctx.send("Failed to retrieve DingDingDing countdown timer.")
        return False

    return True

# Main function to handle DingDingDing
async def dingdingding_casino(ctx, driver, bot):
    global authenticated

    # Get the Discord channel
    channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL")))

    # Check if the user is already authenticated, if not, authenticate first
    if not authenticated:
        await ctx.send("Authenticating into DingDingDing...")
        authenticated = await authenticate_dingdingding(driver, bot, ctx)

    # Proceed to claim the bonus if authenticated
    if authenticated:
        await claim_dingdingding_bonus(driver, ctx)
        await asyncio.sleep(5)

    # Check the countdown for the next available bonus
    await check_dingdingding_countdown(driver, ctx)
