# Drake Hooks
# Casino Claim 2
# Never Miss a Casino Bonus Again! A discord app for claiming social casino bonuses.

import os
from datetime import datetime, timedelta
import time
import re
import sqlite3
import discord
import asyncio

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.common.exceptions import NoSuchElementException, TimeoutException

import datetime
from dotenv import load_dotenv
import undetected_chromedriver as uc
from discord import Intents, Client, Message
from discord.ext import commands, tasks
from seleniumbase import Driver
from selenium.webdriver.common.action_chains import ActionChains

import importlib

# ───────────────────────────────────────────────────────────
# Dynamic API imports
# ───────────────────────────────────────────────────────────
api_modules = [
    "fortunewheelzAPI",
    "stakeAPI",
    "modoAPI",
    "googleauthAPI",
    "chancedAPI",
    "rollingrichesAPI",
    "jefebetAPI",
    "spinpalsAPI",
    "spinquestAPI",
    "funrizeAPI",
    "globalpokerAPI",
    "dingdingdingAPI",
    "chumbaAPI",
    "crowncoinsAPI",
    "zulaAPI",
    "luckybirdAPI",
    "sportzinoAPI",
    "nolimitcoinsAPI",   # ← NoLimitCoins
]

for module_name in api_modules:
    try:
        module = importlib.import_module(module_name)
        globals().update(vars(module))
    except Exception as e:
        print(f"Warning: Failed to import {module_name}: {e}")

# ───────────────────────────────────────────────────────────
# Env & Discord setup
# ───────────────────────────────────────────────────────────
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL = int(os.getenv("DISCORD_CHANNEL"))

intents = Intents.default()
intents.message_content = True

# ───────────────────────────────────────────────────────────
# Selenium driver
# ───────────────────────────────────────────────────────────
caps = DesiredCapabilities.CHROME
caps["goog:loggingPrefs"] = {"performance": "ALL"}

options = Options()
options.add_argument('--ignore-certificate-errors')
options.add_argument('--ignore-ssl-errors')
options.add_argument("disable-infobars")
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_argument('--no-sandbox')
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit(537.36) (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
options.add_argument(f"--user-agent={user_agent}")

# IMPORTANT. If you need custom user data dir for extensions, uncomment here and in Dockerfile.
# user_data_dir = "/temp/google-chrome/"
# options.add_argument(f"--user-data-dir={user_data_dir}")
options.add_argument("--window-size=1920,1080")
options.add_argument("--no-first-run")
options.set_capability("goog:loggingPrefs", caps["goog:loggingPrefs"])
options.add_argument("--allow-geolocation")
options.add_argument("--disable-features=DisableLoadExtensionCommandLineSwitch")
options.add_argument("--enable-third-party-cookies")
options.add_extension('/temp/CAPTCHA-Solver-auto-hCAPTCHA-reCAPTCHA-freely-Chrome-Web-Store.crx')
options.add_argument('--disable-notifications')

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# ───────────────────────────────────────────────────────────
# Discord bot
# ───────────────────────────────────────────────────────────
bot = commands.Bot(command_prefix='!', intents=intents, case_insensitive=True)
# after bot = commands.Bot(...)
bot.awaiting_2fa_for = None        # site name we're waiting for, e.g. "luckybird"
bot.pending_2fa_code = None        # the captured code (string) when available
bot._pending_2fa_event = asyncio.Event()  # event used to wake up waiting coroutine

bot.remove_command("help")
# bot.two_fa_code = None  # Variable to store the 2FA code

# Authentication flags
auth_status = {
    "dingdingding": False,
    "modo": False,
    "stake": False,
    "luckybird": False,
}

# Task handles
chanced_casino_task = None
luckybird_task = None
globalpoker_task = None
CrownCoinsCasino_task = None
chumba_task = None
dingdingding_task = None
stake_task = None
zula_task = None
rollingriches_task = None
jefebet_task = None
spinpals_task = None
spinquest_task = None
funrize_task = None
sportzino_task = None
fortunewheelz_task = None

# Running flags
chanced_casino_running = False
luckybird_running = False
globalpoker_running = False
CrownCoinsCasino_running = False
chumba_running = False
dingdingding_running = False
stake_running = False
zula_running = False
rollingriches_running = False
jefebet_running = False
spinpals_running = False
spinquest_running = False
funrize_running = False
funrize_running = False
sportzino_running = False
fortunewheelz_running = False
# ───────────────────────────────────────────────────────────
# Bot events
# ───────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"Bot has connected as {bot.user}")

    channel = bot.get_channel(DISCORD_CHANNEL)
    if channel:
        await channel.send("Discord bot has started...")
    else:
        print("Invalid DISCORD_CHANNEL")

    # Start loops
    await asyncio.sleep(60)
    if not casino_loop.is_running():
        casino_loop.start()
    await asyncio.sleep(1800)
    if not eighthour_loop.is_running():
        eighthour_loop.start()

# ───────────────────────────────────────────────────────────
# Commands
# ───────────────────────────────────────────────────────────
@bot.command(name="ping")
async def ping(ctx):
    await ctx.send("Pong")

@bot.command(name="captcha")
async def captcha(ctx):
    """Open the captcha solver extension page and send a screenshot."""
    await ctx.send("Opening captcha solver page...")
    try:
        driver.get("chrome://extensions")
        time.sleep(5)
        driver.get("chrome-extension://hlifkpholllijblknnmbfagnkjneagid/popup/popup.html#/")
        time.sleep(5)
        screenshot_path = "captcha_screenshot.png"
        driver.save_screenshot(screenshot_path)
        await ctx.send(file=discord.File(screenshot_path))
        os.remove(screenshot_path)
    except Exception as e:
        await ctx.send("Failed to capture captcha solver page.")
        print(f"Captcha command error: {e}")

@bot.command(name="about")
async def about(ctx):
    """Show the exact Chrome build that SeleniumBase UC is running."""
    await ctx.send("🔍 Retrieving Chrome version …")

    # 1) open the internal diagnostics page
    driver.get("chrome://version/")
    await asyncio.sleep(2)          # small wait so the DOM is ready

    # 2) pull the <span id="version"> text
    try:
        version_raw = driver.find_element(By.ID, "version").text
        # chrome://version/ puts lots of info; grab first word ⇒ "138.0.7204.157"
        version_num = version_raw.split()[0]
    except Exception:
        version_num = "unknown 🤷"

    # 3) screenshot for extra context / troubleshooting
    snap = "chrome_version.png"
    driver.save_screenshot(snap)

    await ctx.send(f"🧩 **Chrome build running inside the bot:** `{version_num}`",
                   file=discord.File(snap))

    os.remove(snap)


@bot.command(name="help")
async def help_cmd(ctx):
    await ctx.send("""Commands are not recommended. 
    🎰 Casino Commands: 
    !chanced - Check Chanced.com for bonus
    !luckybird - Check LuckyBird.io for bonus
    !globalpoker - Check GlobalPoker for bonus
    !crowncoins - Check CrownCoinsCasino for bonus
    !chumba - Check Chumba for bonus
    !modo - Check Modo for bonus
    !sweepslots - Check SweepSlots for bonus
    !zula - Check Zula for bonus
    !rollingriches - Check RollingRiches for bonus
    !jefebet - Check JefeBet for bonus
    !spinpals - Check SpinPals for bonus
    !spinquest - Check SpinQuest for bonus
    !funrize - Check Funrize for bonus
    !sportzino - Check Sportzino for bonus
    !fortunecoins - Check Fortunecoins for bonus
    !nolimitcoins - Check NoLimitCoins for bonus
    !fortunewheelz - Check Fortune Wheelz for bonus
    ---------------------------------------
    ⚙️ General Commands:                             
    !ping - Check if the bot is online
    !restart - Restart the bot     
    !help - Display the available commands
    !captcha - Open the captcha solver extension page            
    !stop - Stop the bot               

    ---------------------------------------
    ✅ Auth Commands:
    !auth google - Authenticate Google Account (global)
    !auth <site> - Authenticate into a specific site (e.g., Modo, DingDingDing, Stake, LuckyBird)
    !auth <site> <method> - Authenticate using a specific method
       (e.g. !auth crowncoins google, !auth crowncoins env, !auth nolimitcoins env)
    """)

async def action_notification(ctx, message):
    await ctx.send(f"Notification: {message}")

@bot.event
async def on_command_error(ctx, error):
    print(f"Command Error: {error}")
    await ctx.send(f"Command Error: {error}")
    await ctx.send("Type '!help' for a list of commands")

@bot.command(name="restart")
async def restart(ctx):
    await ctx.send("Restarting...")
    await bot.close()
    os._exit(0)

# (Deprecated wrapper) Keep old command working but point users to !auth google
@bot.command(name="googleauth")
async def googleauth(ctx):
    await ctx.send("`!googleauth` is deprecated. Use `!auth google`.")
    google_credentials = os.getenv("GOOGLE_LOGIN")
    if google_credentials:
        google_username, google_password = google_credentials.split(':', 1)
        credentials = (google_username, google_password)
    else:
        await ctx.send("Google credentials not found in .env file.")
        credentials = (None, None)
    channel = bot.get_channel(DISCORD_CHANNEL)
    await google_auth(ctx, driver, channel, credentials)

@bot.event
async def on_message(message):
    """Capture 2FA codes posted in the bot channel."""
    if message.channel.id == DISCORD_CHANNEL:
        text = message.content.strip()

        # Accept 5–8 digit numeric codes (covers most sites)
        if text.isdigit() and 5 <= len(text) <= 8:
            # Event-driven path (preferred)
            if getattr(bot, "awaiting_2fa_for", None):
                bot.pending_2fa_code = text
                try:
                    bot._pending_2fa_event.set()
                except Exception:
                    # first-run safety
                    bot._pending_2fa_event = asyncio.Event()
                    bot._pending_2fa_event.set()
            else:
                # Legacy fallback if nobody is actively waiting
                bot.two_fa_code = text
                print(f"[2FA] Stored code (legacy): {bot.two_fa_code}")

    await bot.process_commands(message)



async def wait_for_2fa(site_name: str, timeout: int = 90) -> Optional[str]:
    """
    Wait for a 2FA code for `site_name` up to `timeout` seconds.
    Returns the captured code (string) or None if timed out.
    Ensures only one waiter runs at a time.
    """
    # guard: don't let concurrent waits run
    if bot.awaiting_2fa_for:
        # someone else is already waiting
        return None

    bot.awaiting_2fa_for = site_name
    bot.pending_2fa_code = None
    # recreate/reset the event
    bot._pending_2fa_event = asyncio.Event()

    try:
        # Wait until event is set or timeout
        await asyncio.wait_for(bot._pending_2fa_event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        # timed out
        code = None
    else:
        code = bot.pending_2fa_code

    # cleanup
    bot.awaiting_2fa_for = None
    bot.pending_2fa_code = None
    # ensure event is cleared for next use
    bot._pending_2fa_event = asyncio.Event()
    return code

# ── Site Commands ──────────────────────────────────────────
@bot.command(name="chumba")
async def chumba(ctx):
    await ctx.send("Checking Chumba for Bonus...")
    driver.get("https://lobby.chumbacasino.com/")
    await asyncio.sleep(5)
    if driver.current_url.startswith("https://login.chumbacasino.com/"):
        bot.chumba_2fa_code = None
        authenticated = await authenticate_chumba(driver, bot, ctx)
        if not authenticated:
            await ctx.send("Chumba authentication failed.")
            return
    if driver.current_url.startswith("https://lobby.chumbacasino.com/"):
        await claim_chumba_bonus(driver, ctx)
        await check_chumba_countdown(driver, ctx)
    else:
        await ctx.send("Failed to reach the Chumba lobby.")

@bot.command(name="RollingRiches")
async def rollingriches(ctx):
    await ctx.send("Checking Rolling Riches for Bonus...")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await rolling_riches_casino(ctx, driver, channel)

@bot.command(name="JefeBet")
async def jefebet(ctx):
    await ctx.send("Checking JefeBet for Bonus...")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await jefebet_casino(ctx, driver, channel)

@bot.command(name="SpinPals")
async def spinpals(ctx):
    await ctx.send("Checking SpinPals for Bonus...")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await spinpals_flow(ctx, driver, channel)

@bot.command(name="SpinQuest")
async def spinquest(ctx):
    await ctx.send("Checking SpinQuest for Bonus...")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await spinquest_flow(ctx, driver, channel)

@bot.command(name="Funrize")
async def funrize(ctx):
    global funrize_task
    if not funrize_task or funrize_task.done():
        await ctx.send("Checking Funrize for Bonus...")
        channel = bot.get_channel(DISCORD_CHANNEL)
        await funrize_flow(ctx, driver, channel)
    else:
        await ctx.send("Funrize automation is already running.")

@bot.command(name="FortuneWheelz")
async def fortunewheelz(ctx):
    global fortunewheelz_task
    if not fortunewheelz_task or fortunewheelz_task.done():
        await ctx.send("Checking Fortune Wheelz for Bonus...")
        channel = bot.get_channel(DISCORD_CHANNEL)
        await fortunewheelz_flow(ctx, driver, channel)
    else:
        await ctx.send("Fortune Wheelz automation is already running.")


@bot.command(name="Stake")
async def stake(ctx):
    await ctx.send("Checking Stake for Bonus...")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await stake_claim(driver, bot, ctx, channel)

@bot.command(name="chanced")
async def chanced(ctx):
    await ctx.send("Checking Chanced.com for Bonus...")
    chanced_credentials = os.getenv("CHANCED")
    if chanced_credentials:
        chanced_username, chanced_password = chanced_credentials.split(':', 1)
        credentials = (chanced_username, chanced_password)
    else:
        credentials = (None, None)
    channel = bot.get_channel(DISCORD_CHANNEL)
    await chanced_casino(ctx, driver, channel, credentials)

@bot.command(name="luckybird")
async def luckybird_command(ctx):
    """Run LuckyBird: auth if needed, then claim or report countdown."""
    channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL")))
    await ctx.send("Checking LuckyBird or Bonus...")
    try:
        await luckybird_entry(ctx, driver, bot, channel)
    except Exception as e:
        await channel.send(f"Error running LuckyBird command: {e}")

@bot.command(name="globalpoker")
async def global_poker_command(ctx):
    global globalpoker_running
    if not globalpoker_running:
        await ctx.send("Checking GlobalPoker for Bonus...")
        globalpoker_running = True
        channel = bot.get_channel(DISCORD_CHANNEL)
        await global_poker(ctx, driver, channel)
        globalpoker_running = False
    else:
        await ctx.send("GlobalPoker automation is already running.")

@bot.command(name="CrownCoins")
async def crowncoinscasino(ctx):
    await ctx.send("Checking Crown Coins Casino for Bonus...")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await crowncoins_casino(driver, bot, ctx, channel)

@bot.command(name="dingdingding")
async def DingDingDing(ctx):
    await ctx.send("Checking DingDingDing for bonus...")
    channel = bot.get_channel(DISCORD_CHANNEL)
    bonus_claimed = await claim_dingdingding_bonus(driver, bot, ctx, channel)
    if not bonus_claimed:
        await check_dingdingding_countdown(driver, bot, ctx, channel)

@bot.command(name="modo")
async def modo(ctx):
    await ctx.send("Checking Modo for bonus...")
    channel = bot.get_channel(DISCORD_CHANNEL)
    bonus_claimed = await claim_modo_bonus(driver, bot, ctx, channel)
    if not bonus_claimed:
        await check_modo_countdown(driver, bot, ctx, channel)

@bot.command(name="Zula")
async def zula(ctx):
    await ctx.send("Checking Zula Casino for Bonus...")
    await zula_casino(driver, bot, ctx)

@bot.command(name="Sportzino")
async def sportzino(ctx):
    await ctx.send("Checking Sportzino for Bonus...")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await Sportzino(ctx, driver, channel)

@bot.command(name="nolimitcoins", aliases=["nlc"])
async def nolimitcoins(ctx):
    """Check NoLimitCoins for a claim or report the countdown."""
    await ctx.send("Checking NoLimitCoins for bonus...")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await nolimitcoins_flow(ctx, driver, channel)

# ── Auth router ────────────────────────────────────────────
@bot.command(name="auth")
async def authenticate_command(ctx, site: str, method: str = None):
    channel = bot.get_channel(DISCORD_CHANNEL)

    # Normalize site name (e.g., "no limit coins" -> "nolimitcoins")
    norm_site = re.sub(r"\s+", "", site.lower())

    # 1) Global Google auth: !auth google
    if norm_site == "google":
        await ctx.send("Authenticating Google Account...")
        google_credentials = os.getenv("GOOGLE_LOGIN")
        if google_credentials:
            google_username, google_password = google_credentials.split(":", 1)
            credentials = (google_username, google_password)
        else:
            await ctx.send("Google credentials not found in .env file.")
            credentials = (None, None)
        await google_auth(ctx, driver, channel, credentials)
        return

    # 2) CrownCoins
    elif norm_site == "crowncoins":
        if method is None:
            await ctx.send("Please specify the authentication method: `google` or `env`.")
            return
        if method.lower() == "google":
            await ctx.send("Authenticating CrownCoins using Google...")
            ok = await auth_crown_google(driver, bot, ctx, channel)
            if not ok:
                screenshot_path = "crowncoins_google_auth_failed.png"
                driver.save_screenshot(screenshot_path)
                await ctx.send("", file=discord.File(screenshot_path))
                os.remove(screenshot_path)
        elif method.lower() == "env":
            await ctx.send("Authenticating CrownCoins using .env credentials...")
            ok = await auth_crown_env(driver, bot, ctx, channel)
            if not ok:
                screenshot_path = "crowncoins_env_auth_failed.png"
                driver.save_screenshot(screenshot_path)
                await ctx.send("", file=discord.File(screenshot_path))
                os.remove(screenshot_path)
        else:
            await ctx.send("Invalid authentication method. Use `google` or `env`.")

    # 3) DingDingDing
    elif norm_site == "dingdingding":
        await ctx.send("Authenticating DingDingDing...")
        ok = await authenticate_dingdingding(driver, bot, ctx, channel)
        if not ok:
            screenshot_path = "dingdingding_auth_failed.png"
            driver.save_screenshot(screenshot_path)
            await ctx.send("Authentication failed. Unable to proceed.", file=discord.File(screenshot_path))
            os.remove(screenshot_path)

    # 4) Modo
    elif norm_site == "modo":
        await ctx.send("Authenticating Modo...")
        ok = await authenticate_modo(driver, bot, ctx, channel)
        if not ok:
            screenshot_path = "modo_auth_failed.png"
            driver.save_screenshot(screenshot_path)
            await ctx.send("Modo authentication failed. Unable to proceed.", file=discord.File(screenshot_path))
            os.remove(screenshot_path)

    # 5) Stake
    elif norm_site == "stake":
        await ctx.send("Authenticating Stake...")
        ok = await stake_auth(driver, bot, ctx, channel)
        if not ok:
            screenshot_path = "stake_auth_failed.png"
            driver.save_screenshot(screenshot_path)
            await ctx.send("Stake authentication failed. Unable to proceed.", file=discord.File(screenshot_path))
            os.remove(screenshot_path)

    # 6) LuckyBird
    elif norm_site == "luckybird":
        await ctx.send("Authenticating LuckyBird...")
        ok = await authenticate_luckybird(driver, bot, ctx, channel)
        if not ok:
            screenshot_path = "luckybird_auth_failed.png"
            driver.save_screenshot(screenshot_path)
            await ctx.send("LuckyBird authentication failed. Unable to proceed.", file=discord.File(screenshot_path))
            os.remove(screenshot_path)

    # 7) NoLimitCoins (supports multiple aliases)
    elif norm_site in {"nolimit", "nolimitcoins", "nlc", "no limit coins"}:
        if method is None:
            await ctx.send("Please specify the authentication method: `google` or `env`.")
            return

        if method.lower() == "google":
            await ctx.send("Authenticating NoLimitCoins using Google...")
            ok = await auth_nolimit_google(driver, channel, ctx)
            if ok:
                print("NoLimitCoins authentication via Google succeeded.")
            else:
                screenshot_path = "nolimit_google_auth_failed.png"
                driver.save_screenshot(screenshot_path)
                await ctx.send("", file=discord.File(screenshot_path))
                os.remove(screenshot_path)

        elif method.lower() == "env":
            await ctx.send("Authenticating NoLimitCoins using .env credentials...")
            ok = await auth_nolimit_env(driver, channel, ctx)
            if ok:
                print("NoLimitCoins authentication via .env credentials succeeded.")
            else:
                screenshot_path = "nolimit_env_auth_failed.png"
                driver.save_screenshot(screenshot_path)
                await ctx.send("", file=discord.File(screenshot_path))
                os.remove(screenshot_path)
        else:
            await ctx.send("Invalid authentication method. Use `google` or `env`.")

    # 8) Unknown
    else:
        await ctx.send(f"Authentication for '{site}' is not implemented.")







# ───────────────────────────────────────────────────────────
# Loops
# ───────────────────────────────────────────────────────────
@tasks.loop(hours=2)
async def casino_loop():
    print("Starting casino_loop...")

    channel = bot.get_channel(DISCORD_CHANNEL)
    if channel is None:
        print(f"Error: Invalid channel ID '{DISCORD_CHANNEL}' or bot is not connected.")
        return

    try:
        # Run the casino tasks sequentially with sleeps between
        try:
            await asyncio.sleep(40)
            await zula_casino(None, driver, channel)
        except Exception:
            print("Error in Zula")
            await asyncio.sleep(50)
        await asyncio.sleep(80)

        try:
            await Sportzino(None, driver, channel)
            await asyncio.sleep(50)
        except Exception:
            print("Error in Sportzino")
            await asyncio.sleep(50)
        await asyncio.sleep(80)

        # NoLimitCoins run
        try:
            await nolimitcoins_flow(None, driver, channel)
        except Exception:
            print("Error in NoLimitCoins")
        await asyncio.sleep(10)
        try:
            await funrize_flow(None, driver, channel)
        except Exception:
            print("Error in Funrize")
        await asyncio.sleep(10)
        try:
            await global_poker(None, driver, channel)
            await asyncio.sleep(10)
        except Exception:
            print("Error in GlobalPoker")
        await asyncio.sleep(10)
        try:
            await jefebet_casino(None, driver, channel)
        except Exception:
            print("Error in JefeBet")
        await asyncio.sleep(30)
        try:
            await luckybird_entry(None, driver, channel)
        except Exception:
            print("Error in LuckyBird")
        await asyncio.sleep(10)
        try:
            await crowncoins_casino(driver, bot, None, channel)
        except Exception:
            print("Error in CrownCoinsCasino")
        await asyncio.sleep(30)
        try:
            bonus_claimed = await claim_modo_bonus(driver, bot, None, channel)
            if not bonus_claimed:
                await check_modo_countdown(driver, bot, None, channel)
        except Exception:
            print("Error in Modo")
        await asyncio.sleep(100)

        await asyncio.sleep(10)
        try:
            await rolling_riches_casino(None, driver, channel)
        except Exception:
            print("Error in RollingRiches")
        try:
            await stake_claim(driver, bot, None, channel)
        except Exception:
            print("Error in Stake")

    except Exception as e:
        print(f"Error in loop: {str(e)}")




# ───────────────────────────────────────────────────────────────────────────────────────────────────────────
# Loop ran on 8 hour intervals. Helpful for casinos without countdowns or missing logic for countdown.
# ───────────────────────────────────────────────────────────────────────────────────────────────────────────
@tasks.loop(hours=8)
async def eighthour_loop():
    print("Starting Eight Hour Loop")
    channel = bot.get_channel(DISCORD_CHANNEL)
    if channel is None:
        print(f"Error: Invalid channel ID '{DISCORD_CHANNEL}' or bot is not connected.")
        return
    try:
        try:
            await fortunewheelz_flow(None, driver, channel)
        except Exception:
            print("Error in FortuneWheelz")            
        try:
            await spinquest_flow(None, driver, channel)
        except Exception:
            print("Error in SpinQuest")
    except Exception as e:
        print(f"Error in loop: {str(e)}")

# ───────────────────────────────────────────────────────────────────────────────────────────────────────────
# Run bot
# ───────────────────────────────────────────────────────────────────────────────────────────────────────────
bot.run(DISCORD_TOKEN)
