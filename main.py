# Drake Hooks
# Casino Claim 3
# Never Miss a Casino Bonus Again! A discord app for claiming social casino bonuses.

import os
import sys
import glob
import re
import time
import shutil
import signal
import inspect
import traceback
import discord
import asyncio
import importlib
import importlib.util
import threading
from pathlib import Path
from dataclasses import dataclass, field
import datetime as dt
from typing import Awaitable, Callable, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv

# ───────────────────────────────────────────────────────────
# Selenium / Chrome
# ───────────────────────────────────────────────────────────
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.common.exceptions import SessionNotCreatedException
from webdriver_manager.chrome import ChromeDriverManager

# Discord
from discord import Intents
from discord.ext import commands
from discord.ext import commands as dcommands

# Other modules may use this.
import undetected_chromedriver as uc  # noqa: F401

try:
    import psutil
except Exception:
    psutil = None


# ───────────────────────────────────────────────────────────
# Env
# ───────────────────────────────────────────────────────────
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_RAW = os.getenv("DISCORD_CHANNEL")

if not DISCORD_TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN in .env")

if not DISCORD_CHANNEL_RAW:
    raise RuntimeError("Missing DISCORD_CHANNEL in .env")

DISCORD_CHANNEL = int(DISCORD_CHANNEL_RAW)


# ───────────────────────────────────────────────────────────
# Executor tracking
# ───────────────────────────────────────────────────────────
_executor = ThreadPoolExecutor(max_workers=4)

_active_exec_jobs = 0
_active_exec_lock = threading.Lock()


def _exec_job_started():
    global _active_exec_jobs
    with _active_exec_lock:
        _active_exec_jobs += 1


def _exec_job_finished():
    global _active_exec_jobs
    with _active_exec_lock:
        _active_exec_jobs = max(0, _active_exec_jobs - 1)


# ───────────────────────────────────────────────────────────
# Debug helpers
# ───────────────────────────────────────────────────────────
from helperAPI import normalize_casino_key, run_with_periodic_screenshots


# ───────────────────────────────────────────────────────────
# Dynamic API imports
# Missing modules are OK, but failures are recorded clearly.
# Run !imports in Discord to see exact problems.
# ───────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent

api_modules = [
    "fortunewheelzAPI",
    "fortunecoinsAPI",
    "americanluckAPI",
    "stakeAPI",
    "modoAPI",
    "googleauthAPI",
    "chancedAPI",
    "rollingrichesAPI",
    "jefebetAPI",
    "spinpalsAPI",
    "spinquestAPI",
    "funrizeAPI",
    "realprizeAPI",
    "globalpokerAPI",
    "dingdingdingAPI",
    "chumbaAPI",
    "crowncoinsAPI",
    "zulaAPI",
    "sportzinoAPI",
    "nolimitcoinsAPI",
    "smilescasinoAPI",
    "jumboAPI",
    "spreeAPI",
    "chipnwinAPI",
    "wildworldAPI",
    "lonestarAPI",
    "gainsAPI",
    "yaycasinoAPI",
    "luckylandAPI",

    # Luck Party
    "luckpartyAPI",

    # WinBonanza
    "winbonanzaAPI",
]

API_MODULES: dict[str, Any] = {}
API_IMPORT_ERRORS: dict[str, str] = {}

API_FILE_CANDIDATES = {
    "luckpartyAPI": [
        "luckpartyAPI.py",
        "luckypartyAPI.py",
        "luckyPartyAPI.py",
        "LuckyPartyAPI.py",
        "luckpartyapi.py",
        "luckypartyapi.py",
    ],
    "winbonanzaAPI": [
        "winbonanzaAPI.py",
        "WinBonanzaAPI.py",
        "winBonanzaAPI.py",
        "winbonanzaapi.py",
    ],
}


def _safe_update_globals_from_module(module) -> None:
    """
    Import API functions into globals like the old main.py did,
    but avoid overwriting __file__, __name__, etc.
    """
    for name, value in vars(module).items():
        if name.startswith("__"):
            continue
        globals()[name] = value


def _load_module_from_file(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))

    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create import spec for {module_name} from {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _matching_py_files_for_debug(module_name: str) -> str:
    party_files = sorted(
        [
            p.name
            for p in BASE_DIR.glob("*.py")
            if (
                "luck" in p.name.lower()
                or "party" in p.name.lower()
                or "bonanza" in p.name.lower()
                or "win" in p.name.lower()
            )
        ]
    )

    all_py = sorted([p.name for p in BASE_DIR.glob("*.py")])

    lines = [
        f"module_name: {module_name}",
        f"base_dir: {BASE_DIR}",
        f"expected_file: {BASE_DIR / (module_name + '.py')}",
        f"expected_file_exists: {(BASE_DIR / (module_name + '.py')).exists()}",
        "",
        "Luck/Party/Win/Bonanza-looking .py files in container:",
        *(f"  - {x}" for x in party_files),
        "",
        "First 80 .py files in container:",
        *(f"  - {x}" for x in all_py[:80]),
        "",
        "sys.path:",
        *(f"  - {x}" for x in sys.path[:20]),
    ]

    return "\n".join(lines)


def _import_api_module(module_name: str):
    """
    Imports normal modules with importlib.import_module().

    If that fails, tries a direct file import from /app or wherever main.py lives.
    This makes Docker copy/name problems obvious.
    """
    try:
        module = importlib.import_module(module_name)
        API_MODULES[module_name] = module
        _safe_update_globals_from_module(module)
        print(f"[API] Imported {module_name}")
        return module

    except Exception as first_error:
        first_tb = traceback.format_exc()

        candidates = API_FILE_CANDIDATES.get(module_name, [f"{module_name}.py"])

        existing_candidates = []
        for filename in candidates:
            candidate = BASE_DIR / filename
            if candidate.exists():
                existing_candidates.append(candidate)

        if existing_candidates:
            candidate = existing_candidates[0]

            try:
                module = _load_module_from_file(module_name, candidate)
                API_MODULES[module_name] = module
                _safe_update_globals_from_module(module)
                print(f"[API] Imported {module_name} from file fallback: {candidate}")
                return module

            except Exception as file_error:
                file_tb = traceback.format_exc()
                msg = (
                    f"FAILED importing {module_name}.\n\n"
                    f"Normal import error:\n{type(first_error).__name__}: {first_error}\n\n"
                    f"Normal import traceback:\n{first_tb}\n\n"
                    f"Found candidate file but file import also failed:\n{candidate}\n\n"
                    f"File import error:\n{type(file_error).__name__}: {file_error}\n\n"
                    f"File import traceback:\n{file_tb}\n\n"
                    f"{_matching_py_files_for_debug(module_name)}"
                )
                API_IMPORT_ERRORS[module_name] = msg
                print(f"Warning: Failed to import {module_name}: {type(file_error).__name__}: {file_error}")
                print(msg)
                return None

        msg = (
            f"FAILED importing {module_name}.\n\n"
            f"Normal import error:\n{type(first_error).__name__}: {first_error}\n\n"
            f"Normal import traceback:\n{first_tb}\n\n"
            f"No candidate file was found in the container.\n"
            f"Docker must contain one of:\n"
            + "\n".join(f"  - {x}" for x in candidates)
            + "\n\n"
            "Fix is usually one of these Dockerfile lines:\n"
            f"  COPY {module_name}.py .\n"
            "or:\n"
            "  COPY *.py ./\n\n"
            f"{_matching_py_files_for_debug(module_name)}"
        )

        API_IMPORT_ERRORS[module_name] = msg
        print(f"Warning: Failed to import {module_name}: {type(first_error).__name__}: {first_error}")
        print(msg)
        return None


for _module_name in api_modules:
    _import_api_module(_module_name)


def _get_api_callable(module_name: str, *function_names: str, allow_global_fallback: bool = True):
    module = API_MODULES.get(module_name)

    if module:
        for function_name in function_names:
            fn = getattr(module, function_name, None)
            if callable(fn):
                return fn

    if not allow_global_fallback:
        return None

    for function_name in function_names:
        fn = globals().get(function_name)
        if callable(fn):
            return fn

    return None


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


async def _send_long_message(target, text: str):
    if not target:
        return

    text = str(text)

    for i in range(0, len(text), 1800):
        chunk = text[i:i + 1800]
        try:
            await target.send(chunk)
        except Exception:
            pass


async def _call_luckparty(channel=None, ctx=None, raise_errors: bool = False):
    """
    Safe Luck Party wrapper.

    Accepts luckpartyAPI.py primarily.
    Also accepts backwards-compatible function names from older luckypartyAPI.py.
    """
    target = ctx or channel

    fn = _get_api_callable(
        "luckpartyAPI",
        "claim_luckparty",
        "luckparty_casino",
        "luckparty_uc",
        "claim_luckyparty",
        "luckyparty_casino",
        "luckyparty_uc",
        "claim_bonus",
        "run",
        "main",
    )

    if not fn:
        import_error = API_IMPORT_ERRORS.get("luckpartyAPI")

        if import_error:
            await _send_long_message(
                target,
                "❌ `luckpartyAPI` is not available.\n"
                "The import failed. Exact reason:\n"
                f"```text\n{import_error[:1600]}\n```"
            )

            if len(import_error) > 1600:
                await _send_long_message(
                    target,
                    "More import detail:\n"
                    f"```text\n{import_error[1600:3200]}\n```"
                )
        else:
            await _send_long_message(
                target,
                "❌ `luckpartyAPI` imported, but no callable was found.\n"
                "Expected one of: `claim_luckparty`, `luckparty_casino`, `luckparty_uc`, "
                "`claim_luckyparty`, `claim_bonus`, `run`, `main`."
            )

        if raise_errors:
            raise RuntimeError("luckpartyAPI is unavailable. Run !imports luckparty for details.")

        return None

    try:
        try:
            sig = inspect.signature(fn)
            params = sig.parameters

            if "channel" in params and "ctx" in params:
                result = fn(channel=channel, ctx=ctx)
            elif "channel" in params:
                result = fn(channel=channel)
            elif "ctx" in params:
                result = fn(ctx=ctx)
            elif len(params) >= 1:
                result = fn(channel)
            else:
                result = fn()

        except (ValueError, TypeError):
            result = fn(channel=channel)

        return await _maybe_await(result)

    except Exception as e:
        msg = f"⚠️ Luck Party error: `{type(e).__name__}: {e}`"
        await _send_long_message(target, msg)

        if raise_errors:
            raise

        return None


async def _call_winbonanza(channel=None, ctx=None, raise_errors: bool = False):
    """
    Safe WinBonanza wrapper.

    Uses winbonanzaAPI.py and avoids generic function names so it never accidentally
    calls another casino's claim_bonus/run/main.
    """
    target = ctx or channel

    fn = _get_api_callable(
        "winbonanzaAPI",
        "claim_winbonanza",
        "winbonanza_casino",
        "winbonanza_uc",
        allow_global_fallback=False,
    )

    if not fn:
        import_error = API_IMPORT_ERRORS.get("winbonanzaAPI")

        if import_error:
            await _send_long_message(
                target,
                "❌ `winbonanzaAPI` is not available.\n"
                "The import failed. Exact reason:\n"
                f"```text\n{import_error[:1600]}\n```"
            )

            if len(import_error) > 1600:
                await _send_long_message(
                    target,
                    "More import detail:\n"
                    f"```text\n{import_error[1600:3200]}\n```"
                )
        else:
            await _send_long_message(
                target,
                "❌ `winbonanzaAPI` imported, but no callable was found.\n"
                "Expected one of: `claim_winbonanza`, `winbonanza_casino`, `winbonanza_uc`."
            )

        if raise_errors:
            raise RuntimeError("winbonanzaAPI is unavailable. Run !imports winbonanza for details.")

        return None

    try:
        try:
            sig = inspect.signature(fn)
            params = sig.parameters

            if "channel" in params and "ctx" in params:
                result = fn(channel=channel, ctx=ctx)
            elif "channel" in params:
                result = fn(channel=channel)
            elif "ctx" in params:
                result = fn(ctx=ctx)
            elif len(params) >= 1:
                result = fn(channel)
            else:
                result = fn()

        except (ValueError, TypeError):
            result = fn(channel=channel)

        return await _maybe_await(result)

    except Exception as e:
        msg = f"⚠️ WinBonanza error: `{type(e).__name__}: {e}`"
        await _send_long_message(target, msg)

        if raise_errors:
            raise

        return None


# ───────────────────────────────────────────────────────────
# Discord setup
# ───────────────────────────────────────────────────────────
intents = Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, case_insensitive=True)
bot.remove_command("help")


# ───────────────────────────────────────────────────────────
# Selenium driver
# Headed; Xvfb is started by entrypoint.sh
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

        fp = os.path.join(prof_path, "DevToolsActivePort")
        if os.path.exists(fp):
            try:
                os.remove(fp)
            except Exception:
                pass

    except Exception:
        pass


def _apply_common_chrome_flags(opts: Options) -> None:
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--hide-crash-restore-bubble")
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

    opts.add_argument("--enable-webgl")
    opts.add_argument("--ignore-gpu-blocklist")
    opts.add_argument("--use-gl=swiftshader")
    opts.add_argument("--enable-unsafe-swiftshader")
    opts.add_argument("--disable-gpu-driver-bug-workarounds")

    opts.add_argument(f"--remote-debugging-port={9222 + (os.getpid() % 1000)}")

    ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
    )
    opts.add_argument(f"--user-agent={ua}")

    opts.set_capability("goog:loggingPrefs", caps["goog:loggingPrefs"])


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
        print("[Chrome] No persistent profile configured. Ephemeral session.")


crx_path = "/temp/CAPTCHA-Solver-auto-hCAPTCHA-reCAPTCHA-freely-Chrome-Web-Store.crx"
if os.path.exists(crx_path):
    options.add_extension(crx_path)

_apply_common_chrome_flags(options)


def _build_driver_with_retry(opts: Options):
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
# 2FA capture plumbing
# ───────────────────────────────────────────────────────────
bot.awaiting_2fa_for = None
bot.pending_2fa_code = None
bot._pending_2fa_event = asyncio.Event()


@bot.event
async def on_message(message: discord.Message):
    if getattr(message.channel, "id", None) == DISCORD_CHANNEL:
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
                bot.two_fa_code = text
                print(f"[2FA] Stored code legacy fallback: {bot.two_fa_code}")

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
# Loop runner
# ───────────────────────────────────────────────────────────
@dataclass
class CasinoLoopEntry:
    key: str
    display_name: str
    runner: Callable[[discord.abc.Messageable], Awaitable[None]]
    interval_minutes: float
    enabled: bool = True
    next_run: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))

    def schedule_next(self):
        self.next_run = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=self.interval_minutes)


LOOP_STAGGER_SECONDS = 30
PER_CASINO_TIMEOUT_SEC = int(os.getenv("CASINO_TIMEOUT_SECONDS", "500"))
MAIN_TICK_SLEEP = 10


async def _run_zula(channel):
    await zula_uc(None, channel)


async def _run_sportzino(channel):
    await Sportzino(None, driver, channel)


async def _run_nlc(channel):
    await nolimitcoins_flow(None, driver, channel)


async def _run_funrize(channel):
    await funrize_flow(None, driver, channel)


async def _run_globalpoker(channel):
    await global_poker(None, driver, channel)


async def _run_jefebet(channel):
    await jefebet_casino(None, driver, channel)


async def _run_crowncoins(channel):
    await crowncoins_casino(driver, bot, None, channel)


async def _run_smilescasino(channel):
    await smilescasino_casino(None, driver, channel)


async def _run_jumbo(channel):
    await jumbo_casino(None, driver, channel)


async def _run_spree(channel):
    await spree_uc(None, channel)


async def _run_chipnwin(channel):
    await chipnwin_casino(None, driver, channel)


async def _run_wildworld(channel):
    await wildworld_casino(None, driver, channel)


async def _run_gains(channel):
    await gains_casino(None, driver, channel)


async def _run_lonestar(channel):
    await lonestar_casino(None, driver, channel)


async def _run_realprize(channel):
    await realprize_casino(None, driver, channel)


async def _run_yaycasino(channel):
    await yaycasino_uc(None, channel)


async def _run_luckyland(channel):
    await luckyland_uc(None, channel)


async def _run_luckparty(channel):
    await _call_luckparty(channel=channel, raise_errors=True)


async def _run_winbonanza(channel):
    await _call_winbonanza(channel=channel, raise_errors=True)


async def _run_modo(channel):
    ok = await claim_modo_bonus(driver, bot, None, channel)

    if not ok:
        await check_modo_countdown(driver, bot, None, channel)


async def _run_rollingriches(channel):
    await rolling_riches_casino(None, driver, channel)


async def _run_stake(channel):
    await stake_claim(driver, bot, None, channel)


async def _run_fortunewheelz(channel):
    await fortunewheelz_flow(None, driver, channel)


async def _run_spinquest(channel):
    await spinquest_flow(None, driver, channel)


async def _run_americanluck(channel):
    await americanluck_uc(None, channel)


async def _run_fortunecoins(channel):
    loop = asyncio.get_running_loop()
    from fortunecoinsAPI import fortunecoins_uc_blocking

    _exec_job_started()
    try:
        await loop.run_in_executor(_executor, fortunecoins_uc_blocking, bot, channel.id, loop)
    finally:
        _exec_job_finished()


casino_loop_entries: List[CasinoLoopEntry] = [
    CasinoLoopEntry("jefebet", "JefeBet", _run_jefebet, 120),
    CasinoLoopEntry("globalpoker", "GlobalPoker", _run_globalpoker, 120),
    CasinoLoopEntry("jumbo", "Jumbo", _run_jumbo, 120),
    CasinoLoopEntry("spree", "Spree", _run_spree, 120),
    CasinoLoopEntry("fortunewheelz", "Fortune Wheelz", _run_fortunewheelz, 120),
    CasinoLoopEntry("nolimitcoins", "NoLimitCoins", _run_nlc, 120),
    CasinoLoopEntry("spinquest", "SpinQuest", _run_spinquest, 120),

    # Enable when wanted:
    # CasinoLoopEntry("modo", "Modo", _run_modo, 120),
    # CasinoLoopEntry("stake", "Stake", _run_stake, 120),

    CasinoLoopEntry("gains", "Gains", _run_gains, 1440),
    CasinoLoopEntry("realprize", "Real Prize", _run_realprize, 1440),
    CasinoLoopEntry("lonestar", "LoneStar Casino", _run_lonestar, 1440),
    CasinoLoopEntry("wildworld", "WildWorld", _run_wildworld, 1440),
    CasinoLoopEntry("funrize", "Funrize", _run_funrize, 1440),
    CasinoLoopEntry("rollingriches", "Rolling Riches", _run_rollingriches, 1440),
    CasinoLoopEntry("americanluck", "American Luck", _run_americanluck, 1440),
    CasinoLoopEntry("fortunecoins", "Fortune Coins", _run_fortunecoins, 1440),
    CasinoLoopEntry("zula", "Zula Casino", _run_zula, 1440),
    CasinoLoopEntry("sportzino", "Sportzino", _run_sportzino, 1440),
    CasinoLoopEntry("yaycasino", "YayCasino", _run_yaycasino, 1440),
    CasinoLoopEntry("chipnwin", "Chipnwin", _run_chipnwin, 1440),
    CasinoLoopEntry("luckparty", "Luck Party", _run_luckparty, 1440),
    CasinoLoopEntry("winbonanza", "WinBonanza", _run_winbonanza, 1440),

    # CasinoLoopEntry("smilescasino", "Smiles Casino", _run_smilescasino, 1440),
    # CasinoLoopEntry("luckyland", "LuckyLand", _run_luckyland, 1440),
]


def reset_loop_schedule():
    base = dt.datetime.now(dt.timezone.utc)
    for i, entry in enumerate(casino_loop_entries):
        entry.next_run = base + dt.timedelta(seconds=i * LOOP_STAGGER_SECONDS)


def find_loop_entry(casino: str) -> Optional[CasinoLoopEntry]:
    casino = (casino or "").strip().lower()
    casino = CASINO_ALIAS_MAP.get(casino, casino)
    return next((e for e in casino_loop_entries if e.key.lower() == casino), None)


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
                if not entry.enabled:
                    continue

                if now >= entry.next_run:
                    try:
                        await asyncio.wait_for(entry.runner(channel), timeout=PER_CASINO_TIMEOUT_SEC)
                    except asyncio.TimeoutError:
                        try:
                            await channel.send(
                                f"⏳ {entry.display_name} timed out after {PER_CASINO_TIMEOUT_SEC}s. Skipping."
                            )
                        except Exception:
                            pass
                        print(f"[Loop] {entry.display_name} timed out.")
                    except Exception as e:
                        print(f"[Loop] Error in {entry.display_name}: {type(e).__name__}: {e}")
                        try:
                            await channel.send(f"⚠️ {entry.display_name} error: `{type(e).__name__}: {e}`")
                        except Exception:
                            pass
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
# Aliases
# ───────────────────────────────────────────────────────────
CASINO_ALIAS_MAP = {
    "nlc": "nolimitcoins",
    "no_limit": "nolimitcoins",
    "no-limit": "nolimitcoins",
    "no limit": "nolimitcoins",
    "gp": "globalpoker",
    "global poker": "globalpoker",
    "fc": "fortunecoins",
    "fw": "fortunecoins",
    "fortune coins": "fortunecoins",
    "fortune wins": "fortunecoins",
    "rr": "rollingriches",
    "rolling riches": "rollingriches",
    "jb": "jefebet",
    "jefe": "jefebet",
    "jefe bet": "jefebet",
    "yay": "yaycasino",
    "rp": "realprize",
    "real prize": "realprize",
    "a_luck": "americanluck",
    "aluck": "americanluck",
    "american luck": "americanluck",

    # Luck Party aliases.
    "lp": "luckparty",
    "luckparty": "luckparty",
    "luck party": "luckparty",
    "luck-party": "luckparty",
    "luckyparty": "luckparty",
    "lucky party": "luckparty",
    "lucky-party": "luckparty",

    # WinBonanza aliases.
    "wb": "winbonanza",
    "winbonanza": "winbonanza",
    "win bonanza": "winbonanza",
    "win-bonanza": "winbonanza",
}


# ───────────────────────────────────────────────────────────
# Modo auth helper
# ───────────────────────────────────────────────────────────
async def run_modo_auth(channel):
    fn = _get_api_callable("modoAPI", "authenticate_modo")

    if not fn:
        if channel:
            await channel.send("❌ Modo auth function `authenticate_modo` is not available.")
        return False

    try:
        result = fn(driver, bot, None, channel)
        return await _maybe_await(result)
    except Exception as e:
        if channel:
            await channel.send(f"⚠️ Modo auth error: `{type(e).__name__}: {e}`")
        raise


# ───────────────────────────────────────────────────────────
# Bot events / commands
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
    else:
        print("Invalid DISCORD_CHANNEL")


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
    "globalpoker",
    "crowncoins",
    "dingdingding",
    "modo",
    "zula",
    "sportzino",
    "nolimitcoins",
    "fortunecoins",
    "smilescasino",
    "americanluck",
    "yaycasino",
    "realprize",
    "jumbo",
    "spree",
    "chipnwin",
    "wildworld",
    "lonestar",
    "gains",
    "luckparty",
    "luckyparty",
    "winbonanza",
    "debug",
}


@bot.check
async def prevent_manual_casino_commands(ctx: commands.Context) -> bool:
    if ctx.command is None:
        return True

    if is_main_loop_running() and ctx.command.name.lower() in MANUAL_CASINO_COMMANDS:
        await ctx.send("The automated casino loop is running. Use `!stop` before manually checking casinos.")
        return False

    return True


@bot.command(name="imports", aliases=["apiimports"])
async def imports_cmd(ctx, *, module_filter: str = ""):
    """
    Shows exact API import failures.
    Usage:
      !imports
      !imports luckparty
      !imports winbonanza
    """
    module_filter = (module_filter or "").strip().lower().replace(".py", "")

    if module_filter in {"luckyparty", "lucky_party", "lucky-party", "lucky party"}:
        module_filter = "luckparty"

    if module_filter in {"win-bonanza", "win bonanza", "wb"}:
        module_filter = "winbonanza"

    if module_filter:
        matched = [
            name for name in api_modules
            if module_filter in name.lower()
        ]

        if not matched:
            await ctx.send(f"❌ No API module matches `{module_filter}`.")
            return

        lines = []

        for name in matched:
            if name in API_MODULES:
                mod = API_MODULES[name]
                lines.append(f"✅ `{name}` imported from `{getattr(mod, '__file__', 'unknown')}`")
            elif name in API_IMPORT_ERRORS:
                lines.append(f"❌ `{name}` failed:\n```text\n{API_IMPORT_ERRORS[name][:1600]}\n```")
            else:
                lines.append(f"❓ `{name}` was not imported and has no stored error.")

        await _send_long_message(ctx, "\n\n".join(lines))
        return

    if not API_IMPORT_ERRORS:
        await ctx.send("✅ All API modules imported successfully.")
        return

    lines = ["⚠️ **API import errors:**"]

    for name, err in API_IMPORT_ERRORS.items():
        lines.append(f"\n`{name}`\n```text\n{err[:1200]}\n```")

    await _send_long_message(ctx, "\n".join(lines))


@bot.command(name="start")
async def start_loop_command(ctx: commands.Context):
    started = await start_main_loop()

    if started:
        await ctx.send("Casino loop started.")
    elif is_main_loop_running():
        await ctx.send("Casino loop is already running.")
    else:
        await ctx.send("Casino loop could not start. Channel missing.")


@bot.command(name="stop")
async def stop_loop_command(ctx: commands.Context):
    stopped = await stop_main_loop()

    if stopped:
        await ctx.send("Casino loop stopped. You can run manual casino commands now.")
    else:
        await ctx.send("Casino loop is not currently running.")


@bot.command(name="cleardatadir")
async def clear_data_dir(ctx: commands.Context):
    global driver

    root = instance_dir or os.getenv("CHROME_USER_DATA_DIR", "").strip()

    if not root:
        await ctx.send("⚠️ No CHROME_INSTANCE_DIR or CHROME_USER_DATA_DIR configured — nothing to clear.")
        return

    await ctx.send(
        "🧹 **Clear Chrome data directory?**\n"
        f"This will stop the loop, quit Chrome, delete:\n```{root}```\n"
        "and then restart Chrome without restarting the bot.\n\n"
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

    await ctx.send("🛑 Stopping the loop…")
    try:
        if is_main_loop_running():
            await stop_main_loop()
    except Exception:
        pass

    await ctx.send("⏳ Waiting for background tasks to finish, up to 20s…")
    for _ in range(40):
        with _active_exec_lock:
            busy = _active_exec_jobs

        if busy == 0:
            break

        await asyncio.sleep(0.5)
    else:
        await ctx.send("⚠️ Background task still running; proceeding anyway.")

    await ctx.send("🔌 Quitting Chrome…")
    try:
        driver.quit()
    except Exception:
        pass

    try:
        killed = 0

        if psutil:
            for p in psutil.process_iter(attrs=["name", "cmdline"]):
                nm = (p.info.get("name") or "").lower()
                cmd = " ".join(p.info.get("cmdline") or [])

                if "chrome" in nm or "chromium" in nm:
                    if (not root) or (f"--user-data-dir={root}" in cmd):
                        try:
                            p.send_signal(signal.SIGKILL)
                            killed += 1
                        except Exception:
                            pass

        if killed:
            await ctx.send(f"🔪 Killed {killed} stray Chrome processes.")

    except Exception:
        pass

    await ctx.send(f"🧽 Clearing Chrome user-data at:\n```{root}```")

    try:
        shutil.rmtree(root, ignore_errors=True)
        await ctx.send("✅ Chrome user-data cleared.")
    except Exception as e:
        await ctx.send(f"⚠️ Failed to clear profile dir: `{e}`")
        return

    await ctx.send("🚀 Restarting Chrome with a fresh profile…")

    try:
        _apply_common_chrome_flags(options)
        driver = _build_driver_with_retry(options)
        await ctx.send("✅ Chrome restarted.")
    except Exception as e:
        await ctx.send(f"❌ Failed to restart Chrome: `{e}`")
        return

    try:
        channel = bot.get_channel(DISCORD_CHANNEL)
        if channel and not is_main_loop_running():
            await start_main_loop(channel)
            await ctx.send("🎰 Casino loop restarted.")
    except Exception:
        pass


# ───────────────────────────────────────────────────────────
# !reset
# ───────────────────────────────────────────────────────────
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


def _detect_user_data_dir() -> Optional[str]:
    if "instance_dir" in globals():
        v = str(globals()["instance_dir"]) or ""
        if v.strip():
            return v.strip()

    for k in ("CHROME_INSTANCE_DIR", "CHROME_USER_DATA_DIR", "SB_USER_DATA_DIR"):
        v = os.getenv(k, "").strip()
        if v:
            return v

    return None


def _q(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"


async def _run(ctx, args, cwd=None, prefix=""):
    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    out = (await proc.stdout.read()).decode(errors="ignore")
    err = (await proc.stderr.read()).decode(errors="ignore")
    rc = await proc.wait()

    if out.strip():
        await ctx.send(f"{prefix}```\n{out[-1700:]}\n```")

    if rc != 0 and err.strip():
        await ctx.send(f"{prefix}(stderr)```\n{err[-1700:]}\n```")

    return rc, out, err


@bot.command(name="reset")
async def reset_cmd(ctx, mode: str = ""):
    compose_dir = os.getenv("COMPOSE_DIR", os.getcwd()).strip()
    compose_file = os.getenv("COMPOSE_FILE", "").strip() or os.path.join(compose_dir, "docker-compose.yml")
    helper_image = os.getenv("RESET_HELPER_IMAGE", "drakehooks/casinoclaim:testing").strip()
    project_name = os.getenv("COMPOSE_PROJECT_NAME", "").strip()
    target_svc = os.getenv("TARGET_SERVICE", "casino-bot").strip()
    nocache = "nocache" in (mode or "").lower()
    user_data = _detect_user_data_dir()

    if not shutil.which("docker"):
        await ctx.send("❌ Docker CLI not found in PATH. Install docker-cli in this container.")
        return

    if not os.path.exists(compose_file):
        await ctx.send(f"❌ Compose file not found at `{compose_file}`.")
        return

    await ctx.send(
        "🧹 **Reset requested**\n"
        f"• Compose dir: `{compose_dir}`\n"
        f"• Compose file: `{compose_file}`\n"
        f"• Target service: `{target_svc}` watchtower stays running\n"
        f"• Chrome profile: `{user_data or '(none configured)'}`\n"
        f"• Build mode: `{'--no-cache' if nocache else '(cached)'}`\n"
        f"• Helper image: `{helper_image}`\n\n"
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

    await ctx.send("🛑 Stopping loop & shutting down Chrome…")

    try:
        if _maybe_is_main_loop_running():
            await _maybe_stop_main_loop()
    except Exception:
        pass

    _maybe_quit_driver()

    if psutil:
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

    if user_data:
        await ctx.send(f"🧽 Clearing Chrome user-data at:\n```{user_data}```")
        try:
            shutil.rmtree(user_data, ignore_errors=True)
            await ctx.send("✅ Chrome user-data cleared.")
        except Exception as e:
            await ctx.send(f"⚠️ Failed to clear profile dir: `{e}` continuing")

    await ctx.send("🛠️ Launching reset helper rebuild & recreate target service only…")

    pn = f" --project-name {_q(project_name)}" if project_name else ""
    cf = f" -f {_q(compose_file)}"
    nc = " --no-cache" if nocache else ""

    helper_name = "casino-reset-helper"

    helper_script = (
        "set -euo pipefail; "
        f"docker rm -f {_q(target_svc)} || true; "
        f"docker compose{pn}{cf} build{nc} {_q(target_svc)}; "
        f"docker compose{pn}{cf} up -d --no-deps --remove-orphans {_q(target_svc)}"
    )

    await _run(ctx, ["docker", "pull", helper_image], prefix="pull ")

    run_cmd = [
        "docker",
        "run",
        "-d",
        "--rm",
        "--name",
        helper_name,
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
        "-v",
        f"{compose_dir}:{compose_dir}",
        "-w",
        compose_dir,
        helper_image,
        "sh",
        "-lc",
        helper_script,
    ]

    rc, out, err = await _run(ctx, run_cmd, prefix="run ")

    if rc == 0 and out.strip():
        helper_id = out.strip()[:12]

        await ctx.send(
            f"✅ Helper started as `{helper_id}`.\n"
            f"It will rebuild & up **{target_svc}** only. Watchtower stays running.\n"
            f"To watch progress from host: `docker logs -f {helper_name}`"
        )

        await ctx.send("👋 Exiting current bot container so the helper can replace it.")

        try:
            await bot.close()
        finally:
            os._exit(0)

        return

    await ctx.send("⚠️ Helper failed to start. Falling back to host-side background reset…")

    bg_log = "/tmp/reset-fallback.log"

    script = (
        f"set -euo pipefail; "
        f"docker rm -f {_q(target_svc)} || true; "
        f"docker compose{pn}{cf} build{nc} {_q(target_svc)}; "
        f"docker compose{pn}{cf} up -d --no-deps --remove-orphans {_q(target_svc)}"
    )

    bg_cmd = ["sh", "-lc", f"nohup sh -lc {_q(script)} > {bg_log} 2>&1 & echo $!"]
    rc2, out2, err2 = await _run(ctx, bg_cmd, cwd=compose_dir, prefix="fallback ")

    if rc2 == 0:
        pid = out2.strip()

        await ctx.send(
            f"✅ Background reset launched PID {pid}.\n"
            f"Logs: `{bg_log}` inside this container until it exits.\n"
            "From the host you can also run:\n"
            f"```bash\ndocker compose -f {compose_file} ps\n"
            f"docker logs -f {target_svc}\n```"
        )

        await ctx.send("👋 Exiting current bot container now.")

        try:
            await bot.close()
        finally:
            os._exit(0)

        return

    await ctx.send("❌ Reset helper and fallback both failed. Check stderr above and your Docker setup.")


# ───────────────────────────────────────────────────────────
# Config command
# ───────────────────────────────────────────────────────────
def format_loop_config() -> str:
    status = "running" if is_main_loop_running() else "stopped"

    lines = [
        "🎛️ **Casino loop configuration**",
        f"Status: **{status}**",
        "Order, state, and intervals:",
    ]

    for i, e in enumerate(casino_loop_entries, 1):
        state = "enabled" if e.enabled else "disabled"
        lines.append(
            f"{i}. {e.display_name} (`{e.key}`) – **{state}** – every {e.interval_minutes:.1f} minutes"
        )

    lines += [
        "",
        "Use `!config interval <casino> <minutes>` to change an interval.",
        "Use `!config enable <casino>` to enable a casino in the loop.",
        "Use `!config disable <casino>` to disable a casino in the loop.",
        "Use `!config order <casino1> <casino2> ...>` to set a new run order.",
    ]

    return "\n".join(lines)


@dcommands.group(name="config", invoke_without_command=True)
async def _config(ctx: dcommands.Context):
    await ctx.send(format_loop_config())


bot.add_command(_config)


@_config.command(name="interval")
async def config_interval(ctx: dcommands.Context, casino: str, minutes: float):
    target = find_loop_entry(casino)

    if not target:
        await ctx.send(f"Casino `{casino}` is not part of the automated loop.")
        return

    if minutes <= 0:
        await ctx.send("Interval must be greater than zero.")
        return

    target.interval_minutes = minutes
    target.next_run = dt.datetime.now(dt.timezone.utc)

    await ctx.send(f"Updated {target.display_name} to run every {minutes:.1f} minutes.")


@_config.command(name="enable")
async def config_enable(ctx: dcommands.Context, casino: str):
    target = find_loop_entry(casino)

    if not target:
        await ctx.send(f"Casino `{casino}` is not part of the automated loop.")
        return

    if target.enabled:
        await ctx.send(f"{target.display_name} is already enabled.")
        return

    target.enabled = True
    target.next_run = dt.datetime.now(dt.timezone.utc)

    await ctx.send(f"✅ Enabled {target.display_name} in the automated loop.")


@_config.command(name="disable")
async def config_disable(ctx: dcommands.Context, casino: str):
    target = find_loop_entry(casino)

    if not target:
        await ctx.send(f"Casino `{casino}` is not part of the automated loop.")
        return

    if not target.enabled:
        await ctx.send(f"{target.display_name} is already disabled.")
        return

    target.enabled = False

    await ctx.send(f"⏸️ Disabled {target.display_name} in the automated loop.")


@_config.command(name="order")
async def config_order(ctx: dcommands.Context, *casinos: str):
    if not casinos:
        await ctx.send("Provide the complete list of casino keys in the desired order.")
        return

    desired = [CASINO_ALIAS_MAP.get(c.lower(), c.lower()) for c in casinos]
    current = [e.key for e in casino_loop_entries]

    if len(desired) != len(current) or set(desired) != set(current):
        await ctx.send(f"You must include each of: {', '.join(current)} exactly once.")
        return

    lookup = {e.key: e for e in casino_loop_entries}
    casino_loop_entries[:] = [lookup[k] for k in desired]

    reset_loop_schedule()

    await ctx.send("Casino loop order updated.\n" + format_loop_config())


# ───────────────────────────────────────────────────────────
# General commands
# ───────────────────────────────────────────────────────────
@bot.command(name="ping")
async def ping(ctx):
    await ctx.send("Pong")


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

    try:
        await ctx.send(f"🧩 **Chrome build:** `{version_num}`", file=discord.File(snap))
    finally:
        try:
            os.remove(snap)
        except Exception:
            pass


@bot.command(name="restart")
async def restart(ctx):
    await ctx.send("Restarting…")
    await bot.close()
    os._exit(0)


# ───────────────────────────────────────────────────────────
# Manual casino commands
# ───────────────────────────────────────────────────────────
@bot.command(name="realprize", aliases=["real prize", "rp"])
async def realprize_cmd(ctx):
    await ctx.send("Checking Real Prize for bonus…")
    await realprize_casino(ctx, driver, bot.get_channel(DISCORD_CHANNEL))


@bot.command(name="zula", aliases=["zula casino", "zulacasino"])
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


@bot.command(name="yaycasino", aliases=["yay", "yay casino"])
async def yaycasino_cmd(ctx):
    await ctx.send("Checking YayCasino for bonus…")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await yaycasino_uc(ctx, channel)


@bot.command(name="globalpoker", aliases=["gp", "global poker"])
async def globalpoker_cmd(ctx):
    await ctx.send("Checking GlobalPoker for bonus…")
    await global_poker(ctx, driver, bot.get_channel(DISCORD_CHANNEL))


@bot.command(name="jefebet", aliases=["jefe", "jefebet casino", "jefe bet", "jb"])
async def jefebet_cmd(ctx):
    await ctx.send("Checking JefeBet for bonus…")
    await jefebet_casino(ctx, driver, bot.get_channel(DISCORD_CHANNEL))


@bot.command(name="smilescasino", aliases=["smiles", "smiles casino"])
async def smilescasino_cmd(ctx):
    await ctx.send("Checking Smiles Casino for bonus...")
    await smilescasino_casino(ctx, driver, bot.get_channel(DISCORD_CHANNEL))


@bot.command(name="jumbo")
async def jumbo_cmd(ctx):
    await ctx.send("Checking Jumbo for bonus...")
    await jumbo_casino(ctx, driver, bot.get_channel(DISCORD_CHANNEL))


@bot.command(name="spree")
async def spree_cmd(ctx):
    await ctx.send("Checking Spree for bonus...")
    await spree_uc(ctx, bot.get_channel(DISCORD_CHANNEL))


@bot.command(name="wildworld")
async def wildworld_cmd(ctx):
    await ctx.send("Checking Wild World Casino for bonus...")
    await wildworld_casino(ctx, driver, bot.get_channel(DISCORD_CHANNEL))


@bot.command(name="lonestar")
async def lonestar_cmd(ctx):
    await ctx.send("Checking LoneStar Casino for bonus...")
    await lonestar_casino(ctx, driver, bot.get_channel(DISCORD_CHANNEL))


@bot.command(name="gains")
async def gains_cmd(ctx):
    await ctx.send("Checking Gains for bonus...")
    await gains_casino(ctx, driver, bot.get_channel(DISCORD_CHANNEL))


@bot.command(name="chipnwin")
async def chipnwin_cmd(ctx):
    await ctx.send("Checking Chipnwin for bonus...")
    await chipnwin_casino(ctx, driver, bot.get_channel(DISCORD_CHANNEL))


@bot.command(name="crowncoins")
async def crowncoins_cmd(ctx):
    await ctx.send("Checking Crown Coins Casino for bonus…")
    await crowncoins_casino(driver, bot, ctx, bot.get_channel(DISCORD_CHANNEL))


@bot.command(name="americanluck", aliases=["aluck", "a-luck", "american luck"])
async def americanluck_cmd(ctx):
    await ctx.send("Checking American Luck for bonus…")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await americanluck_uc(ctx, channel)


@bot.command(
    name="luckparty",
    aliases=[
        "luckyparty",
        "lp",
        "luck-party",
        "lucky-party",
        "luckpartycasino",
        "luckypartycasino",
    ],
)
async def luckparty_cmd(ctx):
    channel = bot.get_channel(DISCORD_CHANNEL)
    await _call_luckparty(channel=channel, ctx=ctx, raise_errors=False)


@bot.command(
    name="winbonanza",
    aliases=[
        "wb",
        "win-bonanza",
        "win bonanza",
        "winbonanzacasino",
    ],
)
async def winbonanza_cmd(ctx):
    channel = bot.get_channel(DISCORD_CHANNEL)
    await _call_winbonanza(channel=channel, ctx=ctx, raise_errors=False)


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


@bot.command(name="luckyland", aliases=["lucky land"])
async def luckyland_cmd(ctx):
    await ctx.send("Checking LuckyLand for bonus…")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await luckyland_uc(ctx, channel)


@bot.command(name="stake")
async def stake_cmd(ctx):
    await ctx.send("Checking Stake for bonus…")
    await stake_claim(driver, bot, ctx, bot.get_channel(DISCORD_CHANNEL))


@bot.command(name="fortunewheelz")
async def fortunewheelz_cmd(ctx):
    await ctx.send("Checking Fortune Wheelz for bonus…")
    await fortunewheelz_flow(ctx, driver, bot.get_channel(DISCORD_CHANNEL))


@bot.command(name="fortunewins", aliases=["fortune wins", "fw", "fortune coins", "fc", "fortunecoins"])
async def fortunecoins_cmd(ctx):
    await ctx.send("Checking Fortune Wins for bonus…")

    channel = bot.get_channel(DISCORD_CHANNEL)
    loop = asyncio.get_running_loop()

    from fortunecoinsAPI import fortunecoins_uc_blocking

    _exec_job_started()
    try:
        await loop.run_in_executor(_executor, fortunecoins_uc_blocking, bot, channel.id, loop)
    finally:
        _exec_job_finished()


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
# !debug <casino>
# ───────────────────────────────────────────────────────────
def _runner_to_coro(runner_func: Callable[[], Any]):
    async def _wrapped():
        result = runner_func()
        return await _maybe_await(result)

    return _wrapped()


@bot.command(name="debug")
async def debug_cmd(ctx, *, casino: str):
    key = normalize_casino_key(casino)

    if not key:
        await ctx.send("Usage: `!debug <casino>` example: `!debug spinquest`")
        return

    key = CASINO_ALIAS_MAP.get(key, key)

    channel = bot.get_channel(DISCORD_CHANNEL)

    runners = {
        "realprize": lambda: realprize_casino(ctx, driver, channel),
        "zula": lambda: zula_uc(ctx, channel),
        "sportzino": lambda: Sportzino(ctx, driver, channel),
        "nolimitcoins": lambda: nolimitcoins_flow(ctx, driver, channel),
        "funrize": lambda: funrize_flow(ctx, driver, channel),
        "yaycasino": lambda: yaycasino_uc(ctx, channel),
        "globalpoker": lambda: global_poker(ctx, driver, channel),
        "jefebet": lambda: jefebet_casino(ctx, driver, channel),
        "smilescasino": lambda: smilescasino_casino(ctx, driver, channel),
        "jumbo": lambda: jumbo_casino(ctx, driver, channel),
        "spree": lambda: spree_uc(ctx, channel),
        "chipnwin": lambda: chipnwin_casino(ctx, driver, channel),
        "wildworld": lambda: wildworld_casino(ctx, driver, channel),
        "lonestar": lambda: lonestar_casino(ctx, driver, channel),
        "gains": lambda: gains_casino(ctx, driver, channel),
        "crowncoins": lambda: crowncoins_casino(driver, bot, ctx, channel),
        "americanluck": lambda: americanluck_uc(ctx, channel),
        "rollingriches": lambda: rolling_riches_casino(ctx, driver, channel),
        "luckyland": lambda: luckyland_uc(ctx, channel),
        "stake": lambda: stake_claim(driver, bot, ctx, channel),
        "fortunewheelz": lambda: fortunewheelz_flow(ctx, driver, channel),
        "spinquest": lambda: spinquest_flow(ctx, driver, channel),
        "spinpals": lambda: spinpals_flow(ctx, driver, channel),
        "chumba": lambda: chumba_cmd(ctx),
        "chanced": lambda: chanced_cmd(ctx),
        "dingdingding": lambda: dingdingding_cmd(ctx),

        # Custom wrappers.
        "luckparty": lambda: _call_luckparty(channel=channel, ctx=ctx, raise_errors=True),
        "winbonanza": lambda: _call_winbonanza(channel=channel, ctx=ctx, raise_errors=True),
    }

    if key == "modo":
        async def _modo_flow():
            ok = await claim_modo_bonus(driver, bot, ctx, channel)
            if not ok:
                await check_modo_countdown(driver, bot, ctx, channel)

        target_coro = _modo_flow()

    elif key in runners:
        target_coro = _runner_to_coro(runners[key])

    else:
        await ctx.send(
            f"❌ Unknown casino `{casino}`.\n"
            "Try one of: " + ", ".join(sorted(list(runners.keys()) + ["modo"]))
        )
        return

    await ctx.send(f"🧪 Debugging `{key}` — sending periodic screenshots while it runs…")

    interval = int(os.getenv("DEBUG_SCREENSHOT_INTERVAL", "4"))
    max_shots = int(os.getenv("DEBUG_SCREENSHOT_MAX", "40"))

    try:
        await run_with_periodic_screenshots(
            channel=ctx.channel,
            driver=driver,
            casino_key=key,
            coro=target_coro,
            interval_seconds=interval,
            max_shots=max_shots,
            label="debug",
        )

        await ctx.send(f"✅ Debug finished for `{key}`.")

    except Exception as e:
        await ctx.send(f"⚠️ Debug error for `{key}`: `{type(e).__name__}: {e}`")


# ───────────────────────────────────────────────────────────
# Auth router
# ───────────────────────────────────────────────────────────
@bot.command(name="auth")
async def authenticate_command(ctx: commands.Context, site: str, method: str = None):
    channel = bot.get_channel(DISCORD_CHANNEL)
    norm_site = re.sub(r"\s+", "", site.lower())

    if norm_site == "google":
        await ctx.send("Authenticating Google Account…")

        google_credentials = os.getenv("GOOGLE_LOGIN")

        if google_credentials:
            u, p = google_credentials.split(":", 1)
            creds = (u, p)
        else:
            await ctx.send("🔐 Google credentials not found in `.env` `GOOGLE_LOGIN`.")
            creds = (None, None)

        try:
            await google_auth(ctx, driver, channel, creds)
        except Exception as e:
            snap = "google_auth_failed.png"
            try:
                driver.save_screenshot(snap)
                await ctx.send(f"Google auth error: `{e}`", file=discord.File(snap))
            finally:
                try:
                    os.remove(snap)
                except Exception:
                    pass

        return

    if norm_site == "modo":
        await ctx.send("Authenticating Modo…")
        await run_modo_auth(channel)
        return

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
                try:
                    os.remove(snap)
                except Exception:
                    pass

        return

    if norm_site == "dingdingding":
        await ctx.send("Authenticating DingDingDing…")

        ok = await authenticate_dingdingding(driver, bot, ctx, channel)

        if not ok:
            snap = "dingdingding_auth_failed.png"
            try:
                driver.save_screenshot(snap)
                await ctx.send("Authentication failed.", file=discord.File(snap))
            finally:
                try:
                    os.remove(snap)
                except Exception:
                    pass

        return

    if norm_site == "stake":
        await ctx.send("Authenticating Stake…")

        ok = await stake_auth(driver, bot, ctx, channel)

        if not ok:
            snap = "stake_auth_failed.png"
            try:
                driver.save_screenshot(snap)
                await ctx.send("Stake authentication failed.", file=discord.File(snap))
            finally:
                try:
                    os.remove(snap)
                except Exception:
                    pass

        return

    if norm_site in {"nolimitcoins", "nlc", "nolimit", "no limit coins"}:
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
                try:
                    os.remove(snap)
                except Exception:
                    pass

        return

    await ctx.send(
        f"❓ Authentication for `{site}` is not implemented. "
        "Run `!help` for supported sites. Run `!debug <casino>` for screenshot debugging."
    )


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

    await ctx.send(f"⚠️ An error occurred while handling that command: `{type(error).__name__}: {error}`")


# ───────────────────────────────────────────────────────────
# Help command
# ───────────────────────────────────────────────────────────
@bot.command(name="help")
async def help_cmd(ctx):
    await ctx.send(
        """Commands are not recommended while the casino loop is running.

🎰 **Casino Commands:**  
!chanced, !globalpoker, !crowncoins, !chumba, !modo, !zula,  
!rollingriches, !jefebet, !spinpals, !spinquest, !funrize, !sportzino,  
!fortunecoins, !nolimitcoins, !fortunewheelz, !stake, !dingdingding,
!smilescasino, !yaycasino, !realprize, !luckyland, !jumbo, !spree,
!chipnwin, !wildworld, !lonestar, !gains, !luckparty, !winbonanza

Aliases:
!luckyparty, !lp
!wb

---------------------------------------  
🧪 **Debug:**  
!debug <casino>   ex: !debug spinquest
!debug luckparty
!debug winbonanza

---------------------------------------  
✅ **Auth Commands:**  
!auth google  
!auth modo  
!auth crowncoins google | !auth crowncoins env  
!auth nolimitcoins google | !auth nolimitcoins env  
!authmodo  shortcut

---------------------------------------  
🧩 **Diagnostics:**
!imports
!imports luckparty
!imports winbonanza

---------------------------------------  
⚙️ **General:**  
!ping, !restart, !help, !start, !stop, !about, !config, !reset

Examples:
`!config disable spinquest`
`!config enable winbonanza`
`!winbonanza`
"""
    )


# ───────────────────────────────────────────────────────────
# Run bot
# ───────────────────────────────────────────────────────────
bot.run(DISCORD_TOKEN)