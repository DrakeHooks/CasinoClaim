# Drake Hooks
# Casino Claim
# Chumba API



import os
import asyncio
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import re

# Function to authenticate into Chumba Casino
async def authenticate_chumba(driver, bot, channel):
    try:
        # Load environment variables for login
        creds = os.getenv("CHUMBA")
        if not creds:
            await channel.send("CHUMBA credentials not found in environment variables.")
            return False
        username, password = creds.split(":")

        # Enter login details
        WebDriverWait(driver, 90).until(EC.presence_of_element_located((By.ID, "login_email-input")))
        driver.find_element(By.ID, "login_email-input").send_keys(username)
        WebDriverWait(driver, 90).until(EC.presence_of_element_located((By.ID, "login_password-input")))
        driver.find_element(By.ID, "login_password-input").send_keys(password)

        # Click the login button
        loginBtn = WebDriverWait(driver, 90).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div/div/div/div[2]/form/button"))
        )
        loginBtn.click()
        await asyncio.sleep(5)

        # Check if we are redirected to the lobby
        if driver.current_url.startswith("https://lobby.chumbacasino.com/"):
            print("Chumba Casino authenticated successfully!")
            return True

        # Handle 2FA input if required
        try:
            sendCodeBtn = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "send-code-button")))
            sendCodeBtn.click()
            await channel.send("Please provide the Chumba 2FA code sent to your email in this channel.")

            # Wait for the Chumba 2FA code from Discord
            while bot.chumba_2fa_code is None:
                await asyncio.sleep(1)

            # Enter the Chumba 2FA code
            for i, digit in enumerate(bot.chumba_2fa_code):
                input_field = driver.find_element(By.ID, f"otp-code-input-{i}")
                input_field.send_keys(digit)

            # Reset Chumba 2FA code after usage
            bot.chumba_2fa_code = None

            await channel.send("2FA code entered, completing the login process.")

            # Click the verify button
            verify_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div/div/div[2]/div/div/div[2]/form/button"))
            )
            verify_button.click()
            await asyncio.sleep(5)

            # Final check
            if driver.current_url.startswith("https://lobby.chumbacasino.com/"):
                await channel.send("Chumba Casino authenticated successfully!")
                return True
            else:
                await channel.send("Chumba authentication failed. Could not reach the lobby.")
                return False

        except TimeoutException:
            await channel.send("No 2FA required. Proceeding...")
            return True

    except Exception as e:
        await channel.send("Error during authentication")
        return False

# Function to claim Chumba Casino bonus
async def claim_chumba_bonus(driver, channel):
    try:
        getCoinsBtn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div/nav/div[1]/div/div[2]/button[1]"))
        )
        getCoinsBtn.click()

        # Try multiple xpaths for dailyBonusLabel (div[7], div[9], div[10])
        dailyBonus_xpaths = [
            "/html/body/div[7]/div/div/div/div[2]/div[1]/div/div[3]/label",
            "/html/body/div[9]/div/div/div/div[2]/div[1]/div/div[3]/label",
            "/html/body/div[10]/div/div/div/div[2]/div[1]/div/div[3]/label"
        ]
        dailyBonusLabel = None
        for xpath in dailyBonus_xpaths:
            try:
                dailyBonusLabel = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.XPATH, xpath)))
                dailyBonusLabel.click()
                break
            except TimeoutException:
                continue
        if not dailyBonusLabel:
            await channel.send("Daily bonus label not found.")
            return

        # Claim button xpaths (already includes multiple div indices)
        claim_button_xpaths = [
            "/html/body/div[9]/div/div/div/div[2]/div[2]/div/button",
            "/html/body/div[7]/div/div/div/div[2]/div[2]/div/button",
            "/html/body/div[10]/div/div/div/div[2]/div[2]/div/button"
        ]
        for xpath in claim_button_xpaths:
            try:
                claimBtn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, xpath)))
                claimBtn.click()
                await channel.send("Chumba Daily Bonus Claimed!")
                break
            except TimeoutException:
                continue
    except Exception as e:
        await channel.send("Error claiming Chumba bonus.")

# Function to check countdown timer for next bonus
async def check_chumba_countdown(driver, channel):
    try:
        # Try multiple xpaths for the countdown element (div[7], div[9], div[10])
        countdown_xpaths = [
            "/html/body/div[7]/div/div/div/div[2]/div[2]/div/div[3]/p",
            "/html/body/div[9]/div/div/div/div[2]/div[2]/div/div[3]/p",
            "/html/body/div[10]/div/div/div/div[2]/div[2]/div/div[3]/p"
        ]
        countdownElement = None
        for xpath in countdown_xpaths:
            try:
                countdownElement = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
                break
            except TimeoutException:
                continue
        if not countdownElement:
            await channel.send("Countdown element not found.")
            return

        countdownValue = countdownElement.text
        hours, minutes = map(int, re.findall(r'\d+', countdownValue)[:2])
        formatted_countdown = f"{hours:02}:{minutes:02}:00"
        await channel.send(f"Next Chumba Bonus Available in: {formatted_countdown}")
    except Exception as e:
        await channel.send("Failed to retrieve Chumba countdown.")

# Main function for Chumba Casino bonus claiming
async def chumba_casino(ctx, driver, bot):
    channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL")))
    if ctx is not None:
        channel = bot.get_channel(int(ctx.channel.id))

    driver.get("https://lobby.chumbacasino.com/")
    await asyncio.sleep(5)

    # Step 1: Check if we are on the login page and authenticate if necessary
    if driver.current_url.startswith("https://login.chumbacasino.com/"):
        authenticated = await authenticate_chumba(driver, bot, channel)

        if not authenticated:
            await channel.send("Chumba authentication failed.")
            return

    # Step 2: Proceed with claiming the bonus if authenticated
    if driver.current_url.startswith("https://lobby.chumbacasino.com/"):
        await claim_chumba_bonus(driver, channel)
        await check_chumba_countdown(driver, channel)
    else:
        await channel.send("Failed to reach the Chumba lobby.")
