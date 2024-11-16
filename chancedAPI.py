import re
import os
import asyncio
from dotenv import load_dotenv  # Import load_dotenv to load environment variables
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Load environment variables from the .env file
load_dotenv()

# Function to log out and then log back in
async def logout_and_login(ctx, driver, channel, credentials):
    try:

        # Get the URL and allow page to load
        driver.get("https://chanced.com/")
        await asyncio.sleep(5)
        # Click the menu button to open the dropdown
        menu_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "headlessui-menu-button-8"))
        )
        menu_button.click()
        
        # Click the logout button
        logout_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Logout')]"))
        )
        logout_button.click()
        
        await asyncio.sleep(5)  # Wait for the logout process to complete
        
        print("Logged out of Chanced.com, attempting to log back in...")

        # Now perform the login again
        await chanced_casino(ctx, driver, channel, credentials)
    
    except TimeoutException as e:
        print(f"Timeout while logging out: {e}")
        await channel.send("Failed to log out or find the logout button. You may need to run !chanced command if this is the first run.")
    except Exception as e:
        print(f"Error in logout_and_login: {e}")
        await channel.send(f"Error during logout and login: {e}")




# Function to log in and claim Chanced bonus
async def chanced_casino(ctx, driver, channel, credentials):
    try:
        # driver.quit()
        await asyncio.sleep(5)
        # Get the URL and allow page to load
        driver.get("https://chanced.com/")
        await asyncio.sleep(5)
        # Check for the login button
        try:
            login_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CLASS_NAME, "header-btn.btn-login"))
            )
            login_button_present = True
        except TimeoutException:
            login_button_present = False

        # Handle the login logic
        if login_button_present:
            # Use passed credentials or fallback to environment variables if not provided
            if credentials:
                username, password = credentials
            else:
                username = os.getenv("CHANCED_USERNAME")
                password = os.getenv("CHANCED_PASSWORD")
            
            if username and password:
                # Notify about logging in
                print("Logging into Chanced.com with provided credentials...")

                login_button.click()
                email_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "email-address"))
                )
                email_input.send_keys(username)
                password_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "email-password"))
                )
                password_input.send_keys(password)
                password_input.send_keys(Keys.ENTER)
                await asyncio.sleep(5)  # Wait for login process to complete
                await channel.send("Logged into Chanced.com.")
            else:
                print("No credentials found. Attempting saved session in Chrome user data.")
        else:
            print("Login button not found. Assuming login is saved in the browser session.")

        # Now proceed with claiming the bonus
        await claim_chanced_bonus(ctx, driver, channel)

    except TimeoutException as e:
        print(f"Login timeout: {e}")
        await channel.send("Login to Chanced.com failed or no credentials provided.")
    except Exception as e:
        print(f"Error in chanced_casino: {e}")
        

# Function to claim the hourly bonus
async def claim_chanced_bonus(ctx, driver, channel):
    try:
        # Navigate to the wallet and hourly bonus
        walletBtn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div[2]/div[4]/header/div/div/div[1]/div/button"))
        )
        walletBtn.click()

        dailyBonusBtn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[7]/div/div/div/div/div/div[2]/div[2]/ul/li[3]/button"))
        )
        dailyBonusBtn.click()
        print("Navigated to Chanced.com Daily Bonus page.")
        await asyncio.sleep(5)
        # Check for the claim button and click it if available
        for div_index in [6, 7]:
            try:
                first_button_xpath = f"/html/body/div[{div_index}]/div/div/div/div/div/div[2]/div[3]/section/div/div/div/form/div[7]/button"
                first_button = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, first_button_xpath))
                )
                # If the button text contains "Claim Hourly Bonus", click it
                if "Claim Daily Bonus" in first_button.text:
                    first_button.click()
                    second_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "/html/body/div[8]/div/div[6]/button[1]"))
                    )
                    second_button.click()
                    break  # Exit the loop if successful
            except Exception as e:
                print(f"Error with div[{div_index}]: {str(e)}")
                continue
            await asyncio.sleep(2)
        yes_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[8]/div/div[6]/button[1]"))
        )
        yes_button.click()
        await asyncio.sleep(1)

        await channel.send("Chanced.com Daily Bonus Claimed!")
    except TimeoutException as e:
        print(f"Error claiming bonus: {e}")
        print("Chanced.com Bonus is unavailable right now.")
    # After the bonus is claimed or unavailable, proceed to check the countdown
    await check_chanced_countdown(ctx, driver, channel)
# Function to check the countdown timer for the next bonus
async def check_chanced_countdown(ctx, driver, channel):
    try:
        # Check both div[6] and div[7] for the countdown elements
        for div_index in [6, 7]:
            try:
                hours_xpath = f"/html/body/div[{div_index}]/div/div/div/div/div/div[2]/div[3]/section/div/div/div/form/div[5]/div[1]"
                minutes_xpath = f"/html/body/div[{div_index}]/div/div/div/div/div/div[2]/div[3]/section/div/div/div/form/div[5]/div[2]"
                seconds_xpath = f"/html/body/div[{div_index}]/div/div/div/div/div/div[2]/div[3]/section/div/div/div/form/div[5]/div[3]"

                hours_element = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.XPATH, hours_xpath)))
                minutes_element = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.XPATH, minutes_xpath)))
                seconds_element = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.XPATH, seconds_xpath)))

                hours = re.sub(r'\D', '', hours_element.text).zfill(2)
                minutes = re.sub(r'\D', '', minutes_element.text).zfill(2)
                seconds = re.sub(r'\D', '', seconds_element.text).zfill(2)

                countdown_message = f"Next Chanced Bonus Available in: {hours}:{minutes}:{seconds}"
                await channel.send(countdown_message)
                return  # If countdown is successfully retrieved, exit the loop

            except TimeoutException:
                continue  # Try the next div_index if elements are not found

    except Exception as e:
        print(f"Error checking countdown: {e}")
        await channel.send(f"Error checking countdown: {str(e)}")
