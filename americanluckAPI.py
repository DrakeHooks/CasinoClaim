# Drake Hooks + WaterTrooper
# Casino Claim 2
# American Luck API (SeleniumBase UC)
# Notes: Popup handler included. Xpaths subject to change.

import os
import discord
from dotenv import load_dotenv
from seleniumbase import SB


# ───────────────────────────────────────────────────────────
# American Luck Config and Constants
# ───────────────────────────────────────────────────────────

load_dotenv()

LOGIN_URL = "https://americanluck.com/login"
LOBBY_URL = "https://americanluck.com/lobby"

POPUP_CLOSE_XP   = "/html/body/div[5]/div/button"
GET_COINS_BTN_XP = "/html/body/div[1]/div[2]/header/div[2]/button[1]"

# Collect button via CSS selector (from devtools)
COLLECT_BTN_CSS = (
    "body > div.dialog-container > div > div > section:nth-child(2) > div > div > "
    "div:nth-child(1) > div > div.free-reward-card__button-container > "
    "button.rag-button.rag-button--primary.free-reward-card__button > div.button-content"
)


# ───────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────

async def _send_shot(sb: SB, channel: discord.abc.Messageable, path: str, caption: str):
    """Save a screenshot, send it to Discord, then clean it up."""
    try:
        sb.save_screenshot(path)
        await channel.send(caption, file=discord.File(path))
    except Exception:
        # Fall back to text-only if something goes wrong
        try:
            await channel.send(caption)
        except Exception:
            pass
    finally:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


def _force_click_xpath(sb: SB, xpath: str, timeout: float = 10) -> bool:
    """
    Try hard to click an element by XPath.
    Returns True if any strategy succeeds, False otherwise.
    """
    try:
        sb.wait_for_element_visible(xpath, timeout=timeout)
    except Exception:
        return False

    try:
        sb.scroll_to(xpath)
    except Exception:
        pass

    # Try a few different click strategies
    strategies = ("click", "slow", "js", "directjs")
    for mode in strategies:
        try:
            if mode == "click":
                sb.click_xpath(xpath, timeout=4)
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


def _force_click_css(sb: SB, css: str, timeout: float = 10) -> bool:
    """
    Try hard to click an element by CSS selector.
    Returns True if any strategy succeeds, False otherwise.
    """
    try:
        sb.wait_for_element_visible(css, timeout=timeout)
    except Exception:
        return False

    try:
        sb.scroll_to(css)
    except Exception:
        pass

    strategies = ("click", "slow", "js", "directjs")
    for mode in strategies:
        try:
            if mode == "click":
                sb.click(css)
            elif mode == "slow":
                sb.slow_click(css)
            elif mode == "js":
                sb.js_click(css)
            else:
                el = sb.find_element(css)
                sb.execute_script("arguments[0].click();", el)
            return True
        except Exception:
            continue

    return False


# ───────────────────────────────────────────────────────────
# American Luck Main flow (UC mode)
# ───────────────────────────────────────────────────────────

async def americanluck_uc(ctx, channel: discord.abc.Messageable):
    await channel.send("Launching **American Luck** (UC)…")

    creds = os.getenv("AMERICANLUCK")
    if not creds or ":" not in creds:
        await channel.send("⚠️ AMERICANLUCK not set in `.env` (expected `email:password`).")
        return
    username, password = creds.split(":", 1)

    sb = None
    try:
        with SB(uc=True, headed=True) as sb:
            # ── Step 1: open login page ──
            sb.uc_open_with_reconnect(LOGIN_URL, 8)
            sb.wait_for_ready_state_complete()

            # ── Step 2: type credentials and click login ──
            sb.wait(1)
            sb.type("input[id='emailAddress']", username)
            sb.type("input[id='password']", password)

            # Try to solve captcha via helper, if available
            try:
                sb.uc_gui_click_captcha()
            except Exception:
                pass

            sb.wait(1.5)
            _force_click_xpath(
                sb,
                "/html/body/div[1]/div[2]/main/div/div/div/div[2]/form/div[4]/button",
                timeout=10,
            )

            sb.wait(6)
            sb.wait_for_ready_state_complete()

            # ── Step 3: close any popup if present ──
            _force_click_xpath(sb, POPUP_CLOSE_XP, timeout=4)
            try:
                sb.press_keys("body", "ESCAPE")
            except Exception:
                pass

            sb.wait(2)
            sb.wait_for_ready_state_complete()

            # ── Step 4: detect login state ──
            login_ok = False
            try:
                sb.wait_for_element_visible(GET_COINS_BTN_XP, timeout=8)
                login_ok = True
            except Exception:
                login_ok = False

            # Fallback: URL heuristic
            if not login_ok:
                try:
                    current_url = sb.get_current_url()
                    if current_url.startswith(LOBBY_URL):
                        login_ok = True
                except Exception:
                    pass

            if not login_ok:
                # Login failed / not in lobby – send screenshot for debugging
                await _send_shot(
                    sb,
                    channel,
                    "americanluck_login_failed.png",
                    "American Luck: Login failed or bonus unavailable.",
                )
                return

            # ── Step 5: open Get Coins modal ──
            opened = _force_click_xpath(sb, GET_COINS_BTN_XP, timeout=8)
            if not opened:
                sb.wait(3)
                opened = _force_click_xpath(sb, GET_COINS_BTN_XP, timeout=6)

            if not opened:
                await _send_shot(
                    sb,
                    channel,
                    "americanluck_getcoins_missing.png",
                    "American Luck: Could not open **Get Coins**. "
                    "Layout may have changed or bonus is unavailable.",
                )
                return

            sb.wait_for_ready_state_complete()
            sb.wait(3)

            # ── Step 6: click Collect via CSS selector ──
            collected = _force_click_css(sb, COLLECT_BTN_CSS, timeout=8)
            if not collected:
                sb.wait(4)
                collected = _force_click_css(sb, COLLECT_BTN_CSS, timeout=6)

            if collected:
                sb.wait(2)
                await _send_shot(
                    sb,
                    channel,
                    "americanluck_claimed.png",
                    "American Luck Daily Bonus Claimed!",
                )
            else:
                # This is the case you care about: Collect button missing / selector changed
                await _send_shot(
                    sb,
                    channel,
                    "americanluck_collect_missing.png",
                    "[American Luck] Could not find **Collect** button. "
                    "Bonus may be unavailable, or COLLECT_BTN_CSS needs update.",
                )

    except Exception as e:
        # Top-level crash: try to capture the state for debugging
        try:
            if sb is not None:
                await _send_shot(
                    sb,
                    channel,
                    "americanluck_error.png",
                    f"⚠️ American Luck crashed: `{e}`",
                )
            else:
                await channel.send(
                    f"⚠️ American Luck crashed before browser started: `{e}`"
                )
        except Exception:
            # Last-resort: swallow any errors trying to report the crash
            pass
