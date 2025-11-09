# Drake Hooks + WaterTrooper
# Casino Claim 2
# LuckyLand API (SeleniumBase UC + OpenCV on HTML canvas)
# Debug build: detect & click login with robust canvas click + screenshots

import os
import time
from typing import Optional, Tuple, List

import discord
from dotenv import load_dotenv
from seleniumbase import SB

import cv2
import numpy as np

from selenium.webdriver.common.keys import Keys

load_dotenv()

LOGIN_URL = "https://luckylandslots.com/"
LUCKYLAND_CRED = os.getenv("LUCKYLAND", "")  # "email:password"
DPR = float(os.getenv("LUCKYLAND_DPR", "1.0"))  # devicePixelRatio correction if needed

# Images (put in ./images/ or repo root)
COOKIES_IMG = "luckyland_cookies.png"      # optional
PRELOGIN_BTN_IMG = "luckyland_loginbtn0.png"  # optional first opener
LOGIN_BTN_IMG = "luckylandloginbtn.png"       # purple "Log into Existing Account"

# Thresholds / timing
COOKIES_THRESH = 0.80
PRELOGIN_THRESH = 0.80
LOGIN_THRESH = 0.75
FIND_RETRIES = 10
FIND_DELAY = 0.7
POST_CLICK_PAUSE = 0.15        # between press/release bursts
AFTER_CLICK_DEBUG_WAIT = 5.0   # user asked for 5s after-click shot

# ───────────────────────────────────────────────────────────
# Image helpers
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

# ───────────────────────────────────────────────────────────
# Screenshot helpers
# ───────────────────────────────────────────────────────────
def _save_debug(sb: SB, name: str) -> str:
    path = f"/tmp/{name}.png"
    sb.save_screenshot(path)
    print(f"[DEBUG] Saved {path}")
    return path

async def _send_shot(channel, caption: str, path: str):
    if os.path.exists(path):
        await channel.send(caption, file=discord.File(path))

# ───────────────────────────────────────────────────────────
# Robust canvas click helpers
# ───────────────────────────────────────────────────────────
def _cdp_mouse_move(sb: SB, x: float, y: float):
    sb.driver.execute_cdp_cmd("Input.dispatchMouseEvent",
        {"type": "mouseMoved", "x": x, "y": y, "buttons": 0, "pointerType": "mouse"})

def _cdp_mouse_press_release(sb: SB, x: float, y: float, button: str = "left"):
    # press
    sb.driver.execute_cdp_cmd("Input.dispatchMouseEvent",
        {"type": "mousePressed", "x": x, "y": y, "button": button, "clickCount": 1, "buttons": 1, "pointerType": "mouse"})
    time.sleep(POST_CLICK_PAUSE)
    # release
    sb.driver.execute_cdp_cmd("Input.dispatchMouseEvent",
        {"type": "mouseReleased", "x": x, "y": y, "button": button, "clickCount": 1, "buttons": 0, "pointerType": "mouse"})
    time.sleep(POST_CLICK_PAUSE)

def _js_synthetic_click(sb: SB, x_css: float, y_css: float) -> str:
    """Dispatch DOM MouseEvents to the element under (x, y). Returns a short descriptor."""
    js = r"""
    const x = arguments[0], y = arguments[1];
    const el = document.elementFromPoint(x, y);
    if (!el) return "NO-ELEMENT";
    const ev = (type)=>el.dispatchEvent(new MouseEvent(type, {bubbles:true, cancelable:true, view:window, clientX:x, clientY:y, button:0}));
    try {
        ev('mousemove'); ev('mouseover'); ev('mousedown'); ev('mouseup'); ev('click');
    } catch(e) {}
    const id = el.id ? ('#' + el.id) : '';
    let cls = '';
    if (el.classList && el.classList.length) { cls = '.' + Array.from(el.classList).join('.'); }
    return el.tagName + id + cls;
    """
    try:
        desc = sb.execute_script(js, x_css, y_css) or ""
    except Exception:
        desc = ""
    return str(desc)

def _smart_click(sb: SB, x_view_css: int, y_view_css: int):
    """
    Try multiple realistic click paths at (x,y) in CSS px relative to the viewport.
    Order: move → CDP press/release (burst) → JS synthetic MouseEvents fallback.
    """
    X = x_view_css * DPR
    Y = y_view_css * DPR

    # Move pointer first (helps hover states on canvas UIs)
    _cdp_mouse_move(sb, X, Y)

    # Small burst at/around the point
    offsets = [(0,0), (1,1), (-1,-1), (2,0), (0,2)]
    for dx, dy in offsets:
        _cdp_mouse_move(sb, X+dx, Y+dy)
        _cdp_mouse_press_release(sb, X+dx, Y+dy)

    # JS synthetic on the element under the point (extra safety for overlay/canvas)
    desc = _js_synthetic_click(sb, x_view_css, y_view_css)
    print(f"[DEBUG] JS synthetic click on: {desc}")

# ───────────────────────────────────────────────────────────
# Try-find-click using OpenCV, then smart click
# ───────────────────────────────────────────────────────────
def _try_click(sb: SB, tmpl: Optional[np.ndarray], thresh: float, label: str) -> bool:
    if tmpl is None:
        return False
    for _ in range(FIND_RETRIES):
        bgr = _grab_bgr(sb)
        pt = _match_center(bgr, tmpl, thresh)
        if pt:
            print(f"[DEBUG] Found {label} at {pt} — attempting smart click")
            _smart_click(sb, pt[0], pt[1])
            return True
        time.sleep(FIND_DELAY)
    print(f"[DEBUG] Could not find {label}")
    return False

# ───────────────────────────────────────────────────────────
# Main
# ───────────────────────────────────────────────────────────
async def luckyland_uc(ctx, channel: discord.abc.Messageable):
    if ":" not in LUCKYLAND_CRED:
        await channel.send("[LuckyLand][ERROR] Missing LUCKYLAND='email:password' in .env")
        return

    cookies_tmpl  = _load_template(COOKIES_IMG)          # optional
    prelogin_tmpl = _load_template(PRELOGIN_BTN_IMG)     # optional
    login_tmpl    = _load_template(LOGIN_BTN_IMG)        # required

    if login_tmpl is None:
        await channel.send("[LuckyLand][ERROR] Missing luckylandloginbtn.png")
        return

    await channel.send("Starting LuckyLand debug (robust canvas click)…")

    try:
        with SB(uc=True) as sb:
            sb.set_window_size(1920, 1080)
            sb.uc_open(LOGIN_URL)
            sb.wait_for_ready_state_complete()
            sb.scroll_to_top()

            # Wake the canvas so it accepts pointer events
            _smart_click(sb, 960, 540)

            # Cookies (non-fatal)
            if cookies_tmpl is not None:
                _try_click(sb, cookies_tmpl, COOKIES_THRESH, "cookies")

            # Prelogin (non-fatal)
            if prelogin_tmpl is not None:
                _try_click(sb, prelogin_tmpl, PRELOGIN_THRESH, "prelogin")

            # Debug screenshot BEFORE login click
            before_path = _save_debug(sb, "before_login_click")
            await _send_shot(channel, "Before login button detection:", before_path)

            # Detect & smart-click the purple login button
            clicked = _try_click(sb, login_tmpl, LOGIN_THRESH, "login button")

            if clicked:
                print(f"[DEBUG] Clicked login — waiting {AFTER_CLICK_DEBUG_WAIT}s for modal to appear")
                time.sleep(AFTER_CLICK_DEBUG_WAIT)
                after_path = _save_debug(sb, "after_login_click")
                await _send_shot(channel, "After clicking login button (5s later):", after_path)
            else:
                fail_path = _save_debug(sb, "login_not_found")
                await _send_shot(channel, "[LuckyLand][ERROR] Could not find login button.", fail_path)

            await channel.send("✅ Debug run complete. Check screenshots above + container /tmp.")

    except Exception as e:
        await channel.send(f"[LuckyLand][ERROR] Exception: {e}")
