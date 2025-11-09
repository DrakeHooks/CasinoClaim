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
COOKIES_IMG            = "luckyland_cookies.png"      # accept cookies banner
PRELOGIN_BTN_IMG       = "luckyland_loginbtn0.png"    # pre-login opener
LOGIN_BTN_IMG          = "luckylandloginbtn.png"      # purple "Log into Existing Account"
COLLECT_IMG_CANDIDATES = ["luckyland_collect.png", "luckylandcollect.png"]

# Template match thresholds (kept forgiving for canvas AA)
COOKIES_THRESH  = 0.75
PRELOGIN_THRESH = 0.75
LOGIN_THRESH    = 0.68
COLLECT_THRESH  = 0.70

# Attempts / timing
FIND_RETRIES       = 14
FIND_DELAY         = 0.6
POST_CLICK_PAUSE   = 0.9
AFTER_LOGIN_WAIT   = 3.0
POST_MODAL_WAIT    = 1.0

# Multiscale matching scales (wider band for this page)
SCALES: Iterable[float] = (1.00, 0.95, 1.05, 0.90, 1.10, 0.85, 1.15, 0.80, 1.20, 0.75, 1.25, 1.30)

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

def _prep_variants(img: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (color, gray, edges) variants for robust matching."""
    color = img
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # light blur helps with canvas AA; edges help with bold text/button shapes
    gray_blur = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(gray_blur, 40, 120)
    return color, gray_blur, edges

def _best_match_center(scene_bgr: np.ndarray, tmpl_bgr: np.ndarray, threshold: float) -> Optional[Tuple[int,int]]:
    """
    Try color, grayscale, and edges across multiple scales; return best center if >= threshold.
    """
    if scene_bgr is None or tmpl_bgr is None:
        return None

    scene_color, scene_gray, scene_edges = _prep_variants(scene_bgr)
    tmpl_color, tmpl_gray, tmpl_edges = _prep_variants(tmpl_bgr)

    ih, iw = scene_color.shape[:2]
    th0, tw0 = tmpl_color.shape[:2]

    best = None
    best_val = -1.0

    # Try three modes: color, gray, edges
    for mode in ("color", "gray", "edges"):
        scene = {"color": scene_color, "gray": scene_gray, "edges": scene_edges}[mode]
        tmpl0 = {"color": tmpl_color,  "gray":  tmpl_gray,  "edges": tmpl_edges}[mode]
        method = cv2.TM_CCOEFF_NORMED

        for s in SCALES:
            th = max(6, int(th0 * s))
            tw = max(6, int(tw0 * s))
            tmpl = cv2.resize(tmpl0, (tw, th), interpolation=cv2.INTER_AREA if s < 1.0 else cv2.INTER_CUBIC)
            if scene.shape[0] < th or scene.shape[1] < tw:
                continue

            res = cv2.matchTemplate(scene, tmpl, method)
            _, maxVal, _, maxLoc = cv2.minMaxLoc(res)
            if maxVal > best_val:
                best_val = maxVal
                if maxVal >= threshold:
                    x, y = maxLoc
                    cx = int(x + tw // 2)
                    cy = int(y + th // 2)
                    best = (cx, cy)
    return best

def _viewport_click(sb: SB, x: int, y: int, delay_after: float = POST_CLICK_PAUSE) -> None:
    X = x * DPR
    Y = y * DPR
    sb.driver.execute_cdp_cmd("Input.dispatchMouseEvent",
                              {"type": "mousePressed", "x": X, "y": Y, "button": "left", "clickCount": 1})
    sb.driver.execute_cdp_cmd("Input.dispatchMouseEvent",
                              {"type": "mouseReleased", "x": X, "y": Y, "button": "left", "clickCount": 1})
    time.sleep(delay_after)

def _burst_click(sb: SB, x: int, y: int) -> None:
    """Center + tiny offsets; helps with hover-state hitboxes on canvas."""
    offsets = [(0,0), (1,1), (-1,-1), (2,0), (0,2)]
    for dx, dy in offsets:
        _viewport_click(sb, x+dx, y+dy, delay_after=0.15)
    time.sleep(POST_CLICK_PAUSE)

def _cdp_insert_text(sb: SB, text: str) -> None:
    sb.driver.execute_cdp_cmd("Input.insertText", {"text": text})

def _cdp_key(sb: SB, key: str) -> None:
    sb.driver.execute_cdp_cmd("Input.dispatchKeyEvent", {"type": "keyDown", "key": key})
    sb.driver.execute_cdp_cmd("Input.dispatchKeyEvent", {"type": "keyUp", "key": key})

def _try_find_and_click(sb: SB, tmpl: Optional[np.ndarray], threshold: float, attempts: int, between: float, label: str, burst: bool = True) -> bool:
    if tmpl is None:
        return False
    for _ in range(attempts):
        bgr = _png_to_bgr(_grab_viewport_png(sb))
        center = _best_match_center(bgr, tmpl, threshold)
        if center:
            if burst:
                _burst_click(sb, center[0], center[1])
            else:
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
    login_tmpl     = _load_template(LOGIN_BTN_IMG)        # required
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

            # Focus wake-up: click center of canvas once so it starts receiving input.
            _viewport_click(sb, 960, 540, delay_after=0.2)

            # A) Cookies (non-fatal)
            if cookies_tmpl is not None:
                _try_find_and_click(sb, cookies_tmpl, COOKIES_THRESH, attempts=6, between=0.4, label="cookies")
                time.sleep(0.3)

            # We'll allow one refresh retry if opener chain stalls
            for attempt in range(2):  # 0 = first pass, 1 = retry after refresh
                # B1) Prelogin (non-fatal; helps reveal login)
                _try_find_and_click(sb, prelogin_tmpl, PRELOGIN_THRESH, attempts=6, between=0.5, label="prelogin")

                # B2) Main login (REQUIRED) – stubborn mode
                main_login_ok = _try_find_and_click(sb, login_tmpl, LOGIN_THRESH, attempts=FIND_RETRIES, between=FIND_DELAY, label="login")

                if main_login_ok:
                    break

                if attempt == 0:
                    # Refresh & re-try whole chain once
                    sb.refresh_page()
                    sb.wait_for_ready_state_complete()
                    time.sleep(0.8)
                    sb.scroll_to_top()
                    _viewport_click(sb, 960, 540, delay_after=0.2)  # re-focus canvas
                    if cookies_tmpl is not None:
                        _try_find_and_click(sb, cookies_tmpl, COOKIES_THRESH, attempts=4, between=0.4, label="cookies2")

            if not main_login_ok:
                png = _grab_viewport_png(sb)
                await _send_screenshot(channel, "[LuckyLand][ERROR] Could not find/click the login button.", png)
                return

            time.sleep(POST_MODAL_WAIT)  # modal animate / focus first field

            # C) Type credentials (email → TAB → password → ENTER)
            try:
                _cdp_insert_text(sb, email)
                _cdp_key(sb, "Tab")
                _cdp_insert_text(sb, password)
                _cdp_key(sb, "Enter")
            except Exception:
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

            # D) Wait for lobby / draw
            time.sleep(AFTER_LOGIN_WAIT)
            sb.wait_for_ready_state_complete(timeout=12)

            # E) Collect
            collected = _try_find_and_click(sb, collect_tmpl, COLLECT_THRESH, attempts=FIND_RETRIES, between=FIND_DELAY, label="collect")

            # Final screenshot either way
            final_png = _grab_viewport_png(sb)
            if collected:
                await _send_screenshot(channel, "LuckyLand Daily Bonus Claimed", final_png)
            else:
                await _send_screenshot(channel, "LuckyLand: Could not detect the Collect button.", final_png)

    except Exception as e:
        try:
            await channel.send(f"[LuckyLand][ERROR] Exception: {e}")
        except Exception:
            pass
