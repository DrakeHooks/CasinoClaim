# Drake Hooks + WaterTrooper
# Casino Claim 2
# American Luck API (SeleniumBase UC)
# Exposes: async def americanluck_uc(ctx, channel)

import os
import discord
from dotenv import load_dotenv
from seleniumbase import SB

load_dotenv()

LOGIN_URL = "https://americanluck.com/login"
LOBBY_URL = "https://americanluck.com/lobby"

# Provided xpaths
POPUP_CLOSE_XP   = "/html/body/div[5]/div/button"
GET_COINS_BTN_XP = "/html/body/div[1]/div[2]/header/div[2]/button"
COLLECT_BTN_XP   = "/html/body/div[7]/div/div/section[1]/div/div/div/div/div[3]/button[1]/div[1]"


async def _send_shot(sb: SB, channel: discord.abc.Messageable, path: str, caption: str):
    """Save a screenshot, send to Discord, and clean up the file."""
    try:
        sb.save_screenshot(path)
        await channel.send(caption, file=discord.File(path))
    except Exception:
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


def _force_click_xpath(sb: SB, xpath: str, timeout: float = 12) -> bool:
    """Click a stubborn XPath with multiple strategies."""
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


async def americanluck_uc(ctx, channel: discord.abc.Messageable):
    await channel.send("Launching **American Luck** (UC)…")

    creds = os.getenv("AMERICANLUCK")
    if not creds or ":" not in creds:
        await channel.send("⚠️ AMERICANLUCK not set (email:pass) in .env")
        return
    username, password = creds.split(":", 1)

    sb = None
    try:
        with SB(uc=True, headed=True) as sb:
            # Open login
            sb.uc_open_with_reconnect(LOGIN_URL, 8)
            sb.wait_for_ready_state_complete()
            # await _send_shot(sb, channel, "americanluck_login.png",
            #                      " American Luck: Login page ")

            # Try to type only into these two fields
            typed = False
            try:
                sb.type("input[id='emailAddress']", username)
                sb.type("input[id='password']", password)
                sb.uc_gui_click_captcha()
                sb.wait(10)
                _force_click_xpath(sb, "/html/body/div[1]/div[2]/main/div/div/div/div[2]/form/div[4]/button", timeout=12)

                # await _send_shot(sb, channel, "americanluck_login1.png",
                #                  " American Luck: Login page creds entered ")
                pass
            except Exception:
                    await _send_shot(sb, channel, "americanluck_login_failed.png",
                    "🟥 American Luck: Login failed (Get Coins not visible).")


            # Let auth redirects settle
            sb.wait(6)
            sb.refresh_page()
            sb.wait_for_ready_state_complete()

            # Go to lobby (if not already there)
            try:
                sb.open(LOBBY_URL)
                sb.wait_for_ready_state_complete()
            except Exception:
                pass

            # Close known popup and escape any stray modals
            _force_click_xpath(sb, POPUP_CLOSE_XP, timeout=5)
            try:
                sb.press_keys("body", "ESCAPE")
            except Exception:
                pass

            # Check login state by presence of Get Coins button
            login_ok = False
            try:
                sb.wait_for_element_visible(GET_COINS_BTN_XP, timeout=8)
                login_ok = True
            except Exception:
                login_ok = False

            if login_ok:
                # Send login success screenshot
                # await _send_shot(sb, channel, "americanluck_logged_in.png",
                #                  "✅ American Luck: Logged in (post-login state).")

                # ───────── Claim logic (quiet unless success) ─────────
                opened = _force_click_xpath(sb, GET_COINS_BTN_XP, timeout=8)
                if not opened:
                    sb.wait(3)
                    opened = _force_click_xpath(sb, GET_COINS_BTN_XP, timeout=6)

                if opened:
                    sb.wait_for_ready_state_complete()
                    sb.wait(3)
                    collected = _force_click_xpath(sb, COLLECT_BTN_XP, timeout=8)
                    if not collected:
                        sb.wait(4)
                        collected = _force_click_xpath(sb, COLLECT_BTN_XP, timeout=5)

                    if collected:
                        sb.wait(2)
                        await _send_shot(sb, channel, "americanluck_claimed.png",
                                         "American Luck Daily Bonus Claimed!")
                # If not opened or not collected, stay quiet (test mode)
            else:
                # Send login **failure** screenshot
                await _send_shot(sb, channel, "americanluck_login_failed.png",
                                 "🟥 American Luck: Login failed (Get Coins not visible).")

    except Exception as e:
        # Try to send an error-state screenshot if the browser exists
        try:
            if sb is not None:
                await _send_shot(sb, channel, "americanluck_error.png",
                                 f"⚠️ American Luck crashed: {e}")
            else:
                await channel.send(f"⚠️ American Luck crashed before browser started: {e}")
        except Exception:
            pass
