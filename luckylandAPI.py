# Drake Hooks + WaterTrooper
# Casino Claim 2
# LuckyLand API (SeleniumBase UC + OpenCV on HTML canvas)
# Debug build — focused on login button detection and screenshots

import os
import time
import tempfile
from typing import Optional, Tuple, List, Iterable

import discord
from dotenv import load_dotenv
from seleniumbase import SB

import cv2
import numpy as np
from selenium.webdriver.common.keys import Keys

load_dotenv()

LOGIN_URL = "https://luckylandslots.com/"
LUCKYLAND_CRED = os.getenv("LUCKYLAND", "")  # "email:password"
DPR = float(os.getenv("LUCKYLAND_DPR", "1.0"))

# Images
COOKIES_IMG = "luckyland_cookies.png"
PRELOGIN_BTN_IMG = "luckyland_loginbtn0.png"
LOGIN_BTN_IMG = "luckylandloginbtn.png"

# Thresholds
COOKIES_THRESH = 0.80
PRELOGIN_THRESH = 0.80
LOGIN_THRESH = 0.75

# Attempts
FIND_RETRIES = 10
FIND_DELAY = 0.7
POST_CLICK_PAUSE = 1.0

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
            return cv2.imread(p, cv2.IMREAD_COLOR)
    return None

def _grab_bgr(sb: SB) -> np.ndarray:
    data = np.frombuffer(sb.driver.get_screenshot_as_png(), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)

def _match_center(bgr: np.ndarray, tmpl: np.ndarray, thresh: float) -> Optional[Tuple[int,int]]:
    res = cv2.matchTemplate(bgr, tmpl, cv2.TM_CCOEFF_NORMED)
    _, maxVal, _, maxLoc = cv2.minMaxLoc(res)
    if maxVal >= thresh:
        th, tw = tmpl.shape[:2]
        return (maxLoc[0] + tw // 2, maxLoc[1] + th // 2)
    return None

def _viewport_click(sb: SB, x: int, y: int):
    X, Y = x * DPR, y * DPR
    sb.driver.execute_cdp_cmd("Input.dispatchMouseEvent",
        {"type":"mousePressed","x":X,"y":Y,"button":"left","clickCount":1})
    sb.driver.execute_cdp_cmd("Input.dispatchMouseEvent",
        {"type":"mouseReleased","x":X,"y":Y,"button":"left","clickCount":1})
    time.sleep(POST_CLICK_PAUSE)

def _try_click(sb: SB, tmpl: np.ndarray, thresh: float, label: str) -> bool:
    for i in range(FIND_RETRIES):
        bgr = _grab_bgr(sb)
        pt = _match_center(bgr, tmpl, thresh)
        if pt:
            print(f"[DEBUG] Found {label} at {pt}")
            _viewport_click(sb, pt[0], pt[1])
            return True
        time.sleep(FIND_DELAY)
    print(f"[DEBUG] Could not find {label}")
    return False

def _save_debug(sb: SB, name: str):
    path = f"/tmp/{name}.png"
    sb.save_screenshot(path)
    print(f"[DEBUG] Saved {path}")
    return path

async def _send_shot(channel, caption: str, path: str):
    if os.path.exists(path):
        await channel.send(caption, file=discord.File(path))

# ───────────────────────────────────────────────────────────
# Main
# ───────────────────────────────────────────────────────────
async def luckyland_uc(ctx, channel: discord.abc.Messageable):
    if ":" not in LUCKYLAND_CRED:
        await channel.send("[LuckyLand][ERROR] Missing LUCKYLAND='email:password' in .env")
        return

    cookies_tmpl  = _load_template(COOKIES_IMG)
    prelogin_tmpl = _load_template(PRELOGIN_BTN_IMG)
    login_tmpl    = _load_template(LOGIN_BTN_IMG)

    if login_tmpl is None:
        await channel.send("[LuckyLand][ERROR] Missing luckylandloginbtn.png")
        return

    await channel.send("Starting LuckyLand debug run…")

    try:
        with SB(uc=True) as sb:
            sb.set_window_size(1920, 1080)
            sb.uc_open(LOGIN_URL)
            sb.wait_for_ready_state_complete()
            sb.scroll_to_top()

            # Step 1: Cookies
            if cookies_tmpl is not None:
                _try_click(sb, cookies_tmpl, COOKIES_THRESH, "cookies")

            # Step 2: Prelogin (if exists)
            if prelogin_tmpl is not None:
                _try_click(sb, prelogin_tmpl, PRELOGIN_THRESH, "prelogin")

            # Step 3: Screenshot before login detection
            before_path = _save_debug(sb, "before_login_click")
            await _send_shot(channel, "Before login button detection:", before_path)

            # Step 4: Try to detect and click login button
            clicked = _try_click(sb, login_tmpl, LOGIN_THRESH, "login button")

            # Step 5: Screenshot results
            if clicked:
                after_wait = 5
                print(f"[DEBUG] Clicked login button; waiting {after_wait}s for modal…")
                time.sleep(after_wait)
                after_path = _save_debug(sb, "after_login_click")
                await _send_shot(channel, "After clicking login button (5s later):", after_path)
            else:
                fail_path = _save_debug(sb, "login_not_found")
                await _send_shot(channel, "[LuckyLand][ERROR] Could not find login button.", fail_path)

            await channel.send("✅ Debug run complete. Check screenshots above and /tmp folder.")

    except Exception as e:
        await channel.send(f"[LuckyLand][ERROR] Exception: {e}")
