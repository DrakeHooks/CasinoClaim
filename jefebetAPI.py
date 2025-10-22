# Drake Hooks + WaterTrooper
# Casino Claim 2
# JefeBet API

import re
import os
import asyncio
import discord
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Load environment variables from the .env file
load_dotenv()


async def check_and_close_popup(driver):
    """If the blocking popup is visible, close it."""
    popup_xpath = "/html/body/div[2]/div/div[2]/div[4]/a[2]"
    try:
        popup_close = WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((By.XPATH, popup_xpath))
        )
        popup_close.click()
        print("[JefeBet] Popup closed automatically.")
        await asyncio.sleep(1)
    except TimeoutException:
        pass  # popup not present, continue normally


# Function to log in and claim JefeBet bonus
async def jefebet_casino(ctx, driver, channel):
    try:
        jefebet_credentials = os.getenv("JEFEBET")
        if not jefebet_credentials:
            await channel.send("JefeBet credentials not found in environment variables.")
            return

        username, password = jefebet_credentials.split(":")

        driver.get("https://www.jefebet.com/")
        await asyncio.sleep(10)
        await check_and_close_popup(driver)

        login_button = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable(
                (By.XPATH, "/html/body/app-root/app-main-header/div/div/div/div/header/div[2]/div/button[2]")
            )
        )
        login_button.click()
        await asyncio.sleep(5)
        await check_and_close_popup(driver)

        email_input = WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.ID, "email")))
        password_input = driver.find_element(By.ID, "password")
        email_input.send_keys(username)
        password_input.send_keys(password)
        password_input.send_keys(Keys.ENTER)
        print("Logging into JefeBet…")
        await asyncio.sleep(20)

        await check_and_close_popup(driver)
        await claim_jefebet_bonus(ctx, driver, channel)

    except TimeoutException as e:
        await channel.send("JefeBet Authentication timed out, will try again later.")
        print(f"[JefeBet] Login timeout: {e}")
    except Exception as e:
        print(f"[JefeBet] Error during login: {e}")
        await channel.send("Login to JefeBet failed.")


# Function to claim the 6-hour bonus
async def claim_jefebet_bonus(ctx, driver, channel):
    try:
        await check_and_close_popup(driver)
        if "lobby" in driver.current_url:
            print("[JefeBet] Authenticated into lobby successfully!")
        await asyncio.sleep(5)

        # Click “Get Coins” button
        get_coins = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, "/html/body/app-root/app-main-header/div/div/div/div/header/div[1]/nav/div[2]/div/div[2]/nav/div/div[3]/button")
            )
        )
        get_coins.click()
        await asyncio.sleep(5)
        await check_and_close_popup(driver)

        # Click “Daily Bonus” tab
        daily_bonus = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="daily-bonus-tab"]'))
        )
        daily_bonus.click()
        await asyncio.sleep(5)
        await check_and_close_popup(driver)

        # Click “Claim” button
        claim_button = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'btn') and contains(@class, 'btn-red')]"))
        )
        claim_button.click()
        await channel.send("JefeBet 6-Hour Bonus Claimed!")

    except Exception as e:
        print(f"[JefeBet] Error during claim: {e}")
    finally:
        await asyncio.sleep(5)
        await check_and_close_popup(driver)
        print("[JefeBet] Checking for countdown element.")

        countdown_xpaths = [
            "/html/body/app-root/app-get-coin/div/div[2]/div/app-hourly-bonus/div/div/div[3]/div/label",
            "/html/body/div[1]/div[2]/div/mat-dialog-container/div/div/app-get-coin/div/div[2]/div/app-hourly-bonus/div/div/div[3]/div/label",
            "/html/body/div[2]/div[2]/div/mat-dialog-container/div/div/app-get-coin/div/div[2]/div/app-hourly-bonus/div/div/div[3]/div/label",
            "/html/body/div[3]/div[2]/div/mat-dialog-container/div/div/app-get-coin/div/div[2]/div/app-hourly-bonus/div/div/div[5]/div/label",
        ]

        countdown_element = None
        for xpath in countdown_xpaths:
            try:
                countdown_element = WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
                if countdown_element:
                    break
            except:
                continue

        if countdown_element:
            countdown_value = countdown_element.text.strip()
            countdown_value = countdown_value.replace(" ", ":")
            time_parts = countdown_value.split(":")
            while len(time_parts) < 3:
                time_parts.insert(0, "00")
            formatted = ":".join(time_parts)
            await channel.send(f"Next JefeBet Bonus Available in: {formatted}")
        else:
            print("[JefeBet] Countdown element not found.")
