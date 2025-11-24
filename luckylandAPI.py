# Drake Hooks + WaterTrooper
# Casino Claim 2
# LuckyLand API — canvas-targeted pointer click (with debug screenshots, improved cookies + canvas coords)

import os
import time
from typing import Optional, Tuple, List

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

# Template images (put in ./images/ or repo root)
COOKIES_IMG       = "luckyland_cookies.png"      # optional
PRELOGIN_BTN_IMG  = "luckyland_loginbtn0.png"    # optional first button
LOGIN_BTN_IMG     = "luckylandloginbtn.png"      # purple "Log into Existing Account"

# Thresholds / timing
COOKIES_THRESH    = 0.80
PRELOGIN_THRESH   = 0.80
LOGIN_THRESH      = 0.75
FIND_RETRIES      = 10
FIND_DELAY        = 0.6
AFTER_CLICK_WAIT  = 5.0


# -------------- image helpers --------------
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


def _match_center(bgr: np.ndarray, tmpl: np.ndarray, thresh: float) -> Optional[Tuple[int, int]]:
    res = cv2.matchTemplate(bgr, tmpl, cv2.TM_CCOEFF_NORMED)
    _, maxVal, _, maxLoc = cv2.minMaxLoc(res)
    if maxVal >= thresh:
        th, tw = tmpl.shape[:2]
        return (maxLoc[0] + tw // 2, maxLoc[1] + th // 2)
    return None


# -------------- screenshots --------------
def _save_debug(sb: SB, name: str) -> str:
    path = f"/tmp/{name}.png"
    sb.save_screenshot(path)
    print(f"[DEBUG] Saved {path}")
    return path


async def _send_shot(channel, caption: str, path: str):
    if os.path.exists(path):
        await channel.send(caption, file=discord.File(path))


# -------------- canvas-targeted click --------------
_JS_CANVAS_CLICK = r"""
(function(xCss, yCss){
  // Find the canvas element; be robust to class/name variations.
  const canvas =
    document.querySelector('#lis-main-canvas') ||
    document.querySelector('canvas[id*="lis-main-canvas"]') ||
    document.querySelector('canvas') ||
    document.elementFromPoint(xCss, yCss);

  if (!canvas) return { ok:false, why:"NO_CANVAS" };

  const r = canvas.getBoundingClientRect();
  const cx = xCss;
  const cy = yCss;

  const Ev = (window.PointerEvent || window.MouseEvent);

  const ev = (type, extra={}) =>
    canvas.dispatchEvent(new Ev(
      type,
      Object.assign({
        bubbles:true,
        cancelable:true,
        view:window,
        clientX: cx,
        clientY: cy,
        pointerType:'mouse',
        pointerId:1,
        button: 0,
        buttons: (type === 'mousedown' || type === 'pointerdown') ? 1 : 0
      }, extra)
    ));

  try {
    ev('pointermove');
    ev('mousemove');
    ev('pointerdown');
    ev('mousedown');
    ev('mouseup');
    ev('pointerup');
    ev('click');
  } catch (e) {
    return { ok:false, why:String(e) };
  }

  return {
    ok:true,
    canvasRect:[r.left|0,r.top|0,r.width|0,r.height|0],
    element: canvas.tagName + (canvas.id ? '#'+canvas.id : '')
  };
})(arguments[0], arguments[1]);
"""


def _canvas_click(sb: SB, x_css: int, y_css: int) -> dict:
    """
    x_css / y_css are in CSS pixels (what JS sees as clientX/Y).

    We use DPR only for the low-level CDP calls; JS gets raw CSS coords.
    """
    dev_x = x_css * DPR
    dev_y = y_css * DPR

    # Move the "system" pointer (helps hover states)
    try:
        sb.driver.execute_cdp_cmd(
            "Input.dispatchMouseEvent",
            {
                "type": "mouseMoved",
                "x": dev_x,
                "y": dev_y,
                "buttons": 0,
                "pointerType": "mouse",
            },
        )
    except Exception as e:
        print(f"[DEBUG] CDP mouseMoved error: {e}")

    # Fire canvas-targeted DOM events
    result = {}
    try:
        result = sb.execute_script(_JS_CANVAS_CLICK, x_css, y_css) or {}
    except Exception as e:
        result = {"ok": False, "why": f"JS_ERR: {e}"}
    print(f"[DEBUG] Canvas click result: {result}")

    # Low-level press/release for good measure
    try:
        sb.driver.execute_cdp_cmd(
            "Input.dispatchMouseEvent",
            {
                "type": "mousePressed",
                "x": dev_x,
                "y": dev_y,
                "button": "left",
                "clickCount": 1,
                "buttons": 1,
                "pointerType": "mouse",
            },
        )
        sb.driver.execute_cdp_cmd(
            "Input.dispatchMouseEvent",
            {
                "type": "mouseReleased",
                "x": dev_x,
                "y": dev_y,
                "button": "left",
                "clickCount": 1,
                "buttons": 0,
                "pointerType": "mouse",
            },
        )
    except Exception as e:
        print(f"[DEBUG] CDP press/release error: {e}")

    return result


def _try_detect_and_click(sb: SB, tmpl: Optional[np.ndarray], thresh: float, label: str) -> bool:
    """
    Template-match on the full screenshot, then convert template center
    from screenshot pixels -> CSS pixels using DPR, then canvas-click there.
    """
    if tmpl is None:
        return False

    for _ in range(FIND_RETRIES):
        bgr = _grab_bgr(sb)
        pt = _match_center(bgr, tmpl, thresh)
        if pt:
            # pt is in screenshot pixels; map to CSS pixels using DPR
            css_x = int(pt[0] / DPR)
            css_y = int(pt[1] / DPR)
            print(f"[DEBUG] Found {label} at screenshot={pt}, css=({css_x},{css_y}) — canvas-targeted click")
            _canvas_click(sb, css_x, css_y)
            return True
        time.sleep(FIND_DELAY)

    print(f"[DEBUG] Could not find {label}")
    return False


# -------------- helpers for DOM / cookies --------------

def _click_by_text(sb: SB, texts: List[str]) -> bool:
    """
    JS helper that clicks the first button-like element whose
    inner text contains one of the given strings (case-insensitive).
    Good for cookie banners that change structure but keep similar text.
    """
    js = r"""
      const needles = arguments[0].map(t => t.toLowerCase());
      const lower = s => (s || "").toLowerCase().trim();
      const candidates = Array.from(
        document.querySelectorAll('button, [role="button"], .btn, .button')
      );
      for (const el of candidates) {
        const txt = lower(el.innerText || el.textContent || '');
        if (!txt) continue;
        for (const n of needles) {
          if (txt.includes(n)) {
            el.click();
            return true;
          }
        }
      }
      return false;
    """
    try:
        return bool(sb.execute_script(js, texts))
    except Exception as e:
        print(f"[DEBUG] _click_by_text error: {e}")
        return False


def _close_cookies(sb: SB, cookies_tmpl: Optional[np.ndarray]) -> None:
    """
    Best-effort cookies closer:
      1) Try clicking by text (Accept, Agree, etc.)
      2) Try some generic selectors
      3) Fall back to image template (OpenCV)
    """
    print("[DEBUG] Attempting to close cookies banner…")

    # 1) Text-based click
    if _click_by_text(sb, ["accept", "agree", "ok", "got it", "continue", "yes, i agree"]):
        print("[DEBUG] Closed cookies via text search")
        return

    # 2) Common consent selectors
    selectors = [
        "#onetrust-accept-btn-handler",
        "button#onetrust-accept-btn-handler",
        "button[class*='accept']",
        "button[class*='Accept']",
        "button[data-testid*='accept']",
        "button[data-testid*='consent']",
    ]
    for sel in selectors:
        try:
            # click_if_visible won't explode if it's not there
            sb.click_if_visible(sel, timeout=2)
            print(f"[DEBUG] Closed cookies via selector {sel}")
            return
        except Exception:
            continue

    # 3) Image-based click (canvas-style) if we have a template
    if cookies_tmpl is not None:
        clicked = _try_detect_and_click(sb, cookies_tmpl, COOKIES_THRESH, "cookies")
        if clicked:
            print("[DEBUG] Closed cookies via image template")
        else:
            print("[DEBUG] Could not close cookies (image template)")
    else:
        print("[DEBUG] No cookies template provided; skipping image-based close")


# -------------- main --------------
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

    await channel.send("Starting LuckyLand (canvas-click debug)…")

    try:
        with SB(uc=True) as sb:
            sb.set_window_size(1920, 1080)
            sb.uc_open(LOGIN_URL)
            sb.wait_for_ready_state_complete()
            sb.scroll_to_top()

            # Wake the canvas once (center of viewport in CSS pixels)  # UPDATED
            try:
                size = sb.get_window_size()
                cx = int(size["width"] / 2)
                cy = int(size["height"] / 2)
            except Exception:
                cx, cy = 960, 540
            _canvas_click(sb, cx, cy)

            # Cookies (non-fatal)  # UPDATED
            _close_cookies(sb, cookies_tmpl)

            # Pre-login button (non-fatal, image-based, still canvas)  # unchanged logic, fixed coords
            if prelogin_tmpl is not None:
                _try_detect_and_click(sb, prelogin_tmpl, PRELOGIN_THRESH, "prelogin")

            # Screenshot BEFORE
            before_path = _save_debug(sb, "before_login_click")
            await _send_shot(channel, "Before login button detection:", before_path)

            # Detect & click the purple "Log into Existing Account"
            clicked = _try_detect_and_click(sb, login_tmpl, LOGIN_THRESH, "login button")

            # Screenshot AFTER (5s later if clicked; otherwise show failure)
            if clicked:
                time.sleep(AFTER_CLICK_WAIT)
                after_path = _save_debug(sb, "after_login_click")
                await _send_shot(channel, "After clicking login (5s later):", after_path)
            else:
                fail_path = _save_debug(sb, "login_not_found")
                await _send_shot(channel, "[LuckyLand][ERROR] Could not find login button.", fail_path)

            await channel.send(
                "✅ LuckyLand debug complete. "
                "If the canvas clicks still look off, try adjusting `LUCKYLAND_DPR` (e.g., 1.0, 1.25, 1.5)."
            )

    except Exception as e:
        await channel.send(f"[LuckyLand][ERROR] Exception: {e}")
