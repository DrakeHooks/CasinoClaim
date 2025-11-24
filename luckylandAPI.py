# Drake Hooks + WaterTrooper
# Casino Claim 2
# LuckyLand API — canvas-targeted pointer click (with debug screenshots)

import os
import time
from typing import Optional, Tuple, List

import asyncio
from concurrent.futures import ThreadPoolExecutor

import discord
from dotenv import load_dotenv
from seleniumbase import SB

import cv2
import numpy as np

load_dotenv()

LOGIN_URL = "https://luckylandslots.com/"
LUCKYLAND_CRED = os.getenv("LUCKYLAND", "")  # "email:password"

# If coordinates seem slightly off in your environment, tweak DPR
DPR = float(os.getenv("LUCKYLAND_DPR", "1.25"))

# Templates (put these in ./images or repo root)
COOKIES_IMG       = "luckyland_cookies.png"       # optional
PRELOGIN_BTN_IMG  = "luckyland_loginbtn0.png"     # optional
LOGIN_BTN_IMG     = "luckylandloginbtn.png"       # required ("Log into Existing Account")

COOKIES_THRESH    = 0.80
PRELOGIN_THRESH   = 0.80
LOGIN_THRESH      = 0.75

FIND_RETRIES      = 10
FIND_DELAY        = 0.5
AFTER_CLICK_WAIT  = 5.0


# -------------- basic helpers --------------

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


def _save_debug(sb: SB, name: str) -> str:
    path = f"/tmp/luckyland_{name}.png"
    sb.save_screenshot(path)
    return path


async def _send_shot(channel: discord.abc.Messageable, caption: str, path: str):
    if os.path.exists(path):
        await channel.send(caption, file=discord.File(path))
    else:
        await channel.send(f"{caption} (screenshot missing: {path})")


# -------------- canvas clicking via JS --------------

_JS_CANVAS_CLICK = r"""
(function(xCss, yCss){
  const el = document.elementFromPoint(xCss, yCss);
  if (!el) return {ok:false, why:"NO_ELEMENT"};

  const Ev = (window.PointerEvent || window.MouseEvent);
  const base = {
    bubbles: true,
    cancelable: true,
    view: window,
    clientX: xCss,
    clientY: yCss,
    button: 0,
    buttons: 1,
    pointerType: 'mouse',
    pointerId: 1,
  };

  function fire(type) {
    try {
      el.dispatchEvent(new Ev(type, base));
    } catch(e) {
      try {
        el.dispatchEvent(new MouseEvent(type, base));
      } catch(e2) {}
    }
  }

  try {
    fire('pointermove');
    fire('mousemove');
    fire('pointerdown');
    fire('mousedown');
    fire('mouseup');
    fire('pointerup');
    fire('click');
  } catch(e) {
    return {ok:false, why:String(e), tag: el.tagName, id: el.id || null, className: el.className || null};
  }

  return {
    ok:true,
    tag: el.tagName,
    id: el.id || null,
    className: el.className || null
  };
})(arguments[0], arguments[1]);
"""


def _canvas_click(sb: SB, x_css: int, y_css: int) -> None:
    try:
        result = sb.execute_script(_JS_CANVAS_CLICK, int(x_css), int(y_css)) or {}
        print(f"[LuckyLand] canvas_click at ({x_css},{y_css}) -> {result}")
    except Exception as e:
        print(f"[LuckyLand] canvas_click JS error: {e}")


# -------------- template matching --------------

def _match_center(
    bgr: np.ndarray,
    tmpl: np.ndarray,
    thresh: float
) -> Optional[Tuple[int, int]]:
    """
    Match template in screenshot and return center (x, y) in screenshot pixels.
    """
    res = cv2.matchTemplate(bgr, tmpl, cv2.TM_CCOEFF_NORMED)
    minVal, maxVal, minLoc, maxLoc = cv2.minMaxLoc(res)
    print(f"[LuckyLand] match score={maxVal:.3f}, threshold={thresh}")
    if maxVal >= thresh:
        th, tw = tmpl.shape[:2]
        return (maxLoc[0] + tw // 2, maxLoc[1] + th // 2)
    return None


def _screenshot_point_to_css(sb: SB, pt: Tuple[int, int], bgr: np.ndarray) -> Tuple[int, int]:
    """
    Convert screenshot pixel coords to CSS coords, accounting for DPR.
    """
    h, w = bgr.shape[:2]
    vw = sb.execute_script("return window.innerWidth || document.documentElement.clientWidth || document.body.clientWidth || 0;")
    vh = sb.execute_script("return window.innerHeight || document.documentElement.clientHeight || document.body.clientHeight || 0;")

    # Fallbacks
    vw = int(vw or 1920)
    vh = int(vh or 1080)

    scale_x = vw / (w / DPR)
    scale_y = vh / (h / DPR)

    css_x = int(pt[0] * scale_x)
    css_y = int(pt[1] * scale_y)

    print(f"[LuckyLand] point screenshot={pt}, screenshot_size=({w}x{h}), viewport=({vw}x{vh}), "
          f"DPR={DPR}, css=({css_x},{css_y})")

    return css_x, css_y


def _try_detect_and_click(sb: SB, tmpl: Optional[np.ndarray], thresh: float, label: str) -> bool:
    if tmpl is None:
        return False
    for _ in range(FIND_RETRIES):
        bgr = _grab_bgr(sb)
        pt = _match_center(bgr, tmpl, thresh)
        if pt:
            print(f"[DEBUG] Found {label} at {pt} — canvas-targeted click")
            css_x, css_y = _screenshot_point_to_css(sb, pt, bgr)
            _canvas_click(sb, css_x, css_y)
            return True
        time.sleep(FIND_DELAY)
    print(f"[DEBUG] Could not find {label}")
    return False


# -------------- threading + CDP integration --------------

EXECUTOR = ThreadPoolExecutor(max_workers=1)


def _send_text_sync(loop: asyncio.AbstractEventLoop, channel: discord.abc.Messageable, message: str) -> None:
    """Thread-safe helper to send a text message from the LuckyLand worker."""
    try:
        fut = asyncio.run_coroutine_threadsafe(channel.send(message), loop)
        fut.result()
    except Exception as e:
        print(f"[LuckyLand][WARN] Failed to send message: {e}")


def _send_shot_sync(loop: asyncio.AbstractEventLoop, channel: discord.abc.Messageable, caption: str, path: str) -> None:
    """Thread-safe helper to send a screenshot from the LuckyLand worker."""
    try:
        fut = asyncio.run_coroutine_threadsafe(_send_shot(channel, caption, path), loop)
        fut.result()
    except Exception as e:
        print(f"[LuckyLand][WARN] Failed to send screenshot: {e}")


def _luckyland_worker(loop: asyncio.AbstractEventLoop, channel: discord.abc.Messageable) -> None:
    """Runs the LuckyLand SeleniumBase UC+CDP flow in a background thread."""

    cookies_tmpl  = _load_template(COOKIES_IMG)          # optional
    prelogin_tmpl = _load_template(PRELOGIN_BTN_IMG)     # optional
    login_tmpl    = _load_template(LOGIN_BTN_IMG)        # required

    if login_tmpl is None:
        _send_text_sync(loop, channel, "[LuckyLand][ERROR] Missing luckylandloginbtn.png")
        return

    _send_text_sync(
        loop,
        channel,
        "Starting LuckyLand (UC + CDP canvas-click debug)…",
    )

    try:
        # UC Mode + CDP Mode
        with SB(uc=True, uc_cdp=True) as sb:
            sb.set_window_size(1920, 1080)
            sb.activate_cdp_mode(LOGIN_URL)
            sb.sleep(3.0)
            sb.wait_for_ready_state_complete()
            sb.scroll_to_top()

            # Wake the canvas once (center of viewport)
            _canvas_click(sb, 960, 540)

            # Cookies (non-fatal)
            if cookies_tmpl is not None:
                _try_detect_and_click(sb, cookies_tmpl, COOKIES_THRESH, "cookies")

            # Pre-login (non-fatal)
            if prelogin_tmpl is not None:
                _try_detect_and_click(sb, prelogin_tmpl, PRELOGIN_THRESH, "prelogin")

            # Screenshot BEFORE
            before_path = _save_debug(sb, "before_login_click")
            _send_shot_sync(loop, channel, "Before login button detection:", before_path)

            # Detect & click the purple "Log into Existing Account"
            clicked = _try_detect_and_click(sb, login_tmpl, LOGIN_THRESH, "login button")

            # Screenshot AFTER (5s later if clicked; otherwise show failure)
            if clicked:
                time.sleep(AFTER_CLICK_WAIT)
                after_path = _save_debug(sb, "after_login_click")
                _send_shot_sync(loop, channel, "After clicking login (5s later):", after_path)
            else:
                fail_path = _save_debug(sb, "login_not_found")
                _send_shot_sync(loop, channel, "[LuckyLand][ERROR] Could not find login button.", fail_path)

            _send_text_sync(
                loop,
                channel,
                "✅ Debug complete. If modal didn’t open, try tweaking `LUCKYLAND_DPR` (e.g., 1.25).",
            )

    except Exception as e:
        _send_text_sync(loop, channel, f"[LuckyLand][ERROR] Exception: {e}")


async def luckyland_uc(ctx, channel: discord.abc.Messageable):
    """LuckyLand entrypoint for Discord bot (runs SeleniumBase UC+CDP in a worker thread)."""
    if ":" not in LUCKYLAND_CRED:
        await channel.send("[LuckyLand][ERROR] Missing LUCKYLAND='email:password' in .env")
        return

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(EXECUTOR, _luckyland_worker, loop, channel)
