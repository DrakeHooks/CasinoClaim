# Drake Hooks
# Casino Claim 2
# Helper API

"""Utility helpers used across the bot."""

import asyncio
import os
import time
from typing import Optional, Callable, Awaitable, Dict, Tuple

import discord


async def open_captcha_solver_page(driver):
    """Open the captcha solver extension page."""
    try:
        # Open the extensions page first so the extension context is loaded
        driver.get("chrome://extensions")
        await asyncio.sleep(2)
        # Navigate directly to the captcha solver popup
        driver.get(
            "chrome-extension://hlifkpholllijblknnmbfagnkjneagid/popup/popup.html#/"
        )
        await asyncio.sleep(5)
        return True
    except Exception as e:  # pragma: no cover - best effort
        print(f"Failed to open captcha solver page: {e}")
        return False


# ────────────────────────────────────────────────────────────
# Debug screenshot plumbing (used by !debug <casino>)
# ────────────────────────────────────────────────────────────

# key: (author_id, channel_id, casino_key) -> expires_at_epoch
_DEBUG_REQUESTS: Dict[Tuple[int, int, str], float] = {}


def normalize_casino_key(name: str) -> str:
    """
    Normalize a casino name like:
      "SpinQuest", "spin quest", "spinquest", "Spin Quest" -> "spinquest"
    """
    if not name:
        return ""
    return "".join(ch for ch in name.lower().strip() if ch.isalnum())


def enable_debug(author_id: int, channel_id: int, casino_key: str, ttl_seconds: int = 300) -> None:
    """
    Turn on debug for (author, channel, casino) for a short TTL.
    You can use this if you want future per-step calls inside APIs to key off it.
    """
    key = (author_id, channel_id, casino_key)
    _DEBUG_REQUESTS[key] = time.time() + ttl_seconds


def consume_debug(author_id: int, channel_id: int, casino_key: str) -> bool:
    """
    One-shot check. If debug is enabled & not expired, consume it and return True.
    """
    key = (author_id, channel_id, casino_key)
    exp = _DEBUG_REQUESTS.get(key)
    if not exp:
        return False
    if time.time() > exp:
        _DEBUG_REQUESTS.pop(key, None)
        return False
    # consume
    _DEBUG_REQUESTS.pop(key, None)
    return True


async def send_temp_screenshot(
    channel: discord.abc.Messageable,
    driver,
    filename: str,
    caption: Optional[str] = None,
) -> None:
    """
    Save screenshot to a temp file, send it, then delete it (always).
    """
    try:
        driver.save_screenshot(filename)
        if caption:
            await channel.send(caption)
        await channel.send(file=discord.File(filename))
    finally:
        try:
            if os.path.exists(filename):
                os.remove(filename)
        except Exception:
            pass


async def run_with_periodic_screenshots(
    *,
    channel: discord.abc.Messageable,
    driver,
    casino_key: str,
    coro: Awaitable[None],
    interval_seconds: int = 4,
    max_shots: int = 40,
    label: str = "debug",
) -> None:
    """
    Wrap any casino coroutine and automatically send screenshots:
      - 1 at start
      - then every interval_seconds while it runs (up to max_shots)
      - 1 at end (success) OR on exception
    This is the core of `!debug <casino>`.
    """

    casino_key = normalize_casino_key(casino_key) or "casino"
    interval_seconds = max(1, int(interval_seconds))
    max_shots = max(3, int(max_shots))

    async def shot(i: int, note: str) -> None:
        ts = int(time.time())
        fname = f"{casino_key}_{label}_{ts}_{i:02d}.png"
        await send_temp_screenshot(
            channel,
            driver,
            fname,
            caption=f"📸 **{casino_key}** {note} (#{i})",
        )

    stop_flag = {"stop": False}

    async def ticker():
        i = 2  # start shot is #1
        try:
            while not stop_flag["stop"] and i <= max_shots:
                await asyncio.sleep(interval_seconds)
                if stop_flag["stop"]:
                    break
                await shot(i, f"snapshot +{interval_seconds}s")
                i += 1
        except Exception:
            # best-effort; never let debug ticker kill the run
            pass

    # Start shot
    await shot(1, "start")

    tick_task = asyncio.create_task(ticker())
    try:
        await coro
    except Exception as e:
        stop_flag["stop"] = True
        try:
            await shot(max_shots, f"exception: {type(e).__name__}")
        except Exception:
            pass
        raise
    finally:
        stop_flag["stop"] = True
        try:
            tick_task.cancel()
            await tick_task
        except Exception:
            pass

    # End shot
    try:
        await shot(max_shots, "end")
    except Exception:
        pass
