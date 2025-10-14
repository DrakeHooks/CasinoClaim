# Drake Hooks
# Casino Claim 2
# LuckyBird API — Try claim/countdown; auth only if needed, then retry once.

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

LB_URL = "https://luckybird.io/"

# Navigation → Buy tab → Daily bonus card
X_BUY_TAB        = (By.XPATH, "/html/body/div[1]/div/div[1]/div/section/section/header/div/div/ul[1]/li[2]/p")
X_DAILY_BONUS    = (By.XPATH, "/html/body/section/div[2]/div[2]/div[2]/div[1]/div/div/div/div[5]")

# Claim button inside daily bonus view
X_CLAIM_BUTTON   = (By.XPATH, "/html/body/section/div[2]/div[2]/div[2]/div[2]/div/div[2]/button[1]")

# Countdown text (e.g. “Next claim available at 2025/10/14 12:00 AM”)
X_COUNTDOWN_TEXT = (By.XPATH, "/html/body/section/div[2]/div[2]/div[2]/div[2]/div/div[3]/p[1]")

# Login / 2FA
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
    Input like 'Next claim available at 2025/10/14 12:00 AM' → 'Next LuckyBird Bonus Available in: HH:MM:SS'
    """
    raw = target_str.replace("Next claim available at", "").strip()
    try:
        target_dt = datetime.datetime.strptime(raw, "%Y/%m/%d %I:%M %p")
    except Exception:
        return f"Next LuckyBird Bonus Available at: {raw}"

    now = datetime.datetime.now()
    diff = target_dt - now
    total = max(int(diff.total_seconds()), 0)

    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)

    if days == 0:
        return f"Next LuckyBird Bonus Available in: {hours:02}:{minutes:02}:{seconds:02}"
    return f"Next LuckyBird Bonus Available in: {days} days, {hours:02}:{minutes:02}:{seconds:02}"

async def _shot(channel, driver, name, caption):
    """Only used for the 2FA prompt screenshot."""
    try:
        driver.save_screenshot(name)
        await channel.send(caption, file=discord.File(name))
        os.remove(name)
    except Exception:
        pass

# ───────────────────────────────────────────────────────────
# Core flow (returns True if it posted a result; False if it couldn't reach UI)
# ───────────────────────────────────────────────────────────
async def luckybird_flow(ctx, driver, channel) -> bool:
    """
    Navigate to daily bonus UI. If claimable → claim; else post countdown.
    Returns:
      True  = flow reached UI and posted a message (claimed OR countdown OR 'no timer').
      False = couldn't open Buy tab or Daily Bonus card (likely needs auth).
    """
    driver.get(LB_URL)
    await asyncio.sleep(3)

    # Buy tab
    try:
        buy = WebDriverWait(driver, 8).until(EC.element_to_be_clickable(X_BUY_TAB))
        buy.click()
        await asyncio.sleep(0.8)
    except TimeoutException:
        # Not even the Buy tab—treat as "needs auth"
        return False

    # Daily Bonus card
    try:
        daily = WebDriverWait(driver, 8).until(EC.element_to_be_clickable(X_DAILY_BONUS))
        daily.click()
        await asyncio.sleep(1)
    except TimeoutException:
        # Couldn’t open the card → likely needs auth
        return False

    # Try to claim
    try:
        claim = WebDriverWait(driver, 4).until(EC.element_to_be_clickable(X_CLAIM_BUTTON))
        claim.click()
        await asyncio.sleep(1.2)
        await channel.send("LuckyBird Daily Bonus Claimed!")
        return True
    except TimeoutException:
        # Not claimable → read countdown
        pass

    try:
        cd_node = WebDriverWait(driver, 6).until(EC.presence_of_element_located(X_COUNTDOWN_TEXT))
        await channel.send(_fmt_remaining(cd_node.text))
        return True
    except TimeoutException:
        await channel.send("LuckyBird: neither Claim button nor countdown was found.")
        return True

# ───────────────────────────────────────────────────────────
# Authentication (single 2FA screenshot)
# ───────────────────────────────────────────────────────────
async def authenticate_luckybird(driver, bot, ctx, channel) -> bool:
    creds = os.getenv("LUCKYBIRD", "")
    if ":" not in creds:
        await channel.send("LUCKYBIRD credentials not found in .env (LUCKYBIRD=username:password).")
        return False
    username_text, password_text = creds.split(":", 1)

    try:
        driver.get(LB_URL)
        await asyncio.sleep(2)

        login_tab = WebDriverWait(driver, 10).until(EC.element_to_be_clickable(X_LOGIN_TAB))
        login_tab.click()
        await asyncio.sleep(0.6)

        email_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located(X_EMAIL))
        email_input.clear(); email_input.send_keys(username_text)
        await asyncio.sleep(0.2)

        password_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located(X_PASS))
        password_input.clear(); password_input.send_keys(password_text)
        await asyncio.sleep(0.2)
        password_input.send_keys(Keys.ENTER)
        await asyncio.sleep(5)
        await _shot(channel, driver, "luckybird_login.png", "Luckybird credentials entered.")

        # 2FA detection
        needs_2fa = False
        try:
            WebDriverWait(driver, 3).until(EC.presence_of_element_located(X_2FA_BTN))
            needs_2fa = True
        except TimeoutException:
            try:
                WebDriverWait(driver, 2).until(EC.presence_of_element_located(X_2FA_INPUT))
                needs_2fa = True
            except TimeoutException:
                needs_2fa = False

        if needs_2fa:
            await channel.send("2FA required. Please reply in this channel with your 6–8 digit code.")
            await _shot(channel, driver, "luckybird_2fa_prompt.png", "2FA prompt visible.")

            # Event-based wait (needs on_message in main.py)
            if not hasattr(bot, "_pending_2fa_event"):
                bot._pending_2fa_event = asyncio.Event()

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
            bot.awaiting_2fa_for = None

            if not code:
                await channel.send("Timed out waiting for LuckyBird 2FA code.")
                return False

            try:
                twofa_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located(X_2FA_INPUT))
                twofa_input.clear(); twofa_input.send_keys(code)
                await asyncio.sleep(0.4)
                twofa_input.send_keys(Keys.ENTER)
                await asyncio.sleep(2)
            except TimeoutException:
                await channel.send("Could not find the 2FA input to type the code.")
                return False

        return True

    except TimeoutException:
        await channel.send("LuckyBird login step timed out.")
        return False
    except Exception as e:
        await channel.send(f"LuckyBird login failed. Error: {e}")
        return False

# ───────────────────────────────────────────────────────────
# Public entry point for the Discord command
# ───────────────────────────────────────────────────────────
async def luckybird_entry(ctx, driver, bot, channel):
    """
    Run the flow. If navigation fails (likely not logged in),
    authenticate and retry the flow once.
    """
    # First attempt: try to post a result without forcing auth
    ok = await luckybird_flow(ctx, driver, channel)
    if ok:
        return

    # Flow couldn't reach UI → authenticate, then retry once
    await channel.send("Authenticating LuckyBird...")
    authed = await authenticate_luckybird(driver, bot, ctx, channel)
    if not authed:
        await channel.send("LuckyBird authentication failed.")
        return

    await channel.send("Authenticated. Checking daily bonus...")
    _ = await luckybird_flow(ctx, driver, channel)  # Post whatever result it finds
