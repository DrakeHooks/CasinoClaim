# Drake Hooks + WaterTrooper
# Casino Claim 2
# American Luck API (SeleniumBase UC)
# Exposes: async def americanluck_uc(ctx, channel)

import os
from dotenv import load_dotenv
from seleniumbase import SB
import discord

load_dotenv()

LOGIN_URL = "https://americanluck.com/login"
LOBBY_URL = "https://americanluck.com/lobby"

# ── Provided by you ──────────────────────────────────────────────
POPUP_CLOSE_XP   = "/html/body/div[5]/div/button"
GET_COINS_BTN_XP = "/html/body/div[1]/div[2]/header/div[2]/button"
COLLECT_BTN_XP   = "/html/body/div[7]/div/div/section[1]/div/div/div/div/div[3]/button[1]/div[1]"


# ───────────────────────────────────────────────────────────────
# Screenshot helpers
# ───────────────────────────────────────────────────────────────
async def _send_status_shot(sb: SB, channel, filename: str, caption: str):
    """Always send a screenshot (success or failure)."""
    try:
        sb.save_screenshot(filename)
        await channel.send(caption, file=discord.File(filename))
    except Exception:
        try:
            await channel.send(caption)
        except Exception:
            pass
    finally:
        try:
            if os.path.exists(filename):
                os.remove(filename)
        except Exception:
            pass


def _force_click_xpath(sb: SB, xpath: str, timeout: float = 12) -> bool:
    """Robust click chain for stubborn elements."""
    try:
        sb.wait_for_element_visible(xpath, timeout=timeout)
    except Exception:
        return False
    try:
        sb.scroll_to(xpath)
    except Exception:
        pass
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


def _try_type_any(sb: SB, selectors, text: str, clear_first=False) -> bool:
    for sel in selectors:
        try:
            sb.wait_for_element_visible(sel, timeout=3)
            if clear_first:
                try:
                    sb.clear(sel)
                except Exception:
                    pass
            sb.type(sel, text)
            return True
        except Exception:
            continue
    return False


# ───────────────────────────────────────────────────────────────
# Main UC logic
# ───────────────────────────────────────────────────────────────
async def americanluck_uc(ctx, channel: discord.abc.Messageable):
    """American Luck via SeleniumBase (uc=True)."""
    await channel.send("Launching **American Luck** (UC)…")

    creds = os.getenv("AMERICANLUCK")
    if not creds or ":" not in creds:
        await channel.send("⚠️ AMERICANLUCK not set (email:pass) in .env")
        return

    username, password = creds.split(":", 1)

    try:
        with SB(uc=True, headed=True) as sb:
            sb.uc_open_with_reconnect(LOGIN_URL, 4)
            sb.wait_for_ready_state_complete()

            # ── Attempt login if form visible ─────────────────────────────
            email_selectors = [
                "input[type='email']", "input[name='email']", "input#email",
                "//input[contains(translate(@id,'EMAIL','email'),'email')]",
                "//input[contains(translate(@name,'EMAIL','email'),'email')]",
                "//input[contains(translate(@placeholder,'EMAIL','email'),'email')]",
            ]
            pass_selectors = [
                "input[type='password']", "input[name='password']", "input#password",
                "//input[contains(translate(@id,'PASSWORD','password'),'password')]",
                "//input[contains(translate(@name,'PASSWORD','password'),'password')]",
                "//input[contains(translate(@placeholder,'PASSWORD','password'),'password')]",
            ]

            typed_email = _try_type_any(sb, email_selectors, username, clear_first=True)
            typed_pass  = _try_type_any(sb, pass_selectors, password, clear_first=True)

            if typed_email and typed_pass:
                try:
                    sb.press_keys(pass_selectors[0], "ENTER")
                except Exception:
                    try:
                        sb.execute_script("document.querySelector('form')?.submit?.()")
                    except Exception:
                        pass
                try:
                    sb.uc_gui_click_captcha()
                    sb.wait(8)
                except Exception:
                    pass

            sb.wait(6)
            sb.refresh_page()
            sb.wait_for_ready_state_complete()

            try:
                sb.open(LOBBY_URL)
                sb.wait_for_ready_state_complete()
            except Exception:
                pass

            # ── Close popup if exists ────────────────────────────────────
            _try_click_any(sb, [POPUP_CLOSE_XP], timeout_each=5)
            try:
                sb.press_keys("body", "ESCAPE")
            except Exception:
                pass

            # ── Open rewards / get coins ─────────────────────────────────
            opened = _try_click_any(sb, [GET_COINS_BTN_XP], timeout_each=10)
            if not opened:
                sb.wait(3)
                _try_click_any(sb, [GET_COINS_BTN_XP], timeout_each=6)

            sb.wait_for_ready_state_complete()
            sb.wait(3)

            # ── Collect if available ─────────────────────────────────────
            collected = _try_click_any(sb, [COLLECT_BTN_XP], timeout_each=8)
            if not collected:
                sb.wait(4)
                collected = _try_click_any(sb, [COLLECT_BTN_XP], timeout_each=5)

            if collected:
                sb.wait(2)
                await _send_status_shot(sb, channel, "americanluck_success.png",
                                        "American Luck Daily Bonus Claimed!")
            else:
                await _send_status_shot(sb, channel, "americanluck_fail.png",
                                        "American Luck: No claim available or flow failed.")

    except Exception as e:
        try:
            with SB(uc=True, headed=True) as sb:
                await _send_status_shot(sb, channel, "americanluck_error.png",
                                        f"⚠️ American Luck crashed")
        except Exception:
            await channel.send(f"⚠️ American Luck fatal error")
