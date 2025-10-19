# Drake Hooks
# Casino Claim 2
# Never Miss a Casino Bonus Again! A discord app for claiming social casino bonuses.

import os
import glob
import re
import time
import sqlite3
import discord
import asyncio
import traceback
import datetime
from dataclasses import dataclass, field
from datetime import datetime as dt, timedelta
from functools import wraps
from typing import Awaitable, Callable, List, Optional

from dotenv import load_dotenv

# Selenium / Chrome
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

# Discord bot
from discord import Intents, Client, Message
from discord.ext import commands

import undetected_chromedriver as uc  # (kept for other modules using it)
from seleniumbase import Driver       # (unused here but kept to avoid breaking other imports)

import importlib

# ───────────────────────────────────────────────────────────
# Dynamic API imports
# ───────────────────────────────────────────────────────────
api_modules = [
    "fortunewheelzAPI",
    "fortunecoinsAPI",   # ← Fortune Coins UC now behaves like any other API module
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
    "nolimitcoinsAPI",
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
# Selenium driver (headed, under Xvfb provided by entrypoint)
# ───────────────────────────────────────────────────────────
caps = DesiredCapabilities.CHROME
caps["goog:loggingPrefs"] = {"performance": "ALL"}

options = Options()

# Prefer instance-scoped profile prepared by entrypoint (no collisions)
instance_dir = os.getenv("CHROME_INSTANCE_DIR", "").strip()
profile_dir = os.getenv("CHROME_PROFILE_DIR", "Default").strip()

if instance_dir:
    os.makedirs(os.path.join(instance_dir, profile_dir), exist_ok=True)
    for p in glob.glob(os.path.join(instance_dir, profile_dir, "Singleton*")):
        try:
            os.remove(p)
        except Exception:
            pass
    options.add_argument(f"--user-data-dir={instance_dir}")
    options.add_argument(f"--profile-directory={profile_dir}")
else:
    # Legacy persistent profile (only if instance_dir is NOT set)
    user_data_root = os.getenv("CHROME_USER_DATA_DIR", "").strip()
    if user_data_root:
        try:
            os.makedirs(user_data_root, exist_ok=True)
            options.add_argument(f"--user-data-dir={user_data_root}")
            options.add_argument(f"--profile-directory={profile_dir}")
            print(f"[Chrome] Using persistent profile: {user_data_root} ({profile_dir})")
        except Exception as e:
            print(f"[Chrome] Failed to set user-data-dir; continuing without persistence: {e}")
    else:
        print("[Chrome] No CHROME_INSTANCE_DIR / CHROME_USER_DATA_DIR — using ephemeral session.")

# Headed/X quirks & safety
options.add_argument(f"--remote-debugging-port={9222 + (os.getpid() % 1000)}")
options.add_argument("--no-first-run")
options.add_argument("--no-default-browser-check")
options.add_argument("--disable-dev-shm-usage")

# Your existing flags
options.add_argument("--ignore-certificate-errors")
options.add_argument("--ignore-ssl-errors")
options.add_argument("disable-infobars")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--no-sandbox")
options.add_argument("--window-size=1920,1080")
options.set_capability("goog:loggingPrefs", caps["goog:loggingPrefs"])
options.add_argument("--allow-geolocation")
options.add_argument("--disable-features=DisableLoadExtensionCommandLineSwitch")
options.add_argument("--enable-third-party-cookies")
options.add_argument("--disable-notifications")

# UA pin (you can update to match your Chrome)
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit(537.36) (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
options.add_argument(f"--user-agent={user_agent}")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# ───────────────────────────────────────────────────────────
# Discord bot
# ───────────────────────────────────────────────────────────
bot = commands.Bot(command_prefix='!', intents=intents, case_insensitive=True)

# State for 2FA capture
bot.awaiting_2fa_for = None
bot.pending_2fa_code = None
bot._pending_2fa_event = asyncio.Event()

bot.remove_command("help")

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
sportzino_running = False
fortunewheelz_running = False

# ───────────────────────────────────────────────────────────
# Casino loop configuration
# ───────────────────────────────────────────────────────────

@dataclass
class CasinoLoopEntry:
    key: str
    display_name: str
    runner: Callable[[discord.abc.Messageable], Awaitable[None]]
    interval_minutes: float
    next_run: dt = field(default_factory=lambda: dt.utcnow())

    def interval_seconds(self) -> float:
        return self.interval_minutes * 60

    def schedule_next(self) -> None:
        self.next_run = dt.utcnow() + timedelta(seconds=self.interval_seconds())

async def _run_luckybird(channel: discord.abc.Messageable) -> None:
    await luckybird_entry(None, driver, bot, channel)

async def _run_zula(channel: discord.abc.Messageable) -> None:
    await zula_casino(None, driver, channel)

async def _run_sportzino(channel: discord.abc.Messageable) -> None:
    await Sportzino(None, driver, channel)

async def _run_nolimitcoins(channel: discord.abc.Messageable) -> None:
    await nolimitcoins_flow(None, driver, channel)

async def _run_funrize(channel: discord.abc.Messageable) -> None:
    await funrize_flow(None, driver, channel)

async def _run_global_poker(channel: discord.abc.Messageable) -> None:
    await global_poker(None, driver, channel)

async def _run_jefebet(channel: discord.abc.Messageable) -> None:
    await jefebet_casino(None, driver, channel)

async def _run_crowncoins(channel: discord.abc.Messageable) -> None:
    await crowncoins_casino(driver, bot, None, channel)

async def _run_modo(channel: discord.abc.Messageable) -> None:
    bonus_claimed = await claim_modo_bonus(driver, bot, None, channel)
    if not bonus_claimed:
        await check_modo_countdown(driver, bot, None, channel)

async def _run_rolling_riches(channel: discord.abc.Messageable) -> None:
    await rolling_riches_casino(None, driver, channel)

async def _run_stake(channel: discord.abc.Messageable) -> None:
    await stake_claim(driver, bot, None, channel)

async def _run_fortunewheelz(channel: discord.abc.Messageable) -> None:
    await fortunewheelz_flow(None, driver, channel)

async def _run_spinquest(channel: discord.abc.Messageable) -> None:
    await spinquest_flow(None, driver, channel)

LOOP_STAGGER_SECONDS = 30

casino_loop_entries: List[CasinoLoopEntry] = [
    CasinoLoopEntry("luckybird", "LuckyBird", _run_luckybird, 120),
    CasinoLoopEntry("zula", "Zula Casino", _run_zula, 120),
    CasinoLoopEntry("sportzino", "Sportzino", _run_sportzino, 120),
    CasinoLoopEntry("nolimitcoins", "NoLimitCoins", _run_nolimitcoins, 120),
    CasinoLoopEntry("funrize", "Funrize", _run_funrize, 120),
    CasinoLoopEntry("globalpoker", "GlobalPoker", _run_global_poker, 120),
    CasinoLoopEntry("jefebet", "JefeBet", _run_jefebet, 120),
    CasinoLoopEntry("crowncoins", "CrownCoinsCasino", _run_crowncoins, 120),
    CasinoLoopEntry("modo", "Modo", _run_modo, 120),
    CasinoLoopEntry("rollingriches", "Rolling Riches", _run_rolling_riches, 120),
    CasinoLoopEntry("stake", "Stake", _run_stake, 120),
    CasinoLoopEntry("fortunewheelz", "Fortune Wheelz", _run_fortunewheelz, 480),
    CasinoLoopEntry("spinquest", "SpinQuest", _run_spinquest, 480),
]

main_loop_task: Optional[asyncio.Task] = None
main_loop_running: bool = False

MANUAL_CASINO_COMMANDS = {
    "chumba",
    "rollingriches",
    "jefebet",
    "spinpals",
    "spinquest",
    "funrize",
    "fortunewheelz",
    "stake",
    "chanced",
    "luckybird",
    "globalpoker",
    "crowncoins",
    "dingdingding",
    "modo",
    "zula",
    "sportzino",
    "nolimitcoins",
    "fortunecoins",   # ← added
}

def reset_loop_schedule() -> None:
    base_time = dt.utcnow()
    for index, entry in enumerate(casino_loop_entries):
        entry.next_run = base_time + timedelta(seconds=index * LOOP_STAGGER_SECONDS)

def get_loop_entry(key: str) -> Optional[CasinoLoopEntry]:
    key_lower = key.lower()
    for entry in casino_loop_entries:
        if entry.key.lower() == key_lower:
            return entry
    return None

def format_loop_config() -> str:
    status = "running" if is_main_loop_running() else "stopped"
    lines = [
        "🎰 **Casino loop configuration**",
        f"Status: **{status}**",
        "Order and intervals:",
    ]
    for idx, entry in enumerate(casino_loop_entries, start=1):
        lines.append(
            f"{idx}. {entry.display_name} (`{entry.key}`) – every {entry.interval_minutes:.1f} minutes"
        )
    lines.append("")
    lines.append("Use `!config interval <casino> <minutes>` to change an interval.")
    lines.append("Use `!config order <casino1> <casino2> ...>` to set a new run order.")
    return "\n".join(lines)

def is_main_loop_running() -> bool:
    return main_loop_running and main_loop_task is not None and not main_loop_task.done()

async def run_main_loop(channel: discord.abc.Messageable) -> None:
    global main_loop_running
    try:
        while main_loop_running:
            for entry in casino_loop_entries:
                now = dt.utcnow()
                if now >= entry.next_run:
                    try:
                        await entry.runner(channel)
                    except Exception as exc:
                        print(f"[Loop] Error while running {entry.display_name}: {exc}")
                        try:
                           print(f"⚠️ Error while running {entry.display_name}: {exc}")
                        except Exception:
                            pass
                    finally:
                        entry.schedule_next()
            await asyncio.sleep(5)
    except asyncio.CancelledError:
        pass
    finally:
        main_loop_running = False

async def start_main_loop(channel: Optional[discord.abc.Messageable] = None) -> bool:
    global main_loop_task, main_loop_running
    if is_main_loop_running():
        return False
    if channel is None:
        channel = bot.get_channel(DISCORD_CHANNEL)
    if channel is None:
        print("[Loop] Unable to start main loop – channel not found.")
        return False
    reset_loop_schedule()
    main_loop_running = True
    main_loop_task = asyncio.create_task(run_main_loop(channel))
    return True

async def stop_main_loop() -> bool:
    global main_loop_task, main_loop_running
    if not is_main_loop_running():
        return False
    main_loop_running = False
    if main_loop_task:
        main_loop_task.cancel()
        try:
            await main_loop_task
        except asyncio.CancelledError:
            pass
    main_loop_task = None
    return True

@bot.check
async def prevent_manual_casino_commands(ctx: commands.Context) -> bool:
    if ctx.command is None:
        return True
    if is_main_loop_running() and ctx.command.name.lower() in MANUAL_CASINO_COMMANDS:
        await ctx.send(
            "The automated casino loop is running. Use `!stop` before manually checking casinos."
        )
        return False
    return True

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
    if await start_main_loop(channel):
        try:
            await channel.send("Casino loop started with current configuration.")
        except Exception:
            pass

# ───────────────────────────────────────────────────────────
# Commands
# ───────────────────────────────────────────────────────────

@bot.command(name="start")
async def start_loop_command(ctx: commands.Context):
    started = await start_main_loop()
    if started:
        await ctx.send("Casino loop started.")
    elif is_main_loop_running():
        await ctx.send("Casino loop is already running.")
    else:
        await ctx.send("Casino loop could not start. Check the configured channel.")

@bot.command(name="stop")
async def stop_loop_command(ctx: commands.Context):
    stopped = await stop_main_loop()
    if stopped:
        await ctx.send("Casino loop stopped. You can run manual casino commands now.")
    else:
        await ctx.send("Casino loop is not currently running.")

@bot.group(name="config", invoke_without_command=True)
async def config_group(ctx: commands.Context):
    await ctx.send(format_loop_config())

@config_group.command(name="interval")
async def config_interval(ctx: commands.Context, casino: str, minutes: float):
    entry = get_loop_entry(casino)
    if entry is None:
        await ctx.send(f"Casino `{casino}` is not part of the automated loop.")
        return
    if minutes <= 0:
        await ctx.send("Interval must be greater than zero.")
        return
    entry.interval_minutes = minutes
    entry.next_run = dt.utcnow()
    await ctx.send(f"Updated {entry.display_name} to run every {minutes:.1f} minutes.")

@config_group.command(name="order")
async def config_order(ctx: commands.Context, *casinos: str):
    if not casinos:
        await ctx.send("Provide the complete list of casino keys in the desired order.")
        return
    desired_order = [name.lower() for name in casinos]
    current_keys = [entry.key for entry in casino_loop_entries]
    if len(desired_order) != len(current_keys):
        await ctx.send("You must specify every casino exactly once when reordering the loop.")
        return
    if set(desired_order) != set(current_keys):
        missing = set(current_keys) - set(desired_order)
        extra = set(desired_order) - set(current_keys)
        parts = []
        if missing:
            parts.append("missing: " + ", ".join(sorted(missing)))
        if extra:
            parts.append("unknown: " + ", ".join(sorted(extra)))
        await ctx.send("Unable to reorder – " + "; ".join(parts))
        return
    lookup = {entry.key: entry for entry in casino_loop_entries}
    new_order = [lookup[key] for key in desired_order]
    casino_loop_entries[:] = new_order
    reset_loop_schedule()
    await ctx.send("Casino loop order updated.\n" + format_loop_config())

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
    driver.get("chrome://version/")
    await asyncio.sleep(2)
    try:
        version_raw = driver.find_element(By.ID, "version").text
        version_num = version_raw.split()[0]
    except Exception:
        version_num = "unknown 🤷"
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
    !start - Start the automated casino loop
    !stop - Stop the automated casino loop
    !config - View or edit the casino loop order and intervals

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
            if getattr(bot, "awaiting_2fa_for", None):
                bot.pending_2fa_code = text
                try:
                    bot._pending_2fa_event.set()
                except Exception:
                    bot._pending_2fa_event = asyncio.Event()
                    bot._pending_2fa_event.set()
            else:
                bot.two_fa_code = text
                print(f"[2FA] Stored code (legacy): {bot.two_fa_code}")
    await bot.process_commands(message)

async def wait_for_2fa(site_name: str, timeout: int = 90) -> Optional[str]:
    """Wait for a 2FA code up to `timeout` seconds; ensures only one waiter at a time."""
    if bot.awaiting_2fa_for:
        return None
    bot.awaiting_2fa_for = site_name
    bot.pending_2fa_code = None
    bot._pending_2fa_event = asyncio.Event()
    try:
        await asyncio.wait_for(bot._pending_2fa_event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        code = None
    else:
        code = bot.pending_2fa_code
    bot.awaiting_2fa_for = None
    bot.pending_2fa_code = None
    bot._pending_2fa_event = asyncio.Event()
    return code

# ───────────────────────────────────────────────────────────
# Decorator for casino commands (simple error wrapper + nice message)
# ───────────────────────────────────────────────────────────
def casino_command_handler(display_name: str):
    """Wrap a bot command so errors are caught and reported nicely."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            ctx = args[0] if args else None
            try:
                return await func(*args, **kwargs)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                traceback.print_exc()
                if ctx is not None:
                    try:
                        await ctx.send(f"⚠️ {display_name} error: {e}")
                    except Exception:
                        pass
        return wrapper
    return decorator

# ── Site Commands ──────────────────────────────────────────

@bot.command(name="chumba")
@casino_command_handler("Chumba")
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
@casino_command_handler("Rolling Riches")
async def rollingriches(ctx):
    await ctx.send("Checking Rolling Riches for Bonus...")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await rolling_riches_casino(ctx, driver, channel)

@bot.command(name="JefeBet")
@casino_command_handler("JefeBet")
async def jefebet(ctx):
    await ctx.send("Checking JefeBet for Bonus...")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await jefebet_casino(ctx, driver, channel)

@bot.command(name="SpinPals")
@casino_command_handler("SpinPals")
async def spinpals(ctx):
    await ctx.send("Checking SpinPals for Bonus...")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await spinpals_flow(ctx, driver, channel)

@bot.command(name="SpinQuest")
@casino_command_handler("SpinQuest")
async def spinquest(ctx):
    await ctx.send("Checking SpinQuest for Bonus...")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await spinquest_flow(ctx, driver, channel)

@bot.command(name="Funrize")
@casino_command_handler("Funrize")
async def funrize(ctx):
    global funrize_task
    if not funrize_task or funrize_task.done():
        await ctx.send("Checking Funrize for Bonus...")
        channel = bot.get_channel(DISCORD_CHANNEL)
        await funrize_flow(ctx, driver, channel)
    else:
        await ctx.send("Funrize automation is already running.")

@bot.command(name="FortuneWheelz")
@casino_command_handler("Fortune Wheelz")
async def fortunewheelz(ctx):
    global fortunewheelz_task
    if not fortunewheelz_task or fortunewheelz_task.done():
        await ctx.send("Checking Fortune Wheelz for Bonus...")
        channel = bot.get_channel(DISCORD_CHANNEL)
        await fortunewheelz_flow(ctx, driver, channel)
    else:
        await ctx.send("Fortune Wheelz automation is already running.")

@bot.command(name="Stake")
@casino_command_handler("Stake")
async def stake(ctx):
    await ctx.send("Checking Stake for Bonus...")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await stake_claim(driver, bot, ctx, channel)

@bot.command(name="chanced")
@casino_command_handler("Chanced")
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
@casino_command_handler("LuckyBird")
async def luckybird_command(ctx):
    channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL")))
    await ctx.send("Checking LuckyBird or Bonus...")
    await luckybird_entry(ctx, driver, bot, channel)

@bot.command(name="globalpoker")
@casino_command_handler("GlobalPoker")
async def global_poker_command(ctx):
    global globalpoker_running
    if not globalpoker_running:
        await ctx.send("Checking GlobalPoker for Bonus...")
        globalpoker_running = True
        channel = bot.get_channel(DISCORD_CHANNEL)
        try:
            await global_poker(ctx, driver, channel)
        finally:
            globalpoker_running = False
    else:
        await ctx.send("GlobalPoker automation is already running.")

@bot.command(name="CrownCoins")
@casino_command_handler("Crown Coins Casino")
async def crowncoinscasino(ctx):
    await ctx.send("Checking Crown Coins Casino for Bonus...")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await crowncoins_casino(driver, bot, ctx, channel)

@bot.command(name="dingdingding")
@casino_command_handler("DingDingDing")
async def DingDingDing(ctx):
    await ctx.send("Checking DingDingDing for bonus...")
    channel = bot.get_channel(DISCORD_CHANNEL)
    bonus_claimed = await claim_dingdingding_bonus(driver, bot, ctx, channel)
    if not bonus_claimed:
        await check_dingdingding_countdown(driver, bot, ctx, channel)

@bot.command(name="modo")
@casino_command_handler("Modo")
async def modo(ctx):
    await ctx.send("Checking Modo for bonus...")
    channel = bot.get_channel(DISCORD_CHANNEL)
    bonus_claimed = await claim_modo_bonus(driver, bot, ctx, channel)
    if not bonus_claimed:
        await check_modo_countdown(driver, bot, ctx, channel)

@bot.command(name="Zula")
@casino_command_handler("Zula")
async def zula(ctx):
    await ctx.send("Checking Zula Casino for Bonus...")
    await zula_casino(driver, bot, ctx)

@bot.command(name="Sportzino")
@casino_command_handler("Sportzino")
async def sportzino(ctx):
    await ctx.send("Checking Sportzino for Bonus...")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await Sportzino(ctx, driver, channel)

@bot.command(name="nolimitcoins", aliases=["nlc"])
@casino_command_handler("NoLimitCoins")
async def nolimitcoins(ctx):
    """Check NoLimitCoins for a claim or report the countdown."""
    await ctx.send("Checking NoLimitCoins for bonus...")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await nolimitcoins_flow(ctx, driver, channel)

# NEW: Fortune Coins (UC) as a standard API-driven command
@bot.command(name="fortunecoins")
@casino_command_handler("FortuneCoins")
async def fortunecoins(ctx):
    channel = bot.get_channel(DISCORD_CHANNEL)
    if 'fortunecoins_uc' in globals() and callable(fortunecoins_uc):
        await ctx.send("Checking Fortune Coins for bonus (UC)…")
        await fortunecoins_uc(ctx, channel)
    else:
        await ctx.send("Fortune Coins module not available on this build.")

# ── Auth router ────────────────────────────────────────────
@bot.command(name="auth")
async def authenticate_command(ctx, site: str, method: str = None):
    channel = bot.get_channel(DISCORD_CHANNEL)
    norm_site = re.sub(r"\s+", "", site.lower())

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

    elif norm_site == "dingdingding":
        await ctx.send("Authenticating DingDingDing...")
        ok = await authenticate_dingdingding(driver, bot, ctx, channel)
        if not ok:
            screenshot_path = "dingdingding_auth_failed.png"
            driver.save_screenshot(screenshot_path)
            await ctx.send("Authentication failed. Unable to proceed.", file=discord.File(screenshot_path))
            os.remove(screenshot_path)

    elif norm_site == "modo":
        await ctx.send("Authenticating Modo...")
        ok = await authenticate_modo(driver, bot, ctx, channel)
        if not ok:
            screenshot_path = "modo_auth_failed.png"
            driver.save_screenshot(screenshot_path)
            await ctx.send("Modo authentication failed. Unable to proceed.", file=discord.File(screenshot_path))
            os.remove(screenshot_path)

    elif norm_site == "stake":
        await ctx.send("Authenticating Stake...")
        ok = await stake_auth(driver, bot, ctx, channel)
        if not ok:
            screenshot_path = "stake_auth_failed.png"
            driver.save_screenshot(screenshot_path)
            await ctx.send("Stake authentication failed. Unable to proceed.", file=discord.File(screenshot_path))
            os.remove(screenshot_path)

    elif norm_site == "luckybird":
        await ctx.send("Authenticating LuckyBird...")
        ok = await authenticate_luckybird(driver, bot, ctx, channel)
        if not ok:
            screenshot_path = "luckybird_auth_failed.png"
            driver.save_screenshot(screenshot_path)
            await ctx.send("LuckyBird authentication failed. Unable to proceed.", file=discord.File(screenshot_path))
            os.remove(screenshot_path)

    elif norm_site in {"nolimit", "nolimitcoins", "nlc", "nolimitcoins"}:
        if method is None:
            await ctx.send("Please specify the authentication method: `google` or `env`.")
            return
        if method.lower() == "google":
            await ctx.send("Authenticating NoLimitCoins using Google...")
            ok = await auth_nolimit_google(driver, channel, ctx)
            if not ok:
                screenshot_path = "nolimit_google_auth_failed.png"
                driver.save_screenshot(screenshot_path)
                await ctx.send("", file=discord.File(screenshot_path))
                os.remove(screenshot_path)
        elif method.lower() == "env":
            await ctx.send("Authenticating NoLimitCoins using .env credentials...")
            ok = await auth_nolimit_env(driver, channel, ctx)
            if not ok:
                screenshot_path = "nolimit_env_auth_failed.png"
                driver.save_screenshot(screenshot_path)
                await ctx.send("", file=discord.File(screenshot_path))
                os.remove(screenshot_path)
        else:
            await ctx.send("Invalid authentication method. Use `google` or `env`.")

    else:
        await ctx.send(f"Authentication for '{site}' is not implemented.")

# ─────────────────────────────────────────────────────────────────────────────
# Run bot
# ─────────────────────────────────────────────────────────────────────────────
bot.run(DISCORD_TOKEN)
