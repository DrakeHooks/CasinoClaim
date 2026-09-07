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
import logging
import discord
import asyncio
import importlib
import importlib.util
import threading
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
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

DISCORD_HEARTBEAT_TIMEOUT = float(os.getenv("DISCORD_HEARTBEAT_TIMEOUT", "300"))
DISCORD_GATEWAY_LOG_LEVEL = os.getenv("DISCORD_GATEWAY_LOG_LEVEL", "WARNING").upper()
RUN_CASINOS_IN_WORKER_THREAD = os.getenv("RUN_CASINOS_IN_WORKER_THREAD", "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logging.getLogger("discord.gateway").setLevel(
    getattr(logging, DISCORD_GATEWAY_LOG_LEVEL, logging.WARNING)
)
logging.getLogger("discord.client").setLevel(logging.INFO)


# ───────────────────────────────────────────────────────────
# Executor tracking
# ───────────────────────────────────────────────────────────
_executor = ThreadPoolExecutor(max_workers=int(os.getenv("BOT_MISC_WORKERS", "4")))

# One dedicated Selenium worker keeps Discord's asyncio heartbeat loop responsive.
# Keep this at 1 worker because the shared Chrome driver/profile is not safe to
# use from multiple casino checks at the same time.
_casino_executor = ThreadPoolExecutor(max_workers=1)

_active_exec_jobs = 0
_active_exec_lock = threading.Lock()

_casino_worker_lock = threading.Lock()
_casino_worker_current_job: Optional[str] = None
_casino_worker_started_at: Optional[dt.datetime] = None
_worker_local = threading.local()


def _exec_job_started():
    global _active_exec_jobs
    with _active_exec_lock:
        _active_exec_jobs += 1


def _exec_job_finished():
    global _active_exec_jobs
    with _active_exec_lock:
        _active_exec_jobs = max(0, _active_exec_jobs - 1)


def _casino_worker_started(label: str) -> None:
    global _casino_worker_current_job, _casino_worker_started_at

    with _casino_worker_lock:
        _casino_worker_current_job = label
        _casino_worker_started_at = dt.datetime.now(dt.timezone.utc)


def _casino_worker_finished() -> None:
    global _casino_worker_current_job, _casino_worker_started_at

    with _casino_worker_lock:
        _casino_worker_current_job = None
        _casino_worker_started_at = None


def _casino_worker_status() -> dict:
    with _casino_worker_lock:
        label = _casino_worker_current_job
        started = _casino_worker_started_at

    age_seconds = None
    if started is not None:
        age_seconds = int((dt.datetime.now(dt.timezone.utc) - started).total_seconds())

    return {
        "active": bool(label),
        "label": label,
        "started_at": started,
        "age_seconds": age_seconds,
    }


def _casino_worker_busy() -> bool:
    return bool(_casino_worker_status()["active"])


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

CONFIG_PATH = Path(
    os.getenv("CASINO_CONFIG_PATH")
    or os.getenv("BOT_CONFIG_PATH")
    or os.getenv("CONFIG_PATH")
    or "config.toml"
)

if not CONFIG_PATH.is_absolute():
    CONFIG_PATH = BASE_DIR / CONFIG_PATH

CONFIG_LAST_MTIME: Optional[float] = None
CONFIG_LOCK = threading.Lock()

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
    "stormrushAPI",
    "scarletsandsAPI",
    "playtanaAPI",
    "cashoomoAPI",
    "taofortuneAPI",
    "sweepjungleAPI",
    "zumoAPI",
    "jollysweepsAPI",
    "gleamingAPI",
    "sweepicoAPI",
    "sweepsharkAPI",
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


class MainLoopMessageProxy:
    """
    Small proxy used by the Selenium worker thread.

    It lets casino APIs keep doing `await channel.send(...)`, while the actual
    Discord send runs safely on the real Discord/bot event loop.
    """

    def __init__(self, target, main_loop: asyncio.AbstractEventLoop):
        self._target = target
        self._main_loop = main_loop
        self.id = getattr(target, "id", None)
        self.name = getattr(target, "name", None)
        self.guild = getattr(target, "guild", None)

    @property
    def channel(self):
        return self

    async def send(self, *args, **kwargs):
        if self._main_loop.is_closed():
            return None

        future = asyncio.run_coroutine_threadsafe(
            self._target.send(*args, **kwargs),
            self._main_loop,
        )
        return await asyncio.wrap_future(future)

    def __getattr__(self, item):
        return getattr(self._target, item)


class MainLoopBotProxy:
    """Proxy bot methods that must run on the real Discord event loop."""

    def __init__(self, real_bot: commands.Bot, main_loop: asyncio.AbstractEventLoop):
        self._bot = real_bot
        self._main_loop = main_loop

    def get_channel(self, channel_id):
        channel = self._bot.get_channel(channel_id)
        if channel is None:
            return None
        return MainLoopMessageProxy(channel, self._main_loop)

    async def wait_for(self, *args, **kwargs):
        future = asyncio.run_coroutine_threadsafe(
            self._bot.wait_for(*args, **kwargs),
            self._main_loop,
        )
        return await asyncio.wrap_future(future)

    async def close(self):
        future = asyncio.run_coroutine_threadsafe(self._bot.close(), self._main_loop)
        return await asyncio.wrap_future(future)

    def __getattr__(self, item):
        return getattr(self._bot, item)


class MainLoopContextProxy:
    """Proxy command context used from the Selenium worker thread.

    This keeps old API files working when they do `await ctx.send(...)` while the
    casino code itself is running away from Discord's real event loop.
    """

    def __init__(self, ctx: commands.Context, main_loop: asyncio.AbstractEventLoop):
        self._ctx = ctx
        self._main_loop = main_loop
        self.bot = MainLoopBotProxy(bot, main_loop)
        self.channel = MainLoopMessageProxy(ctx.channel, main_loop)
        self.guild = getattr(ctx, "guild", None)
        self.author = getattr(ctx, "author", None)
        self.message = getattr(ctx, "message", None)
        self.command = getattr(ctx, "command", None)
        self.prefix = getattr(ctx, "prefix", None)

    async def send(self, *args, **kwargs):
        if self._main_loop.is_closed():
            return None

        future = asyncio.run_coroutine_threadsafe(
            self._ctx.send(*args, **kwargs),
            self._main_loop,
        )
        return await asyncio.wrap_future(future)

    async def reply(self, *args, **kwargs):
        if self._main_loop.is_closed():
            return None

        future = asyncio.run_coroutine_threadsafe(
            self._ctx.reply(*args, **kwargs),
            self._main_loop,
        )
        return await asyncio.wrap_future(future)

    def typing(self):
        return self._ctx.typing()

    def __getattr__(self, item):
        return getattr(self._ctx, item)


def _bot():
    return getattr(_worker_local, "bot_proxy", bot)


def _run_runner_in_worker_thread(
    runner: Callable[[discord.abc.Messageable], Awaitable[None]],
    channel: discord.abc.Messageable,
    main_loop: asyncio.AbstractEventLoop,
    label: str,
):
    """Run one casino runner in the dedicated Selenium thread."""
    proxy_channel = MainLoopMessageProxy(channel, main_loop)
    _worker_local.bot_proxy = MainLoopBotProxy(bot, main_loop)
    _casino_worker_started(label)

    try:
        async def _inner():
            result = runner(proxy_channel)
            return await _maybe_await(result)

        return asyncio.run(_inner())

    finally:
        try:
            delattr(_worker_local, "bot_proxy")
        except Exception:
            pass
        _casino_worker_finished()


async def _run_entry_without_blocking_discord(entry: Any, channel: discord.abc.Messageable):
    """
    Keep Discord alive by moving blocking Selenium work off the main asyncio loop.

    FortuneCoins already uses its own blocking executor path that needs the real
    Discord loop, so leave it on the main loop wrapper.
    """
    if not RUN_CASINOS_IN_WORKER_THREAD or entry.key == "fortunecoins":
        return await entry.runner(channel)

    main_loop = asyncio.get_running_loop()
    return await main_loop.run_in_executor(
        _casino_executor,
        _run_runner_in_worker_thread,
        entry.runner,
        channel,
        main_loop,
        entry.display_name,
    )


async def _run_callable_without_blocking_discord(label: str, func, channel: discord.abc.Messageable):
    if not RUN_CASINOS_IN_WORKER_THREAD:
        result = func(channel)
        return await _maybe_await(result)

    main_loop = asyncio.get_running_loop()
    return await main_loop.run_in_executor(
        _casino_executor,
        _run_runner_in_worker_thread,
        func,
        channel,
        main_loop,
        label,
    )


def _run_manual_action_in_worker_thread(label: str, ctx: commands.Context, main_loop: asyncio.AbstractEventLoop, action):
    """Run a manual command's Selenium code away from Discord's event loop."""
    proxy_ctx = MainLoopContextProxy(ctx, main_loop)
    real_channel = bot.get_channel(DISCORD_CHANNEL) or ctx.channel
    proxy_channel = MainLoopMessageProxy(real_channel, main_loop)

    _worker_local.bot_proxy = MainLoopBotProxy(bot, main_loop)
    _casino_worker_started(label)

    try:
        async def _inner():
            result = action(proxy_ctx, proxy_channel)
            return await _maybe_await(result)

        return asyncio.run(_inner())

    finally:
        try:
            delattr(_worker_local, "bot_proxy")
        except Exception:
            pass
        _casino_worker_finished()


async def _run_manual_casino_command(ctx: commands.Context, label: str, action, *, queued_message: bool = True):
    """Queue one manual Selenium command without blocking Discord heartbeats.

    `action` receives `(proxy_ctx, proxy_channel)`. Any `await ctx.send()` or
    `await channel.send()` done by older API files is forwarded to the real
    Discord loop safely.
    """
    if _casino_worker_busy():
        worker = _casino_worker_status()
        try:
            await ctx.send(
                f"⏳ Selenium worker is busy with `{worker['label']}` for ~{worker['age_seconds']}s. "
                f"Queued `{label}` next. `!ping` and `!status` will still work."
            )
        except Exception:
            pass
    elif queued_message:
        try:
            await ctx.send(
                f"`{label}` is running in the Selenium worker so Discord heartbeat/commands stay alive."
            )
        except Exception:
            pass

    if not RUN_CASINOS_IN_WORKER_THREAD:
        try:
            result = action(ctx, bot.get_channel(DISCORD_CHANNEL) or ctx.channel)
            return await _maybe_await(result)
        except Exception as e:
            print(f"[Manual] Error in {label}: {type(e).__name__}: {e}")
            traceback.print_exc()
            await ctx.send(f"⚠️ `{label}` error: `{type(e).__name__}: {e}`")
            return None

    main_loop = asyncio.get_running_loop()

    try:
        return await main_loop.run_in_executor(
            _casino_executor,
            _run_manual_action_in_worker_thread,
            label,
            ctx,
            main_loop,
            action,
        )
    except Exception as e:
        print(f"[Manual] Error in {label}: {type(e).__name__}: {e}")
        traceback.print_exc()
        try:
            await ctx.send(f"⚠️ `{label}` error: `{type(e).__name__}: {e}`")
        except Exception:
            pass
        return None


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


async def _call_fortunewheelz(channel=None, ctx=None, raise_errors: bool = False):
    """
    Safe Fortune Wheelz wrapper.

    Newer Fortune Wheelz API files use `fortunewheelz_casino`.
    Older main.py files called `fortunewheelz_flow`, which causes:
      NameError: name 'fortunewheelz_flow' is not defined

    This wrapper accepts either function name so main.py will not break
    if the API file changes again.
    """
    target = ctx or channel

    fn = _get_api_callable(
        "fortunewheelzAPI",
        "fortunewheelz_casino",
        "fortunewheelz_flow",
    )

    if not fn:
        import_error = API_IMPORT_ERRORS.get("fortunewheelzAPI")

        if import_error:
            await _send_long_message(
                target,
                "❌ `fortunewheelzAPI` is not available.\n"
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
                "❌ `fortunewheelzAPI` imported, but no callable was found.\n"
                "Expected one of: `fortunewheelz_casino` or `fortunewheelz_flow`."
            )

        if raise_errors:
            raise RuntimeError("fortunewheelzAPI is unavailable. Run !imports fortunewheelz for details.")

        return None

    try:
        try:
            sig = inspect.signature(fn)
            params = sig.parameters

            if len(params) >= 3:
                result = fn(ctx, driver, channel)
            elif "channel" in params and "ctx" in params:
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
            result = fn(ctx, driver, channel)

        return await _maybe_await(result)

    except Exception as e:
        msg = f"⚠️ Fortune Wheelz error: `{type(e).__name__}: {e}`"
        await _send_long_message(target, msg)

        if raise_errors:
            raise

        return None


# ───────────────────────────────────────────────────────────
# Discord setup
# ───────────────────────────────────────────────────────────
intents = Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, case_insensitive=True, heartbeat_timeout=DISCORD_HEARTBEAT_TIMEOUT)
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
bot._pending_2fa_event = threading.Event()
bot._2fa_lock = threading.Lock()


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
                    bot._pending_2fa_event = threading.Event()
                    bot._pending_2fa_event.set()
            else:
                bot.two_fa_code = text
                print(f"[2FA] Stored code legacy fallback: {bot.two_fa_code}")

    try:
        await bot.process_commands(message)
    except Exception as e:
        print(f"[on_message] process_commands failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        try:
            await message.channel.send(f"⚠️ Command handling error: `{type(e).__name__}: {e}`")
        except Exception:
            pass


async def wait_for_2fa(site_name: str, timeout: int = 90) -> Optional[str]:
    """
    Thread-safe 2FA capture.

    Casino checks may now run in the Selenium worker thread so Discord's heartbeat
    loop stays alive. A normal asyncio.Event is tied to one event loop, so use a
    threading.Event and wait on it without blocking whichever asyncio loop called us.
    """
    with bot._2fa_lock:
        if bot.awaiting_2fa_for:
            return None

        bot.awaiting_2fa_for = site_name
        bot.pending_2fa_code = None
        bot._pending_2fa_event = threading.Event()

    try:
        got_code = await asyncio.to_thread(bot._pending_2fa_event.wait, timeout)
        code = bot.pending_2fa_code if got_code else None
    finally:
        with bot._2fa_lock:
            bot.awaiting_2fa_for = None
            bot.pending_2fa_code = None
            bot._pending_2fa_event = threading.Event()

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


LOOP_STAGGER_SECONDS = int(os.getenv("LOOP_STAGGER_SECONDS", "30"))
PER_CASINO_TIMEOUT_SEC = int(os.getenv("CASINO_TIMEOUT_SECONDS", "500"))
MAIN_TICK_SLEEP = int(os.getenv("MAIN_TICK_SLEEP_SECONDS", "10"))

AUTOAUTH_ENABLED = False
AUTOAUTH_INTERVAL_MINUTES = 720.0
AUTOAUTH_RUN_ON_START = False
AUTOAUTH_NEXT_RUN: Optional[dt.datetime] = None
AUTOAUTH_SIGNATURE = None

AUTODATACLEAR_ENABLED = False
AUTODATACLEAR_INTERVAL_MINUTES = 1440.0
AUTODATACLEAR_RUN_ON_START = False
AUTODATACLEAR_NEXT_RUN: Optional[dt.datetime] = None
AUTODATACLEAR_SIGNATURE = None


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
    await crowncoins_casino(driver, _bot(), None, channel)


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


async def _run_stormrush(channel):
    await stormrush_casino(None, driver, channel)


async def _run_scarletsands(channel):
    await scarletsands_casino(None, driver, channel)


async def _run_playtana(channel):
    await playtana_casino(None, driver, channel)


async def _run_cashoomo(channel):
    await cashoomo_casino(None, driver, channel)


async def _run_taofortune(channel):
    await taofortune_casino(None, driver, channel)


async def _run_sweepjungle(channel):
    await sweepjungle_casino(None, driver, channel)


async def _run_zumo(channel):
    await zumo_casino(None, driver, channel)


async def _run_jollysweeps(channel):
    await jollysweeps_casino(None, driver, channel)


async def _run_gleaming(channel):
    await gleaming_casino(None, driver, channel)


async def _run_sweepico(channel):
    await sweepico_casino(None, driver, channel)


async def _run_sweepshark(channel):
    await sweepshark_casino(None, driver, channel)


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
    ok = await claim_modo_bonus(driver, _bot(), None, channel)

    if not ok:
        await check_modo_countdown(driver, _bot(), None, channel)


async def _run_rollingriches(channel):
    await rolling_riches_casino(None, driver, channel)


async def _run_stake(channel):
    await stake_claim(driver, _bot(), None, channel)


async def _run_fortunewheelz(channel):
    await _call_fortunewheelz(channel=channel, ctx=None, raise_errors=True)


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

    CasinoLoopEntry("cashoomo", "Cashoomo", _run_cashoomo, 720),
    CasinoLoopEntry("taofortune", "TaoFortune", _run_taofortune, 1440),
    CasinoLoopEntry("gains", "Gains", _run_gains, 1440),
    CasinoLoopEntry("stormrush", "Stormrush", _run_stormrush, 1440),
    CasinoLoopEntry("scarletsands", "Scarlet Sands", _run_scarletsands, 1440),
    CasinoLoopEntry("playtana", "Playtana", _run_playtana, 1440),
    CasinoLoopEntry("realprize", "Real Prize", _run_realprize, 1440),
    CasinoLoopEntry("lonestar", "LoneStar Casino", _run_lonestar, 1440),
    CasinoLoopEntry("wildworld", "WildWorld", _run_wildworld, 1440),
    CasinoLoopEntry("funrize", "Funrize", _run_funrize, 1440),

    CasinoLoopEntry("sweepico", "Sweepico", _run_sweepico, 1440),
    CasinoLoopEntry("sweepshark", "Sweepshark", _run_sweepshark, 1440),

    CasinoLoopEntry("sweepjungle", "SweepJungle", _run_sweepjungle, 1440),
    CasinoLoopEntry("zumo", "Zumo", _run_zumo, 1440),

    CasinoLoopEntry("jollysweeps", "Jolly Sweeps", _run_jollysweeps, 1440),

    CasinoLoopEntry("gleaming", "Gleaming", _run_gleaming, 1440),

    CasinoLoopEntry("rollingriches", "Rolling Riches", _run_rollingriches, 1440),
    CasinoLoopEntry("americanluck", "American Luck", _run_americanluck, 1440),
    CasinoLoopEntry("fortunecoins", "Fortune Coins", _run_fortunecoins, 1440),
    CasinoLoopEntry("zula", "Zula Casino", _run_zula, 1440),
    CasinoLoopEntry("sportzino", "Sportzino", _run_sportzino, 1440),
    CasinoLoopEntry("yaycasino", "YayCasino", _run_yaycasino, 1440),
    CasinoLoopEntry("chipnwin", "Chipnwin", _run_chipnwin, 1440),
    CasinoLoopEntry("luckparty", "Luck Party", _run_luckparty, 1440),
    CasinoLoopEntry("winbonanza", "WinBonanza", _run_winbonanza, 1440),

    # CasinoLoopEntry("modo", "Modo", _run_modo, 120),
    # CasinoLoopEntry("stake", "Stake", _run_stake, 120),
    # CasinoLoopEntry("smilescasino", "Smiles Casino", _run_smilescasino, 1440),
    # CasinoLoopEntry("luckyland", "LuckyLand", _run_luckyland, 1440),
]


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
    "fortunewheelz": "fortunewheelz",
    "fortune wheelz": "fortunewheelz",
    "fortune-wheelz": "fortunewheelz",
    "fzw": "fortunewheelz",
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
# Persistent TOML config
# ───────────────────────────────────────────────────────────
def normalize_config_key(value: str) -> str:
    key = (value or "").strip().lower()
    key = re.sub(r"\s+", " ", key)
    key = CASINO_ALIAS_MAP.get(key, key)
    key = key.replace(" ", "")
    return CASINO_ALIAS_MAP.get(key, key)


def _toml_escape(value: str) -> str:
    return (
        '"'
        + str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        + '"'
    )


def _toml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, int):
        return str(value)

    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value)

    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"

    return _toml_escape(str(value))


def _config_dict_from_runtime() -> dict:
    return {
        "bot": {
            "loop_stagger_seconds": int(LOOP_STAGGER_SECONDS),
            "per_casino_timeout_seconds": int(PER_CASINO_TIMEOUT_SEC),
            "main_tick_sleep_seconds": int(MAIN_TICK_SLEEP),
        },
        "autoauth": {
            "enabled": bool(AUTOAUTH_ENABLED),
            "interval_minutes": float(AUTOAUTH_INTERVAL_MINUTES),
            "run_on_start": bool(AUTOAUTH_RUN_ON_START),
        },
        "autodataclear": {
            "enabled": bool(AUTODATACLEAR_ENABLED),
            "interval_minutes": float(AUTODATACLEAR_INTERVAL_MINUTES),
            "run_on_start": bool(AUTODATACLEAR_RUN_ON_START),
        },
        "casinos": [
            {
                "key": entry.key,
                "display_name": entry.display_name,
                "enabled": bool(entry.enabled),
                "interval_minutes": float(entry.interval_minutes),
            }
            for entry in casino_loop_entries
        ],
    }


def _write_toml_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# CasinoClaim persistent configuration",
        "# This file is safe to bind-mount so settings survive Watchtower/container updates.",
        "# You can edit this file directly or use Discord !config commands.",
        "",
        "[bot]",
    ]

    bot_config = config.get("bot", {})
    for key in ("loop_stagger_seconds", "per_casino_timeout_seconds", "main_tick_sleep_seconds"):
        lines.append(f"{key} = {_toml_value(bot_config.get(key))}")

    lines += [
        "",
        "[autoauth]",
    ]

    autoauth_config = config.get("autoauth", {})
    for key in ("enabled", "interval_minutes", "run_on_start"):
        lines.append(f"{key} = {_toml_value(autoauth_config.get(key))}")

    lines += [
        "",
        "[autodataclear]",
    ]

    autodataclear_config = config.get("autodataclear", {})
    for key in ("enabled", "interval_minutes", "run_on_start"):
        lines.append(f"{key} = {_toml_value(autodataclear_config.get(key))}")

    for casino in config.get("casinos", []):
        lines += [
            "",
            "[[casinos]]",
            f"key = {_toml_value(casino.get('key'))}",
            f"display_name = {_toml_value(casino.get('display_name'))}",
            f"enabled = {_toml_value(bool(casino.get('enabled', True)))}",
            f"interval_minutes = {_toml_value(float(casino.get('interval_minutes', 1440)))}",
        ]

    CONFIG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_config_from_runtime() -> None:
    global CONFIG_LAST_MTIME

    with CONFIG_LOCK:
        config = _config_dict_from_runtime()
        _write_toml_config(config)

        try:
            CONFIG_LAST_MTIME = CONFIG_PATH.stat().st_mtime
        except Exception:
            CONFIG_LAST_MTIME = None


def _bool_from_config(value, default=False) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "enabled", "enable"}

    return default


def _float_from_config(value, default: float) -> float:
    try:
        parsed = float(value)
        if parsed <= 0:
            return default
        return parsed
    except Exception:
        return default


def _int_from_config(value, default: int) -> int:
    try:
        parsed = int(float(value))
        if parsed <= 0:
            return default
        return parsed
    except Exception:
        return default


def _sync_auto_schedules(force: bool = False) -> None:
    global AUTOAUTH_NEXT_RUN, AUTOAUTH_SIGNATURE
    global AUTODATACLEAR_NEXT_RUN, AUTODATACLEAR_SIGNATURE

    now = dt.datetime.now(dt.timezone.utc)

    autoauth_sig = (AUTOAUTH_ENABLED, AUTOAUTH_INTERVAL_MINUTES, AUTOAUTH_RUN_ON_START)
    if force or autoauth_sig != AUTOAUTH_SIGNATURE:
        AUTOAUTH_SIGNATURE = autoauth_sig

        if AUTOAUTH_ENABLED:
            if AUTOAUTH_RUN_ON_START:
                AUTOAUTH_NEXT_RUN = now
            else:
                AUTOAUTH_NEXT_RUN = now + dt.timedelta(minutes=AUTOAUTH_INTERVAL_MINUTES)
        else:
            AUTOAUTH_NEXT_RUN = None

    dataclear_sig = (AUTODATACLEAR_ENABLED, AUTODATACLEAR_INTERVAL_MINUTES, AUTODATACLEAR_RUN_ON_START)
    if force or dataclear_sig != AUTODATACLEAR_SIGNATURE:
        AUTODATACLEAR_SIGNATURE = dataclear_sig

        if AUTODATACLEAR_ENABLED:
            if AUTODATACLEAR_RUN_ON_START:
                AUTODATACLEAR_NEXT_RUN = now
            else:
                AUTODATACLEAR_NEXT_RUN = now + dt.timedelta(minutes=AUTODATACLEAR_INTERVAL_MINUTES)
        else:
            AUTODATACLEAR_NEXT_RUN = None


def apply_config_to_runtime(config: dict, preserve_next_runs: bool = True) -> None:
    global LOOP_STAGGER_SECONDS, PER_CASINO_TIMEOUT_SEC, MAIN_TICK_SLEEP
    global AUTOAUTH_ENABLED, AUTOAUTH_INTERVAL_MINUTES, AUTOAUTH_RUN_ON_START
    global AUTODATACLEAR_ENABLED, AUTODATACLEAR_INTERVAL_MINUTES, AUTODATACLEAR_RUN_ON_START

    bot_config = config.get("bot", {})
    autoauth_config = config.get("autoauth", {})
    autodataclear_config = config.get("autodataclear", {})

    LOOP_STAGGER_SECONDS = _int_from_config(
        bot_config.get("loop_stagger_seconds", LOOP_STAGGER_SECONDS),
        LOOP_STAGGER_SECONDS,
    )

    PER_CASINO_TIMEOUT_SEC = _int_from_config(
        bot_config.get("per_casino_timeout_seconds", PER_CASINO_TIMEOUT_SEC),
        PER_CASINO_TIMEOUT_SEC,
    )

    MAIN_TICK_SLEEP = _int_from_config(
        bot_config.get("main_tick_sleep_seconds", MAIN_TICK_SLEEP),
        MAIN_TICK_SLEEP,
    )

    AUTOAUTH_ENABLED = _bool_from_config(
        autoauth_config.get("enabled", AUTOAUTH_ENABLED),
        AUTOAUTH_ENABLED,
    )

    AUTOAUTH_INTERVAL_MINUTES = _float_from_config(
        autoauth_config.get("interval_minutes", AUTOAUTH_INTERVAL_MINUTES),
        AUTOAUTH_INTERVAL_MINUTES,
    )

    AUTOAUTH_RUN_ON_START = _bool_from_config(
        autoauth_config.get("run_on_start", AUTOAUTH_RUN_ON_START),
        AUTOAUTH_RUN_ON_START,
    )

    AUTODATACLEAR_ENABLED = _bool_from_config(
        autodataclear_config.get("enabled", AUTODATACLEAR_ENABLED),
        AUTODATACLEAR_ENABLED,
    )

    AUTODATACLEAR_INTERVAL_MINUTES = _float_from_config(
        autodataclear_config.get("interval_minutes", AUTODATACLEAR_INTERVAL_MINUTES),
        AUTODATACLEAR_INTERVAL_MINUTES,
    )

    AUTODATACLEAR_RUN_ON_START = _bool_from_config(
        autodataclear_config.get("run_on_start", AUTODATACLEAR_RUN_ON_START),
        AUTODATACLEAR_RUN_ON_START,
    )

    lookup = {entry.key: entry for entry in casino_loop_entries}
    configured_entries = []

    for item in config.get("casinos", []):
        if not isinstance(item, dict):
            continue

        key = normalize_config_key(str(item.get("key", "")))
        if not key or key not in lookup:
            continue

        entry = lookup[key]

        entry.enabled = _bool_from_config(item.get("enabled", entry.enabled), entry.enabled)
        entry.interval_minutes = _float_from_config(
            item.get("interval_minutes", entry.interval_minutes),
            entry.interval_minutes,
        )

        display_name = str(item.get("display_name", "")).strip()
        if display_name:
            entry.display_name = display_name

        configured_entries.append(entry)

    seen = {entry.key for entry in configured_entries}

    for entry in casino_loop_entries:
        if entry.key not in seen:
            configured_entries.append(entry)

    if configured_entries:
        casino_loop_entries[:] = configured_entries

    _sync_auto_schedules(force=not preserve_next_runs)


def load_config_from_disk(force: bool = False, create_missing: bool = True) -> bool:
    """
    Returns True if config was loaded or created.
    """
    global CONFIG_LAST_MTIME

    if not CONFIG_PATH.exists():
        if create_missing:
            save_config_from_runtime()
            print(f"[Config] Created default config at {CONFIG_PATH}")
            return True

        return False

    try:
        current_mtime = CONFIG_PATH.stat().st_mtime
    except Exception:
        current_mtime = None

    if not force and CONFIG_LAST_MTIME is not None and current_mtime == CONFIG_LAST_MTIME:
        return False

    try:
        with CONFIG_PATH.open("rb") as f:
            config = tomllib.load(f)

        apply_config_to_runtime(config, preserve_next_runs=True)
        CONFIG_LAST_MTIME = current_mtime
        print(f"[Config] Loaded config from {CONFIG_PATH}")
        return True

    except Exception as e:
        print(f"[Config] Failed to load {CONFIG_PATH}: {type(e).__name__}: {e}")
        return False


def reload_config_if_changed() -> bool:
    return load_config_from_disk(force=False, create_missing=True)


def reset_loop_schedule():
    base = dt.datetime.now(dt.timezone.utc)
    for i, entry in enumerate(casino_loop_entries):
        entry.next_run = base + dt.timedelta(seconds=i * LOOP_STAGGER_SECONDS)


def find_loop_entry(casino: str) -> Optional[CasinoLoopEntry]:
    casino = normalize_config_key(casino)
    return next((e for e in casino_loop_entries if e.key.lower() == casino), None)


main_loop_task: Optional[asyncio.Task] = None
main_loop_running = False


def is_main_loop_running() -> bool:
    return main_loop_running and main_loop_task and not main_loop_task.done()


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


async def clear_chrome_user_data(channel=None, reason: str = "manual") -> bool:
    global driver

    root = _detect_user_data_dir()

    if not root:
        if channel:
            await channel.send("⚠️ No CHROME_INSTANCE_DIR or CHROME_USER_DATA_DIR configured — nothing to clear.")
        return False

    if channel:
        await channel.send(f"🧽 Clearing Chrome user-data for `{reason}`:\n```{root}```")

    for _ in range(40):
        with _active_exec_lock:
            busy = _active_exec_jobs

        if busy == 0:
            break

        await asyncio.sleep(0.5)

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

        if killed and channel:
            await channel.send(f"🔪 Killed {killed} stray Chrome processes.")

    except Exception:
        pass

    try:
        shutil.rmtree(root, ignore_errors=True)
    except Exception as e:
        if channel:
            await channel.send(f"⚠️ Failed to clear profile dir: `{e}`")
        return False

    try:
        driver = _build_driver_with_retry(options)
    except Exception as e:
        if channel:
            await channel.send(f"❌ Failed to restart Chrome after data clear: `{type(e).__name__}: {e}`")
        return False

    if channel:
        await channel.send("✅ Chrome user-data cleared and Chrome restarted.")

    return True


async def run_auto_google_auth(channel) -> bool:
    google_credentials = os.getenv("GOOGLE_LOGIN")

    if not google_credentials or ":" not in google_credentials:
        try:
            await channel.send("⚠️ Autoauth skipped: missing `.env` `GOOGLE_LOGIN=email:password`.")
        except Exception:
            pass
        return False

    u, p = google_credentials.split(":", 1)
    creds = (u, p)

    try:
        await channel.send("🔐 Autoauth: authenticating Google account…")
    except Exception:
        pass

    try:
        result = google_auth(None, driver, channel, creds)
        await _maybe_await(result)

        try:
            await channel.send("✅ Autoauth Google finished.")
        except Exception:
            pass

        return True

    except Exception as e:
        try:
            await channel.send(f"⚠️ Autoauth Google failed: `{type(e).__name__}: {e}`")
        except Exception:
            pass

        return False


async def maybe_run_auto_tasks(channel):
    global AUTOAUTH_NEXT_RUN, AUTODATACLEAR_NEXT_RUN

    now = dt.datetime.now(dt.timezone.utc)

    if AUTOAUTH_ENABLED and AUTOAUTH_NEXT_RUN is not None and now >= AUTOAUTH_NEXT_RUN:
        try:
            await _run_callable_without_blocking_discord("Autoauth Google", run_auto_google_auth, channel)
        finally:
            AUTOAUTH_NEXT_RUN = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=AUTOAUTH_INTERVAL_MINUTES)

    if AUTODATACLEAR_ENABLED and AUTODATACLEAR_NEXT_RUN is not None and now >= AUTODATACLEAR_NEXT_RUN:
        try:
            await clear_chrome_user_data(channel=channel, reason="autodataclear")
        finally:
            AUTODATACLEAR_NEXT_RUN = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
                minutes=AUTODATACLEAR_INTERVAL_MINUTES
            )


async def run_main_loop(channel: discord.abc.Messageable):
    global main_loop_running

    try:
        while main_loop_running:
            reload_config_if_changed()

            if _casino_worker_busy():
                # A previous Selenium run timed out from the scheduler's point of view,
                # but the browser thread is still unwinding. Do not queue more browser work.
                await asyncio.sleep(MAIN_TICK_SLEEP)
                continue

            await maybe_run_auto_tasks(channel)

            now = dt.datetime.now(dt.timezone.utc)

            for entry in list(casino_loop_entries):
                if not entry.enabled:
                    continue

                if _casino_worker_busy():
                    break

                if now >= entry.next_run:
                    timed_out = False

                    try:
                        await asyncio.wait_for(
                            _run_entry_without_blocking_discord(entry, channel),
                            timeout=PER_CASINO_TIMEOUT_SEC,
                        )
                    except asyncio.TimeoutError:
                        timed_out = True
                        try:
                            await channel.send(
                                f"⏳ {entry.display_name} timed out after {PER_CASINO_TIMEOUT_SEC}s. "
                                "Discord is still online; waiting for the Selenium worker to finish before queueing more."
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

                    if timed_out:
                        break

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

    load_config_from_disk(force=True, create_missing=True)
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


# Load/create config before the bot starts.
load_config_from_disk(force=True, create_missing=True)


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
async def on_connect():
    print("[Discord] Gateway connected.")


@bot.event
async def on_disconnect():
    print("[Discord] Gateway disconnected. discord.py will reconnect automatically.")


@bot.event
async def on_resumed():
    print("[Discord] Gateway session resumed.")


@bot.event
async def on_ready():
    first_ready = not getattr(bot, "_startup_complete", False)
    bot._startup_complete = True

    print(f"Bot has connected as {bot.user}")
    channel = bot.get_channel(DISCORD_CHANNEL)

    if not channel:
        print("Invalid DISCORD_CHANNEL")
        return

    if first_ready:
        await channel.send("Discord bot has started…")

    if await start_main_loop(channel):
        await channel.send("🎰 Casino loop started with current TOML configuration.")
    elif first_ready:
        await channel.send("🎰 Casino loop is already running.")


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
    "stormrush",
    "scarletsands",
    "playtana",
    "cashoomo",
    "taofortune",
    "sweepjungle",
    "zumo",
    "jollysweeps",
    "gleaming",
    "sweepico",
    "sweepshark",
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
        worker = _casino_worker_status()
        msg = "Casino loop stopped. You can run manual casino commands now."

        if worker["active"]:
            msg += (
                f"\n⚠️ `{worker['label']}` is still finishing in the Selenium worker "
                "thread. Use `!status` to watch it, or `!restart` if Chrome is truly stuck."
            )

        await ctx.send(msg)
    else:
        await ctx.send("Casino loop is not currently running.")


@bot.command(name="cleardatadir")
async def clear_data_dir(ctx: commands.Context):
    root = _detect_user_data_dir()

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

    try:
        if is_main_loop_running():
            await stop_main_loop()
    except Exception:
        pass

    await clear_chrome_user_data(channel=ctx.channel, reason="manual cleardatadir")

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
        f"• Config file: `{CONFIG_PATH}`\n"
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
def _next_run_text(value: Optional[dt.datetime]) -> str:
    if value is None:
        return "disabled"

    now = dt.datetime.now(dt.timezone.utc)
    seconds = max(0, int((value - now).total_seconds()))
    minutes = seconds // 60

    return f"in ~{minutes} min"


def format_loop_config() -> str:
    reload_config_if_changed()

    status = "running" if is_main_loop_running() else "stopped"

    lines = [
        "🎛️ **CasinoClaim TOML configuration**",
        f"Config file: `{CONFIG_PATH}`",
        f"Status: **{status}**",
        "",
        "**Bot:**",
        f"loop_stagger_seconds: `{LOOP_STAGGER_SECONDS}`",
        f"per_casino_timeout_seconds: `{PER_CASINO_TIMEOUT_SEC}`",
        f"main_tick_sleep_seconds: `{MAIN_TICK_SLEEP}`",
        "",
        "**Automation:**",
        f"autoauth: `{'enabled' if AUTOAUTH_ENABLED else 'disabled'}` every `{AUTOAUTH_INTERVAL_MINUTES:g}` min, next `{_next_run_text(AUTOAUTH_NEXT_RUN)}`",
        f"autodataclear: `{'enabled' if AUTODATACLEAR_ENABLED else 'disabled'}` every `{AUTODATACLEAR_INTERVAL_MINUTES:g}` min, next `{_next_run_text(AUTODATACLEAR_NEXT_RUN)}`",
        "",
        "**Casino order, state, and intervals:**",
    ]

    for i, e in enumerate(casino_loop_entries, 1):
        state = "enabled" if e.enabled else "disabled"
        lines.append(
            f"{i}. {e.display_name} (`{e.key}`) – **{state}** – every {e.interval_minutes:.1f} minutes"
        )

    lines += [
        "",
        "**Commands:**",
        "`!config reload` - reload config from TOML",
        "`!config save` - overwrite TOML with current runtime config",
        "`!config enable <casino>`",
        "`!config disable <casino>`",
        "`!config interval <casino> <minutes>`",
        "`!config order <casino1> <casino2> ...>`",
        "`!config autoauth enable|disable|interval|runonstart [value]`",
        "`!config autodataclear enable|disable|interval|runonstart [value]`",
        "`!config bot loop_stagger_seconds|per_casino_timeout_seconds|main_tick_sleep_seconds <value>`",
    ]

    return "\n".join(lines)


@dcommands.group(name="config", invoke_without_command=True)
async def _config(ctx: dcommands.Context):
    await _send_long_message(ctx, format_loop_config())


bot.add_command(_config)


@_config.command(name="path")
async def config_path(ctx: dcommands.Context):
    await ctx.send(f"Config path:\n```{CONFIG_PATH}```")


@_config.command(name="reload")
async def config_reload(ctx: dcommands.Context):
    loaded = load_config_from_disk(force=True, create_missing=True)

    if loaded:
        reset_loop_schedule()
        await ctx.send("✅ Reloaded TOML config and reset loop schedule.")
    else:
        await ctx.send("⚠️ Could not reload TOML config. Check container logs.")


@_config.command(name="save")
async def config_save(ctx: dcommands.Context):
    save_config_from_runtime()
    await ctx.send(f"✅ Wrote current runtime config to:\n```{CONFIG_PATH}```")


@_config.command(name="show")
async def config_show(ctx: dcommands.Context):
    await _send_long_message(ctx, format_loop_config())


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
    save_config_from_runtime()

    await ctx.send(f"✅ Updated {target.display_name} to run every {minutes:.1f} minutes and wrote TOML config.")


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
    save_config_from_runtime()

    await ctx.send(f"✅ Enabled {target.display_name} in the automated loop and wrote TOML config.")


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
    save_config_from_runtime()

    await ctx.send(f"⏸️ Disabled {target.display_name} in the automated loop and wrote TOML config.")


@_config.command(name="order")
async def config_order(ctx: dcommands.Context, *casinos: str):
    if not casinos:
        await ctx.send("Provide the complete list of casino keys in the desired order.")
        return

    desired = [normalize_config_key(c) for c in casinos]
    current = [e.key for e in casino_loop_entries]

    if len(desired) != len(current) or set(desired) != set(current):
        await ctx.send(
            "You must include each casino exactly once.\n"
            f"Current keys:\n```{', '.join(current)}```"
        )
        return

    lookup = {e.key: e for e in casino_loop_entries}
    casino_loop_entries[:] = [lookup[k] for k in desired]

    reset_loop_schedule()
    save_config_from_runtime()

    await ctx.send("✅ Casino loop order updated and TOML config overwritten.\n" + format_loop_config())


@_config.command(name="bot")
async def config_bot(ctx: dcommands.Context, setting: str = "", value: str = ""):
    global LOOP_STAGGER_SECONDS, PER_CASINO_TIMEOUT_SEC, MAIN_TICK_SLEEP

    setting = (setting or "").strip().lower()
    value = (value or "").strip()

    allowed = {
        "loop_stagger_seconds",
        "per_casino_timeout_seconds",
        "main_tick_sleep_seconds",
    }

    if setting not in allowed or not value:
        await ctx.send(
            "Usage:\n"
            "`!config bot loop_stagger_seconds 30`\n"
            "`!config bot per_casino_timeout_seconds 500`\n"
            "`!config bot main_tick_sleep_seconds 10`"
        )
        return

    try:
        parsed = int(float(value))
    except Exception:
        await ctx.send("Value must be a number.")
        return

    if parsed <= 0:
        await ctx.send("Value must be greater than zero.")
        return

    if setting == "loop_stagger_seconds":
        LOOP_STAGGER_SECONDS = parsed
    elif setting == "per_casino_timeout_seconds":
        PER_CASINO_TIMEOUT_SEC = parsed
    elif setting == "main_tick_sleep_seconds":
        MAIN_TICK_SLEEP = parsed

    save_config_from_runtime()
    await ctx.send(f"✅ Updated `{setting}` to `{parsed}` and wrote TOML config.")


def _parse_bool_arg(value: str) -> Optional[bool]:
    value = (value or "").strip().lower()

    if value in {"1", "true", "yes", "y", "on", "enable", "enabled"}:
        return True

    if value in {"0", "false", "no", "n", "off", "disable", "disabled"}:
        return False

    return None


@_config.command(name="autoauth")
async def config_autoauth(ctx: dcommands.Context, action: str = "", value: str = ""):
    global AUTOAUTH_ENABLED, AUTOAUTH_INTERVAL_MINUTES, AUTOAUTH_RUN_ON_START

    action = (action or "").strip().lower()
    value = (value or "").strip()

    if action in {"enable", "enabled", "on", "true"}:
        AUTOAUTH_ENABLED = True

        if value:
            try:
                AUTOAUTH_INTERVAL_MINUTES = float(value)
            except Exception:
                await ctx.send("Interval must be a number of minutes.")
                return

        _sync_auto_schedules(force=True)
        save_config_from_runtime()
        await ctx.send(f"✅ Autoauth enabled every `{AUTOAUTH_INTERVAL_MINUTES:g}` minutes and TOML config written.")
        return

    if action in {"disable", "disabled", "off", "false"}:
        AUTOAUTH_ENABLED = False
        _sync_auto_schedules(force=True)
        save_config_from_runtime()
        await ctx.send("⏸️ Autoauth disabled and TOML config written.")
        return

    if action == "interval":
        try:
            minutes = float(value)
        except Exception:
            await ctx.send("Usage: `!config autoauth interval <minutes>`")
            return

        if minutes <= 0:
            await ctx.send("Interval must be greater than zero.")
            return

        AUTOAUTH_INTERVAL_MINUTES = minutes
        _sync_auto_schedules(force=True)
        save_config_from_runtime()
        await ctx.send(f"✅ Autoauth interval set to `{minutes:g}` minutes and TOML config written.")
        return

    if action in {"runonstart", "run_on_start"}:
        parsed = _parse_bool_arg(value)

        if parsed is None:
            await ctx.send("Usage: `!config autoauth runonstart true|false`")
            return

        AUTOAUTH_RUN_ON_START = parsed
        _sync_auto_schedules(force=True)
        save_config_from_runtime()
        await ctx.send(f"✅ Autoauth run_on_start set to `{parsed}` and TOML config written.")
        return

    await ctx.send(
        "Usage:\n"
        "`!config autoauth enable [minutes]`\n"
        "`!config autoauth disable`\n"
        "`!config autoauth interval <minutes>`\n"
        "`!config autoauth runonstart true|false`"
    )


@_config.command(name="autodataclear")
async def config_autodataclear(ctx: dcommands.Context, action: str = "", value: str = ""):
    global AUTODATACLEAR_ENABLED, AUTODATACLEAR_INTERVAL_MINUTES, AUTODATACLEAR_RUN_ON_START

    action = (action or "").strip().lower()
    value = (value or "").strip()

    if action in {"enable", "enabled", "on", "true"}:
        AUTODATACLEAR_ENABLED = True

        if value:
            try:
                AUTODATACLEAR_INTERVAL_MINUTES = float(value)
            except Exception:
                await ctx.send("Interval must be a number of minutes.")
                return

        _sync_auto_schedules(force=True)
        save_config_from_runtime()
        await ctx.send(
            f"✅ Autodataclear enabled every `{AUTODATACLEAR_INTERVAL_MINUTES:g}` minutes and TOML config written."
        )
        return

    if action in {"disable", "disabled", "off", "false"}:
        AUTODATACLEAR_ENABLED = False
        _sync_auto_schedules(force=True)
        save_config_from_runtime()
        await ctx.send("⏸️ Autodataclear disabled and TOML config written.")
        return

    if action == "interval":
        try:
            minutes = float(value)
        except Exception:
            await ctx.send("Usage: `!config autodataclear interval <minutes>`")
            return

        if minutes <= 0:
            await ctx.send("Interval must be greater than zero.")
            return

        AUTODATACLEAR_INTERVAL_MINUTES = minutes
        _sync_auto_schedules(force=True)
        save_config_from_runtime()
        await ctx.send(f"✅ Autodataclear interval set to `{minutes:g}` minutes and TOML config written.")
        return

    if action in {"runonstart", "run_on_start"}:
        parsed = _parse_bool_arg(value)

        if parsed is None:
            await ctx.send("Usage: `!config autodataclear runonstart true|false`")
            return

        AUTODATACLEAR_RUN_ON_START = parsed
        _sync_auto_schedules(force=True)
        save_config_from_runtime()
        await ctx.send(f"✅ Autodataclear run_on_start set to `{parsed}` and TOML config written.")
        return

    await ctx.send(
        "Usage:\n"
        "`!config autodataclear enable [minutes]`\n"
        "`!config autodataclear disable`\n"
        "`!config autodataclear interval <minutes>`\n"
        "`!config autodataclear runonstart true|false`"
    )


# ───────────────────────────────────────────────────────────
# General commands
# ───────────────────────────────────────────────────────────
@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"Pong `{bot.latency * 1000:.0f}ms`")


@bot.command(name="status")
async def status_cmd(ctx):
    worker = _casino_worker_status()

    if worker["active"]:
        worker_text = f"`{worker['label']}` for ~{worker['age_seconds']}s"
    else:
        worker_text = "`idle`"

    with _active_exec_lock:
        active_misc_jobs = _active_exec_jobs

    await ctx.send(
        "🧩 **CasinoClaim status**\n"
        f"Discord ready: `{'yes' if bot.is_ready() else 'no'}`\n"
        f"Discord latency: `{bot.latency * 1000:.0f}ms`\n"
        f"Main loop: `{'running' if is_main_loop_running() else 'stopped'}`\n"
        f"Selenium worker: {worker_text}\n"
        f"Misc executor jobs: `{active_misc_jobs}`\n"
        f"Worker-thread mode: `{'enabled' if RUN_CASINOS_IN_WORKER_THREAD else 'disabled'}`\n"
        f"Heartbeat timeout: `{DISCORD_HEARTBEAT_TIMEOUT:g}s`\n"
        f"Config: `{CONFIG_PATH}`"
    )


async def _about_chrome_worker(ctx, channel):
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


@bot.command(name="about")
async def about(ctx):
    await ctx.send("🔍 Retrieving Chrome version …")
    await _run_manual_casino_command(ctx, "about:chrome", _about_chrome_worker, queued_message=False)


@bot.command(name="restart")
async def restart(ctx):
    await ctx.send("Restarting…")
    await bot.close()
    os._exit(0)


# ───────────────────────────────────────────────────────────
# Manual casino commands
# IMPORTANT:
# Every Selenium-heavy manual command runs through _run_manual_casino_command().
# This is what prevents commands like !zula from freezing Discord's heartbeat.
# ───────────────────────────────────────────────────────────
async def _manual_chumba_flow(ctx, channel):
    driver.get("https://lobby.chumbacasino.com/")
    await asyncio.sleep(5)

    if driver.current_url.startswith("https://login.chumbacasino.com/"):
        authenticated = await authenticate_chumba(driver, _bot(), ctx)

        if not authenticated:
            await ctx.send("Chumba authentication failed.")
            return

    if driver.current_url.startswith("https://lobby.chumbacasino.com/"):
        await claim_chumba_bonus(driver, ctx)
        await check_chumba_countdown(driver, ctx)
    else:
        await ctx.send("Failed to reach the Chumba lobby.")


async def _manual_modo_flow(ctx, channel):
    ok = await claim_modo_bonus(driver, _bot(), ctx, channel)

    if not ok:
        await check_modo_countdown(driver, _bot(), ctx, channel)


async def _manual_dingdingding_flow(ctx, channel):
    claimed = await claim_dingdingding_bonus(driver, _bot(), ctx, channel)

    if not claimed:
        await check_dingdingding_countdown(driver, _bot(), ctx, channel)


async def _manual_fortunecoins_flow(ctx, channel):
    """Fortune Coins/Fortune Wins has its own blocking entrypoint.

    Run it inside the same single Selenium worker lane, but give it the real main
    Discord loop so its existing cross-thread sends still work.
    """
    from fortunecoinsAPI import fortunecoins_uc_blocking

    main_loop = getattr(channel, "_main_loop", None)
    real_channel_id = getattr(channel, "id", None) or DISCORD_CHANNEL

    if main_loop is None:
        # Fallback for worker-thread mode disabled.
        main_loop = asyncio.get_running_loop()

    _exec_job_started()
    try:
        return fortunecoins_uc_blocking(_bot(), real_channel_id, main_loop)
    finally:
        _exec_job_finished()


@bot.command(name="realprize", aliases=["real prize", "rp"])
async def realprize_cmd(ctx):
    await ctx.send("Checking Real Prize for bonus…")
    await _run_manual_casino_command(
        ctx,
        "Real Prize",
        lambda pctx, channel: realprize_casino(pctx, driver, channel),
    )


@bot.command(name="zula", aliases=["zula casino", "zulacasino"])
async def zula_cmd(ctx):
    await ctx.send("Checking Zula Casino for bonus…")
    await _run_manual_casino_command(
        ctx,
        "Zula Casino",
        lambda pctx, channel: zula_uc(pctx, channel),
    )


@bot.command(name="sportzino")
async def sportzino_cmd(ctx):
    await ctx.send("Checking Sportzino for bonus…")
    await _run_manual_casino_command(
        ctx,
        "Sportzino",
        lambda pctx, channel: Sportzino(pctx, driver, channel),
    )


@bot.command(name="nolimitcoins", aliases=["nlc", "no limit", "no limit coins"])
async def nolimitcoins_cmd(ctx):
    await ctx.send("Checking NoLimitCoins for bonus…")
    await _run_manual_casino_command(
        ctx,
        "NoLimitCoins",
        lambda pctx, channel: nolimitcoins_flow(pctx, driver, channel),
    )


@bot.command(name="funrize")
async def funrize_cmd(ctx):
    await ctx.send("Checking Funrize for bonus…")
    await _run_manual_casino_command(
        ctx,
        "Funrize",
        lambda pctx, channel: funrize_flow(pctx, driver, channel),
    )


@bot.command(name="yaycasino", aliases=["yay", "yay casino"])
async def yaycasino_cmd(ctx):
    await ctx.send("Checking YayCasino for bonus…")
    await _run_manual_casino_command(
        ctx,
        "YayCasino",
        lambda pctx, channel: yaycasino_uc(pctx, channel),
    )


@bot.command(name="globalpoker", aliases=["gp", "global poker"])
async def globalpoker_cmd(ctx):
    await ctx.send("Checking GlobalPoker for bonus…")
    await _run_manual_casino_command(
        ctx,
        "GlobalPoker",
        lambda pctx, channel: global_poker(pctx, driver, channel),
    )


@bot.command(name="jefebet", aliases=["jefe", "jefebet casino", "jefe bet", "jb"])
async def jefebet_cmd(ctx):
    await ctx.send("Checking JefeBet for bonus…")
    await _run_manual_casino_command(
        ctx,
        "JefeBet",
        lambda pctx, channel: jefebet_casino(pctx, driver, channel),
    )


@bot.command(name="smilescasino", aliases=["smiles", "smiles casino"])
async def smilescasino_cmd(ctx):
    await ctx.send("Checking Smiles Casino for bonus...")
    await _run_manual_casino_command(
        ctx,
        "Smiles Casino",
        lambda pctx, channel: smilescasino_casino(pctx, driver, channel),
    )


@bot.command(name="jumbo")
async def jumbo_cmd(ctx):
    await ctx.send("Checking Jumbo for bonus...")
    await _run_manual_casino_command(
        ctx,
        "Jumbo",
        lambda pctx, channel: jumbo_casino(pctx, driver, channel),
    )


@bot.command(name="spree")
async def spree_cmd(ctx):
    await ctx.send("Checking Spree for bonus...")
    await _run_manual_casino_command(
        ctx,
        "Spree",
        lambda pctx, channel: spree_uc(pctx, channel),
    )


@bot.command(name="wildworld")
async def wildworld_cmd(ctx):
    await ctx.send("Checking Wild World Casino for bonus...")
    await _run_manual_casino_command(
        ctx,
        "Wild World",
        lambda pctx, channel: wildworld_casino(pctx, driver, channel),
    )


@bot.command(name="lonestar")
async def lonestar_cmd(ctx):
    await ctx.send("Checking LoneStar Casino for bonus...")
    await _run_manual_casino_command(
        ctx,
        "LoneStar Casino",
        lambda pctx, channel: lonestar_casino(pctx, driver, channel),
    )


@bot.command(name="gains")
async def gains_cmd(ctx):
    await ctx.send("Checking Gains for bonus...")
    await _run_manual_casino_command(
        ctx,
        "Gains",
        lambda pctx, channel: gains_casino(pctx, driver, channel),
    )


@bot.command(name="stormrush")
async def stormrush_cmd(ctx):
    await ctx.send("Checking Stormrush for bonus...")
    await _run_manual_casino_command(
        ctx,
        "Stormrush",
        lambda pctx, channel: stormrush_casino(pctx, driver, channel),
    )


@bot.command(name="scarletsands")
async def scarletsands_cmd(ctx):
    await ctx.send("Checking Scarlet Sands for bonus...")
    await _run_manual_casino_command(
        ctx,
        "Scarlet Sands",
        lambda pctx, channel: scarletsands_casino(pctx, driver, channel),
    )


@bot.command(name="playtana")
async def playtana_cmd(ctx):
    await ctx.send("Checking Playtana for bonus...")
    await _run_manual_casino_command(
        ctx,
        "Playtana",
        lambda pctx, channel: playtana_casino(pctx, driver, channel),
    )


@bot.command(name="cashoomo")
async def cashoomo_cmd(ctx):
    await ctx.send("Checking Cashoomo for bonus...")
    await _run_manual_casino_command(
        ctx,
        "Cashoomo",
        lambda pctx, channel: cashoomo_casino(pctx, driver, channel),
    )


@bot.command(name="taofortune")
async def taofortune_cmd(ctx):
    await ctx.send("Checking TaoFortune for bonus...")
    await _run_manual_casino_command(
        ctx,
        "TaoFortune",
        lambda pctx, channel: taofortune_casino(pctx, driver, channel),
    )


@bot.command(name="sweepjungle")
async def sweepjungle_cmd(ctx):
    await ctx.send("Checking SweepJungle for bonus...")
    await _run_manual_casino_command(
        ctx,
        "SweepJungle",
        lambda pctx, channel: sweepjungle_casino(pctx, driver, channel),
    )


@bot.command(name="zumo")
async def zumo_cmd(ctx):
    await ctx.send("Checking Zumo for bonus...")
    await _run_manual_casino_command(
        ctx,
        "Zumo",
        lambda pctx, channel: zumo_casino(pctx, driver, channel),
    )


@bot.command(name="jollysweeps")
async def jollysweeps_cmd(ctx):
    await ctx.send("Checking Jolly Sweeps for bonus...")
    await _run_manual_casino_command(
        ctx,
        "Jolly Sweeps",
        lambda pctx, channel: jollysweeps_casino(pctx, driver, channel),
    )


@bot.command(name="gleaming")
async def gleaming_cmd(ctx):
    await ctx.send("Checking Gleaming for bonus...")
    await _run_manual_casino_command(
        ctx,
        "Gleaming",
        lambda pctx, channel: gleaming_casino(pctx, driver, channel),
    )


@bot.command(name="sweepico")
async def sweepico_cmd(ctx):
    await ctx.send("Checking Sweepico for bonus...")
    await _run_manual_casino_command(
        ctx,
        "Sweepico",
        lambda pctx, channel: sweepico_casino(pctx, driver, channel),
    )


@bot.command(name="sweepshark")
async def sweepshark_cmd(ctx):
    await ctx.send("Checking Sweepshark for bonus...")
    await _run_manual_casino_command(
        ctx,
        "Sweepshark",
        lambda pctx, channel: sweepshark_casino(pctx, driver, channel),
    )


@bot.command(name="chipnwin")
async def chipnwin_cmd(ctx):
    await ctx.send("Checking Chipnwin for bonus...")
    await _run_manual_casino_command(
        ctx,
        "Chipnwin",
        lambda pctx, channel: chipnwin_casino(pctx, driver, channel),
    )


@bot.command(name="crowncoins")
async def crowncoins_cmd(ctx):
    await ctx.send("Checking Crown Coins Casino for bonus…")
    await _run_manual_casino_command(
        ctx,
        "Crown Coins",
        lambda pctx, channel: crowncoins_casino(driver, _bot(), pctx, channel),
    )


@bot.command(name="americanluck", aliases=["aluck", "a-luck", "american luck"])
async def americanluck_cmd(ctx):
    await ctx.send("Checking American Luck for bonus…")
    await _run_manual_casino_command(
        ctx,
        "American Luck",
        lambda pctx, channel: americanluck_uc(pctx, channel),
    )


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
    await _run_manual_casino_command(
        ctx,
        "Luck Party",
        lambda pctx, channel: _call_luckparty(channel=channel, ctx=pctx, raise_errors=False),
    )


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
    await _run_manual_casino_command(
        ctx,
        "WinBonanza",
        lambda pctx, channel: _call_winbonanza(channel=channel, ctx=pctx, raise_errors=False),
    )


@bot.command(name="modo")
async def modo_cmd(ctx):
    await ctx.send("Checking Modo for bonus…")
    await _run_manual_casino_command(ctx, "Modo", _manual_modo_flow)


@bot.command(name="rollingriches", aliases=["rr", "rolling riches"])
async def rollingriches_cmd(ctx):
    await ctx.send("Checking Rolling Riches for bonus…")
    await _run_manual_casino_command(
        ctx,
        "Rolling Riches",
        lambda pctx, channel: rolling_riches_casino(pctx, driver, channel),
    )


@bot.command(name="luckyland", aliases=["lucky land"])
async def luckyland_cmd(ctx):
    await ctx.send("Checking LuckyLand for bonus…")
    await _run_manual_casino_command(
        ctx,
        "LuckyLand",
        lambda pctx, channel: luckyland_uc(pctx, channel),
    )


@bot.command(name="stake")
async def stake_cmd(ctx):
    await ctx.send("Checking Stake for bonus…")
    await _run_manual_casino_command(
        ctx,
        "Stake",
        lambda pctx, channel: stake_claim(driver, _bot(), pctx, channel),
    )


@bot.command(name="fortunewheelz", aliases=["fortune wheelz", "fortune-wheelz", "fzw"])
async def fortunewheelz_cmd(ctx):
    await ctx.send("Checking Fortune Wheelz for bonus…")
    await _run_manual_casino_command(
        ctx,
        "Fortune Wheelz",
        lambda pctx, channel: _call_fortunewheelz(channel=channel, ctx=pctx, raise_errors=False),
    )


@bot.command(name="fortunewins", aliases=["fortune wins", "fw", "fortune coins", "fc", "fortunecoins"])
async def fortunecoins_cmd(ctx):
    await ctx.send("Checking Fortune Wins for bonus…")
    await _run_manual_casino_command(ctx, "Fortune Coins/Wins", _manual_fortunecoins_flow)


@bot.command(name="spinquest")
async def spinquest_cmd(ctx):
    await ctx.send("Checking SpinQuest for bonus…")
    await _run_manual_casino_command(
        ctx,
        "SpinQuest",
        lambda pctx, channel: spinquest_flow(pctx, driver, channel),
    )


@bot.command(name="spinpals")
async def spinpals_cmd(ctx):
    await ctx.send("Checking SpinPals for bonus…")
    await _run_manual_casino_command(
        ctx,
        "SpinPals",
        lambda pctx, channel: spinpals_flow(pctx, driver, channel),
    )


@bot.command(name="chumba")
async def chumba_cmd(ctx):
    await ctx.send("Checking Chumba for bonus…")
    await _run_manual_casino_command(ctx, "Chumba", _manual_chumba_flow)


@bot.command(name="chanced")
async def chanced_cmd(ctx):
    await ctx.send("Checking Chanced.com for bonus…")

    creds = os.getenv("CHANCED")

    if creds:
        u, p = creds.split(":", 1)
        pair = (u, p)
    else:
        pair = (None, None)

    await _run_manual_casino_command(
        ctx,
        "Chanced",
        lambda pctx, channel: chanced_casino(pctx, driver, channel, pair),
    )


@bot.command(name="dingdingding")
async def dingdingding_cmd(ctx):
    await ctx.send("Checking DingDingDing for bonus…")
    await _run_manual_casino_command(ctx, "DingDingDing", _manual_dingdingding_flow)


# ───────────────────────────────────────────────────────────
# !debug <casino>
# ───────────────────────────────────────────────────────────
def _runner_to_coro(runner_func: Callable[[], Any]):
    async def _wrapped():
        result = runner_func()
        return await _maybe_await(result)

    return _wrapped()


async def _debug_worker_flow(ctx, channel, key: str):
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
        "stormrush": lambda: stormrush_casino(ctx, driver, channel),
        "scarletsands": lambda: scarletsands_casino(ctx, driver, channel),
        "playtana": lambda: playtana_casino(ctx, driver, channel),
        "cashoomo": lambda: cashoomo_casino(ctx, driver, channel),
        "taofortune": lambda: taofortune_casino(ctx, driver, channel),
        "sweepjungle": lambda: sweepjungle_casino(ctx, driver, channel),
        "zumo": lambda: zumo_casino(ctx, driver, channel),
        "jollysweeps": lambda: jollysweeps_casino(ctx, driver, channel),
        "gleaming": lambda: gleaming_casino(ctx, driver, channel),
        "sweepico": lambda: sweepico_casino(ctx, driver, channel),
        "sweepshark": lambda: sweepshark_casino(ctx, driver, channel),
        "crowncoins": lambda: crowncoins_casino(driver, _bot(), ctx, channel),
        "americanluck": lambda: americanluck_uc(ctx, channel),
        "rollingriches": lambda: rolling_riches_casino(ctx, driver, channel),
        "luckyland": lambda: luckyland_uc(ctx, channel),
        "stake": lambda: stake_claim(driver, _bot(), ctx, channel),
        "fortunewheelz": lambda: _call_fortunewheelz(channel=channel, ctx=ctx, raise_errors=True),
        "spinquest": lambda: spinquest_flow(ctx, driver, channel),
        "spinpals": lambda: spinpals_flow(ctx, driver, channel),
        "chumba": lambda: _manual_chumba_flow(ctx, channel),
        "chanced": lambda: chanced_casino(ctx, driver, channel, (None, None)),
        "dingdingding": lambda: _manual_dingdingding_flow(ctx, channel),
        "modo": lambda: _manual_modo_flow(ctx, channel),
        "luckparty": lambda: _call_luckparty(channel=channel, ctx=ctx, raise_errors=True),
        "winbonanza": lambda: _call_winbonanza(channel=channel, ctx=ctx, raise_errors=True),
    }

    if key not in runners:
        await ctx.send(
            f"❌ Unknown casino `{key}`.\n"
            "Try one of: " + ", ".join(sorted(runners.keys()))
        )
        return

    target_coro = _runner_to_coro(runners[key])

    await ctx.send(f"🧪 Debugging `{key}` — periodic screenshots run inside the Selenium worker…")

    interval = int(os.getenv("DEBUG_SCREENSHOT_INTERVAL", "4"))
    max_shots = int(os.getenv("DEBUG_SCREENSHOT_MAX", "40"))

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


@bot.command(name="debug")
async def debug_cmd(ctx, *, casino: str):
    key = normalize_casino_key(casino)

    if not key:
        await ctx.send("Usage: `!debug <casino>` example: `!debug spinquest`")
        return

    key = CASINO_ALIAS_MAP.get(key, key)
    await _run_manual_casino_command(
        ctx,
        f"debug:{key}",
        lambda pctx, channel: _debug_worker_flow(pctx, channel, key),
    )


# ───────────────────────────────────────────────────────────
# Auth router
# Auth flows also touch Selenium, so they use the same worker lane.
# ───────────────────────────────────────────────────────────
async def _auth_google_flow(ctx, channel):
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
        raise


async def _auth_modo_flow(ctx, channel):
    await run_modo_auth(channel)


async def _auth_crowncoins_flow(ctx, channel, method: str):
    if method.lower() == "google":
        await ctx.send("Authenticating CrownCoins via Google…")
        ok = await auth_crown_google(driver, _bot(), ctx, channel)
    elif method.lower() == "env":
        await ctx.send("Authenticating CrownCoins via .env credentials…")
        ok = await auth_crown_env(driver, _bot(), ctx, channel)
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


async def _auth_dingdingding_flow(ctx, channel):
    ok = await authenticate_dingdingding(driver, _bot(), ctx, channel)

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


async def _auth_stake_flow(ctx, channel):
    ok = await stake_auth(driver, _bot(), ctx, channel)

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


async def _auth_nolimit_flow(ctx, channel, method: str):
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


@bot.command(name="auth")
async def authenticate_command(ctx: commands.Context, site: str, method: str = None):
    norm_site = re.sub(r"\s+", "", site.lower())

    if norm_site == "google":
        await ctx.send("Authenticating Google Account…")
        await _run_manual_casino_command(ctx, "auth:google", _auth_google_flow)
        return

    if norm_site == "modo":
        await ctx.send("Authenticating Modo…")
        await _run_manual_casino_command(ctx, "auth:modo", _auth_modo_flow)
        return

    if norm_site == "crowncoins":
        if method is None:
            await ctx.send("Usage: `!auth crowncoins google` or `!auth crowncoins env`")
            return

        await _run_manual_casino_command(
            ctx,
            f"auth:crowncoins:{method.lower()}",
            lambda pctx, channel: _auth_crowncoins_flow(pctx, channel, method),
        )
        return

    if norm_site == "dingdingding":
        await ctx.send("Authenticating DingDingDing…")
        await _run_manual_casino_command(ctx, "auth:dingdingding", _auth_dingdingding_flow)
        return

    if norm_site == "stake":
        await ctx.send("Authenticating Stake…")
        await _run_manual_casino_command(ctx, "auth:stake", _auth_stake_flow)
        return

    if norm_site in {"nolimitcoins", "nlc", "nolimit", "no limit coins"}:
        if method is None:
            await ctx.send("Usage: `!auth nolimitcoins google` or `!auth nolimitcoins env`")
            return

        await _run_manual_casino_command(
            ctx,
            f"auth:nolimitcoins:{method.lower()}",
            lambda pctx, channel: _auth_nolimit_flow(pctx, channel, method),
        )
        return

    await ctx.send(
        f"❓ Authentication for `{site}` is not implemented. "
        "Run `!help` for supported sites. Run `!debug <casino>` for screenshot debugging."
    )


@bot.command(name="authmodo")
async def authmodo_cmd(ctx):
    await ctx.send("Authenticating Modo…")
    await _run_manual_casino_command(ctx, "auth:modo", _auth_modo_flow)


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
!chipnwin, !wildworld, !lonestar, !gains, !luckparty, !winbonanza,
!stormrush, !scarletsands, !playtana, !cashoomo, !taofortune,
!sweepjungle, !zumo, !jollysweeps, !sweepico, !sweepshark, !gleaming,

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
!status
!imports
!imports luckparty
!imports winbonanza

---------------------------------------  
⚙️ **Config/TOML:**
!config
!config path
!config reload
!config save (IMPORTANT: USE THIS TO SAVE YOUR BOT CONFIG)
!config enable <casino>
!config disable <casino>
!config interval <casino> <minutes>
!config order <all casinos in order>
!config autoauth enable|disable|interval|runonstart [value]
!config autodataclear enable|disable|interval|runonstart [value]
!config bot loop_stagger_seconds|per_casino_timeout_seconds|main_tick_sleep_seconds <value>

---------------------------------------  
⚙️ **General:**  
!ping, !status, !restart, !help, !start, !stop, !about, !reset

Examples:
`!config disable spinquest`
`!config enable winbonanza`
`!config autoauth enable 720`
`!config autodataclear enable 1440`
`!winbonanza`
"""
    )


# ───────────────────────────────────────────────────────────
# Run bot
# ───────────────────────────────────────────────────────────
def _run_bot_supervised():
    """Start Discord with a final crash guard.

    Normal command/API errors should be contained by the command wrappers above.
    This is only the last line of defense for a fatal discord.py/client crash.
    In Docker, `restart: unless-stopped` is still recommended.
    """
    try:
        bot.run(DISCORD_TOKEN, reconnect=True)
    except KeyboardInterrupt:
        raise
    except SystemExit:
        raise
    except Exception as e:
        print(f"[Fatal] bot.run crashed: {type(e).__name__}: {e}")
        traceback.print_exc()

        if os.getenv("BOT_SUPERVISOR_RESTART_ON_FATAL", "1").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            delay = float(os.getenv("BOT_SUPERVISOR_RESTART_DELAY_SECONDS", "8"))
            print(f"[Fatal] Restarting Python process in {delay:g}s...")
            time.sleep(delay)
            os.execv(sys.executable, [sys.executable] + sys.argv)

        raise


if __name__ == "__main__":
    _run_bot_supervised()
