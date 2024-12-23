import os
import datetime
import asyncio
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# LuckyBird credentials from the .env file
try:
    luckybird_credentials = os.getenv("LUCKYBIRD").split(":")
    username_text = luckybird_credentials[0]
    password_text = luckybird_credentials[1]
except:
    print("LuckyBird credentials not found in environment variables.")
    
# Function to extract countdown information
async def extract_countdown_info(channel, driver):
    try:
        # Locate the countdown element
        countdown_element = WebDriverWait(driver, 90).until(
            EC.presence_of_element_located(
                (By.XPATH, "/html/body/section/div[2]/div[2]/div[2]/div[2]/div/div[3]/p[1]")
            )
        )
        countdown_value = countdown_element.text.strip("Next claim available at")
        next_bonus_time = datetime.datetime.strptime(countdown_value, '%Y/%m/%d %I:%M %p')
        time_difference = next_bonus_time - datetime.datetime.now()

        # Calculate days, hours, minutes, and seconds
        days = time_difference.days
        hours, remainder = divmod(time_difference.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        # Format the countdown message
        if days == 0:
            formatted_time = f"Next LuckyBird Bonus Available in: {hours:02}:{minutes:02}:{seconds:02}"
        else:
            formatted_time = f"Next LuckyBird Bonus Available in: {days} days, {hours:02}:{minutes:02}:{seconds:02}"

        await channel.send(formatted_time)
    except Exception as e:
        await channel.send("Failed to extract countdown timer.")

# Main function to handle LuckyBird
async def LuckyBird(ctx, driver, bot):
    channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL")))
    if ctx is not None:
        channel = bot.get_channel(int(ctx.channel.id))

    driver.get("https://luckybird.io/")
    await asyncio.sleep(5)
    
    try:
        # Step 1: Click the buttons to get to the countdown element
        buyButton = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div[1]/div/section/section/header/div/div/ul[1]/li[2]/p"))
        )
        buyButton.click()

        dailyBonusBtn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/section/div[2]/div[2]/div[2]/div[1]/div/div/div/div[5]"))
        )
        dailyBonusBtn.click()
        print("LuckyBird Daily Bonus Button found and clicked!")
        
        claimBtn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/section/div[2]/div[2]/div[2]/div[2]/div/div[2]/button[1]"))
        )
        claimBtn.click()
        await channel.send("LuckyBird Daily Bonus Claimed!")
        return  # End the function if the bonus was successfully claimed
    except TimeoutException:
        print("LuckyBird Bonus Unavailable or login required.")
    
    try:
        # Step 2: Check if login is required
        loginButton = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "tab-login"))
        )
        if loginButton:
            loginButton.click()

            # Enter email
            emailField = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div/div[1]/div/div/div[1]/div/div[1]/div/div[2]/div[2]/div/form[2]/div[1]/div/div[1]/input"))
            )
            emailField.send_keys(username_text)

            # Enter password
            passwordField = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div/div[1]/div/div/div[1]/div/div[1]/div/div[2]/div[2]/div/form[2]/div[2]/div/div/input"))
            )
            passwordField.send_keys(password_text)
            passwordField.send_keys(Keys.ENTER)

        await asyncio.sleep(10)
        # Check if 2FA is required
        try:
            twoFA_button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "/html/body/section/div[1]/div/button"))
            )
            if twoFA_button:
                await channel.send("Waiting for 2FA code...")

                # Wait for the 2FA code from Discord
                while bot.two_fa_code is None:
                    await asyncio.sleep(1)

                # Enter the 2FA code
                twoFA_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "/html/body/section/div[1]/div/div/input"))
                )
                twoFA_input.send_keys(bot.two_fa_code)
                twoFA_input.send_keys(Keys.ENTER)

                await channel.send("LuckyBird authenticated successfully!")
        except TimeoutException:
            print("No 2FA required. Proceeding.")
    except Exception as e:
        print(f"LuckyBird Login flow failed: {str(e)}")
    finally:
        # Step 4: Try to extract the countdown in the finally block
        await extract_countdown_info(channel, driver)

