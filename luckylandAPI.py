# Drake Hooks + WaterTrooper
# Casino Claim 2
# LuckyLand API (SeleniumBase UC + OpenCV on HTML canvas)
# Exposes: async def luckyland_uc(ctx, channel)

import os
import time
import tempfile
from typing import Optional, Tuple, List, Iterable

import discord
from dotenv import load_dotenv
from seleniumbase import SB

# OpenCV / numpy
import cv2
import numpy as np

# Keys for TAB/ENTER fallbacks
from selenium.webdriver.common.keys import Keys

load_dotenv()

# ───────────────────────────────────────────────────────────
# Config
# ───────────────────────────────────────────────────────────
LOGIN_URL = "https://luckylandslots.com/"
LUCKYLAND_CRED = os.getenv("LUCKYLAND", "")  # "email:password"

# Optional devicePixelRatio correction if clicks land off (usually 1.0 at 1920x1080)
DPR = float(os.getenv("LUCKYLAND_DPR", "1.0"))

# Image filenames (we'll search ./images and CWD)
COOKIES_IMG          = "luckyland_cookies.png"     # accept cookies banner
PRELOGIN_BTN_IMG     = "luckyland_loginbtn0.png"   # pre-login opener
LOGIN_BTN_IMG        = "luckylandloginbtn.png"     # the actual "Login" button/modal trigger
COLLECT_IMG_CANDIDATES = ["luckyland_collect.png", "luckylandcollect.png"]

# Template match thresholds
COOKIES_THRESH  = 0.80
PRELOGIN_THRESH = 0.80
LOGIN_THRESH    = 0.60
COLLECT_THRESH  = 0.60

# Max attempts / timing
FIND_RETRIES       = 12
FIND_DELAY         = 0.7   # seconds between attempts
POST_CLICK_PAUSE   = 1.0
AFTER_LOGIN_WAIT   = 3.0
POST_MODAL_WAIT    = 1.0

# Multiscale matching scales (to tolerate small draw differences)
SCALES: Iterable[float] = (1.00, 0.95, 1.05, 0.90, 1.10, 0.85, 1.15)

# ───────────────────────────────────────────────────────────
# Utilities
# ───────────────────────────────────────────────────────────
def _img_search_paths(filename: str) -> List[str]:
    here = os.path.dirname(os.path.abspath(__file__))
    return [
        os.path.join(here, "images", filename),
        os.path.join(here, filename),
        os.path.join(os.getcwd(), "images", filename),
        os.path.join(os.getcwd(), filename),
    ]

def _load_template(filename: str) -> Optional[np.ndarray]:
    for p in _img_search_paths(filename):
        if os.path.exists(p):
            img = cv2.imread(p, cv2.IMREAD_COLOR)
            if img is not None:
                return img
    return None

def _grab_viewport_png(sb: SB) -> bytes:
    return sb.driver.get_screenshot_as_png()

def _png_to_bgr(png_bytes: bytes) -> np.ndarray:
    data = np.frombuffer(png_bytes, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)

def _match_center_multiscale(bgr_image: np.ndarray, bgr_template: np.ndarray, threshold: float) -> Optional[Tuple[int,int]]:
    if bgr_image is None or bgr_template is None:
        return None
    ih, iw = bgr_image.shape[:2]
    th0, tw0 = bgr_template.shape[:2]
    best = None
    best_val = -1.0

    for s in SCALES:
        th = int(th0 * s)
        tw = int(tw0 * s)
        if th < 6 or tw < 6:
            continue
        tmpl = cv2.resize(bgr_template, (tw, th), interpolation=cv2.INTER_AREA if s < 1.0 else cv2.INTER_CUBIC)
        if ih < th or iw < tw:
            continue
        res = cv2.matchTemplate(bgr_image, tmpl, cv2.TM_CCOEFF_NORMED)
        minVal, maxVal, minLoc, maxLoc = cv2.minMaxLoc(res)
        if maxVal > best_val:
            best_val = maxVal
            if maxVal >= threshold:
                x, y = maxLoc
                cx = x + tw // 2
                cy = y + th // 2
                best = (int(cx), int(cy))
                # we still finish loop to see if an even better match exists
    return best

def _viewport_click(sb: SB, x: int, y: int, delay_after: float = POST_CLICK_PAUSE) -> None:
    # Correct for DPR if specified
    X = x * DPR
    Y = y * DPR
    sb.driver.execute_cdp_cmd("Input.dispatchMouseEvent",
                              {"type": "mousePressed", "x": X, "y": Y, "button": "left", "clickCount": 1})
    sb.driver.execute_cdp_cmd("Input.dispatchMouseEvent",
                              {"type": "mouseReleased", "x": X, "y": Y, "button": "left", "clickCount": 1})
    time.sleep(delay_after)

def _cdp_insert_text(sb: SB, text: str) -> None:
    sb.driver.execute_cdp_cmd("Input.insertText", {"text": text})

def _cdp_key(sb: SB, key: str) -> None:
    sb.driver.execute_cdp_cmd("Input.dispatchKeyEvent", {"type": "keyDown", "key": key})
    sb.driver.execute_cdp_cmd("Input.dispatchKeyEvent", {"type": "keyUp", "key": key})

def _try_find_and_click(sb: SB, tmpl: Optional[np.ndarray], threshold: float, attempts: int, between: float, label: str) -> bool:
    """Repeatedly screenshot, match (multiscale), and click the center if found."""
    if tmpl is None:
        return False
    for _ in range(attempts):
        bgr = _png_to_bgr(_grab_viewport_png(sb))
        center = _match_center_multiscale(bgr, tmpl, threshold)
        if center:
            _viewport_click(sb, center[0], center[1])
            return True
        time.sleep(between)
    return False

async def _send_screenshot(channel: discord.abc.Messageable, caption: str, png_bytes: bytes):
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix="luckyland_", suffix=".png")
        os.close(fd)
        with open(tmp, "wb") as f:
            f.write(png_bytes)
        await channel.send(caption, file=discord.File(tmp))
    finally:
        if tmp and os.path.exists(tmp):
            try: os.remove(tmp)
            except Exception: pass

# ───────────────────────────────────────────────────────────
# Main Flow
# ───────────────────────────────────────────────────────────
async def luckyland_uc(ctx, channel: discord.abc.Messageable):
    if ":" not in LUCKYLAND_CRED:
        await channel.send("[LuckyLand][ERROR] Missing env var LUCKYLAND='email:password'.")
        return

    email, password = LUCKYLAND_CRED.split(":", 1)

    # Load templates
    cookies_tmpl   = _load_template(COOKIES_IMG)          # optional
    prelogin_tmpl  = _load_template(PRELOGIN_BTN_IMG)     # optional
    login_tmpl     = _load_template(LOGIN_BTN_IMG)        # required (or we bail)
    collect_tmpl   = None
    for nm in COLLECT_IMG_CANDIDATES:
        collect_tmpl = _load_template(nm)
        if collect_tmpl is not None:
            break

    if login_tmpl is None:
        await channel.send("[LuckyLand][ERROR] Missing login template image: luckylandloginbtn.png")
        return
    if collect_tmpl is None:
        await channel.send("[LuckyLand][ERROR] Missing collect template image: luckyland_collect.png (or luckylandcollect.png)")
        return

    try:
        with SB(uc=True) as sb:
            sb.set_window_size(1920, 1080)
            sb.uc_open(LOGIN_URL)
            sb.wait_for_ready_state_complete()
            sb.scroll_to_top()

            # --- Step A: Accept cookies if present (always attempt; harmless if not there)
            if cookies_tmpl is not None:
                _try_find_and_click(sb, cookies_tmpl, COOKIES_THRESH, attempts=6, between=0.5, label="cookies")
                time.sleep(0.4)

            # We'll do one refresh fallback later if we get stuck.
            refreshed_once = False

            # --- Step B: Open login chain
            # Preferred path: prelogin → login
            # 1) Try prelogin if available; if not, we still try the main login directly.
            pre_clicked = _try_find_and_click(sb, prelogin_tmpl, PRELOGIN_THRESH, attempts=6, between=0.6, label="prelogin")

            if pre_clicked:
                time.sleep(POST_MODAL_WAIT)
                sb.wait_for_ready_state_complete(timeout=10)

            # 2) Now hunt the main login
            main_login_ok = _try_find_and_click(sb, login_tmpl, LOGIN_THRESH, attempts=FIND_RETRIES, between=FIND_DELAY, label="login")

            if not main_login_ok:
                # If we didn’t find the main login:
                # - Try one quick refresh and repeat cookie → prelogin → login sequence once.
                if not refreshed_once:
                    sb.refresh_page()
                    refreshed_once = True
                    sb.wait_for_ready_state_complete()
                    time.sleep(0.8)
                    sb.scroll_to_top()
                    # cookies again (non-fatal)
                    if cookies_tmpl is not None:
                        _try_find_and_click(sb, cookies_tmpl, COOKIES_THRESH, attempts=4, between=0.5, label="cookies2")
                    # prelogin again (non-fatal)
                    _try_find_and_click(sb, prelogin_tmpl, PRELOGIN_THRESH, attempts=5, between=0.6, label="prelogin2")
                    # main login again (required)
                    main_login_ok = _try_find_and_click(sb, login_tmpl, LOGIN_THRESH, attempts=FIND_RETRIES, between=FIND_DELAY, label="login2")

            if not main_login_ok:
                png = _grab_viewport_png(sb)
                await _send_screenshot(channel, "[LuckyLand][ERROR] Could not find/click the login button.", png)
                return

            time.sleep(POST_MODAL_WAIT)  # modal animate / focus field

            # --- Step C: Type credentials (email → TAB → password → ENTER)
            try:
                _cdp_insert_text(sb, email)
                _cdp_key(sb, "Tab")
                _cdp_insert_text(sb, password)
                _cdp_key(sb, "Enter")
            except Exception:
                # Fallback to active element
                try:
                    ae = sb.driver.switch_to.active_element
                    ae.send_keys(email)
                    ae.send_keys(Keys.TAB)
                    ae = sb.driver.switch_to.active_element
                    ae.send_keys(password)
                    ae.send_keys(Keys.ENTER)
                except Exception:
                    png = _grab_viewport_png(sb)
                    await _send_screenshot(channel, "[LuckyLand][ERROR] Unable to type credentials.", png)
                    return

            # --- Step D: Wait for lobby / draw
            time.sleep(AFTER_LOGIN_WAIT)
            sb.wait_for_ready_state_complete(timeout=12)

            # --- Step E: Find & click Collect
            collected = _try_find_and_click(sb, collect_tmpl, COLLECT_THRESH, attempts=FIND_RETRIES, between=FIND_DELAY, label="collect")

            # --- Final screenshot either way
            final_png = _grab_viewport_png(sb)
            if collected:
                await _send_screenshot(channel, "LuckyLand: Daily bonus collected! 🎉", final_png)
            else:
                await _send_screenshot(channel, "LuckyLand: Could not detect the Collect button. ❌", final_png)

    except Exception as e:
        try:
            await channel.send(f"[LuckyLand][ERROR] Exception: {e}")
        except Exception:
            pass
