# Drake Hooks
# Casino Claim
# Sportzino API




import os
import sqlite3
import asyncio
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables from the .env file
load_dotenv()

# Initialize SQLite connection
conn = sqlite3.connect('casino_bonus.db')
cursor = conn.cursor()

# Create a table to store claimed timestamps if it doesn't already exist
cursor.execute('''
CREATE TABLE IF NOT EXISTS bonus_claims (
    id INTEGER PRIMARY KEY,
    casino_name TEXT NOT NULL,
    last_claimed TIMESTAMP NOT NULL
)
''')
conn.commit()

# Function to get the last claimed time from the database
def get_last_claimed(casino_name):
    cursor.execute("SELECT last_claimed FROM bonus_claims WHERE casino_name = ?", (casino_name,))
    row = cursor.fetchone()
    if row:
        # Parse the timestamp string into a datetime object (with microseconds)
        return datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S.%f')
    return None  # Return None if no record is found

# Function to update the claimed time in the database
def update_claimed_time(casino_name):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Ensure proper formatting for database
    cursor.execute("INSERT OR REPLACE INTO bonus_claims (casino_name, last_claimed) VALUES (?, ?)", (casino_name, now))
    conn.commit()
    print(f"Updated claimed time for {casino_name} to {now}")

# Function to calculate the countdown for the next bonus
def get_countdown(last_claimed_time, interval_hours=24):
    if last_claimed_time is None:
        return "00:00:00"  # Default when there's no previous record

    now = datetime.now()
    next_claim_time = last_claimed_time + timedelta(hours=interval_hours)
    remaining_time = next_claim_time - now

    if remaining_time.total_seconds() > 0:
        # Format the remaining time into HH:MM:SS
        hours, remainder = divmod(int(remaining_time.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    
    return "00:00:00"  # Bonus is available now

# Close popups logic for Sportzino
def close_popups_sz(driver):
    popup_xpaths_sz = [
        "/html/body/div[3]/div/div[1]/div/div/div/div[1]/div[2]/button",
        "/html/body/div[3]/div/div[1]/div/div/button",
        "/html/body/div[1]/div[1]/div/div/div/div[2]/div[2]/button",
        "/html/body/div[4]/div/div[1]/div/div/button",
        "/html/body/div[1]/div[1]/div/div/div/div[2]/div[2]/button",
        "/html/body/div[5]/div/div[1]/div/div/button",
        "/html/body/div[4]/div/div[1]/div/div/div/div[2]/button",
        "/html/body/div[6]/div/div[1]/div/div/div/div[2]/button"
    ]

    retries = 3  # Retry a few times to ensure all popups are closed
    for _ in range(retries):
        for xpath in popup_xpaths_sz:
            try:
                popup_close_button = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                popup_close_button.click()
                print(f"Closed popup with XPath: {xpath}")
            except TimeoutException:
                pass  # Continue if the popup is not found

        # Check for common close buttons
        try:
            close_buttons = driver.find_elements(By.XPATH, "//button[contains(text(),'Close')]")
            for close_button in close_buttons:
                if close_button.is_displayed():
                    close_button.click()
                    print("Closed a popup using a general 'Close' button.")
                    
        except Exception as e:
            print(f"Error while closing popups using general 'Close' buttons: {e}")

# Main function for automating Sportzino
async def Sportzino(ctx, driver, channel):
    casino_name = "Sportzino"
    driver.get("https://sportzino.com/login?")
    await asyncio.sleep(5)

    try:
        # Login process
        await asyncio.sleep(5)
        WebDriverWait(driver, 90).until(EC.presence_of_element_located((By.ID, "emailAddress")))

        creds = os.getenv("SPORTZINO")
        if not creds:
            await channel.send("SPORTZINO credentials not found in environment variables.")
            return
        credentials = creds.split(":")
        username_text = credentials[0]
        password_text = credentials[1]

        # Input credentials
        username_field = driver.find_element(By.ID, "emailAddress")
        for char in username_text:
            username_field.send_keys(char)
            await asyncio.sleep(0.3)

        password_field = driver.find_element(By.ID, "password")
        for char in password_text:
            password_field.send_keys(char)
            await asyncio.sleep(0.3)
        
        password_field.send_keys(Keys.ENTER)
        await asyncio.sleep(10)
        close_popups_sz(driver)  # Close any pop-ups

        # Claim bonus
        free_coins_btn_xpath = "/html/body/div[1]/div/nav/div/div[4]/div[1]/button"
        free_coins_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, free_coins_btn_xpath)))
        free_coins_btn.click()

        # Click the collect button
        try:
            collect_btn_xpath = "/html/body/div[4]/div/div[1]/div/div/div[2]/div[2]/div[2]/div[1]/div/div[3]/div/div[1]/button"
            collect_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, collect_btn_xpath)))
            collect_btn.click()
            update_claimed_time(casino_name)  # Update claimed time in the DB
            await channel.send("Sportzino Daily Bonus Claimed!")
        except:
            print("Sportzino Bonus not available, checking countdown...")

        # Bonus not available, calculate countdown
        last_claimed = get_last_claimed(casino_name)
        countdown = get_countdown(last_claimed, interval_hours=24)
        await channel.send(f"Next Sportzino Bonus Available in: {countdown}")
        
    except Exception as e:
        print(f"Error during Sportzino automation: {e}")
