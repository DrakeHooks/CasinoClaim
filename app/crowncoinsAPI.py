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
# Function to close popups on Crown Coins Casino
def ccc_close_popups(driver):
    popup_xpaths = [
        "/html/body/div[2]/div[5]/div/div/div/div[1]/div[2]",
        "/html/body/div[2]/div[5]/div/div/div/div[1]/div",
        "/html/body/div[2]/div[5]/div/div/div/div[2]/div/div[2]/button/div",
        "/html/body/div[4]/div/div[1]/div/div/button",
        "/html/body/div[3]/div/div[1]/div/div/button",
        "/html/body/div[5]/div/div/div[2]/button[2]",
        "/html/body/div[2]/div[4]/div/div/div/div[2]/div"
    ]

    for xpath in popup_xpaths:
        try:
            WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, xpath))).click()
            print(f"Closed popup with XPath: {xpath}")
        except TimeoutException:
            pass  # Popup not found or already closed, continue with next one

    # General popup close logic if "CLOSE" is detected
    try:
        close_buttons = WebDriverWait(driver, 3).until(
            EC.presence_of_all_elements_located((By.XPATH, "//button[contains(text(), 'CLOSE')]"))
        )
        for close_button in close_buttons:
            close_button.click()
            print("Closed popup using 'CLOSE' button.")
    except TimeoutException:
        print("No 'CLOSE' button found.")


# Main function for CrownCoinsCasino bonus claiming
async def crowncoins_casino(ctx, driver, channel):
    try:
        driver.get("https://crowncoinscasino.com/")
        await asyncio.sleep(10)
        # Close popups if present
        try:
            ccc_close_popups(driver)
        except Exception as e:
            print(f"Unable to close popups: {e}")

        # Navigate to rewards page
        try:
            hamburger_btn_xpath = "/html/body/div[2]/div[1]/div[1]/div[2]/button"
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, hamburger_btn_xpath))).click()
            await asyncio.sleep(2)

            rewards_btn_xpath = "/html/body/div[2]/div[3]/div[2]/div/ul[2]/li[2]/button"
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, rewards_btn_xpath))).click()
            await asyncio.sleep(2)

            view_btn_xpath = "//button[contains(@class, 'button--main') and contains(@class, 'rewards__card_button')]"
            WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.XPATH, view_btn_xpath))).click()
        except Exception as e:
            await channel.send(f"Unable to navigate to Rewards page: {e}")
            return

        await asyncio.sleep(5)

        # Check for countdown or available bonus
        try:
            countdown_element = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "/html/body/div[2]/div[5]/div[2]/div/div[4]"))
            )
            countdown_value = countdown_element.text.strip()

            # Check if the countdown says "TAP TO COLLECT YOUR DAILY BONUS"
            if "TAP TO COLLECT YOUR DAILY BONUS" in countdown_value.upper():
                print("Bonus is available. Attempting to claim the bonus...")
                await claim_bonus(driver, channel)
            elif "NEXT IN:" in countdown_value.upper():
                # Strip the "NEXT IN:" part and format the time
                time_remaining = countdown_value.replace("NEXT IN:", "").strip()
                await channel.send(f"Next CrownCoins Bonus Available in: {time_remaining}")
            else:
                await channel.send(f"Next CrownCoins Bonus Available: {countdown_value}")
        except TimeoutException:
            await channel.send("Unable to find CrownCoins countdown.")

    except Exception as e:
        print(f"An error occurred in the CrownCoinsCasino function: {e}")


# Function to claim the bonus on CrownCoinsCasino
async def claim_bonus(driver, channel):
    try:
        day1_btn_xpath = "/html/body/div[2]/div[5]/div[2]/div/div[3]/div"
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, day1_btn_xpath))).click()
        await asyncio.sleep(2)
        print("CrownCoinsCasino Day 1 Bonus Claimed!")
        await channel.send("CrownCoinsCasino Daily Bonus Claimed!")
    except TimeoutException:
        try:
            day7_btn_xpath = "/html/body/div[2]/div[5]/div[2]/div/div[3]/div[7]"
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, day7_btn_xpath))).click()
            await asyncio.sleep(2)
            print("CrownCoinsCasino Day 7 Bonus Claimed!")
            await channel.send("CrownCoinsCasino Daily Bonus Claimed!")
        except TimeoutException:
            print("Failed to click bonus buttons.")
