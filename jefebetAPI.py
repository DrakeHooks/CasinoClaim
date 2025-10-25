# Drake Hooks + WaterTrooper
# Casino Claim 2
# JefeBet API

import os
import asyncio
from typing import Optional, List

from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
import discord
load_dotenv()

# ────────────────────────────────────────────────────────────
# JefeBet Helpers
# ────────────────────────────────────────────────────────────
def _present(driver, by, value, timeout=8):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))

def _clickable(driver, by, value, timeout=8):
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, value)))

def _try_click_any_xpath(driver, xpaths: List[str], timeout_each=3) -> bool:
    for xp in xpaths:
        try:
            btn = WebDriverWait(driver, timeout_each).until(EC.element_to_be_clickable((By.XPATH, xp)))
            try:
                btn.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", btn)
            return True
        except Exception:
            continue
    return False

async def check_and_close_popup(driver) -> bool:
    """Try to close the blocking popup if visible."""
    popup_xpath = "/html/body/div[2]/div/div[2]/div[4]/a[2]"
    try:
        popup_close = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH, popup_xpath)))
        popup_close.click()
        await asyncio.sleep(2)
        print("[JefeBet] Popup closed.")
        return True
    except TimeoutException:
        return False

def _is_logged_in(driver) -> bool:
    """Detect if already logged in."""
    try:
        driver.find_element(
            By.XPATH,
            "/html/body/app-root/app-main-header/div/div/div/div/header/div[1]/nav/div[2]/div/div[2]/nav/div/div[3]/button",
        )
        return True
    except NoSuchElementException:
        pass
    try:
        driver.find_element(By.CSS_SELECTOR, "header button[aria-label*='profile'], header img[alt*='avatar']")
        return True
    except NoSuchElementException:
        return False

def _format_countdown(raw: str) -> Optional[str]:
    """Normalize countdown text to HH:MM:SS."""
    if not raw:
        return None
    cleaned = raw.strip().replace(" ", ":")
    parts = [p for p in cleaned.split(":") if p != ""]
    parts = [p for p in parts if p.replace("0", "", 1).isdigit()]
    if not parts:
        return None
    while len(parts) < 3:
        parts.insert(0, "00")
    return ":".join(parts[:3])

async def send_screenshot(channel: discord.abc.Messageable, driver, name="jefe.png"):
    try:
        driver.save_screenshot(name)
        await channel.send(file=discord.File(name))
    finally:
        try:
            if os.path.exists(name):
                os.remove(name)
        except Exception:
            pass

# ────────────────────────────────────────────────────────────
# Main JefeBet Flow
# ────────────────────────────────────────────────────────────
async def jefebet_casino(ctx, driver, channel):
    creds = os.getenv("JEFEBET")
    if not creds:
        await channel.send("JefeBet credentials not found in environment variables.")
        return

    username, password = creds.split(":", 1)

    try:
        print("[JefeBet] Navigating to site…")
        driver.get("https://www.jefebet.com/")
        await asyncio.sleep(6)
        await check_and_close_popup(driver)

        if _is_logged_in(driver):
            print("[JefeBet] Already logged in, skipping login.")
            await claim_jefebet_bonus(ctx, driver, channel)
            return

        print("[JefeBet] Attempting to log in…")
        try:
            login_button = _clickable(
                driver, By.XPATH,
                "/html/body/app-root/app-main-header/div/div/div/div/header/div[2]/div/button[2]", timeout=8
            )
            login_button.click()
            await asyncio.sleep(1.0)
        except TimeoutException:
            print("[JefeBet] Login button not found; trying claim anyway.")
            if _is_logged_in(driver):
                await claim_jefebet_bonus(ctx, driver, channel)
                return
            await channel.send("JefeBet Authentication timed out, will try again later.")
            await send_screenshot(channel, driver)  # ensure we actually attach a screenshot here
            return

        email_input = _present(driver, By.ID, "email", timeout=10)
        password_input = _present(driver, By.ID, "password", timeout=10)
        email_input.clear()
        email_input.send_keys(username)
        password_input.clear()
        password_input.send_keys(password)
        password_input.send_keys(Keys.ENTER)
        print("[JefeBet] Submitted credentials.")
        await asyncio.sleep(10)

        await check_and_close_popup(driver)
        print("[JefeBet] Login successful, proceeding to claim.")
        await claim_jefebet_bonus(ctx, driver, channel)

    except Exception as e:
        print(f"[JefeBet] Login timeout/error: {e}")
        await channel.send("JefeBet Authentication timed out, will try again later.")
        # This now actually runs even on server/LXC
        try:
            await send_screenshot(channel, driver)
        except Exception as ss_e:
            print(f"[JefeBet] Failed to send screenshot: {ss_e}")

# ────────────────────────────────────────────────────────────
# Claim Function
# ────────────────────────────────────────────────────────────
async def claim_jefebet_bonus(ctx, driver, channel):
    try:
        print("[JefeBet] Checking popups before claim…")
        overlay_closed = await check_and_close_popup(driver)
        if overlay_closed:
            print("[JefeBet] Popup closed successfully.")

        still_blocked = _try_click_any_xpath(driver, ["/html/body/div[2]/div/div[2]/div[4]/a[2]"], timeout_each=1)
        if still_blocked:
            print("[JefeBet] Popup persisted; refreshing page.")
            driver.refresh()
            await asyncio.sleep(4)
            await check_and_close_popup(driver)

        print("[JefeBet] Opening Get Coins menu…")
        get_coins_xpath = "/html/body/app-root/app-main-header/div/div/div/div/header/div[1]/nav/div[2]/div/div[2]/nav/div/div[3]/button"
        get_coins = _clickable(driver, By.XPATH, get_coins_xpath, timeout=10)
        get_coins.click()
        await asyncio.sleep(1.0)

        print("[JefeBet] Opening Daily Bonus tab…")
        daily_bonus = _clickable(driver, By.XPATH, '//*[@id="daily-bonus-tab"]', timeout=10)
        daily_bonus.click()
        await asyncio.sleep(1.0)

        try:
            print("[JefeBet] Attempting to click Claim button…")
            claim_button = _clickable(
                driver, By.XPATH,
                "//button[contains(@class, 'btn') and contains(@class, 'btn-red')]",
                timeout=6
            )
            claim_button.click()
            await asyncio.sleep(1.0)
            print("[JefeBet] Bonus claimed successfully!")
            await channel.send("JefeBet 6-Hour Bonus Claimed!")
        except TimeoutException:
            print("[JefeBet] Claim button not found or already claimed.")

    except Exception as e:
        print(f"[JefeBet] Error during claim: {e}")
        await channel.send(f"JefeBet claim error: {e}")

    finally:
        print("[JefeBet] Checking for countdown timer…")
        await asyncio.sleep(1.0)
        await check_and_close_popup(driver)
        await asyncio.sleep(0.5)

        countdown_xpaths = [
            "/html/body/app-root/app-get-coin/div/div[2]/div/app-hourly-bonus/div/div/div[3]/div/label",
            "/html/body/div[1]/div[2]/div/mat-dialog-container/div/div/app-get-coin/div/div[2]/div/app-hourly-bonus/div/div/div[3]/div/label",
            "/html/body/div[2]/div[2]/div/mat-dialog-container/div/div/app-get-coin/div/div[2]/div/app-hourly-bonus/div/div/div[3]/div/label",
            "/html/body/div[3]/div[2]/div/mat-dialog-container/div/div/app-get-coin/div/div[2]/div/app-hourly-bonus/div/div/div[5]/div/label",
        ]

        countdown_text = None
        for xp in countdown_xpaths:
            try:
                el = WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.XPATH, xp)))
                c_text = el.text.strip()
                if c_text:
                    countdown_text = c_text
                    break
            except Exception:
                continue

        formatted = _format_countdown(countdown_text or "")
        if formatted:
            print(f"[JefeBet] Next bonus available in {formatted}")
            await channel.send(f"Next JefeBet Bonus Available in: {formatted}")
        else:
            print("[JefeBet] Countdown not found.")
