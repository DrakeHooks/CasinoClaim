# Drake Hooks
# Casino Claim 2
# Never Miss a Casino Bonus Again! A discord app for claiming social casino bonuses.

import os
import glob
import re
import time
import discord
import asyncio
import importlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Awaitable, Callable, List, Optional

from dotenv import load_dotenv

# ───────────────────────────────────────────────────────────
# Selenium / Chrome
# ───────────────────────────────────────────────────────────
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from webdriver_manager.chrome import ChromeDriverManager

# Discord
from discord import Intents
from discord.ext import commands

# (other modules may use these; imports are harmless here)
import undetected_chromedriver as uc  # noqa: F401

# ───────────────────────────────────────────────────────────
# Dynamic API imports
# (only names are referenced in runners; missing ones are OK)
# ───────────────────────────────────────────────────────────
api_modules = [
    "fortunewheelzAPI",   # <- fixed and guarded below
    "fortunecoinsAPI",
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
# Selenium driver (headed; Xvfb is started by entrypoint.sh)
# ───────────────────────────────────────────────────────────
from selenium.common.exceptions import SessionNotCreatedException

caps = DesiredCapabilities.CHROME
caps["goog:loggingPrefs"] = {"performance": "ALL"}

options = Options()

instance_dir = os.getenv("CHROME_INSTANCE_DIR", "").strip()
profile_dir  = os.getenv("CHROME_PROFILE_DIR", "Default").strip()

def _clean_chrome_locks(root: str, profile: str) -> None:
    """Delete Chrome lock files that make Chrome think the profile is in use."""
    try:
        # root-level locks (e.g., /data/chrome/Singleton*)
        for pat in ("Singleton*",):
            for p in glob.glob(os.path.join(root, pat)):
                try: os.remove(p)
                except Exception: pass
        # profile-level locks (e.g., /data/chrome/Default/Singleton*)
        prof_path = os.path.join(root, profile)
        os.makedirs(prof_path, exist_ok=True)
        for pat in ("Singleton*",):
            for p in glob.glob(os.path.join(prof_path, pat)):
                try: os.remove(p)
                except Exception: pass
        # sometimes a stale DevToolsActivePort file shows up in the profile root
        for p in ("DevToolsActivePort",):
            fp = os.path.join(prof_path, p)
            if os.path.exists(fp):
                try: os.remove(fp)
                except Exception: pass
    except Exception:
        pass

def _apply_common_chrome_flags(opts: Options) -> None:
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--enable-third-party-cookies")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-features=DisableLoadExtensionCommandLineSwitch")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--ignore-certificate-errors")
    opts.add_argument("--ignore-ssl-errors")
    opts.add_argument("disable-infobars")
    opts.add_argument(f"--remote-debugging-port={9222 + (os.getpid() % 1000)}")
    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36")
    opts.add_argument(f"--user-agent={ua}")
    opts.set_capability("goog:loggingPrefs", caps["goog:loggingPrefs"])

# Prefer persistent profile if provided
if instance_dir:
    print(f"[Chrome] Profile Root: {instance_dir}  Profile Dir: {profile_dir}")
    _clean_chrome_locks(instance_dir, profile_dir)
    options.add_argument(f"--user-data-dir={instance_dir}")
    options.add_argument(f"--profile-directory={profile_dir}")
else:
    user_data_root = os.getenv("CHROME_USER_DATA_DIR", "").strip()
    if user_data_root:
        print(f"[Chrome] Profile Root: {user_data_root}  Profile Dir: {profile_dir}")
        _clean_chrome_locks(user_data_root, profile_dir)
        options.add_argument(f"--user-data-dir={user_data_root}")
        options.add_argument(f"--profile-directory={profile_dir}")
    else:
        print("[Chrome] No persistent profile configured (ephemeral session).")

# Optional CRX
crx_path = "/temp/CAPTCHA-Solver-auto-hCAPTCHA-reCAPTCHA-freely-Chrome-Web-Store.crx"
if os.path.exists(crx_path):
    options.add_extension(crx_path)

_apply_common_chrome_flags(options)

def _build_driver_with_retry(opts: Options):
    """Create the Chrome driver; if Chrome says 'profile in use', force-unlock and retry once."""
    try:
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    except SessionNotCreatedException as e:
        msg = str(e)
        if "user data directory is already in use" in msg:
            # Try one more time after an aggressive cleanup.
            root = instance_dir or os.getenv("CHROME_USER_DATA_DIR", "").strip()
            prof = profile_dir
            if root:
                print("[Chrome] Retrying after force-unlock of profile…")
                _clean_chrome_locks(root, prof)
                time.sleep(1.0)
                return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
        raise  # not that error or second attempt also failed

driver = _build_driver_with_retry(options)


# ───────────────────────────────────────────────────────────
# Discord bot
# ───────────────────────────────────────────────────────────
bot = commands.Bot(command_prefix="!", intents=intents, case_insensitive=True)
bot.remove_command("help")

# 2FA capture plumbing (shared by APIs that ask for codes)
bot.awaiting_2fa_for = None
bot.pending_2fa_code = None
bot._pending_2fa_event = asyncio.Event()

@bot.event
async def on_message(message: discord.Message):
    if message.channel.id == DISCORD_CHANNEL:
        text = message.content.strip()
        if text.isdigit() and 5 <= len(text) <= 8:
            if getattr(bot, "awaiting_2fa_for", None):
                bot.pending_2fa_code = text
                try:
                    bot._pending_2fa_event.set()
                except Exception:
                    bot._pending_2fa_event = asyncio.Event()
                    bot._pending_2fa_event.set()
            else:
                bot.two_fa_code = text  # legacy fallback
                print(f"[2FA] Stored code (legacy): {bot.two_fa_code}")
    await bot.process_commands(message)

async def wait_for_2fa(site_name: str, timeout: int = 90) -> Optional[str]:
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
# Loop runner with hard per-casino timeouts
# ───────────────────────────────────────────────────────────
@dataclass
class CasinoLoopEntry:
    key: str
    display_name: str
    runner: Callable[[discord.abc.Messageable], Awaitable[None]]
    interval_minutes: float
    next_run: datetime = field(default_factory=lambda: datetime.utcnow())

    def schedule_next(self):
        self.next_run = datetime.utcnow() + timedelta(minutes=self.interval_minutes)

LOOP_STAGGER_SECONDS = 30
PER_CASINO_TIMEOUT_SEC = int(os.getenv("CASINO_TIMEOUT_SECONDS", "400"))  # hard cap
MAIN_TICK_SLEEP = 5

async def _run_luckybird(channel):      await luckybird_entry(None, driver, bot, channel)
async def _run_zula(channel):           await zula_casino(None, driver, channel)
async def _run_sportzino(channel):      await Sportzino(None, driver, channel)
async def _run_nlc(channel):            await nolimitcoins_flow(None, driver, channel)
async def _run_funrize(channel):        await funrize_flow(None, driver, channel)
async def _run_globalpoker(channel):    await global_poker(None, driver, channel)
async def _run_jefebet(channel):        await jefebet_casino(None, driver, channel)
async def _run_crowncoins(channel):     await crowncoins_casino(driver, bot, None, channel)
async def _run_modo(channel):
    ok = await claim_modo_bonus(driver, bot, None, channel)
    if not ok:
        await check_modo_countdown(driver, bot, None, channel)
async def _run_rollingriches(channel):  await rolling_riches_casino(None, driver, channel)
async def _run_stake(channel):          await stake_claim(driver, bot, None, channel)
async def _run_fortunewheelz(channel):  await fortunewheelz_flow(None, driver, channel)
async def _run_spinquest(channel):      await spinquest_flow(None, driver, channel)

casino_loop_entries: List[CasinoLoopEntry] = [
    CasinoLoopEntry("luckybird",     "LuckyBird",         _run_luckybird,      120),
    CasinoLoopEntry("zula",          "Zula Casino",       _run_zula,           120),
    CasinoLoopEntry("sportzino",     "Sportzino",         _run_sportzino,      120),
    CasinoLoopEntry("nolimitcoins",  "NoLimitCoins",      _run_nlc,            120),
    CasinoLoopEntry("funrize",       "Funrize",           _run_funrize,        120),
    CasinoLoopEntry("globalpoker",   "GlobalPoker",       _run_globalpoker,    120),
    CasinoLoopEntry("jefebet",       "JefeBet",           _run_jefebet,        120),
    CasinoLoopEntry("crowncoins",    "CrownCoinsCasino",  _run_crowncoins,     120),
    CasinoLoopEntry("modo",          "Modo",              _run_modo,           120),
    CasinoLoopEntry("rollingriches", "Rolling Riches",    _run_rollingriches,  120),
    CasinoLoopEntry("stake",         "Stake",             _run_stake,          120),
    CasinoLoopEntry("fortunewheelz", "Fortune Wheelz",    _run_fortunewheelz,  480),
    CasinoLoopEntry("spinquest",     "SpinQuest",         _run_spinquest,      480),
]

def reset_loop_schedule():
    base = datetime.utcnow()
    for i, entry in enumerate(casino_loop_entries):
        entry.next_run = base + timedelta(seconds=i * LOOP_STAGGER_SECONDS)

main_loop_task: Optional[asyncio.Task] = None
main_loop_running = False

def is_main_loop_running() -> bool:
    return main_loop_running and main_loop_task and not main_loop_task.done()

async def run_main_loop(channel: discord.abc.Messageable):
    global main_loop_running
    try:
        while main_loop_running:
            now = datetime.utcnow()
            for entry in casino_loop_entries:
                if now >= entry.next_run:
                    try:
                        # HARD TIMEOUT (prevents Discord heartbeat blocking)
                        await asyncio.wait_for(entry.runner(channel), timeout=PER_CASINO_TIMEOUT_SEC)
                    except asyncio.TimeoutError:
                        try:
                            await channel.send(f"⏳ {entry.display_name} timed out after {PER_CASINO_TIMEOUT_SEC}s. Skipping.")
                        except Exception:
                            pass
                        print(f"[Loop] {entry.display_name} timed out.")
                    except Exception as e:
                        print(f"[Loop] Error in {entry.display_name}: {e}")
                    finally:
                        entry.schedule_next()
            await asyncio.sleep(MAIN_TICK_SLEEP)
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
        print("[Loop] Cannot start, channel not found.")
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

# ───────────────────────────────────────────────────────────
# Commands
# ───────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"Bot has connected as {bot.user}")
    channel = bot.get_channel(DISCORD_CHANNEL)
    if channel:
        await channel.send("Discord bot has started…")
        # give the gateway a moment before we start scheduling
        await asyncio.sleep(10)
        if await start_main_loop(channel):
            await channel.send("🎰 Casino loop started with current configuration.")
    else:
        print("Invalid DISCORD_CHANNEL")

MANUAL_CASINO_COMMANDS = {
    "chumba","rollingriches","jefebet","spinpals","spinquest","funrize",
    "fortunewheelz","stake","chanced","luckybird","globalpoker","crowncoins",
    "dingdingding","modo","zula","sportzino","nolimitcoins"
}

@bot.check
async def prevent_manual_casino_commands(ctx: commands.Context) -> bool:
    if ctx.command is None:  # not a command
        return True
    if is_main_loop_running() and ctx.command.name.lower() in MANUAL_CASINO_COMMANDS:
        await ctx.send("The automated casino loop is running. Use `!stop` before manually checking casinos.")
        return False
    return True

@bot.command(name="start")
async def start_loop_command(ctx: commands.Context):
    started = await start_main_loop()
    if started: await ctx.send("Casino loop started.")
    elif is_main_loop_running(): await ctx.send("Casino loop is already running.")
    else: await ctx.send("Casino loop could not start (channel missing).")

@bot.command(name="stop")
async def stop_loop_command(ctx: commands.Context):
    stopped = await stop_main_loop()
    if stopped: await ctx.send("Casino loop stopped. You can run manual casino commands now.")
    else: await ctx.send("Casino loop is not currently running.")

def format_loop_config() -> str:
    status = "running" if is_main_loop_running() else "stopped"
    lines = ["🎛️ **Casino loop configuration**", f"Status: **{status}**", "Order and intervals:"]
    for i, e in enumerate(casino_loop_entries, 1):
        lines.append(f"{i}. {e.display_name} (`{e.key}`) – every {e.interval_minutes:.1f} minutes")
    lines += ["", "Use `!config interval <casino> <minutes>` to change an interval.",
              "Use `!config order <casino1> <casino2> ...>` to set a new run order."]
    return "\n".join(lines)

@commands.group(name="config", invoke_without_command=True)
async def _config(ctx: commands.Context):
    await ctx.send(format_loop_config())
bot.add_command(_config)

@_config.command(name="interval")
async def config_interval(ctx: commands.Context, casino: str, minutes: float):
    target = next((e for e in casino_loop_entries if e.key.lower()==casino.lower()), None)
    if not target:
        await ctx.send(f"Casino `{casino}` is not part of the automated loop.")
        return
    if minutes <= 0:
        await ctx.send("Interval must be greater than zero.")
        return
    target.interval_minutes = minutes
    target.next_run = datetime.utcnow()
    await ctx.send(f"Updated {target.display_name} to run every {minutes:.1f} minutes.")

@_config.command(name="order")
async def config_order(ctx: commands.Context, *casinos: str):
    if not casinos:
        await ctx.send("Provide the complete list of casino keys in the desired order.")
        return
    desired = [c.lower() for c in casinos]
    current = [e.key for e in casino_loop_entries]
    if len(desired) != len(current) or set(desired) != set(current):
        await ctx.send(f"You must include each of: {', '.join(current)} (exactly once).")
        return
    lookup = {e.key:e for e in casino_loop_entries}
    casino_loop_entries[:] = [lookup[k] for k in desired]
    reset_loop_schedule()
    await ctx.send("Casino loop order updated.\n" + format_loop_config())

@bot.command(name="ping")
async def ping(ctx): await ctx.send("Pong")

@bot.command(name="about")
async def about(ctx):
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
    await ctx.send(f"🧩 **Chrome build:** `{version_num}`", file=discord.File(snap))
    os.remove(snap)

@bot.command(name="restart")
async def restart(ctx):
    await ctx.send("Restarting…")
    await bot.close()
    os._exit(0)

# ───────────────────────────────────────────────────────────
# Run bot
# ───────────────────────────────────────────────────────────
bot.run(DISCORD_TOKEN)
