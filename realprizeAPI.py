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
# Helper: What counts as "login URL"?
# ───────────────────────────────────────────────────────────
def _looks_like_login_url(url: str) -> bool:
    # RealPrize uses hash-bang for login route.
    return url is not None and "realprize.com/#!login" in url


# ───────────────────────────────────────────────────────────
# DEBUG LOGIN FLOW (with step-by-step screenshots)
# ───────────────────────────────────────────────────────────
async def _debug_login_flow(
    sb: SB,
    channel: discord.abc.Messageable,
    username: str,
    password: str,
    context: str,
) -> bool:
    """
    Perform the login sequence with heavy debug:
      - Screenshot before typing
      - Screenshot after typing
      - Screenshot after clicking login
      - Screenshot after redirect back to lobby
    `context` is just a string tag for prefixes ("route_login", "modal_login", etc).
    Returns True if we appear logged in (not stuck on login URL); else False.
    """
    try:
        await _send_status_shot(
            sb,
            channel,
            f"RealPrize {context}: On login form before typing credentials.",
            f"realprize_{context}_before_typing",
        )

        # Type creds
        sb.type(f"input[id='{EMAIL_ID}']", username, timeout=12)
        sb.type(f"input[id='{PASSWORD_ID}']", password, timeout=12)

        await _send_status_shot(
            sb,
            channel,
            f"RealPrize {context}: After typing credentials, before submitting.",
            f"realprize_{context}_after_typing",
        )

        # Try primary login button
        submitted = False
        try:
            sb.click(f"#{LOGIN_BTN_ID}", timeout=4)
            submitted = True
            print("[RealPrize] Clicked login button by ID.")
        except Exception as e:
            print(f"[RealPrize] Failed to click login button by ID: {e}")

        # Fallback XPath
        if not submitted:
            try:
                sb.click_xpath(LOGIN_BTN_XPATH_FALLBACK, timeout=6)
                submitted = True
                print("[RealPrize] Clicked login button via fallback XPath.")
            except Exception as e:
                print(f"[RealPrize] Failed to click login button via XPath: {e}")

        await _send_status_shot(
            sb,
            channel,
            f"RealPrize {context}: After attempting to submit login.",
            f"realprize_{context}_after_submit",
        )

        if not submitted:
            await channel.send("RealPrize debug: could not submit login form at all.")
            return False

        # Give time to process login
        sb.wait(5)
        try:
            sb.open(LOBBY_URL)
            sb.wait_for_ready_state_complete()
        except Exception as e:
            print(f"[RealPrize] Error navigating to lobby after login: {e}")

        time.sleep(2)

        final_url = sb.get_current_url() or ""
        await _send_status_shot(
            sb,
            channel,
            f"RealPrize {context}: After redirect to lobby. final_url={final_url}",
            f"realprize_{context}_after_redirect",
        )

        if _looks_like_login_url(final_url):
            await channel.send("RealPrize debug: still on login URL after login attempt.")
            return False

        return True

    except Exception as e:
        print(f"[RealPrize] Exception inside _debug_login_flow ({context}): {e}")
        await _send_status_shot(
            sb,
            channel,
            f"RealPrize {context}: exception during login: {e}",
            f"realprize_{context}_exception",
        )
        return False


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
            # ── STEP 1: Open lobby URL ────────────────────────
            try:
                sb.uc_open_with_reconnect(LOBBY_URL, 3)
                sb.wait_for_ready_state_complete()
            except Exception as e:
                print(f"[RealPrize] Error opening lobby: {e}")

            await _send_status_shot(
                sb,
                channel,
                "RealPrize STEP 1: After opening lobby URL.",
                "realprize_step1_open_lobby",
            )

            cur = sb.get_current_url() or ""
            print(f"[RealPrize] Current URL after lobby open: {cur}")
            is_login_route = _looks_like_login_url(cur)

            # ── STEP 2: Detect login page vs modal ────────────
            login_modal_visible = False
            try:
                if sb.is_element_visible(f"input[id='{EMAIL_ID}']", timeout=3) and \
                   sb.is_element_visible(f"input[id='{PASSWORD_ID}']", timeout=3):
                    login_modal_visible = True
            except Exception:
                login_modal_visible = False

            await _send_status_shot(
                sb,
                channel,
                f"RealPrize STEP 2: URL={cur} | is_login_route={is_login_route} | login_modal_visible={login_modal_visible}",
                "realprize_step2_url_and_modal_state",
            )

            # ── STEP 3: Run debug login flow if needed ────────
            logged_in = True

            if is_login_route:
                # Hard login route (#!login)
                logged_in = await _debug_login_flow(
                    sb, channel, username, password, context="route_login"
                )
            elif login_modal_visible:
                # Lobby but login modal showing
                logged_in = await _debug_login_flow(
                    sb, channel, username, password, context="modal_login"
                )
            else:
                # Looks like we might already be logged in; still capture state.
                await _send_status_shot(
                    sb,
                    channel,
                    "RealPrize STEP 3: No explicit login form detected; assuming already logged in.",
                    "realprize_step3_assume_logged_in",
                )
                final_url = sb.get_current_url() or ""
                print(f"[RealPrize] Assuming logged in; final_url={final_url}")
                # If we somehow are actually on login URL here, treat as not logged in.
                if _looks_like_login_url(final_url):
                    logged_in = False

            if not logged_in:
                await _send_status_shot(
                    sb,
                    channel,
                    "RealPrize: login failed or still on login page after attempts.",
                    "realprize_login_failed",
                )
                return

            # ── STEP 4: Focus window & prep for OpenCV click ──
            try:
                sb.activate_html_elements()  # harmless; ensures doc is interactive
            except Exception:
                pass
            try:
                sb.maximize_window()
            except Exception:
                pass

            sb.wait_for_ready_state_complete()
            time.sleep(2.0)

            await _send_status_shot(
                sb,
                channel,
                "RealPrize STEP 4: Lobby after login (before scanning for CLAIM popup).",
                "realprize_step4_lobby_post_login",
            )

            # ── STEP 5: Scan for CLAIM popup via OpenCV ───────
            claimed = False
            start = time.time()
            while time.time() - start < 8.0:
                loc = _find_template_on_screen(template_path, threshold=0.88)
                if loc:
                    await channel.send(f"RealPrize debug: CLAIM template found at {loc}, clicking…")
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
                await _send_status_shot(
                    sb,
                    channel,
                    "RealPrize: bonus unavailable (no CLAIM button detected).",
                    "realprize_unavailable",
                )
                print("[RealPrize] CLAIM button not found; reported unavailable.")

    except Exception as e:
        print(f"[RealPrize][ERROR] {e}")
        # Best-effort screenshot from a fresh SB if possible
        try:
            with SB(uc=True, headed=True) as sb2:
                await _send_status_shot(
                    sb2,
                    channel,
                    "RealPrize: error during automation.",
                    "realprize_error",
                )
        except Exception:
            await channel.send("RealPrize: error during automation.")
