# Drake Hooks + WaterTrooper
# Casino Claim 2
# Fortune Coins API (SeleniumBase UC) — thread-offloaded sync runner
# Exposes:
#   def fortunecoins_uc_blocking(bot, channel_id: int, main_loop):  # call from executor
#   async def fortunecoins_uc(ctx, channel):  # optional thin async wrapper if you want it

import os
import time
import contextlib
from dotenv import load_dotenv
from seleniumbase import SB
import discord
import asyncio

load_dotenv()

FC_EMAIL = os.getenv("FORTUNECOINSEMAIL", "")
FC_PASSWORD = os.getenv("FORTUNECOINSPASSWORD", "")

# ───────────────────────────────────────────────────────────
# Discord helpers (safe to call from a worker thread)
# ───────────────────────────────────────────────────────────
def _send_text_threadsafe(main_loop: asyncio.AbstractEventLoop, channel: discord.abc.Messageable, text: str):
    fut = asyncio.run_coroutine_threadsafe(channel.send(text), main_loop)
    with contextlib.suppress(Exception):
        fut.result(timeout=20)

def _send_file_threadsafe(main_loop: asyncio.AbstractEventLoop, channel: discord.abc.Messageable, path: str, caption: str):
    async def _do():
        try:
            await channel.send(caption, file=discord.File(path))
        finally:
            with contextlib.suppress(Exception):
                os.remove(path)
    fut = asyncio.run_coroutine_threadsafe(_do(), main_loop)
    with contextlib.suppress(Exception):
        fut.result(timeout=60)

# ───────────────────────────────────────────────────────────
# Selenium helpers (UNCHANGED behavior; all sync)
# ───────────────────────────────────────────────────────────
def _force_click_xpath(sb: SB, xpath: str, timeout: float = 12) -> bool:
    try:
        sb.wait_for_element_visible(xpath, timeout=timeout)
    except Exception:
        return False
    with contextlib.suppress(Exception):
        sb.scroll_to(xpath)
    for mode in ("click", "slow", "js", "directjs"):
        try:
            if mode == "click":
                sb.click_xpath(xpath, timeout=2)
            elif mode == "slow":
                sb.slow_click(xpath)
            elif mode == "js":
                sb.js_click(xpath)
            else:
                el = sb.find_element(xpath)
                sb.execute_script("arguments[0].click();", el)
            return True
        except Exception:
            continue
    return False

def _try_click_any(sb: SB, xpaths, timeout_each=10) -> bool:
    for xp in xpaths:
        if _force_click_xpath(sb, xp, timeout=timeout_each):
            return True
    return False

# ───────────────────────────────────────────────────────────
# Primary sync runner (to be called from a worker thread)
# ───────────────────────────────────────────────────────────
def fortunecoins_uc_blocking(bot, channel_id: int, main_loop: asyncio.AbstractEventLoop):
    """
    Runs the entire Fortune Coins flow synchronously in a worker thread.
    Posts messages back to the main Discord loop thread-safely.
    Keeps SeleniumBase's sb.uc_gui_click_captcha() intact.
    """
    if not FC_EMAIL or not FC_PASSWORD:
        ch = bot.get_channel(channel_id)
        if ch:
            _send_text_threadsafe(main_loop, ch, "❌ Missing `FORTUNECOINSEMAIL` or `FORTUNECOINSPASSWORD` in your .env.")
        return

    ch = bot.get_channel(channel_id)
    if ch:
        _send_text_threadsafe(main_loop, ch, "Launching **Fortune Coins** (UC)…")

    try:
        # headed=True so GUI-captcha can operate a visible display (Xvfb)
        with SB(uc=True, headed=True) as sb:
            # Login
            sb.uc_open_with_reconnect("https://fortunecoins.com/login", 4)
            sb.wait_for_ready_state_complete()
            sb.type("input[id='emailAddress']", FC_EMAIL)
            time.sleep(1.5)
            sb.type("input[id='password']", FC_PASSWORD)

            # You wanted to keep the GUI helper — keep it, but we're in a thread now.
            with contextlib.suppress(Exception):
                sb.uc_gui_click_captcha()
                time.sleep(1.0)

            _force_click_xpath(sb, "/html/body/div[1]/div[5]/div/div/div/div[2]/form/div[4]/button", timeout=12)
            time.sleep(5.0)
            sb.refresh_page()
            sb.wait_for_ready_state_complete()

            # Close any modal/popups
            _try_click_any(
                sb,
                [
                    "/html/body/div[5]/div/div[1]/div/div/button",
                    "/html/body/div[4]/div/div[1]/div/div/div[3]/div/button[2]",
                    "/html/body/div[4]/div/div[1]/div/div/button",
                ],
                timeout_each=6,
            )
            with contextlib.suppress(Exception):
                sb.press_keys("body", "ESCAPE")

            # Open Rewards/Get Coins
            _try_click_any(
                sb,
                [
                    "/html/body/div[1]/div[2]/div[1]/div/nav/div[2]/div[3]/button",
                    "/html/body/div[1]/div[2]/div/nav/div[2]/div[3]/button",
                    "/html/body/div[1]/div[2]/div[1]/div/nav/div[2]/div[3]/button",
                ],
                timeout_each=10,
            )
            sb.wait_for_ready_state_complete()
            time.sleep(4.0)

            # Click Collect
            collected = _try_click_any(
                sb,
                [
                    "/html/body/div[5]/div/div[1]/div/div/div[2]/div/div[1]/div[2]/div[1]/div/div[3]/button[1]",
                    "/html/body/div[4]/div/div[1]/div/div/div[2]/div/div[2]/div[2]/div[1]/div/div[3]/button[1]",
                    "/html/body/div[4]/div/div[1]/div/div/div[2]/div/div[1]/div[2]/div[1]/div/div[3]/button[1]",
                    "/html/body/div[6]/div/div[1]/div/div/div[2]/div/div[1]/div[2]/div[1]/div/div[3]/button[1]"
                ],
                timeout_each=8,
            )

            if not collected:
                time.sleep(4.0)
                collected = _try_click_any(
                    sb,
                    [
                        "/html/body/div[4]/div/div[1]/div/div/div[2]/div/div[2]/div[2]/div[1]/div/div[3]/button[1]",
                        "/html/body/div[4]/div/div[1]/div/div/div[2]/div/div[1]/div[2]/div[1]/div/div[3]/button[1]",
                    ],
                    timeout_each=5,
                )

            if ch:
                if collected:
                    snap = "fc_uc_claimed.png"
                    with contextlib.suppress(Exception):
                        sb.save_screenshot(snap)
                    _send_file_threadsafe(main_loop, ch, snap, "Fortune Coins Daily Bonus Claimed!")
                else:
                    _send_text_threadsafe(main_loop, ch, "Fortune Coins: bonus unavailable (likely already collected).")

    except Exception:
        if ch:
            _send_text_threadsafe(main_loop, ch, "⚠️ Fortune Coins (UC) error")

# ───────────────────────────────────────────────────────────
# Optional thin async wrapper (kept for compatibility; not used by executor path)
# ───────────────────────────────────────────────────────────
async def fortunecoins_uc(ctx, channel: discord.abc.Messageable):
    # If someone calls this directly, keep old behavior but without any sleeps that block the loop.
    # (Recommend using the threaded executor path in main.py instead.)
    bot = channel.guild._state._get_client() if hasattr(channel, "guild") else None
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, fortunecoins_uc_blocking, bot, channel.id, loop)
