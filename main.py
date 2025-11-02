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
import datetime as dt
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
from selenium.common.exceptions import SessionNotCreatedException

# Discord
from discord import Intents
from discord.ext import commands

# (other modules may use these; imports are harmless here)
import undetected_chromedriver as uc  # noqa: F401

# ───────────────────────────────────────────────────────────
# Dynamic API imports (missing modules are OK)
# ───────────────────────────────────────────────────────────
api_modules = [
    "fortunewheelzAPI",
    "fortunecoinsAPI",  # UC flow
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
    "smilescasinoAPI",
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
caps = DesiredCapabilities.CHROME
caps["goog:loggingPrefs"] = {"performance": "ALL"}

options = Options()

instance_dir = os.getenv("CHROME_INSTANCE_DIR", "").strip()
profile_dir = os.getenv("CHROME_PROFILE_DIR", "Default").strip()

def _clean_chrome_locks(root: str, profile: str) -> None:
    """Delete Chrome lock files that make Chrome think the profile is in use."""
    try:
        for pat in ("Singleton*",):
            for p in glob.glob(os.path.join(root, pat)):
                try:
                    os.remove(p)
                except Exception:
                    pass
        prof_path = os.path.join(root, profile)
        os.makedirs(prof_path, exist_ok=True)
        for pat in ("Singleton*", "LOCK", "LOCKFILE", "Safe Browsing*"):
            for p in glob.glob(os.path.join(prof_path, pat)):
                try:
                    os.remove(p)
                except Exception:
                    pass
        for p in ("DevToolsActivePort",):
            fp = os.path.join(prof_path, p)
            if os.path.exists(fp):
                try:
                    os.remove(fp)
                except Exception:
                    pass
    except Exception:
        pass

def _apply_common_chrome_flags(opts: Options) -> None:
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--allow-geolocation")
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

# Persistent profile (prefer CHROME_INSTANCE_DIR)
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
            root = instance_dir or os.getenv("CHROME_USER_DATA_DIR", "").strip()
            prof = profile_dir
            if root:
                print("[Chrome] Retrying after force-unlock of profile…")
                _clean_chrome_locks(root, prof)
                time.sleep(1.0)
                return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
        raise

driver = _build_driver_with_retry(options)

# ───────────────────────────────────────────────────────────
# Discord bot + 2FA capture plumbing
# ───────────────────────────────────────────────────────────
bot = commands.Bot(command_prefix="!", intents=intents, case_insensitive=True)
bot.remove_command("help")

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
    next_run: dt = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))

    def schedule_next(self):
        self.next_run = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=self.interval_minutes)

LOOP_STAGGER_SECONDS = 30
PER_CASINO_TIMEOUT_SEC = int(os.getenv("CASINO_TIMEOUT_SECONDS", "500"))  # hard cap
MAIN_TICK_SLEEP = 10

async def _run_luckybird(channel):      await luckybird_entry(None, driver, bot, channel)
async def _run_zula(channel):           await zula_uc(None, channel)
async def _run_sportzino(channel):      await Sportzino(None, driver, channel)
async def _run_nlc(channel):            await nolimitcoins_flow(None, driver, channel)
async def _run_funrize(channel):        await funrize_flow(None, driver, channel)
async def _run_globalpoker(channel):    await global_poker(None, driver, channel)
async def _run_jefebet(channel):        await jefebet_casino(None, driver, channel)
async def _run_crowncoins(channel):     await crowncoins_casino(driver, bot, None, channel)
async def _run_smilescasino(channel):   await smilescasino_casino(None, driver, channel)

# Modo runner used by loop (claim → countdown)
async def _run_modo(channel):
    ok = await claim_modo_bonus(driver, bot, None, channel)
    if not ok:
        await check_modo_countdown(driver, bot, None, channel)

async def _run_rollingriches(channel):  await rolling_riches_casino(None, driver, channel)
async def _run_stake(channel):          await stake_claim(driver, bot, None, channel)
async def _run_fortunewheelz(channel):  await fortunewheelz_flow(None, driver, channel)
async def _run_spinquest(channel):      await spinquest_flow(None, driver, channel)
async def _run_fortunecoins(channel):   await fortunecoins_uc(None, channel)  # <- UC flow, 24h interval

casino_loop_entries: List[CasinoLoopEntry] = [
    CasinoLoopEntry("luckybird",     "LuckyBird",         _run_luckybird,       120),
    CasinoLoopEntry("globalpoker",   "GlobalPoker",       _run_globalpoker,     120),
    CasinoLoopEntry("jefebet",       "JefeBet",           _run_jefebet,         120),
    CasinoLoopEntry("spinquest",     "SpinQuest",         _run_spinquest,       120),
    CasinoLoopEntry("fortunewheelz", "Fortune Wheelz",    _run_fortunewheelz,   120),
    CasinoLoopEntry("nolimitcoins",  "NoLimitCoins",      _run_nlc,             120),

    # Enable when you want Modo and Stake in the loop cadence:
    # CasinoLoopEntry("modo",          "Modo",              _run_modo,            120),
    # CasinoLoopEntry("stake",         "Stake",             _run_stake,           120),

    # 24h cadence group (no countdown/problematic)
    CasinoLoopEntry("funrize",       "Funrize",           _run_funrize,         1440),
    CasinoLoopEntry("rollingriches", "Rolling Riches",    _run_rollingriches,   1440),
    CasinoLoopEntry("fortunecoins",  "Fortune Coins",     _run_fortunecoins,    1440),
    CasinoLoopEntry("zula",          "Zula Casino",       _run_zula,            1440),
    CasinoLoopEntry("sportzino",     "Sportzino",         _run_sportzino,       1440),
    CasinoLoopEntry("smilescasino",  "Smiles Casino",     _run_smilescasino,    1440),
]

def reset_loop_schedule():
    base = dt.datetime.now(dt.timezone.utc)
    for i, entry in enumerate(casino_loop_entries):
        entry.next_run = base + dt.timedelta(seconds=i * LOOP_STAGGER_SECONDS)

main_loop_task: Optional[asyncio.Task] = None
main_loop_running = False

def is_main_loop_running() -> bool:
    return main_loop_running and main_loop_task and not main_loop_task.done()

async def run_main_loop(channel: discord.abc.Messageable):
    global main_loop_running
    try:
        while main_loop_running:
            now = dt.datetime.now(dt.timezone.utc)
            for entry in casino_loop_entries:
                if now >= entry.next_run:
                    try:
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
# Modo auth maintenance (only when loop is STOPPED)
# ───────────────────────────────────────────────────────────
# REFRESH_CHECK_MINUTES = int(os.getenv("MODO_REFRESH_CHECK_MINUTES", "60"))
# modo_auth_lock = asyncio.Lock()  # serialize all modo auth attempts

# async def run_modo_auth(channel):
#     """Serialize calls to modoAPI.authenticate_modo to avoid concurrent UC sessions."""
#     async with modo_auth_lock:
#         try:
#             await authenticate_modo(driver, bot, None, channel)
#         except Exception as e:
#             print(f"[Modo Auth] error: {e}")

# async def modo_auth_maintenance():
#     """
#     Runs in the background, but only refreshes when:
#       - the main loop is NOT running, and
#       - the lock is free, and
#       - refresh is due.
#     This ensures manual !auth modo is responsive after !stop, and nothing collides.
#     """
#     await bot.wait_until_ready()
#     channel = bot.get_channel(DISCORD_CHANNEL)
#     while not bot.is_closed():
#         try:
#             if (not is_main_loop_running()
#                 and 'modo_auth_needs_refresh' in globals()
#                 and modo_auth_needs_refresh()
#                 and not modo_auth_lock.locked()):
#                 if channel:
#                     await channel.send("♻️ Background: refreshing Modo auth…")
#                 await run_modo_auth(channel)
#         except Exception as e:
#             print(f"[Modo Auth Maintenance] outer error: {e}")
#         await asyncio.sleep(REFRESH_CHECK_MINUTES * 60)

# ───────────────────────────────────────────────────────────
# Commands
# ───────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"Bot has connected as {bot.user}")
    channel = bot.get_channel(DISCORD_CHANNEL)
    if channel:
        await channel.send("Discord bot has started…")
        await asyncio.sleep(10)
        if await start_main_loop(channel):
            await channel.send("🎰 Casino loop started with current configuration.")
        # Start the background Modo refresher; it will only act when the loop is stopped.
        # asyncio.create_task(modo_auth_maintenance())
    else:
        print("Invalid DISCORD_CHANNEL")

MANUAL_CASINO_COMMANDS = {
    "chumba","rollingriches","jefebet","spinpals","spinquest","funrize",
    "fortunewheelz","stake","chanced","luckybird","globalpoker","crowncoins",
    "dingdingding","modo","zula","sportzino","nolimitcoins","fortunecoins",
    "smilescasino"
}

@bot.check
async def prevent_manual_casino_commands(ctx: commands.Context) -> bool:
    if ctx.command is None:
        return True
    if is_main_loop_running() and ctx.command.name.lower() in MANUAL_CASINO_COMMANDS:
        await ctx.send("The automated casino loop is running. Use `!stop` before manually checking casinos.")
        return False
    return True

@bot.command(name="start")
async def start_loop_command(ctx: commands.Context):
    started = await start_main_loop()
    if started:
        await ctx.send("Casino loop started.")
    elif is_main_loop_running():
        await ctx.send("Casino loop is already running.")
    else:
        await ctx.send("Casino loop could not start (channel missing).")

@bot.command(name="stop")
async def stop_loop_command(ctx: commands.Context):
    stopped = await stop_main_loop()
    if stopped:
        await ctx.send("Casino loop stopped. You can run manual casino commands now.")
    else:
        await ctx.send("Casino loop is not currently running.")


@bot.command(name="cleardatadir")
async def clear_data_dir(ctx: commands.Context):
    """
    Interactively clear the persistent Chrome user-data directory.
    This will stop the loop, quit Chrome, delete the directory, and restart the bot.
    """
    root = instance_dir or os.getenv("CHROME_USER_DATA_DIR", "").strip()
    if not root:
        await ctx.send("⚠️ No CHROME_INSTANCE_DIR or CHROME_USER_DATA_DIR configured — nothing to clear.")
        return

    # Confirm with the invoking user
    await ctx.send(
        "🧹 **Clear Chrome data directory?**\n"
        f"This will stop the loop, quit Chrome, delete:\n```{root}```\n"
        "and restart the bot. You will want to run !auth <casino site> after for every site needing google auth\n\n"
        "Type **YES** within 20 seconds to confirm, or anything else to cancel."
    )

    def _check(m: discord.Message) -> bool:
        return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id

    try:
        reply: discord.Message = await bot.wait_for("message", timeout=20, check=_check)
    except asyncio.TimeoutError:
        await ctx.send("❎ Timed out — cancelled.")
        return

    if reply.content.strip().upper() != "YES":
        await ctx.send("❎ Cancelled.")
        return

    # Proceed
    await ctx.send("⏳ Stopping the loop and shutting down Chrome…")

    # Stop the automated loop if needed
    try:
        if is_main_loop_running():
            await stop_main_loop()
    except Exception:
        pass

    # Quit Chrome to release locks
    try:
        driver.quit()
    except Exception:
        pass

    # Extra safeguard: kill any stray chrome that might still be alive
    try:
        import signal, psutil  # psutil is optional; ignore if not available
        for p in psutil.process_iter(attrs=["name", "cmdline"]):
            name = (p.info.get("name") or "").lower()
            cmd  = " ".join(p.info.get("cmdline") or [])
            if "chrome" in name or "--user-data-dir=" in cmd:
                try:
                    p.send_signal(signal.SIGKILL)
                except Exception:
                    pass
    except Exception:
        pass

    # Delete directory
    try:
        import shutil
        shutil.rmtree(root, ignore_errors=True)
        await ctx.send("✅ Chrome user data directory cleared. Restarting bot…")
    except Exception as e:
        await ctx.send(f"⚠️ Failed to clear Chrome data directory: `{e}`")
        return

    # Restart the bot process (entrypoint will relaunch and recreate a fresh profile)
    try:
        await bot.close()
    finally:
        os._exit(0)


# ───────────────────────────────────────────────────────────
# !reset — clear profile, rebuild, and re-compose (supports "nocache")
# Usage:
#   !reset           -> docker compose build
#   !reset nocache   -> docker compose build --no-cache
# ───────────────────────────────────────────────────────────
import os
import shutil
import asyncio
import subprocess
from asyncio.subprocess import PIPE
from typing import List, Optional

try:
    import psutil  # optional; used to kill straggler chrome
except Exception:
    psutil = None

try:
    import signal
except Exception:
    signal = None

# If your code defines these, we'll call them. Otherwise we noop.
def _has_callable(name: str) -> bool:
    return name in globals() and callable(globals()[name])

def _maybe_is_main_loop_running() -> bool:
    try:
        if _has_callable("is_main_loop_running"):
            return bool(globals()["is_main_loop_running"]())
    except Exception:
        pass
    return False

async def _maybe_stop_main_loop() -> None:
    try:
        if _has_callable("stop_main_loop"):
            await globals()["stop_main_loop"]()
    except Exception:
        pass

def _maybe_quit_driver() -> None:
    # Works if you keep a global `driver`/`sb` around; otherwise it’s a no-op.
    for key in ("driver", "sb", "browser", "web_driver"):
        if key in globals():
            try:
                obj = globals()[key]
                if obj:
                    # selenium webdriver has .quit(); SeleniumBase SB has .quit()
                    getattr(obj, "quit", lambda: None)()
            except Exception:
                pass

def _docker_compose_cmd() -> List[str]:
    """
    Prefer modern 'docker compose', fallback to legacy 'docker-compose'.
    Returns [] if neither is available in PATH.
    """
    if shutil.which("docker"):
        try:
            out = subprocess.run(
                ["docker", "compose", "version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
            if out.returncode == 0:
                return ["docker", "compose"]
        except Exception:
            pass
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    return []

async def _stream_proc_to_discord(ctx, proc: asyncio.subprocess.Process, prefix: str) -> int:
    """
    Stream a running process's stdout/stderr to Discord in safe 1.8k chunks.
    """
    buf = ""

    async def flush():
        nonlocal buf
        if not buf:
            return
        chunks = [buf[i:i+1800] for i in range(0, len(buf), 1800)]
        for c in chunks:
            try:
                await ctx.send(f"{prefix}```\n{c}\n```")
            except Exception:
                pass
        buf = ""

    if proc.stdout:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            buf += line.decode(errors="ignore")
            if len(buf) >= 1600:
                await flush()
    await flush()
    await proc.wait()

    if proc.returncode != 0 and proc.stderr:
        err = (await proc.stderr.read()).decode(errors="ignore")
        if err.strip():
            for i in range(0, len(err), 1800):
                try:
                    await ctx.send(f"{prefix}(stderr)```\n{err[i:i+1800]}\n```")
                except Exception:
                    pass

    return proc.returncode

def _detect_user_data_dir() -> Optional[str]:
    """
    Tries a few common envs/variables you've used across modules.
    """
    # If your code sets `instance_dir` globally, prefer it.
    if "instance_dir" in globals():
        val = str(globals()["instance_dir"]) or ""
        if val.strip():
            return val.strip()

    # Common envs you've used in past conversations:
    for env_key in ("CHROME_INSTANCE_DIR", "CHROME_USER_DATA_DIR", "SB_USER_DATA_DIR"):
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    return None

# ───────────────────────────────────────────────────────────
# !reset — clear profile, rebuild, and re-compose (with "nocache")
# Adds fallback: if "name is already in use", rm -f the conflicting
# containers (casino-bot, watchtower) and retry `up -d`.
# ───────────────────────────────────────────────────────────
import os
import shutil
import asyncio
import subprocess
from asyncio.subprocess import PIPE
from typing import List, Optional

try:
    import psutil
except Exception:
    psutil = None
try:
    import signal
except Exception:
    signal = None

def _has_callable(name: str) -> bool:
    return name in globals() and callable(globals()[name])

def _maybe_is_main_loop_running() -> bool:
    try:
        if _has_callable("is_main_loop_running"):
            return bool(globals()["is_main_loop_running"]())
    except Exception:
        pass
    return False

async def _maybe_stop_main_loop() -> None:
    try:
        if _has_callable("stop_main_loop"):
            await globals()["stop_main_loop"]()
    except Exception:
        pass

def _maybe_quit_driver() -> None:
    for key in ("driver", "sb", "browser", "web_driver"):
        if key in globals():
            try:
                obj = globals()[key]
                if obj:
                    getattr(obj, "quit", lambda: None)()
            except Exception:
                pass

def _docker_compose_cmd() -> List[str]:
    if shutil.which("docker"):
        try:
            out = subprocess.run(
                ["docker", "compose", "version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
            if out.returncode == 0:
                return ["docker", "compose"]
        except Exception:
            pass
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    return []

async def _stream_proc_to_discord(ctx, proc: asyncio.subprocess.Process, prefix: str) -> int:
    buf = ""
    async def flush():
        nonlocal buf
        if not buf:
            return
        chunks = [buf[i:i+1800] for i in range(0, len(buf), 1800)]
        for c in chunks:
            try:
                await ctx.send(f"{prefix}```\n{c}\n```")
            except Exception:
                pass
        buf = ""

    if proc.stdout:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            buf += line.decode(errors="ignore")
            if len(buf) >= 1600:
                await flush()
    await flush()
    await proc.wait()

    if proc.returncode != 0 and proc.stderr:
        err = (await proc.stderr.read()).decode(errors="ignore")
        if err.strip():
            for i in range(0, len(err), 1800):
                try:
                    await ctx.send(f"{prefix}(stderr)```\n{err[i:i+1800]}\n```")
                except Exception:
                    pass
            # Bubble the stderr back to caller for decisioning
            proc._captured_stderr = err  # attach attribute for caller
    return proc.returncode

def _detect_user_data_dir() -> Optional[str]:
    if "instance_dir" in globals():
        val = str(globals()["instance_dir"]) or ""
        if val.strip():
            return val.strip()
    for env_key in ("CHROME_INSTANCE_DIR", "CHROME_USER_DATA_DIR", "SB_USER_DATA_DIR"):
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    return None

async def _compose_run(ctx, args: List[str], compose_dir: str) -> tuple[int, str]:
    """Run a compose subcommand and return (rc, stderr_text)."""
    proc = await asyncio.create_subprocess_exec(
        *args, cwd=compose_dir, stdout=PIPE, stderr=PIPE
    )
    rc = await _stream_proc_to_discord(ctx, proc, prefix=f"{args[-2] if len(args)>=2 else 'compose'} ")
    stderr_text = getattr(proc, "_captured_stderr", "")
    return rc, (stderr_text or "")

async def _rm_conflicting_containers(ctx, names: List[str]) -> None:
    compose_bin = _docker_compose_cmd()
    docker_bin = ["docker"] if shutil.which("docker") else None
    if not docker_bin:
        await ctx.send("⚠️ Docker CLI not found; cannot remove conflicting containers automatically.")
        return
    for name in names:
        try:
            await ctx.send(f"🗑️ Removing conflicting container `{name}` (if present)…")
            proc = await asyncio.create_subprocess_exec(
                *docker_bin, "rm", "-f", name,
                stdout=PIPE, stderr=PIPE
            )
            # stream briefly (we don't expect much output)
            await _stream_proc_to_discord(ctx, proc, prefix=f"rm {name} ")
        except Exception as e:
            await ctx.send(f"⚠️ Could not remove `{name}`: `{e}`")

@bot.command(name="reset")
async def reset_cmd(ctx, mode: str = ""):
    """
    Clear Chrome user-data, rebuild & re-compose the Docker stack, then exit this bot process.
    Optional: 'nocache' -> build with --no-cache
    Fallback: if name-conflict occurs, rm -f offending containers and retry `up -d`.
    """
    compose_dir  = os.getenv("COMPOSE_DIR", os.getcwd()).strip()
    compose_file = os.getenv("COMPOSE_FILE", "").strip()
    user_data    = _detect_user_data_dir()
    nocache      = "nocache" in (mode or "").lower()

    compose_bin = _docker_compose_cmd()
    if not compose_bin:
        await ctx.send("❌ Could not find `docker compose` nor `docker-compose` in PATH inside this container.")
        await ctx.send("Tip: mount the Docker socket & CLI (e.g., `-v /var/run/docker.sock:/var/run/docker.sock`).")
        return

    await ctx.send(
        "🧹 **Reset requested**\n"
        f"• Compose dir: `{compose_dir}`\n"
        f"• Compose file: `{compose_file or '(default resolution)'}`\n"
        f"• Chrome profile: `{user_data or '(none configured)'}`\n"
        f"• Build mode: `{'--no-cache' if nocache else '(cached)'}`\n\n"
        "Type **YES** within 20 seconds to proceed. Anything else cancels."
    )

    def _check(m: discord.Message) -> bool:
        return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id

    try:
        reply: discord.Message = await bot.wait_for("message", timeout=20, check=_check)
    except asyncio.TimeoutError:
        await ctx.send("❎ Timed out — cancelled.")
        return
    if reply.content.strip().upper() != "YES":
        await ctx.send("❎ Cancelled.")
        return

    # 1) Stop main loop & close browser
    await ctx.send("⏹️ Stopping loop and shutting down Chrome…")
    try:
        if _maybe_is_main_loop_running():
            await _maybe_stop_main_loop()
    except Exception:
        pass
    _maybe_quit_driver()

    # 2) Kill straggler Chrome using same profile
    if psutil and signal:
        try:
            killed = 0
            for p in psutil.process_iter(attrs=["name", "cmdline"]):
                nm = (p.info.get("name") or "").lower()
                cmd = " ".join(p.info.get("cmdline") or [])
                if "chrome" in nm or "chromium" in nm:
                    if (not user_data) or (f"--user-data-dir={user_data}" in cmd):
                        try:
                            p.send_signal(signal.SIGKILL)
                            killed += 1
                        except Exception:
                            pass
            if killed:
                await ctx.send(f"🔪 Killed {killed} stray Chrome processes.")
        except Exception:
            pass

    # 3) Clear profile dir
    if user_data:
        await ctx.send(f"🧽 Clearing Chrome user-data at:\n```{user_data}```")
        try:
            shutil.rmtree(user_data, ignore_errors=True)
            await ctx.send("✅ Chrome user-data cleared.")
        except Exception as e:
            await ctx.send(f"⚠️ Failed to clear profile dir: `{e}` (continuing)")

    # 4) Build (maybe --no-cache)
    await ctx.send(f"🏗️ Building images {'(no cache)…' if nocache else '…'}")
    build_cmd = compose_bin + (["-f", compose_file] if compose_file else []) + ["build"]
    if nocache:
        build_cmd.append("--no-cache")
    rc, _ = await _compose_run(ctx, build_cmd, compose_dir)
    if rc != 0:
        await ctx.send(f"❌ Build failed with exit code {rc}. Aborting reset.")
        return
    await ctx.send("✅ Build finished.")

    # 5) Up -d (first try)
    await ctx.send("🚀 Re-composing (up -d)…")
    up_cmd = compose_bin + (["-f", compose_file] if compose_file else []) + ["up", "-d", "--remove-orphans"]
    rc, stderr_text = await _compose_run(ctx, up_cmd, compose_dir)
    if rc == 0:
        await ctx.send("✅ Compose finished. Exiting current bot process so the refreshed stack can take over…")
        try:
            await bot.close()
        finally:
            os._exit(0)
        return

    # 6) If name-in-use conflict, remove the old containers and retry once
    conflict_markers = ("is already in use by container", "name is already in use")
    if any(m in stderr_text for m in conflict_markers):
        await ctx.send("⚠️ Name conflict detected. Removing old containers and retrying once…")
        await _rm_conflicting_containers(ctx, ["casino-bot", "watchtower"])
        # retry up -d
        rc2, _ = await _compose_run(ctx, up_cmd, compose_dir)
        if rc2 == 0:
            await ctx.send("✅ Compose finished after conflict resolution. Exiting current bot process so the refreshed stack can take over…")
            try:
                await bot.close()
            finally:
                os._exit(0)
            return
        else:
            await ctx.send(f"❌ Compose up failed again (exit {rc2}). You may need to run `docker rm -f casino-bot watchtower` manually.")
            return

    # generic failure
    await ctx.send(f"❌ Compose up failed with exit code {rc}.")


def format_loop_config() -> str:
    status = "running" if is_main_loop_running() else "stopped"
    lines = ["🎛️ **Casino loop configuration**", f"Status: **{status}**", "Order and intervals:"]
    for i, e in enumerate(casino_loop_entries, 1):
        lines.append(f"{i}. {e.display_name} (`{e.key}`) – every {e.interval_minutes:.1f} minutes")
    lines += ["", "Use `!config interval <casino> <minutes>` to change an interval.",
              "Use `!config order <casino1> <casino2> ...>` to set a new run order."]
    return "\n".join(lines)

from discord.ext import commands as dcommands
@dcommands.group(name="config", invoke_without_command=True)
async def _config(ctx: dcommands.Context):
    await ctx.send(format_loop_config())
bot.add_command(_config)

@_config.command(name="interval")
async def config_interval(ctx: dcommands.Context, casino: str, minutes: float):
    target = next((e for e in casino_loop_entries if e.key.lower() == casino.lower()), None)
    if not target:
        await ctx.send(f"Casino `{casino}` is not part of the automated loop.")
        return
    if minutes <= 0:
        await ctx.send("Interval must be greater than zero.")
        return
    target.interval_minutes = minutes
    target.next_run = dt.datetime.now(dt.timezone.utc)
    await ctx.send(f"Updated {target.display_name} to run every {minutes:.1f} minutes.")

@_config.command(name="order")
async def config_order(ctx: dcommands.Context, *casinos: str):
    if not casinos:
        await ctx.send("Provide the complete list of casino keys in the desired order.")
        return
    desired = [c.lower() for c in casinos]
    current = [e.key for e in casino_loop_entries]
    if len(desired) != len(current) or set(desired) != set(current):
        await ctx.send(f"You must include each of: {', '.join(current)} (exactly once).")
        return
    lookup = {e.key: e for e in casino_loop_entries}
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

# Manual casino commands
@bot.command(name="luckybird")
async def luckybird_cmd(ctx):
    await ctx.send("Checking LuckyBird for bonus…")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await luckybird_entry(ctx, driver, bot, channel)

@bot.command(name="zula")
async def zula_cmd(ctx):
    await ctx.send("Checking Zula Casino for bonus…")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await zula_uc(ctx, channel)

@bot.command(name="sportzino")
async def sportzino_cmd(ctx):
    await ctx.send("Checking Sportzino for bonus…")
    await Sportzino(ctx, driver, bot.get_channel(DISCORD_CHANNEL))

@bot.command(name="nolimitcoins", aliases=["nlc", "no limit", "no limit coins"])
async def nolimitcoins_cmd(ctx):
    await ctx.send("Checking NoLimitCoins for bonus…")
    await nolimitcoins_flow(ctx, driver, bot.get_channel(DISCORD_CHANNEL))

@bot.command(name="funrize")
async def funrize_cmd(ctx):
    await ctx.send("Checking Funrize for bonus…")
    await funrize_flow(ctx, driver, bot.get_channel(DISCORD_CHANNEL))

@bot.command(name="globalpoker", aliases=["gp", "global poker"])
async def globalpoker_cmd(ctx):
    await ctx.send("Checking GlobalPoker for bonus…")
    await global_poker(ctx, driver, bot.get_channel(DISCORD_CHANNEL))

@bot.command(name="jefebet", aliases=["jefe", "jefebet casino"])
async def jefebet_cmd(ctx):
    await ctx.send("Checking JefeBet for bonus…")
    await jefebet_casino(ctx, driver, bot.get_channel(DISCORD_CHANNEL))

@bot.command(name="smilescasino", aliases=["smiles", "smiles casino"])
async def smilescasino_cmd(ctx):
    await ctx.send("Checking Smiles Casino for bonus...")
    await smilescasino_casino(ctx, driver, bot.get_channel(DISCORD_CHANNEL))

@bot.command(name="crowncoins")
async def crowncoins_cmd(ctx):
    await ctx.send("Checking Crown Coins Casino for bonus…")
    await crowncoins_casino(driver, bot, ctx, bot.get_channel(DISCORD_CHANNEL))

@bot.command(name="modo")
async def modo_cmd(ctx):
    await ctx.send("Checking Modo for bonus…")
    channel = bot.get_channel(DISCORD_CHANNEL)
    ok = await claim_modo_bonus(driver, bot, ctx, channel)
    if not ok:
        await check_modo_countdown(driver, bot, ctx, channel)

@bot.command(name="rollingriches", aliases=["rr", "rolling riches"])
async def rollingriches_cmd(ctx):
    await ctx.send("Checking Rolling Riches for bonus…")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await rolling_riches_casino(ctx, driver, channel)

@bot.command(name="stake")
async def stake_cmd(ctx):
    await ctx.send("Checking Stake for bonus…")
    await stake_claim(driver, bot, ctx, bot.get_channel(DISCORD_CHANNEL))

@bot.command(name="fortunewheelz")
async def fortunewheelz_cmd(ctx):
    await ctx.send("Checking Fortune Wheelz for bonus…")
    await fortunewheelz_flow(ctx, driver, bot.get_channel(DISCORD_CHANNEL))

@bot.command(name="fortunecoins", aliases=["fortune coins", "fc"])
async def fortunecoins_cmd(ctx):
    await ctx.send("Checking Fortune Coins for bonus…")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await fortunecoins_uc(ctx, channel)

@bot.command(name="spinquest")
async def spinquest_cmd(ctx):
    await ctx.send("Checking SpinQuest for bonus…")
    await spinquest_flow(ctx, driver, bot.get_channel(DISCORD_CHANNEL))

@bot.command(name="spinpals")
async def spinpals_cmd(ctx):
    await ctx.send("Checking SpinPals for bonus…")
    await spinpals_flow(ctx, driver, bot.get_channel(DISCORD_CHANNEL))

@bot.command(name="chumba")
async def chumba_cmd(ctx):
    await ctx.send("Checking Chumba for bonus…")
    driver.get("https://lobby.chumbacasino.com/")
    await asyncio.sleep(5)
    if driver.current_url.startswith("https://login.chumbacasino.com/"):
        authenticated = await authenticate_chumba(driver, bot, ctx)
        if not authenticated:
            await ctx.send("Chumba authentication failed.")
            return
    if driver.current_url.startswith("https://lobby.chumbacasino.com/"):
        await claim_chumba_bonus(driver, ctx)
        await check_chumba_countdown(driver, ctx)
    else:
        await ctx.send("Failed to reach the Chumba lobby.")

@bot.command(name="chanced")
async def chanced_cmd(ctx):
    await ctx.send("Checking Chanced.com for bonus…")
    creds = os.getenv("CHANCED")
    if creds:
        u, p = creds.split(":", 1)
        pair = (u, p)
    else:
        pair = (None, None)
    await chanced_casino(ctx, driver, bot.get_channel(DISCORD_CHANNEL), pair)

@bot.command(name="dingdingding")
async def dingdingding_cmd(ctx):
    await ctx.send("Checking DingDingDing for bonus…")
    channel = bot.get_channel(DISCORD_CHANNEL)
    claimed = await claim_dingdingding_bonus(driver, bot, ctx, channel)
    if not claimed:
        await check_dingdingding_countdown(driver, bot, ctx, channel)

# ───────────────────────────────────────────────────────────
# AUTH ROUTER (restores !auth commands, including !auth modo)
# ───────────────────────────────────────────────────────────
@bot.command(name="auth")
async def authenticate_command(ctx: commands.Context, site: str, method: str = None):
    """
    Examples:
      !auth google
      !auth modo
      !auth nolimitcoins google
      !auth crowncoins env
    """
    channel = bot.get_channel(DISCORD_CHANNEL)
    norm_site = re.sub(r"\s+", "", site.lower())

    # 1) Global Google: !auth google
    if norm_site == "google":
        await ctx.send("Authenticating Google Account…")
        google_credentials = os.getenv("GOOGLE_LOGIN")
        if google_credentials:
            u, p = google_credentials.split(":", 1)
            creds = (u, p)
        else:
            await ctx.send("🔐 Google credentials not found in `.env` (`GOOGLE_LOGIN`).")
            creds = (None, None)
        try:
            await google_auth(ctx, driver, channel, creds)
        except Exception as e:
            snap = "google_auth_failed.png"
            try:
                driver.save_screenshot(snap)
                await ctx.send(f"Google auth error: `{e}`", file=discord.File(snap))
            finally:
                try: os.remove(snap)
                except Exception: pass
        return

    # 2) Modo
    if norm_site == "modo":
        await ctx.send("Authenticating Modo…")
        await run_modo_auth(channel)  # serialized + safe against background task
        return

    # 3) CrownCoins
    if norm_site == "crowncoins":
        if method is None:
            await ctx.send("Usage: `!auth crowncoins google` or `!auth crowncoins env`")
            return
        if method.lower() == "google":
            await ctx.send("Authenticating CrownCoins via Google…")
            ok = await auth_crown_google(driver, bot, ctx, channel)
        elif method.lower() == "env":
            await ctx.send("Authenticating CrownCoins via .env credentials…")
            ok = await auth_crown_env(driver, bot, ctx, channel)
        else:
            await ctx.send("Invalid method. Use `google` or `env`.")
            return
        if not ok:
            snap = f"crowncoins_{method.lower()}_auth_failed.png"
            try:
                driver.save_screenshot(snap)
                await ctx.send("CrownCoins authentication failed.", file=discord.File(snap))
            finally:
                try: os.remove(snap)
                except Exception: pass
        return

    # 4) DingDingDing
    if norm_site == "dingdingding":
        await ctx.send("Authenticating DingDingDing…")
        ok = await authenticate_dingdingding(driver, bot, ctx, channel)
        if not ok:
            snap = "dingdingding_auth_failed.png"
            try:
                driver.save_screenshot(snap)
                await ctx.send("Authentication failed.", file=discord.File(snap))
            finally:
                try: os.remove(snap)
                except Exception: pass
        return

    # 5) Stake
    if norm_site == "stake":
        await ctx.send("Authenticating Stake…")
        ok = await stake_auth(driver, bot, ctx, channel)
        if not ok:
            snap = "stake_auth_failed.png"
            try:
                driver.save_screenshot(snap)
                await ctx.send("Stake authentication failed.", file=discord.File(snap))
            finally:
                try: os.remove(snap)
                except Exception: pass
        return

    # 6) LuckyBird
    if norm_site == "luckybird":
        await ctx.send("Authenticating LuckyBird…")
        ok = await authenticate_luckybird(driver, bot, ctx, channel)
        if not ok:
            snap = "luckybird_auth_failed.png"
            try:
                driver.save_screenshot(snap)
                await ctx.send("LuckyBird authentication failed.", file=discord.File(snap))
            finally:
                try: os.remove(snap)
                except Exception: pass
        return

    # 7) NoLimitCoins
    if norm_site in {"nolimitcoins", "nlc", "nolimit", "nolimitcoins", "no limit coins"}:
        if method is None:
            await ctx.send("Usage: `!auth nolimitcoins google` or `!auth nolimitcoins env`")
            return
        if method.lower() == "google":
            await ctx.send("Authenticating NoLimitCoins via Google…")
            ok = await auth_nolimit_google(driver, channel, ctx)
        elif method.lower() == "env":
            await ctx.send("Authenticating NoLimitCoins via .env credentials…")
            ok = await auth_nolimit_env(driver, channel, ctx)
        else:
            await ctx.send("Invalid method. Use `google` or `env`.")
            return

        if not ok:
            snap = f"nolimit_{method.lower()}_auth_failed.png"
            try:
                driver.save_screenshot(snap)
                await ctx.send("NoLimitCoins authentication failed.", file=discord.File(snap))
            finally:
                try: os.remove(snap)
                except Exception: pass
        return

    await ctx.send(f"❓ Authentication for `{site}` is not implemented. Run `!help` for supported sites.")

# Handy shortcut specifically for Modo
@bot.command(name="authmodo")
async def authmodo_cmd(ctx):
    await ctx.send("Authenticating Modo…")
    await run_modo_auth(bot.get_channel(DISCORD_CHANNEL))

# ───────────────────────────────────────────────────────────
# Invalid command handler
# ───────────────────────────────────────────────────────────
@bot.event
async def on_command_error(ctx: commands.Context, error: Exception):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Invalid command. Run `!help` to see valid commands.")
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send(f"⚠️ {error}")
        return
    try:
        print(f"[on_command_error] {type(error).__name__}: {error}")
    except Exception:
        pass
    await ctx.send("⚠️ An error occurred while handling that command.")

# ───────────────────────────────────────────────────────────
# Help Command
# ───────────────────────────────────────────────────────────
@bot.command(name="help")
async def help_cmd(ctx):
    await ctx.send("""Commands are not recommended while the casino loop is running.

🎰 **Casino Commands:**  
!chanced, !luckybird, !globalpoker, !crowncoins, !chumba, !modo, !zula,  
!rollingriches, !jefebet, !spinpals, !spinquest, !funrize, !sportzino,  
!fortunecoins, !nolimitcoins, !fortunewheelz, !stake, !dingdingding,
!smilescasino

---------------------------------------  
✅ **Auth Commands:**  
!auth google  
!auth modo  
!auth crowncoins google | !auth crowncoins env  
!auth nolimitcoins google | !auth nolimitcoins env  
!authmodo  (shortcut)

---------------------------------------  
⚙️ **General:**  
!ping, !restart, !help, !start, !stop, !about, !config, !reset
""")

# ───────────────────────────────────────────────────────────
# Run bot
# ───────────────────────────────────────────────────────────
bot.run(DISCORD_TOKEN)
