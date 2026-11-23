# Drake Hooks + WaterTrooper
# Casino Claim 3
# SweepJungle API
# Version 3.4
# Updated 2026.11.21

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
SWEEPJUNGLE_CRED = os.getenv("SWEEPJUNGLE")  # format "username:password"

SITE_URL = "https://sweepjungle.com"
LOGIN_URL = "https://sweepjungle.com/?modal=login"

LOGIN_BUTTON_XPATH = "//button[contains(@class, 'bg-blue-300 text-neutral-0 border border-neutral-1000')]"
EMAIL_INPUT_XPATH = "//input[@name='email']"
PASSWORD_INPUT_XPATH = "//input[@name='password']"
LOGIN_SUBMIT_XPATH = "//button[contains(@class, 'bg-yellow-300 text-neutral-0 border border-neutral-1000')]//span[text()='Log in']"

BEST_DEAL_XPATH = "//button[@class='flex size-9 cursor-pointer items-center justify-center rounded-full bg-transparent ease-spring transition-transform duration-100 hover:scale-110 hover:bg-transparent absolute top-6 right-3 z-30']"
WILD_SHOP_XPATH = "//button[@class='flex cursor-pointer items-center justify-center bg-transparent ease-spring duration-100 hover:scale-110 hover:bg-transparent absolute right-0 size-6 rounded-full transition-transform']"
BONUS_MODAL_XPATH = "//button[@class='flex size-9 cursor-pointer items-center justify-center rounded-full bg-transparent ease-spring transition-transform duration-100 hover:scale-110 hover:bg-transparent absolute top-2 right-1']"
GRAND_PRIZE_XPATH = "//button[@class='flex size-9 cursor-pointer items-center justify-center rounded-full bg-transparent ease-spring transition-transform duration-100 hover:scale-110 hover:bg-transparent absolute -top-1 right-1']"
POWER_TOTEM_XPATH = "//button[@class='flex size-9 cursor-pointer items-center justify-center rounded-full bg-transparent ease-spring transition-transform duration-100 hover:scale-110 hover:bg-transparent absolute top-[-40px] right-[-12px]']"
REWARD_BUTTON_XPATH = "//button[@aria-label='daily refill']"
CLAIM_BUTTON_XPATH = "//button[contains(@class, '!text-h5 cursor-pointer w-full py-3 flex items-center')]//span[text()='Claim']"


# ───────────────────────────────────────────────────────────
# 0) Helpers
# ───────────────────────────────────────────────────────────

def _is_logged_in(driver) -> bool:
    """Detect if already logged in."""
    try:
        driver.find_element(By.XPATH, "//span[@class='ml-1 inline-block text-orange-300 sm:ml-2' and (text()='GC')]")
        return True
    except NoSuchElementException:
        pass
    try:
        driver.find_element(By.XPATH, "//span[@class='ml-1 inline-block text-blue-300 sm:ml-2' and (text()='SC')]")
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
        print(f"[SweepJungle] Clicked {label}.")
        return True
    except Exception as e:
        print(f"[SweepJungle] Normal click failed for {label}: {e}")

    try:
        driver.execute_script("arguments[0].click();", element)
        print(f"[SweepJungle] JS clicked {label}.")
        return True
    except Exception as e:
        print(f"[SweepJungle] JS click failed for {label}: {e}")

    return False


async def _send_screenshot(channel, driver, message, filename):
    try:
        driver.save_screenshot(filename)

        await channel.send(
            message,
            file=discord.File(filename)
        )

    except Exception as e:
        print(f"[SweepJungle] Screenshot send failed: {e}")
        await channel.send(message)

    finally:
        try:
            os.remove(filename)
        except Exception:
            pass


# ───────────────────────────────────────────────────────────
# 1) Login Flow
# ───────────────────────────────────────────────────────────

async def sweepjungle_casino(ctx, driver, channel):
    if not SWEEPJUNGLE_CRED:
        await channel.send("❌ Missing `SWEEPJUNGLE` as 'email:password' in your .env.")
        return

    username, password = SWEEPJUNGLE_CRED.split(":", 1)

    print("[SweepJungle] Navigating to site...")
    driver.get(SITE_URL)
    await asyncio.sleep(10)  

    if _is_logged_in(driver):
        print("[SweepJungle] Already logged in.")
        await claim_sweepjungle_bonus(ctx, driver, channel)
        return

    print("[SweepJungle] Attempting to login...")
    try:
        try:
            login = _wait_clickable(driver, By.XPATH, LOGIN_BUTTON_XPATH, timeout=10)
            _safe_click(driver, login, "login button")
            await asyncio.sleep(10)
        except Exception as e:
            print(f"[SweepJungle] Login button failed: {e}")

            try:
                print("[SweepJungle] Trying direct signin URL...")
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
            print(f"[SweepJungle] Email input failed: {e}")

        try:
            pw = _wait_present(driver, By.XPATH, PASSWORD_INPUT_XPATH, timeout=10)
            pw.clear()
            pw.send_keys(password)
            await asyncio.sleep(5)
        except Exception as e:
            print(f"[SweepJungle] Password input failed: {e}")

        try:
            submit = _wait_clickable(driver, By.XPATH, LOGIN_SUBMIT_XPATH, timeout=10)
            _safe_click(driver, submit, "login submit button")
            print("[SweepJungle] Submitted credentials.")
            await asyncio.sleep(10)
        except Exception as e:
            print(f"[SweepJungle] Submit failed: {e}")

        await claim_sweepjungle_bonus(ctx, driver, channel)

    except TimeoutException as e:
        print(f"[SweepJungle] Login timeout: {e}")

        await _send_screenshot(
            channel,
            driver,
            "SweepJungle login timed out.",
            "sweepjungle_login_error.png"
        )


# ───────────────────────────────────────────────────────────
# 2) Claim Bonus
# ───────────────────────────────────────────────────────────

async def claim_sweepjungle_bonus(ctx, driver, channel):

    print("[SweepJungle] Attemping to close best deal modal...")
    try:
        bestdeal = _wait_clickable(driver, By.XPATH, BEST_DEAL_XPATH, timeout=10)
        _safe_click(driver, bestdeal, "best deal close button")
        await asyncio.sleep(10)
    except Exception as e:
        print(f"[SweepJungle] Best deal failed: {e}")

    print("[SweepJungle] Attemping to close wild shop modal...")
    try:
        wildshop = _wait_clickable(driver, By.XPATH, WILD_SHOP_XPATH, timeout=10)
        _safe_click(driver, wildshop, "wild shop close button")
        await asyncio.sleep(10)
    except Exception as e:
        print(f"[SweepJungle] Wild shop failed: {e}")

    print("[SweepJungle] Attemping to close bonus modal...")
    try:
        bonus = _wait_clickable(driver, By.XPATH, BONUS_MODAL_XPATH, timeout=10)
        _safe_click(driver, bonus, "bonus close button")
        await asyncio.sleep(10)
    except Exception as e:
        print(f"[SweepJungle] Bonus failed: {e}")

    print("[SweepJungle] Attemping to close grand prize modal...")
    try:
        grandprize = _wait_clickable(driver, By.XPATH, GRAND_PRIZE_XPATH, timeout=10)
        _safe_click(driver, grandprize, "grand prize close button")
        await asyncio.sleep(10)
    except Exception as e:
        print(f"[SweepJungle] Grand prize failed: {e}")

    print("[SweepJungle] Attemping to close power totem modal...")
    try:
        powertotem = _wait_clickable(driver, By.XPATH, POWER_TOTEM_XPATH, timeout=10)
        _safe_click(driver, powertotem, "power totem close button")
        await asyncio.sleep(10)
    except Exception as e:
        print(f"[SweepJungle] Power totem failed: {e}")

    print("[SweepJungle] Attempting to click on reward button...")
    try:
        reward = _wait_clickable(driver, By.XPATH, REWARD_BUTTON_XPATH, timeout=10)
        _safe_click(driver, reward, "reward button")
        await asyncio.sleep(10)
    except Exception as e:
        print(f"[SweepJungle] Reward failed: {e}")

    print("[SweepJungle] Attempting to claim daily bonus...")
    try:
        claim = _wait_clickable(driver, By.XPATH, CLAIM_BUTTON_XPATH, timeout=10)
        _safe_click(driver, claim, "claim button")

        await asyncio.sleep(5)

        # 📸 success screenshot
        screenshot = "sweepjungle_claim.png"
        driver.save_screenshot(screenshot)

        await channel.send("SweepJungle Daily Bonus Claimed!",file=discord.File(screenshot))

        os.remove(screenshot)

    except Exception as e:
        print(f"[SweepJungle] Claim failed: {e}")

        # 📸 error screenshot
        screenshot = "sweepjungle_claim_error.png"
        driver.save_screenshot(screenshot)

        await channel.send("SweepJungle Daily Bonus Unavailable.",file=discord.File(screenshot))

        os.remove(screenshot)