# Drake Hooks + WaterTrooper
# Casino Claim 3
# Jumbo API
# Version 3.4
# Updated 2026.11.16

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
JUMBO_CRED = os.getenv("JUMBO")  # format "username:password"

SITE_URL = "https://www.jumbo88.com"
LOGIN_URL = "https://www.jumbo88.com/login"
LOBBY_URL = "https://jumbo88.com/games"
REWARDS_URL = "https://jumbo88.com/rewards"
ACTIVE_URL = "https://jumbo88.com/rewards/active"

LOGIN_BUTTON_XPATH = "//button[contains(@class, 'inline-flex items-center justify-center') and text()='Login']"
EMAIL_INPUT_XPATH = "//input[@type='email']"
PASSWORD_INPUT_XPATH = "//input[@type='password']"
LOGIN_SUBMIT_XPATH = "//button[@type='submit' and text()='Login']"

REWARD_BUTTON_XPATH = "//span[@class='text-micro font-bold uppercase tracking-wider text-text-secondary' and text()='Mystery Spin']"
SPIN_BUTTON_XPATH = "//button[contains(@class, 'inline-flex items-center justify-center') and text()='Spin']"
DONE_BUTTON_XPATH = "//button[contains(@class, 'inline-flex items-center justify-center') and text()='Done']"
SEEALL_BUTTON_XPATH = "//a[@href='/rewards/active']"
COINS_BUTTON_XPATH = "//button[@aria-label='View details: Mystery Spin Coins']"
CLAIM_BUTTON_XPATH = "//button[contains(@class, 'inline-flex items-center justify-center') and text()='Claim Bonus']"


# ───────────────────────────────────────────────────────────
# 0) Helpers
# ───────────────────────────────────────────────────────────

def _is_logged_in(driver) -> bool:
    """Detect if already logged in."""
    try:
        driver.find_element(By.XPATH, "//button[@aria-label='Add funds']")
        return True
    except NoSuchElementException:
        pass
    try:
        driver.find_element(By.XPATH, "//a[@aria-label='Open profile']")
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
        print(f"[Jumbo] Clicked {label}.")
        return True
    except Exception as e:
        print(f"[Jumbo] Normal click failed for {label}: {e}")

    try:
        driver.execute_script("arguments[0].click();", element)
        print(f"[Jumbo] JS clicked {label}.")
        return True
    except Exception as e:
        print(f"[Jumbo] JS click failed for {label}: {e}")

    return False


async def _send_screenshot(channel, driver, message, filename):
    try:
        driver.save_screenshot(filename)

        await channel.send(
            message,
            file=discord.File(filename)
        )

    except Exception as e:
        print(f"[Jumbo] Screenshot send failed: {e}")
        await channel.send(message)

    finally:
        try:
            os.remove(filename)
        except Exception:
            pass


# ───────────────────────────────────────────────────────────
# 1) Login Flow
# ───────────────────────────────────────────────────────────

async def jumbo_casino(ctx, driver, channel):
    if not JUMBO_CRED:
        await channel.send("❌ Missing `JUMBO` as 'email:password' in your .env.")
        return

    username, password = JUMBO_CRED.split(":", 1)

    print("[Jumbo] Navigating to site...")
    driver.get(SITE_URL)
    await asyncio.sleep(10)

    if _is_logged_in(driver):
        print("[Jumbo] Already logged in.")
        await claim_jumbo_bonus(ctx, driver, channel)
        return

    print("[Jumbo] Attempting to login...")
    try:
        try:
            login = _wait_clickable(driver, By.XPATH, LOGIN_BUTTON_XPATH, timeout=10)
            _safe_click(driver, login, "login button")
            await asyncio.sleep(10)
        except Exception as e:
            print(f"[Jumbo] Login button failed: {e}")

            try:
                print("[Jumbo] Trying direct signin URL...")
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
            print(f"[Jumbo] Email input failed: {e}")

        try:
            pw = _wait_present(driver, By.XPATH, PASSWORD_INPUT_XPATH, timeout=10)
            pw.clear()
            pw.send_keys(password)
            await asyncio.sleep(5)
        except Exception as e:
            print(f"[Jumbo] Password input failed: {e}")

        try:
            submit = _wait_clickable(driver, By.XPATH, LOGIN_SUBMIT_XPATH, timeout=10)
            _safe_click(driver, submit, "login submit button")
            print("[Jumbo] Submitted credentials.")
            await asyncio.sleep(10)
        except Exception as e:
            print(f"[Jumbo] Submit failed: {e}")

        await claim_jumbo_bonus(ctx, driver, channel)

    except TimeoutException as e:
        print(f"[Jumbo] Login timeout: {e}")

        await _send_screenshot(
            channel,
            driver,
            "Jumbo login timed out.",
            "jumbo_login_error.png"
        )


# ───────────────────────────────────────────────────────────
# 2) Claim Bonus
# ───────────────────────────────────────────────────────────

async def claim_jumbo_bonus(ctx, driver, channel):

    print("[Jumbo] Navigating to rewards...")
    try:
        driver.get(REWARDS_URL)
        await asyncio.sleep(10)
    except Exception as e:
        print(f"[Jumbo] Rewards navigation error: {e}")


    print ("[Jumbo] Attempting to click reward button")
    try:
        reward = _wait_clickable(driver, By.XPATH, REWARD_BUTTON_XPATH, timeout=10)
        _safe_click(driver, reward, "reward button")
        await asyncio.sleep(10)
    except Exception as e:
        print(f"[Jumbo] Reward failed: {e}")

    print ("[Jumbo] Attempting to click spin button")
    try:
        spin = _wait_clickable(driver, By.XPATH, SPIN_BUTTON_XPATH, timeout=10)
        _safe_click(driver, spin, "spin button")
        await asyncio.sleep(10)
    except Exception as e:
        print(f"[Jumbo] Spin failed: {e}")

    print ("[Jumbo] Attempting to click done button")
    try:
        done = _wait_clickable(driver, By.XPATH, DONE_BUTTON_XPATH, timeout=10)
        _safe_click(driver, done, "done button")
        await asyncio.sleep(10)
    except Exception as e:
        print(f"[Jumbo] Done failed: {e}")

    print ("[Jumbo] Attempting to click see all button")
    try:
        seeall = _wait_clickable(driver, By.XPATH, SEEALL_BUTTON_XPATH, timeout=10)
        _safe_click(driver, seeall, "see all button")
        await asyncio.sleep(10)
    except Exception as e:
        print(f"[Jumbo] See all failed: {e}")

        try:
            print("[Jumbo] Trying direct active URL...")
            driver.get(ACTIVE_URL)
            await asyncio.sleep(10)
        except Exception:
            pass

    print ("[Jumbo] Attempting to click coins button")
    try:
        coins = _wait_clickable(driver, By.XPATH, COINS_BUTTON_XPATH, timeout=10)
        _safe_click(driver, coins, "coins button")
        await asyncio.sleep(10)
    except Exception as e:
        print(f"[Jumbo] Coins failed: {e}")

    print("[Jumbo] Attempting to claim daily bonus...")
    try:
        claim = _wait_clickable(driver, By.XPATH, CLAIM_BUTTON_XPATH, timeout=10)
        _safe_click(driver, claim, "claim button")

        await asyncio.sleep(5)

        # 📸 success screenshot
        screenshot = "jumbo_claim.png"
        driver.save_screenshot(screenshot)

        await channel.send("Jumbo Daily Bonus Claimed!",file=discord.File(screenshot))

        os.remove(screenshot)

    except Exception as e:
        print(f"[Jumbo] Claim failed: {e}")

        # 📸 error screenshot
        screenshot = "jumbo_claim_error.png"
        driver.save_screenshot(screenshot)

        await channel.send("Jumbo Daily Bonus Unavailable.",file=discord.File(screenshot))

        os.remove(screenshot)