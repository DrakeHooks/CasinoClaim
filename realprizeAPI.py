# Drake Hooks + WaterTrooper
# Casino Claim 3
# Real Prize API
# Version 3.3
# Updated 2026.05.12

import os
import asyncio
import discord
from dotenv import load_dotenv

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


# ───────────────────────────────────────────────────────────
# Config & Constants
# ───────────────────────────────────────────────────────────
load_dotenv()

REALPRIZE_CRED = os.getenv("REALPRIZE")  # format "email:password"
SITE_URL = "https://realprize.com"

LOGIN_BUTTON_XPATH = "//a[@class='site-header__login-btn btn-login']"
LOGIN_EMAIL_ID = "logemailnbtn"
EMAIL_INPUT_XPATH = "//input[@id='poplogin_email']"
PASSWORD_INPUT_XPATH = "//input[@id='poplogin_password']"
LOGIN_SUBMIT_XPATH = "//button[@id='poploginbtn']"

# First/normal daily button
DAILYBONUS_BUTTON_XPATH = "//div[contains(@class,'daily_button')]"

# Finished popup / second COLLECT button
SECOND_COLLECT_LOCATORS = [
    (
        By.XPATH,
        "//div[contains(@class,'grand_prize_finished_container') "
        "and not(contains(@style,'display: none'))]"
        "//div[contains(@class,'daily_button')]"
    ),
    (
        By.XPATH,
        "//div[contains(@class,'grand_prize_finished_container')]"
        "//div[contains(translate(normalize-space(.), "
        "'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'COLLECT')]"
    ),
    (
        By.XPATH,
        "//div[@id='daily_prize_popup']"
        "//div[contains(translate(normalize-space(.), "
        "'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'COLLECT')]"
    ),
    (
        By.XPATH,
        "/html/body/div[20]/div[2]/div[5]"
    ),
]


# ───────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────
def _is_logged_in(driver) -> bool:
    try:
        driver.find_element(By.XPATH, "//div[@class='gcnum']")
        return True
    except NoSuchElementException:
        pass

    try:
        driver.find_element(By.XPATH, "//div[@class='myviptitle']")
        return True
    except NoSuchElementException:
        return False


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
        print(f"[Real Prize] Clicked {label}.")
        return True
    except Exception as e:
        print(f"[Real Prize] Normal click failed for {label}: {e}")

    try:
        driver.execute_script("arguments[0].click();", element)
        print(f"[Real Prize] JS clicked {label}.")
        return True
    except Exception as e:
        print(f"[Real Prize] JS click failed for {label}: {e}")

    return False


def _find_clickable(driver, locator, timeout=8):
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable(locator)
    )


async def _send_screenshot(channel, driver, message, filename):
    driver.save_screenshot(filename)

    try:
        await channel.send(
            message,
            file=discord.File(filename)
        )
    finally:
        try:
            os.remove(filename)
        except Exception:
            pass


async def _click_second_collect_if_present(driver, wait_seconds=8) -> bool:
    """
    Real Prize shows a second/final COLLECT button inside the finished popup.
    This is the button we now treat as the actual successful claim confirmation.
    """
    for locator in SECOND_COLLECT_LOCATORS:
        try:
            button = _find_clickable(driver, locator, timeout=wait_seconds)

            if _safe_click(driver, button, "finished popup COLLECT button"):
                await asyncio.sleep(3)
                return True

        except TimeoutException:
            continue
        except Exception as e:
            print(f"[Real Prize] Finished popup locator failed: {locator} | {e}")
            continue

    return False


# ───────────────────────────────────────────────────────────
# Login Flow
# ───────────────────────────────────────────────────────────
async def realprize_casino(ctx, driver, channel):
    if not REALPRIZE_CRED:
        await channel.send("❌ Missing `REALPRIZE` as 'email:password' in your .env.")
        return

    username, password = REALPRIZE_CRED.split(":", 1)

    print("[Real Prize] Navigating to site...")
    driver.get(SITE_URL)
    await asyncio.sleep(10)

    if _is_logged_in(driver):
        print("[Real Prize] Already logged in.")
        await claim_realprize_bonus(ctx, driver, channel)
        return

    print("[Real Prize] Attempting login...")

    try:
        try:
            login = _find_clickable(driver, (By.XPATH, LOGIN_BUTTON_XPATH), timeout=10)
            _safe_click(driver, login, "login button")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"[Real Prize] Login button failed: {e}")

        try:
            login_email = _find_clickable(driver, (By.ID, LOGIN_EMAIL_ID), timeout=10)
            _safe_click(driver, login_email, "email login button")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"[Real Prize] Email login button failed: {e}")

        try:
            email = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, EMAIL_INPUT_XPATH))
            )
            email.clear()
            email.send_keys(username)
        except Exception as e:
            print(f"[Real Prize] Email input failed: {e}")

        try:
            pw = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, PASSWORD_INPUT_XPATH))
            )
            pw.clear()
            pw.send_keys(password)
        except Exception as e:
            print(f"[Real Prize] Password input failed: {e}")

        try:
            submit = _find_clickable(driver, (By.XPATH, LOGIN_SUBMIT_XPATH), timeout=10)
            _safe_click(driver, submit, "login submit button")
            await asyncio.sleep(10)
        except Exception as e:
            print(f"[Real Prize] Submit failed: {e}")

        await claim_realprize_bonus(ctx, driver, channel)

    except TimeoutException as e:
        print("[Real Prize] Login timed out:", e)

        await _send_screenshot(
            channel,
            driver,
            "❌ Real Prize login timed out.",
            "realprize_login_error.png"
        )


# ───────────────────────────────────────────────────────────
# Claim Bonus
# ───────────────────────────────────────────────────────────
async def claim_realprize_bonus(ctx, driver, channel):
    print("[Real Prize] Attempting claim...")

    try:
        # If the finished popup is already open, click that second button first.
        if await _click_second_collect_if_present(driver, wait_seconds=3):
            await _send_screenshot(
                channel,
                driver,
                "Real Prize Daily Bonus Claimed!",
                "realprize_claim.png"
            )
            return

        # Click the normal/first daily bonus button.
        print("[Real Prize] Looking for first daily bonus button...")
        first_claim = _find_clickable(
            driver,
            (By.XPATH, DAILYBONUS_BUTTON_XPATH),
            timeout=12
        )

        if not _safe_click(driver, first_claim, "first daily bonus button"):
            raise Exception("Could not click first daily bonus button.")

        await asyncio.sleep(5)

        # Real Prize requires this final popup COLLECT button.
        # Only consider it claimed if this second button gets clicked.
        print("[Real Prize] Looking for finished popup COLLECT button...")
        second_clicked = await _click_second_collect_if_present(driver, wait_seconds=12)

        if not second_clicked:
            raise Exception("First claim clicked, but finished popup COLLECT button was not found.")

        await _send_screenshot(
            channel,
            driver,
            "Real Prize Daily Bonus Claimed!",
            "realprize_claim.png"
        )

    except Exception as e:
        print("[Real Prize] Claim failed:", e)

        await _send_screenshot(
            channel,
            driver,
            "[Real Prize] daily bonus unavailable.",
            "realprize_claim_error.png"
        )