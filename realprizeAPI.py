# Drake Hooks + WaterTrooper
# Casino Claim 2
# RealPrize API — UC + OpenCV image-click on popup "CLAIM"
# Exposes: async def realprize_uc(ctx, channel)

import os
import time
import tempfile
import discord
from dotenv import load_dotenv

# SeleniumBase (UC mode)
from seleniumbase import SB

# OpenCV / PyAutoGUI for template matching + click
import pyautogui
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

import cv2
import numpy as np

load_dotenv()

# ───────────────────────────────────────────────────────────
# ENV: "email:password"
# ───────────────────────────────────────────────────────────
REALPRIZE_CRED = os.getenv("REALPRIZE", "")

# ───────────────────────────────────────────────────────────
# URLs
# ───────────────────────────────────────────────────────────
LOGIN_URL = "https://realprize.com/#!login"
LOBBY_URL = "https://realprize.com/#"

# ───────────────────────────────────────────────────────────
# Login form targets (provided)
# ───────────────────────────────────────────────────────────
EMAIL_ID = "poplogin_email"
PASSWORD_ID = "poplogin_password"
LOGIN_BTN_ID = "poploginbtn"
LOGIN_BTN_XPATH_FALLBACK = "/html/body/div[9]/div/div/div/div[2]/div[3]/div[3]/form/div/div[3]/button"

# No captcha on RealPrize

# ───────────────────────────────────────────────────────────
# Template image for the popup "CLAIM" button
# Support both the expected filename and the UUID'd path you shared.
# ───────────────────────────────────────────────────────────
TEMPLATE_CANDIDATES = [
    "/mnt/data/realprizeclaim.png",
    "/mnt/data/39b319f1-3392-4ab9-92dd-7f1f314eb64f.png",
]

def _existing_template_path() -> str:
    for p in TEMPLATE_CANDIDATES:
        if os.path.exists(p):
            return p
    return TEMPLATE_CANDIDATES[0]  # fall back to the canonical name

# ───────────────────────────────────────────────────────────
# Screenshot helpers (consistent with your other APIs)
# ───────────────────────────────────────────────────────────
async def _send_post_claim(sb: SB, channel: discord.abc.Messageable, path: str, caption: str):
    try:
        sb.save_screenshot(path)
        await channel.send(caption, file=discord.File(path))
    finally:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

async def _send_status_shot(sb: SB, channel: discord.abc.Messageable, caption: str, prefix: str):
    fd, tmp_path = tempfile.mkstemp(prefix=f"{prefix}_", suffix=".png", dir="/tmp")
    os.close(fd)
    try:
        sb.save_screenshot(tmp_path)
        await channel.send(caption, file=discord.File(tmp_path))
    except Exception:
        try:
            await channel.send(caption)
        except Exception:
            pass
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

# ───────────────────────────────────────────────────────────
# OpenCV-based on-screen template match and click
# ───────────────────────────────────────────────────────────
def _find_template_on_screen(template_path: str, threshold: float = 0.88):
    """
    Returns (center_x, center_y) if found with sufficient confidence; else None.
    Works against a full-screen screenshot to be robust to popup positioning.
    """
    if not os.path.exists(template_path):
        return None

    # Screenshot with PyAutoGUI (RGB), convert to BGR for OpenCV
    shot = pyautogui.screenshot()
    screen = cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)

    template = cv2.imread(template_path, cv2.IMREAD_COLOR)
    if template is None:
        return None

    res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    minVal, maxVal, minLoc, maxLoc = cv2.minMaxLoc(res)

    if maxVal >= threshold:
        (tH, tW) = template.shape[:2]
        center_x = maxLoc[0] + tW // 2
        center_y = maxLoc[1] + tH // 2
        return (center_x, center_y)
    return None

def _click_at(x: int, y: int):
    pyautogui.moveTo(x, y, duration=0.08)
    pyautogui.click()

# ───────────────────────────────────────────────────────────
# Login helpers (login only if needed)
# ───────────────────────────────────────────────────────────
def _looks_like_login_url(url: str) -> bool:
    # RealPrize uses hash-bang for login route.
    return url is not None and "realprize.com/#!login" in url

def _ensure_logged_in(sb: SB, username: str, password: str) -> bool:
    """
    Try to open the lobby. If we land on the login route (or form is visible), sign in.
    Returns True if we appear logged in and at lobby; else False.
    """
    try:
        sb.uc_open_with_reconnect(LOBBY_URL, 3)
        sb.wait_for_ready_state_complete()
    except Exception:
        pass

    cur = sb.get_current_url() or ""
    if _looks_like_login_url(cur):
        # Definitely on login
        try:
            sb.type(f"input[id='{EMAIL_ID}']", username, timeout=12)
            sb.type(f"input[id='{PASSWORD_ID}']", password, timeout=12)

            submitted = False
            try:
                sb.click(f"#{LOGIN_BTN_ID}", timeout=4)
                submitted = True
            except Exception:
                pass
            if not submitted:
                try:
                    sb.click_xpath(LOGIN_BTN_XPATH_FALLBACK, timeout=6)
                    submitted = True
                except Exception:
                    submitted = False

            if not submitted:
                print("[RealPrize] Could not submit login form.")
                return False

            sb.wait(5)
            sb.open(LOBBY_URL)
            sb.wait_for_ready_state_complete()
            time.sleep(2)
        except Exception as e:
            print(f"[RealPrize] Login error: {e}")
            return False
    else:
        # Might still be on a page that has the login form rendered in a modal.
        # If so, attempt to detect email/password fields to decide.
        try:
            if sb.is_element_visible(f"input[id='{EMAIL_ID}']", timeout=2) and \
               sb.is_element_visible(f"input[id='{PASSWORD_ID}']", timeout=2):
                sb.type(f"input[id='{EMAIL_ID}']", username)
                sb.type(f"input[id='{PASSWORD_ID}']", password)
                try:
                    sb.click(f"#{LOGIN_BTN_ID}", timeout=3)
                except Exception:
                    try:
                        sb.click_xpath(LOGIN_BTN_XPATH_FALLBACK, timeout=4)
                    except Exception:
                        return False
                sb.wait(5)
                sb.open(LOBBY_URL)
                sb.wait_for_ready_state_complete()
                time.sleep(2)
        except Exception:
            pass

    # If we’re still stuck on login, fail.
    final_url = sb.get_current_url() or ""
    if _looks_like_login_url(final_url):
        return False
    return True

# ───────────────────────────────────────────────────────────
# Main flow
# ───────────────────────────────────────────────────────────
async def realprize_uc(ctx, channel: discord.abc.Messageable):
    await channel.send("Launching **RealPrize** (UC + OpenCV)…")

    if ":" not in REALPRIZE_CRED:
        await channel.send("❌ Missing `REALPRIZE` as 'email:password' in your `.env`.")
        return
    username, password = REALPRIZE_CRED.split(":", 1)

    template_path = _existing_template_path()

    try:
        with SB(uc=True, headed=True) as sb:
            # Open lobby and login only if needed
            if not _ensure_logged_in(sb, username, password):
                await _send_status_shot(sb, channel, "RealPrize: login failed (or session expired).", "realprize_login_failed")
                return

            # Focus the window so PyAutoGUI clicks the right place
            try:
                sb.activate_html_elements()  # harmless; ensures doc is interactive
            except Exception:
                pass
            try:
                sb.maximize_window()
            except Exception:
                pass

            # Give the lobby a moment—popup should present quickly after page ready
            sb.wait_for_ready_state_complete()
            time.sleep(2.0)

            # Try multiple scans over a short window in case of late popup animation
            claimed = False
            start = time.time()
            while time.time() - start < 8.0:
                loc = _find_template_on_screen(template_path, threshold=0.88)
                if loc:
                    _click_at(*loc)
                    claimed = True
                    break
                time.sleep(0.5)

            if claimed:
                sb.wait(2)
                await _send_post_claim(sb, channel, "realprize_claimed.png", "Realprize Daily Bonus Claimed!")
                print("[RealPrize] Claimed via OpenCV click.")
            else:
                # No image detected; still send a screenshot with 'unavailable'
                await _send_status_shot(sb, channel, "RealPrize: bonus unavailable (no CLAIM button detected).", "realprize_unavailable")
                print("[RealPrize] CLAIM button not found; reported unavailable.")

    except Exception as e:
        print(f"[RealPrize][ERROR] {e}")
        # Best-effort screenshot from a fresh SB if possible
        try:
            with SB(uc=True, headed=True) as sb2:
                await _send_status_shot(sb2, channel, "RealPrize: error during automation.", "realprize_error")
        except Exception:
            await channel.send("RealPrize: error during automation.")
