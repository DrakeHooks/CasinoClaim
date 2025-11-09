# Drake Hooks 
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
FIND_DELAY = 0.9  # seconds between attempts
POST_CLICK_PAUSE = 1.2  # wait after clicks
AFTER_LOGIN_WAIT = 3.0   # wait after pressing ENTER on login


# ───────────────────────────────────────────────────────────
# Utilities
# ───────────────────────────────────────────────────────────
def _img_search_paths(filename: str) -> List[str]:
    """Return plausible absolute paths for a given image name."""
    here = os.path.dirname(os.path.abspath(__file__))
    return [
        os.path.join(here, "images", filename),
        os.path.join(here, filename),
        os.path.join(os.getcwd(), "images", filename),
        os.path.join(os.getcwd(), filename),
    ]


def _load_template(filename: str) -> Optional[np.ndarray]:
    """Load an image as BGR from possible locations."""
    for p in _img_search_paths(filename):
        if os.path.exists(p):
            img = cv2.imread(p, cv2.IMREAD_COLOR)
            if img is not None:
                return img
    return None


def _cv_match_center(bgr_image: np.ndarray, bgr_template: np.ndarray, threshold: float) -> Optional[Tuple[int, int]]:
    """
    Return center (x, y) in CSS px if matchTemplate maxVal >= threshold.
    bgr_image: screenshot BGR
    bgr_template: template BGR
    """
    if bgr_image is None or bgr_template is None:
        return None
    ih, iw = bgr_image.shape[:2]
    th, tw = bgr_template.shape[:2]

    if ih < th or iw < tw:
        return None

    res = cv2.matchTemplate(bgr_image, bgr_template, cv2.TM_CCOEFF_NORMED)
    minVal, maxVal, minLoc, maxLoc = cv2.minMaxLoc(res)
    if maxVal >= threshold:
        x, y = maxLoc
        cx = x + tw // 2
        cy = y + th // 2
        return (int(cx), int(cy))
    return None


def _grab_viewport_png(sb: SB) -> bytes:
    """Return a PNG screenshot of the current viewport."""
    # SeleniumBase: get_screenshot_as_png returns bytes
    return sb.driver.get_screenshot_as_png()


def _png_to_bgr(png_bytes: bytes) -> np.ndarray:
    data = np.frombuffer(png_bytes, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    return img


def _viewport_click(sb: SB, x: int, y: int, delay_after: float = POST_CLICK_PAUSE) -> None:
    """
    Click at CSS-pixel coordinates (x, y) in the viewport via CDP.
    """
    # Dispatch mouse events at CSS px
    params_press = {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1}
    params_release = {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1}
    sb.driver.execute_cdp_cmd("Input.dispatchMouseEvent", params_press)
    sb.driver.execute_cdp_cmd("Input.dispatchMouseEvent", params_release)
    time.sleep(delay_after)


def _cdp_insert_text(sb: SB, text: str) -> None:
    """Type text into whichever element currently has focus (ideal for canvas UIs)."""
    sb.driver.execute_cdp_cmd("Input.insertText", {"text": text})


def _cdp_key(sb: SB, key: str) -> None:
    """
    Send key via CDP. key should be like 'Tab' or 'Enter'.
    """
    # keyDown
    sb.driver.execute_cdp_cmd("Input.dispatchKeyEvent", {"type": "keyDown", "key": key})
    # keyUp
    sb.driver.execute_cdp_cmd("Input.dispatchKeyEvent", {"type": "keyUp", "key": key})


def _try_match_and_click(sb: SB, template: np.ndarray, threshold: float, attempts: int, between: float) -> bool:
    """Repeatedly screenshot, match, and click the center if found."""
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
    """Send a screenshot to Discord from PNG bytes; cleans up a temp file."""
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix="luckyland_", suffix=".png")
        os.close(fd)
        with open(tmp, "wb") as f:
            f.write(png_bytes)
        await channel.send(caption, file=discord.File(tmp))
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


# ───────────────────────────────────────────────────────────
# Main Flow
# ───────────────────────────────────────────────────────────
async def luckyland_uc(ctx, channel: discord.abc.Messageable):
    """
    Canvas-first LuckyLand flow driven by OpenCV:
    1. Open site.
    2. Find & click login button (template image).
    3. Type username, TAB, type password, ENTER.
    4. Find & click "Collect" (template image).
    5. Send screenshot on success; otherwise send failure screenshot.
    """
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

    # SeleniumBase UC browser
    # Use your repo-wide UC defaults (profile, headless, etc) via env or SB kwargs if needed.
    sb: Optional[SB] = None
    try:
        sb = SB(uc=True)
        sb.uc_open(LOGIN_URL)
        sb.wait_for_ready_state_complete()

        # Ensure at top-left to stabilize matching
        sb.scroll_to_top()

        # 1) Click the Login button via CV
        clicked_login = _try_match_and_click(sb, login_tmpl, LOGIN_THRESH, attempts=FIND_RETRIES, between=FIND_DELAY)
        if not clicked_login:
            png = _grab_viewport_png(sb)
            await _send_screenshot(channel, "[LuckyLand][ERROR] Could not find login button.", png)
            return

        # Give modal a moment to animate in & focus the email field
        time.sleep(1.0)

        # 2) Type email → TAB → password → ENTER (CDP typing into focused field)
        try:
            _cdp_insert_text(sb, email)
            _cdp_key(sb, "Tab")
            _cdp_insert_text(sb, password)
            _cdp_key(sb, "Enter")
        except Exception:
            # Selenium fallback in case CDP fails
            try:
                active = sb.driver.switch_to.active_element
                active.send_keys(email)
                active.send_keys(Keys.TAB)
                active = sb.driver.switch_to.active_element
                active.send_keys(password)
                active.send_keys(Keys.ENTER)
            except Exception:
                png = _grab_viewport_png(sb)
                await _send_screenshot(channel, "[LuckyLand][ERROR] Unable to type credentials.", png)
                return

        # Wait for navigation / lobby draw
        time.sleep(AFTER_LOGIN_WAIT)
        sb.wait_for_ready_state_complete(timeout=12)

        # 3) Find & click Collect button
        collected = _try_match_and_click(sb, collect_tmpl, COLLECT_THRESH, attempts=FIND_RETRIES, between=FIND_DELAY)

        # Grab a final screenshot either way
        final_png = _grab_viewport_png(sb)

        if collected:
            await _send_screenshot(channel, "LuckyLand: Daily Bonus Claimed! ", final_png)
        else:
            await _send_screenshot(channel, "LuckyLand: Could not detect the Collect button.", final_png)

    except Exception as e:
        try:
            if sb:
                png = _grab_viewport_png(sb)
                await _send_screenshot(channel, f"[LuckyLand][ERROR] Exception: {e}", png)
            else:
                await channel.send(f"[LuckyLand][ERROR] Exception before browser launch: {e}")
        except Exception:
            await channel.send(f"[LuckyLand][ERROR] {e}")
    finally:
        try:
            if sb:
                sb.quit()
        except Exception:
            pass
