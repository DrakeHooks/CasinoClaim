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

# Create a table to store claimed timestamps
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
        # Parse the timestamp string into a datetime object without microseconds
        try:
            return datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S.%f')  # Handles microseconds
        except ValueError:
            return datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')  # Handles without microseconds
    return None  # Return None if no record is found


# Function to update the claimed time in the database
def update_claimed_time(casino_name):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Ensure proper formatting without microseconds
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

# Close popups logic for Zula Casino
def close_popups_zula(driver):
    popup_xpaths_zula = [
        "/html/body/div[4]/div/div[1]/div/div/button",  
        "/html/body/div[4]/div/div/div[2]/button[4]",
        "/html/body/div[4]/div[4]/div/div/div/div[1]/div"
    ]
    
    for xpath in popup_xpaths_zula:
        try:
            popup_close_button = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            popup_close_button.click()
            print(f"Closed popup with XPath: {xpath}")
        except TimeoutException:
            pass  # If the popup is not found, continue to the next one
    
    # General popup close logic for any "CLOSE" button
    try:
        close_buttons = WebDriverWait(driver, 5).until(
            EC.presence_of_all_elements_located((By.XPATH, "//button[contains(text(), 'close')]"))
        )
        for close_button in close_buttons:
            close_button.click()
            print("Closed popup using 'CLOSE' button.")
    except TimeoutException:
        print("No 'CLOSE' button found.")

async def zula_casino(ctx, driver, channel):
    casino_name = "Zula Casino"

    driver.get("https://www.zulacasino.com/login")
    await asyncio.sleep(5)
    
    try:
        # Time to wait for the page to fully load before entering username and password
        await asyncio.sleep(5)
        # Retrieve credentials from .env
        credentials = os.getenv("ZULA").split(":")
        username_text = credentials[0]
        password_text = credentials[1]

        # Find and fill the username field
        WebDriverWait(driver, 90).until(EC.presence_of_element_located((By.ID, "emailAddress")))
        username_field = driver.find_element(By.ID, "emailAddress")
        for char in username_text:
            username_field.send_keys(char)
            await asyncio.sleep(0.3)  # Simulate typing speed

        # Find and fill the password field
        WebDriverWait(driver, 90).until(EC.presence_of_element_located((By.ID, "password")))
        password_field = driver.find_element(By.ID, "password")
        for char in password_text:
            password_field.send_keys(char)
            await asyncio.sleep(0.3)  # Simulate typing speed
        password_field.send_keys(Keys.ENTER)
        await asyncio.sleep(10)
        close_popups_zula(driver)
        close_popups_zula(driver)
    except TimeoutException:
        await channel.send("Login failed. Unable to find login fields.")
        return
    
    # Check if we are logged in and proceed with bonus claiming
    free_coins_btn_xpath = "/html/body/div[1]/div[2]/div[1]/div/nav/div[2]/button[1]"
    free_coins_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, free_coins_btn_xpath)))
    free_coins_btn.click()
        # Claim the bonus
    try:
            daily_bonus_header = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//h2[text()='DAILY BONUS']"))
            )
            collect_btn_xpath = "/html/body/div[4]/div/div[1]/div/div/div[2]/div[1]/div[2]/div[1]/div/button"
            print("DAILY BONUS found, proceeding to click the collect button.")
            collect_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, collect_btn_xpath)))
            collect_btn.click()
            
            # Update the timestamp in the database after claiming
            update_claimed_time(casino_name)
            await channel.send("Zula Daily Bonus Claimed!")
    except:
            # Bonus not available, so calculate countdown or show default
            last_claimed = get_last_claimed(casino_name)
            countdown = get_countdown(last_claimed, interval_hours=24)  # Default 24 hours
            await channel.send(f"Next Zula Bonus Available in: {countdown}")

