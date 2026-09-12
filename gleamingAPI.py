# Drake Hooks + WaterTrooper
# Casino Claim 3
# Gleaming API
# Version 3.4
# Updated 2026.09.06

import re
import os
import asyncio
import discord
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException


# ───────────────────────────────────────────────────────────
# Config & Constants
# ───────────────────────────────────────────────────────────

load_dotenv()
GLEAMING_CRED = os.getenv("GLEAMING")  # format "username:password"

SITE_URL = "https://game.gleamingcasino.com"
LOGIN_URL = "https://game.gleamingcasino.com/login"
LOBBY_URL = "https://game.gleamingcasino.com/lobby"
PROMOTIONS_URL = "https://game.gleamingcasino.com/promotion"

LOGIN_BUTTON_XPATH = "//button[contains(@class, 'inline-flex shrink-0 items-center')]//span[@class='unknown']"
EMAIL_INPUT_XPATH = "//input[@data-testid='login-identifier-input']"
PASSWORD_INPUT_XPATH = "//input[@data-testid='login-password-input']"
LOGIN_SUBMIT_XPATH = "//button[@data-testid='login-submit-button']"

REWARD_BUTTON_XPATH = "//img[@alt='daily_bonus']"
CLAIM_BUTTON_XPATH = "//button[contains(@class, 'inline-flex shrink-0 items-center') and not(@disabled)]//span[text()='CLAIM YOUR BONUS!']"


# ───────────────────────────────────────────────────────────
# 0) Helpers
# ───────────────────────────────────────────────────────────

def _is_logged_in(driver) -> bool:
    """Detect if already logged in."""
    try:
        driver.find_element(By.XPATH, "//span[text()='My Profile']")
        return True
    except NoSuchElementException:
        pass
    try:
        driver.find_element(By.XPATH, "//span[text()='My Rewards']")
        return True
    except NoSuchElementException:
        return False


def _wait_clickable(driver, by, value, timeout=10):
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, value)))


def _wait_present(driver, by, value, timeout=10):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))


def _safe_click(driver, element, label="element") -> bool:
    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'center'});",
            element
        )
    except Exception:
        pass

    try:
        element.click()
        print(f"[Gleaming] Clicked {label}.")
        return True
    except Exception as e:
        print(f"[Gleaming] Normal click failed for {label}: {e}")

    try:
        driver.execute_script("arguments[0].click();", element)
        print(f"[Gleaming] JS clicked {label}.")
        return True
    except Exception as e:
        print(f"[Gleaming] JS click failed for {label}: {e}")

    return False


async def _send_screenshot(channel, driver, message, filename):
    try:
        driver.save_screenshot(filename)

        await channel.send(
            message,
            file=discord.File(filename)
        )

    except Exception as e:
        print(f"[Gleaming] Screenshot send failed: {e}")
        await channel.send(message)

    finally:
        try:
            os.remove(filename)
        except Exception:
            pass


# ───────────────────────────────────────────────────────────
# 1) Login Flow
# ───────────────────────────────────────────────────────────

async def gleaming_casino(ctx, driver, channel):
    if not GLEAMING_CRED:
        await channel.send("❌ Missing `GLEAMING` as 'email:password' in your .env.")
        return

    username, password = GLEAMING_CRED.split(":", 1)

    print("[Gleaming] Navigating to site...")
    driver.get(SITE_URL)
    await asyncio.sleep(10)

    if _is_logged_in(driver):
        print("[Gleaming] Already logged in.")
        await claim_gleaming_bonus(ctx, driver, channel)
        return

    print("[Gleaming] Attempting to login...")
    try:
        try:
            login = _wait_clickable(driver, By.XPATH, LOGIN_BUTTON_XPATH, timeout=10)
            _safe_click(driver, login, "login button")
            await asyncio.sleep(10)
        except Exception as e:
            print(f"[Gleaming] Login button failed: {e}")

            try:
                print("[Gleaming] Trying direct signin URL...")
                driver.get(LOGIN_URL)
                await asyncio.sleep(10)
            except Exception:
                pass

        try:
            email = _wait_present(driver, By.XPATH, EMAIL_INPUT_XPATH, timeout=10)
            email.clear()
            email.send_keys(username)
            await asyncio.sleep(5)
        except Exception as e:
            print(f"[Gleaming] Email input failed: {e}")

        try:
            pw = _wait_present(driver, By.XPATH, PASSWORD_INPUT_XPATH, timeout=10)
            pw.clear()
            pw.send_keys(password)
            await asyncio.sleep(5)
        except Exception as e:
            print(f"[Gleaming] Password input failed: {e}")

        try:
            submit = _wait_clickable(driver, By.XPATH, LOGIN_SUBMIT_XPATH, timeout=10)
            _safe_click(driver, submit, "login submit button")
            print("[Gleaming] Submitted credentials.")
            await asyncio.sleep(10)
        except Exception as e:
            print(f"[Gleaming] Submit failed: {e}")

        await claim_gleaming_bonus(ctx, driver, channel)

    except TimeoutException as e:
        print(f"[Gleaming] Login timeout: {e}")

        await _send_screenshot(
            channel,
            driver,
            "Gleaming login timed out.",
            "gleaming_login_error.png"
        )


# ───────────────────────────────────────────────────────────
# 2) Claim Bonus
# ───────────────────────────────────────────────────────────

async def claim_gleaming_bonus(ctx, driver, channel):

    print("[Gleaming] Navigating to promotions...")
    try:
        driver.get(PROMOTIONS_URL)
        await asyncio.sleep(10)
    except Exception as e:
        print(f"[Gleaming] Promotions navigation error: {e}")

    print ("[Gleaming] Attempting to click reward button")
    try:
        reward = _wait_clickable(driver, By.XPATH, REWARD_BUTTON_XPATH, timeout=10)
        _safe_click(driver, reward, "reward button")
        await asyncio.sleep(10)
    except Exception as e:
        print(f"[Gleaming] Reward failed: {e}")

    print("[Gleaming] Attempting to claim daily bonus...")
    try:
        claim = _wait_clickable(driver, By.XPATH, CLAIM_BUTTON_XPATH, timeout=10)
        _safe_click(driver, claim, "claim button")

        await asyncio.sleep(5)

        # 📸 success screenshot
        screenshot = "gleaming_claim.png"
        driver.save_screenshot(screenshot)

        await channel.send("Gleaming Daily Bonus Claimed!",file=discord.File(screenshot))

        os.remove(screenshot)

    except Exception as e:
        print(f"[Gleaming] Claim failed: {e}")

        # 📸 error screenshot
        screenshot = "gleaming_claim_error.png"
        driver.save_screenshot(screenshot)

        await channel.send("Gleaming Daily Bonus Unavailable.",file=discord.File(screenshot))

        os.remove(screenshot)