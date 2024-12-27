# Drake Hooks
# Casino Claim
# Modo API


import os
import asyncio
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Load environment variables from the .env file
load_dotenv()

# Function to authenticate into modo
async def authenticate_modo(driver, bot, ctx, channel):
    try:
        channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL")))

        web = "https://login.modo.us/login"
        driver.get(web)
        await asyncio.sleep(10)
        try:
        # Wait for email and password fields, enter credentials from environment variables
            email_field = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/main/div/div[2]/form/div/div/div/div/div[2]/div[2]/span/div/div/div/div/div/div/div/div/div[2]/div[3]/div[1]/div/input"))
            )
            email_field.send_keys(os.getenv("MODO").split(":")[0])

            password_field = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/main/div/div[2]/form/div/div/div/div/div[2]/div[2]/span/div/div/div/div/div/div/div/div/div[2]/div[3]/div[2]/div/div/input"))
            )
            password_field.send_keys(os.getenv("MODO").split(":")[1])
        
            await asyncio.sleep(120)

        except:
            await channel.send("Unable to auth Modo!")
            return False

        try:
        # Click login button
            login_btn = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/main/div/div[2]/form/div/div/div/button"))
            )
            login_btn.click()
            await asyncio.sleep(10)
        except:
            await channel.send("Unable to solve Modo captcha!")
            return False
        await asyncio.sleep(10)
        driver.refresh()
        # Check if login was successful
        if driver.current_url == "https://modo.us/lobby":
            await channel.send("Authenticated into modo successfully!")
            return True
        else:
            await channel.send("Authentication failed. Did not reach the lobby.")
            return False
    except TimeoutException:
        await channel.send("Authentication timeout. Please check your credentials or XPaths.")
        return False


# Function to claim modo daily bonus
async def claim_modo_bonus(driver, bot, ctx, channel):
    try:
        channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL")))

        driver.get("https://modo.us/lobby/")
        await asyncio.sleep(10)

        # Try multiple possible XPaths for the claim button
        xpaths = [
            "/html/body/div[4]/div[3]/div/div[3]/button",
            "/html/body/div[5]/div[3]/div/div[3]/button",
            "/html/body/div[6]/div[3]/div/div[3]/button",
            "/html/body/div[7]/div[3]/div/div[3]/button"
        ]

        button_found = False
        for xpath in xpaths:
            try:
                claim_button = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                claim_button.click()
                await channel.send("Modo Bonus Claimed!")
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



# Function to check the countdown for the next bonus
async def check_modo_countdown(driver, bot, ctx, channel):
    try:
        channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL")))

        driver.get("https://modo.us/lobby/")
        await asyncio.sleep(10)

        # Wait for countdown timer element using its class
        countdown_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//p[contains(@class, 'MuiTypography-root') and contains(@class, 'MuiTypography-body1') and contains(@class, 'css-1ttdl7e')]"))
        )

        # Extract countdown time text
        countdown_time = countdown_element.text

        # Send countdown message
        countdown_message = f"Next Modo Bonus Available in: {countdown_time}"
        await channel.send(countdown_message)

    except TimeoutException:
        await channel.send("Failed to retrieve Modo countdown timer.")
        return False

    return True


# Main function to handle modo
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
