# Drake Hooks + WaterTrooper
# Casino Claim 2
# LuckyLand API (SeleniumBase UC + OpenCV on HTML canvas)
# Exposes: async def luckyland_uc(ctx, channel)

import os
import io
import time
import tempfile
from typing import Optional, Tuple, List

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

# Image filenames (we'll search ./images and CWD)
LOGIN_BTN_IMG = "luckylandloginbtn.png"
COLLECT_IMG_CANDIDATES = ["luckyland_collect.png", "luckylandcollect.png"]

# Template match thresholds
LOGIN_THRESH = 0.80
COLLECT_THRESH = 0.82

# Max attempts / timing
FIND_RETRIES = 10
FIND_DELAY = 0.9   # seconds between attempts
POST_CLICK_PAUSE = 1.2
AFTER_LOGIN_WAIT = 3.0

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

def _cv_match_center(bgr_image: np.ndarray, bgr_template: np.ndarray, threshold: float) -> Optional[Tuple[int, int]]:
    if bgr_image is None or bgr_template is None:
        return None
    ih, iw = bgr_image.shape[:2]
    th, tw = bgr_template.shape[:2]
    if ih < th or iw < tw:
        return None
    res = cv2.matchTemplate(bgr_image, bgr_template, cv2.TM_CCOEFF_NORMED)
    _, maxVal, _, maxLoc = cv2.minMaxLoc(res)
    if maxVal >= threshold:
        x, y = maxLoc
        return (int(x + tw // 2), int(y + th // 2))
    return None

def _grab_viewport_png(sb: SB) -> bytes:
    return sb.driver.get_screenshot_as_png()

def _png_to_bgr(png_bytes: bytes) -> np.ndarray:
    data = np.frombuffer(png_bytes, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)

def _viewport_click(sb: SB, x: int, y: int, delay_after: float = POST_CLICK_PAUSE) -> None:
    sb.driver.execute_cdp_cmd("Input.dispatchMouseEvent",
                              {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
    sb.driver.execute_cdp_cmd("Input.dispatchMouseEvent",
                              {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})
    time.sleep(delay_after)

def _cdp_insert_text(sb: SB, text: str) -> None:
    sb.driver.execute_cdp_cmd("Input.insertText", {"text": text})

def _cdp_key(sb: SB, key: str) -> None:
    sb.driver.execute_cdp_cmd("Input.dispatchKeyEvent", {"type": "keyDown", "key": key})
    sb.driver.execute_cdp_cmd("Input.dispatchKeyEvent", {"type": "keyUp", "key": key})

def _try_match_and_click(sb: SB, template: np.ndarray, threshold: float, attempts: int, between: float) -> bool:
    for _ in range(attempts):
        png = _grab_viewport_png(sb)
        bgr = _png_to_bgr(png)
        center = _cv_match_center(bgr, template, threshold)
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
    login_tmpl = _load_template(LOGIN_BTN_IMG)
    collect_tmpl = None
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
        # IMPORTANT: Use SB as a context manager
        with SB(uc=True) as sb:
            # 1920×1080 like the rest
            sb.set_window_size(1920, 1080)

            # Open in UC mode
            sb.uc_open(LOGIN_URL)
            sb.wait_for_ready_state_complete()
            sb.scroll_to_top()

            # 1) Click Login (OpenCV)
            if not _try_match_and_click(sb, login_tmpl, LOGIN_THRESH, attempts=FIND_RETRIES, between=FIND_DELAY):
                png = _grab_viewport_png(sb)
                await _send_screenshot(channel, "[LuckyLand][ERROR] Could not find login button.", png)
                return

            time.sleep(1.0)  # let modal animate / focus first field

            # 2) Type email → TAB → password → ENTER
            try:
                _cdp_insert_text(sb, email)
                _cdp_key(sb, "Tab")
                _cdp_insert_text(sb, password)
                _cdp_key(sb, "Enter")
            except Exception:
                # Fallback: active element keys
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

            # 3) Wait for lobby / draw
            time.sleep(AFTER_LOGIN_WAIT)
            sb.wait_for_ready_state_complete(timeout=12)

            # 4) Find & click Collect
            collected = _try_match_and_click(sb, collect_tmpl, COLLECT_THRESH, attempts=FIND_RETRIES, between=FIND_DELAY)

            # 5) Final screenshot either way
            final_png = _grab_viewport_png(sb)
            if collected:
                await _send_screenshot(channel, "LuckyLand: Daily bonus collected! 🎉", final_png)
            else:
                await _send_screenshot(channel, "LuckyLand: Could not detect the Collect button. ❌", final_png)

    except Exception as e:
        # If something exploded outside the context, just report the error
        await channel.send(f"[LuckyLand][ERROR] Exception: {e}")
