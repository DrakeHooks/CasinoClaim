# Drake Hooks + WaterTrooper
# Casino Claim 2
# LuckyLand API — cookies fix + canvas click with OpenCV bounding-box debug

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

# Default DPR fallback; we'll still try to read window.devicePixelRatio
DPR_DEFAULT = float(os.getenv("LUCKYLAND_DPR", "1.25"))

# Template images (place in ./images/ or repo root)
COOKIES_IMG       = "luckyland_cookies.png"       # optional
PRELOGIN_BTN_IMG  = "luckyland_loginbtn0.png"     # optional
LOGIN_BTN_IMG     = "luckylandloginbtn.png"       # REQUIRED

# Thresholds / timing
COOKIES_THRESH    = 0.80
PRELOGIN_THRESH   = 0.80
LOGIN_THRESH      = 0.75
FIND_RETRIES      = 10
FIND_DELAY        = 0.6
AFTER_CLICK_WAIT  = 5.0


# ────────────────────────────────────────────
# Image + screenshot helpers
# ────────────────────────────────────────────

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
            print(f"[LuckyLand] Loaded template {filename} from {p}")
            return cv2.imread(p, cv2.IMREAD_COLOR)
    print(f"[LuckyLand] Template {filename} not found in expected paths")
    return None


def _grab_bgr(sb: SB) -> np.ndarray:
    data = np.frombuffer(sb.driver.get_screenshot_as_png(), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _match_template(
    bgr: np.ndarray, tmpl: np.ndarray, thresh: float
) -> Optional[Tuple[Tuple[int, int], Tuple[int, int], float]]:
    """
    Returns (top_left, bottom_right, maxVal) if match >= thresh; otherwise None.
    Coordinates are in screenshot pixels.
    """
    res = cv2.matchTemplate(bgr, tmpl, cv2.TM_CCOEFF_NORMED)
    _, maxVal, _, maxLoc = cv2.minMaxLoc(res)
    print(f"[LuckyLand] Template match score: {maxVal:.3f} (thresh={thresh})")
    if maxVal >= thresh:
        th, tw = tmpl.shape[:2]
        top_left = maxLoc
        bottom_right = (maxLoc[0] + tw, maxLoc[1] + th)
        return top_left, bottom_right, maxVal
    return None


def _save_debug(sb: SB, name: str) -> str:
    path = f"/tmp/{name}.png"
    sb.save_screenshot(path)
    print(f"[DEBUG] Saved screenshot {path}")
    return path


async def _send_shot(channel, caption: str, path: str):
    if os.path.exists(path):
        await channel.send(caption, file=discord.File(path))
    else:
        await channel.send(f"{caption} (screenshot missing at {path})")


# ────────────────────────────────────────────
# DPR + canvas click helpers
# ────────────────────────────────────────────

def _get_dpr(sb: SB) -> float:
    try:
        dpr = sb.execute_script("return window.devicePixelRatio || 1;")
        dpr = float(dpr)
        print(f"[LuckyLand] window.devicePixelRatio = {dpr}")
        return dpr
    except Exception as e:
        print(f"[LuckyLand] Failed to read devicePixelRatio, using default {DPR_DEFAULT}: {e}")
        return DPR_DEFAULT


_JS_CANVAS_CLICK = r"""
(function(xCss, yCss){
  // Try to find the main game canvas
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


def _canvas_click(sb: SB, x_css: int, y_css: int, dpr: float) -> dict:
    """
    x_css / y_css are CSS pixel coords (clientX/clientY).
    dpr is used only for CDP "physical" mouse events.
    """
    dev_x = x_css * dpr
    dev_y = y_css * dpr

    # Move physical pointer for hover states
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

    # Canvas-targeted JS events
    result = {}
    try:
        result = sb.execute_script(_JS_CANVAS_CLICK, x_css, y_css) or {}
    except Exception as e:
        result = {"ok": False, "why": f"JS_ERR: {e}"}
    print(f"[DEBUG] Canvas click JS result: {result}")

    # Low-level press/release too
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


# ────────────────────────────────────────────
# Cookie banner helpers
# ────────────────────────────────────────────

def _click_by_text(sb: SB, texts: List[str]) -> bool:
    """
    Clicks the first button-like element whose text contains any of the
    given strings (case-insensitive).
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
        print(f"[LuckyLand] _click_by_text error: {e}")
        return False


def _close_luckyland_cookies(sb: SB, cookies_tmpl: Optional[np.ndarray], dpr: float) -> None:
    """
    Best-effort cookies closer tailored for LuckyLand:
      1) If the left "Do Not Sell My Personal Information" panel is open,
         prefer "Confirm my Choices" or "Accept All".
      2) Otherwise, click bottom bar "Accept Cookies".
      3) As a last resort, try the image template + canvas click.
    We intentionally avoid anything with "Cookie Settings".
    """
    print("[LuckyLand] Attempting to close cookies…")

    # 1) Panel-specific buttons
    if _click_by_text(sb, ["confirm my choices"]):
        print("[LuckyLand] Closed cookies via 'Confirm my Choices'")
        time.sleep(1.0)
        return

    if _click_by_text(sb, ["accept all"]):
        print("[LuckyLand] Closed cookies via 'Accept All'")
        time.sleep(1.0)
        return

    # 2) Bottom bar "Accept Cookies"
    if _click_by_text(sb, ["accept cookies"]):
        print("[LuckyLand] Closed cookies via bottom bar 'Accept Cookies'")
        time.sleep(1.0)
        return

    # 3) Template-based click (optional)
    if cookies_tmpl is not None:
        try:
            bgr = _grab_bgr(sb)
            match = _match_template(bgr, cookies_tmpl, COOKIES_THRESH)
            if match:
                top_left, bottom_right, _ = match
                cx = (top_left[0] + bottom_right[0]) // 2
                cy = (top_left[1] + bottom_right[1]) // 2

                css_x = int(cx / dpr)
                css_y = int(cy / dpr)

                # Draw bounding box debug
                dbg = bgr.copy()
                cv2.rectangle(dbg, top_left, bottom_right, (0, 255, 0), 3)
                cv2.circle(dbg, (cx, cy), 8, (0, 0, 255), -1)
                path = "/tmp/cookies_detect.png"
                cv2.imwrite(path, dbg)
                print("[LuckyLand] Cookies image template found; clicked via canvas.")
                _canvas_click(sb, css_x, css_y, dpr)
                time.sleep(1.0)
                return
        except Exception as e:
            print(f"[LuckyLand] Image-based cookies close failed: {e}")

    print("[LuckyLand] Could not positively close cookies banner (continuing anyway).")


# ────────────────────────────────────────────
# Template click with bounding-box debug
# ────────────────────────────────────────────

async def _click_template_with_overlay(
    sb: SB,
    tmpl: np.ndarray,
    thresh: float,
    label: str,
    channel: discord.abc.Messageable,
    dpr: float,
) -> bool:
    """
    Repeatedly tries to locate the template, draw a bounding box overlay,
    send that overlay to Discord, then click exactly at the detected center
    on the canvas. Also sends a screenshot immediately after the click.
    """
    for attempt in range(1, FIND_RETRIES + 1):
        print(f"[LuckyLand] {label}: template attempt {attempt}/{FIND_RETRIES}")
        bgr = _grab_bgr(sb)
        match = _match_template(bgr, tmpl, thresh)
        if match:
            top_left, bottom_right, score = match
            cx = (top_left[0] + bottom_right[0]) // 2
            cy = (top_left[1] + bottom_right[1]) // 2

            css_x = int(cx / dpr)
            css_y = int(cy / dpr)

            # Draw overlay showing what was detected
            dbg = bgr.copy()
            cv2.rectangle(dbg, top_left, bottom_right, (0, 255, 0), 3)
            cv2.circle(dbg, (cx, cy), 8, (0, 0, 255), -1)
            overlay_path = f"/tmp/{label}_detect_overlay.png"
            cv2.imwrite(overlay_path, dbg)
            print(f"[LuckyLand] {label}: detection overlay saved to {overlay_path}")

            await _send_shot(
                channel,
                f"[LuckyLand] {label}: template detected (score={score:.3f}). "
                f"Green box = match, red dot = click center.",
                overlay_path,
            )

            # Perform the canvas click where we detected the center
            print(f"[LuckyLand] {label}: clicking at CSS ({css_x}, {css_y})")
            _canvas_click(sb, css_x, css_y, dpr)

            # Screenshot immediately after click
            click_path = f"/tmp/{label}_after_click.png"
            sb.save_screenshot(click_path)
            print(f"[LuckyLand] {label}: post-click screenshot saved to {click_path}")
            await _send_shot(
                channel,
                f"[LuckyLand] {label}: screenshot immediately after click.",
                click_path,
            )

            return True

        time.sleep(FIND_DELAY)

    # Could not find template
    fail_path = _save_debug(sb, f"{label}_not_found")
    await _send_shot(
        channel,
        f"[LuckyLand][ERROR] {label}: template not found after {FIND_RETRIES} attempts.",
        fail_path,
    )
    return False


# ────────────────────────────────────────────
# Main entry
# ────────────────────────────────────────────

async def luckyland_uc(ctx, channel: discord.abc.Messageable):
    if ":" not in LUCKYLAND_CRED:
        await channel.send("[LuckyLand][ERROR] Missing LUCKYLAND='email:password' in .env")
        return

    cookies_tmpl  = _load_template(COOKIES_IMG)          # optional
    prelogin_tmpl = _load_template(PRELOGIN_BTN_IMG)     # optional
    login_tmpl    = _load_template(LOGIN_BTN_IMG)        # required

    if login_tmpl is None:
        await channel.send("[LuckyLand][ERROR] Missing luckylandloginbtn.png template.")
        return

    await channel.send("Starting LuckyLand (cookies fix + canvas debug)…")

    try:
        with SB(uc=True) as sb:
            sb.set_window_size(1920, 1080)
            sb.uc_open(LOGIN_URL)
            sb.wait_for_ready_state_complete()
            sb.scroll_to_top()

            dpr = _get_dpr(sb)

            # Wake canvas a bit (center of viewport)
            try:
                size = sb.get_window_size()
                cx = int(size["width"] / 2)
                cy = int(size["height"] / 2)
            except Exception:
                cx, cy = 960, 540
            print(f"[LuckyLand] Waking canvas at ({cx}, {cy}) CSS")
            _canvas_click(sb, cx, cy, dpr)

            # Close cookie stuff
            _close_luckyland_cookies(sb, cookies_tmpl, dpr)

            # Optional pre-login button via simple template (no overlay needed)
            if prelogin_tmpl is not None:
                try:
                    bgr = _grab_bgr(sb)
                    match = _match_template(bgr, prelogin_tmpl, PRELOGIN_THRESH)
                    if match:
                        top_left, bottom_right, _ = match
                        pcx = (top_left[0] + bottom_right[0]) // 2
                        pcy = (top_left[1] + bottom_right[1]) // 2
                        css_x = int(pcx / dpr)
                        css_y = int(pcy / dpr)
                        print(f"[LuckyLand] Prelogin button click at CSS ({css_x}, {css_y})")
                        _canvas_click(sb, css_x, css_y, dpr)
                        time.sleep(2.0)
                except Exception as e:
                    print(f"[LuckyLand] Prelogin template error: {e}")

            # Now do the main login button with overlay + click debug
            await channel.send("[LuckyLand] Searching for the purple 'Log into Existing Account' button…")
            clicked = await _click_template_with_overlay(
                sb,
                login_tmpl,
                LOGIN_THRESH,
                "luckyland_login",
                channel,
                dpr,
            )

            if clicked:
                # Give some time to transition after the earlier post-click shot
                time.sleep(AFTER_CLICK_WAIT)
                final_path = _save_debug(sb, "luckyland_final_state")
                await _send_shot(
                    channel,
                    "[LuckyLand] Final state after waiting for login transition:",
                    final_path,
                )
                await channel.send("✅ LuckyLand debug complete.")
            else:
                await channel.send("❌ LuckyLand: login button template never found.")

    except Exception as e:
        await channel.send(f"[LuckyLand][ERROR] Exception: {e}")
