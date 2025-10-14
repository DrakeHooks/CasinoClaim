# Drake Hooks
# Casino Claim 2
# LuckyBird API — Claim-if-available, else report countdown (with 2FA-capable auth kept intact)

import os
import asyncio
import datetime
import discord
from dotenv import load_dotenv

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

load_dotenv()

# ───────────────────────────────────────────────────────────
# Config & XPaths
# ───────────────────────────────────────────────────────────
LB_URL = "https://luckybird.io/"

# Nav → “Buy” tab → Daily bonus card
X_BUY_TAB        = (By.XPATH, "/html/body/div[1]/div/div[1]/div/section/section/header/div/div/ul[1]/li[2]/p")
X_DAILY_BONUS    = (By.XPATH, "/html/body/section/div[2]/div[2]/div[2]/div[1]/div/div/div/div[5]")

# Claim button inside daily bonus view
X_CLAIM_BUTTON   = (By.XPATH, "/html/body/section/div[2]/div[2]/div[2]/div[2]/div/div[2]/button[1]")

# Countdown (text looks like: “Next claim available at 2025/10/13 01:23 PM”)
X_COUNTDOWN_TEXT = (By.XPATH, "/html/body/section/div[2]/div[2]/div[2]/div[2]/div/div[3]/p[1]")

# Login/2FA bits (kept from your working auth)
X_LOGIN_TAB = (By.ID, "tab-login")
X_EMAIL     = (By.XPATH, "/html/body/div[1]/div/div[1]/div/div/div[1]/div/div[1]/div/div[2]/div[2]/div/div[1]/form[2]/div[1]/div/div/input")
X_PASS      = (By.XPATH, "/html/body/div[1]/div/div[1]/div/div/div[1]/div/div[1]/div/div[2]/div[2]/div/div[1]/form[2]/div[2]/div/div/input")
X_2FA_BTN   = (By.XPATH, "/html/body/section/div[1]/div/button")
X_2FA_INPUT = (By.XPATH, "/html/body/section/div[1]/div/div/input")

# ───────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────
def _fmt_remaining(target_str: str) -> str:
    """
    target_str is like '2025/10/13 01:23 PM' (from the page’s text)
    Returns a human string: 'HH:MM:SS' or 'X days, HH:MM:SS'
    """
    # Normalize the label
    target_str = target_str.replace("Next claim available at", "").strip()
    # Parse: '%Y/%m/%d %I:%M %p'
    try:
        target_dt = datetime.datetime.strptime(target_str, "%Y/%m/%d %I:%M %p")
    except Exception:
        # If parse fails, just echo what we got
        return f"Next LuckyBird Bonus Available at: {target_str}"

    now = datetime.datetime.now()
    diff = target_dt - now
    if diff.total_seconds() < 0:
        return "Next LuckyBird Bonus Available in: 00:00:00"

    days = diff.days
    hours, rem = divmod(diff.seconds, 3600)
    minutes, seconds = divmod(rem, 60)

    if days == 0:
        return f"Next LuckyBird Bonus Available in: {hours:02}:{minutes:02}:{seconds:02}"
    return f"Next LuckyBird Bonus Available in: {days} days, {hours:02}:{minutes:02}:{seconds:02}"

async def _shot(channel, driver, name, caption):
    try:
        driver.save_screenshot(name)
        await channel.send(caption, file=discord.File(name))
        os.remove(name)
    except Exception:
        pass

# ───────────────────────────────────────────────────────────
# Claim flow: try to claim; if not, report countdown
# ───────────────────────────────────────────────────────────
async def luckybird_flow(ctx, driver, channel):
    """Open LB → navigate to daily bonus card → claim if possible → else report countdown."""
    driver.get(LB_URL)
    await asyncio.sleep(3)

    # Go to Buy tab
    try:
        buy = WebDriverWait(driver, 10).until(EC.element_to_be_clickable(X_BUY_TAB))
        buy.click()
        await asyncio.sleep(0.8)
    except TimeoutException:
        await channel.send("LuckyBird: couldn't open the Buy tab.")
        await _shot(channel, driver, "lb_buy_tab_fail.png", "📸 Buy tab not reachable")
        return

    # Open Daily Bonus card
    try:
        daily = WebDriverWait(driver, 10).until(EC.element_to_be_clickable(X_DAILY_BONUS))
        daily.click()
        await asyncio.sleep(1)
    except TimeoutException:
        await channel.send("LuckyBird: couldn't open the Daily Bonus card.")
        await _shot(channel, driver, "lb_daily_card_fail.png", "📸 Daily bonus card not reachable")
        return

    # Try to click "Claim" if available
    try:
        claim = WebDriverWait(driver, 6).until(EC.element_to_be_clickable(X_CLAIM_BUTTON))
        claim.click()
        await asyncio.sleep(1.5)
        await channel.send("LuckyBird Daily Bonus Claimed!")
        return
    except TimeoutException:
        # Not claimable → read the countdown
        pass

    # Read countdown text and format
    try:
        cd_node = WebDriverWait(driver, 6).until(EC.presence_of_element_located(X_COUNTDOWN_TEXT))
        msg = _fmt_remaining(cd_node.text)
        await channel.send(msg)
    except TimeoutException:
        await channel.send("LuckyBird: neither Claim button nor countdown was found.")

# ───────────────────────────────────────────────────────────
# Authentication (your working version, retained)
# ───────────────────────────────────────────────────────────
async def authenticate_luckybird(driver, bot, ctx, channel) -> bool:
    creds = os.getenv("LUCKYBIRD", "")
    if ":" not in creds:
        await channel.send("LUCKYBIRD credentials not found in .env (LUCKYBIRD=username:password).")
        return False
    username_text, password_text = creds.split(":", 1)

    try:
        driver.get(LB_URL)
        await asyncio.sleep(3)

        login_tab = WebDriverWait(driver, 12).until(EC.element_to_be_clickable(X_LOGIN_TAB))
        login_tab.click()
        await asyncio.sleep(1)

        email_input = WebDriverWait(driver, 12).until(EC.presence_of_element_located(X_EMAIL))
        email_input.clear()
        email_input.send_keys(username_text)
        await asyncio.sleep(0.3)

        password_input = WebDriverWait(driver, 12).until(EC.presence_of_element_located(X_PASS))
        password_input.clear()
        password_input.send_keys(password_text)
        await asyncio.sleep(0.3)

        password_input.send_keys(Keys.ENTER)
        await asyncio.sleep(3)

        # 2FA detection
        twofa = False
        try:
            WebDriverWait(driver, 4).until(EC.presence_of_element_located(X_2FA_BTN))
            twofa = True
        except TimeoutException:
            try:
                WebDriverWait(driver, 2).until(EC.presence_of_element_located(X_2FA_INPUT))
                twofa = True
            except TimeoutException:
                twofa = False

        if twofa:
            await channel.send("2FA required. Please reply in this channel with your 6–8 digit code.")
            await _shot(channel, driver, "lb_5_twofa.png", "📸 2FA prompt visible")

            # Event-based wait (provided in main.py’s on_message)
            if not hasattr(bot, "_pending_2fa_event"):
                bot._pending_2fa_event = asyncio.Event()

            # Arm listener
            bot.awaiting_2fa_for = "luckybird"
            bot.pending_2fa_code = None
            try:
                bot._pending_2fa_event.clear()
            except Exception:
                bot._pending_2fa_event = asyncio.Event()

            try:
                await asyncio.wait_for(bot._pending_2fa_event.wait(), timeout=120)
                code = bot.pending_2fa_code
            except asyncio.TimeoutError:
                code = None

            # cleanup
            bot.awaiting_2fa_for = None

            if not code:
                await channel.send("Timed out waiting for LuckyBird 2FA code.")
                await _shot(channel, driver, "lb_6_twofa_timeout.png", "📸 Still waiting at 2FA")
                return False

            try:
                twofa_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located(X_2FA_INPUT))
                twofa_input.clear()
                twofa_input.send_keys(code)
                await asyncio.sleep(0.6)
                twofa_input.send_keys(Keys.ENTER)
                await asyncio.sleep(3)
                await _shot(channel, driver, "lb_7_twofa_entered.png", "📸 2FA code submitted")
            except TimeoutException:
                await channel.send("Could not find the 2FA input field to type the code.")
                await _shot(channel, driver, "lb_6_twofa_no_input.png", "📸 2FA input not found")
                return False

        await _shot(channel, driver, "lb_8_post_login.png", "📸 Post-login state")
        return True

    except TimeoutException as e:
        await channel.send("LuckyBird login step timed out.")
        await _shot(channel, driver, "lb_error_timeout.png", f"Timeout: {e}")
        return False
    except Exception as e:
        await channel.send(f"LuckyBird login failed. Error: {e}")
        await _shot(channel, driver, "lb_error_generic.png", "Error state")
        return False
