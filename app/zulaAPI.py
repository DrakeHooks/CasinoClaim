import os
import asyncio
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

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

# Main function for Zula bonus claiming
async def zula_casino(ctx, driver, channel):
    driver.get("https://www.zulacasino.com")
    
    # Click the login button
    login_button_xpath = "/html/body/div[1]/div[2]/div[1]/div/div/div/button"
    login_button = WebDriverWait(driver, 90).until(EC.element_to_be_clickable((By.XPATH, login_button_xpath)))
    login_button.click()
    
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
        # Wait for the page to load after login
        await asyncio.sleep(10)
        # Close any popups
        close_popups_zula(driver)
        close_popups_zula(driver)

        # Click the "Free Coins" button
        free_coins_btn_xpath = "/html/body/div[1]/div[2]/div[1]/div/nav/div[2]/button[1]"
        free_coins_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, free_coins_btn_xpath))
        )
        free_coins_btn.click()
    
    except:
        await channel.send(f"Unable to login to Zula! ")
        driver.save_screenshot("zula_login_error.png")
        return
    
    # Claim the bonus
    try:
        #Wait for the <h2> element with text "DAILY BONUS"
        dailyBonusHeader = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//h2[text()='DAILY BONUS']"))
            )
        print("DAILY BONUS found, proceeding to click the collect button.")
            
        collect_btn_xpath = "/html/body/div[4]/div/div[1]/div/div/div[2]/div[1]/div[2]/div[1]/div/button"
        collect_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, collect_btn_xpath))
        )
        collect_btn.click()
        await channel.send("Zula Daily Bonus Claimed!")
    except TimeoutException:
        await channel.send("Zula Daily Bonus unavailable.")
