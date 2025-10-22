# Drake Hooks
# Casino Claim 2
# Rolling Riches API (Updated Flow)

import os
import re
import discord
import asyncio
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

load_dotenv()


async def rolling_riches_casino(ctx, driver, channel):
    """Login to Rolling Riches and claim the 6-hour bonus."""
    try:
        rolling_riches_credentials = os.getenv("ROLLING_RICHES")
        if not rolling_riches_credentials:
            await channel.send("Rolling Riches credentials not found in environment variables.")
            return

        username, password = rolling_riches_credentials.split(":")
        driver.get("https://rollingriches.com/login")
        await asyncio.sleep(5)

        # Try to find login inputs
        try:
            email_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            password_input = driver.find_element(By.ID, "password")
            email_input.send_keys(username)
            password_input.send_keys(password)
            password_input.send_keys(Keys.ENTER)
            await asyncio.sleep(10)
            print("Logging into Rolling Riches...")
        except:
            print("Already logged into Rolling Riches or login form not found.")

        # Proceed to claim
        await claim_rolling_riches_bonus(ctx, driver, channel)

    except Exception as e:
        print(f"[RollingRiches] Login error: {e}")
        await channel.send("Rolling Riches login failed.")
        screenshot_path = "rr_login_error.png"
        driver.save_screenshot(screenshot_path)
        await channel.send(file=discord.File(screenshot_path))
        os.remove(screenshot_path)


async def claim_rolling_riches_bonus(ctx, driver, channel):
    """Claim the bonus directly from the lobby flow."""
    try:
        # Ensure we're in the lobby
        await asyncio.sleep(5)

        # Step 1: Click the "bonus section" div
        section_xpath = "/html/body/div/div[3]/div/div[1]/div[2]/div[4]/div/div[5]/div[1]"
        section_div = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, section_xpath))
        )
        section_div.click()
        await asyncio.sleep(5)

        # Step 2: Click the "claim bonus" div
        claim_xpath = "/html/body/div/div[3]/div/div[1]/div[3]/div[3]/div[1]/div/div[3]/div/div/div[5]"
        try:
            claim_btn = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, claim_xpath))
            )
            claim_btn.click()
            await channel.send("Rolling Riches Daily Bonus claimed!")
        except TimeoutException:
            print("RR Bonus not available to claim right now.")
        finally:
        # Step 3: Read countdown value
            countdown_xpath = "/html/body/div/div[3]/div/div[1]/div[3]/div[3]/div[1]/div/div[3]/div/div/div[2]"
            countdown_element = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, countdown_xpath))
            )
            countdown_text = countdown_element.text.strip()

        # Parse "Available in 21:23:00"
            match = re.search(r"(\d{1,2}:\d{2}:\d{2})", countdown_text)
            formatted_time = match.group(1) if match else "Unknown"

            await channel.send(f"Next Rolling Riches bonus available in: `{formatted_time}`")

    except Exception as e:
        print(f"[RollingRiches] Error during claim flow: {e}")
        await channel.send("Error while claiming Rolling Riches bonus.")
        screenshot_path = "rr_claim_error.png"
        driver.save_screenshot(screenshot_path)
        await channel.send(file=discord.File(screenshot_path))
        os.remove(screenshot_path)
