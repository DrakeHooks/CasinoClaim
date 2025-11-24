# Drake Hooks + WaterTrooper
# Casino Claim 2
# LuckyLand API — cookies fix + canvas login button + canvas-based credential submit

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

# Template images (put these in ./images/ or repo root)
COOKIES_IMG       = "luckyland_cookies.png"       # optional
PRELOGIN_BTN_IMG  = "luckyland_loginbtn0.png"     # optional
LOGIN_BTN_IMG     = "luckylandloginbtn.png"       # REQUIRED (purple "Log into Existing Account" button)

# Thresholds / timing
COOKIES_THRESH    = 0.80
PRELOGIN_THRESH   = 0.80
LOGIN_THRESH      = 0.75
FIND_RETRIES      = 10
FIND_DELAY        = 0.6
AFTER_CLICK_WAIT  = 5.0


# ────────────────────────────────────────────
# File / image helpers
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
    print(f"[LuckyLand] Template {filename} not found")
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
    print(f"[LuckyLand] Template score={maxVal:.3f} (thresh={thresh})")
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


async def _send_shot(channel: discord.abc.Messageable, caption: str, path: str):
    if os.path.exists(path):
        await channel.send(caption, file=discord.File(path))
    else:
        await channel.send(f"{caption} (screenshot missing: {path})")


# ────────────────────────────────────────────
# JS click-at-point helper (works on canvas)
# ────────────────────────────────────────────

_JS_CLICK_AT_POINT = r"""
(function(xCss, yCss){
  const el = document.elementFromPoint(xCss, yCss);
  if (!el) return { ok:false, why:"NO_ELEMENT" };

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
    } catch (e) {
      try {
        el.dispatchEvent(new MouseEvent(type, base));
      } catch (e2) {
        // swallow
      }
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
  } catch (e) {
    return { ok:false, why:String(e), tag:el.tagName, id:el.id || null, className:el.className || null };
  }

  return {
    ok:true,
    tag: el.tagName,
    id: el.id || null,
    className: el.className || null
  };
})(arguments[0], arguments[1]);
"""


def _click_at_css_point(sb: SB, x_css: int, y_css: int) -> dict:
    """
    Clicks at given CSS pixel coords by dispatching events to
    document.elementFromPoint(x,y). Works even if it's a canvas.
    """
    try:
        result = sb.execute_script(_JS_CLICK_AT_POINT, int(x_css), int(y_css)) or {}
    except Exception as e:
        result = {"ok": False, "why": f"JS_ERR: {e}"}

    print(f"[DEBUG] Click-at-point result: {result}")
    return result


# ────────────────────────────────────────────
# Cookie helpers
# ────────────────────────────────────────────

def _click_by_text(sb: SB, texts: List[str]) -> bool:
    """
    Clicks first button-like element whose text contains any of the strings.
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


def _close_luckyland_cookies(sb: SB, cookies_tmpl: Optional[np.ndarray]) -> None:
    """
    Tries to dismiss LuckyLand's cookie UI:
      - "Confirm my Choices" (left panel)
      - "Accept All" (left panel)
      - "Accept Cookies" (bottom bar)
    Falls back to template-based click if provided.
    """
    print("[LuckyLand] Attempting to close cookies…")

    if _click_by_text(sb, ["confirm my choices"]):
        print("[LuckyLand] Closed cookies via 'Confirm my Choices'")
        time.sleep(1.0)
        return

    if _click_by_text(sb, ["accept all"]):
        print("[LuckyLand] Closed cookies via 'Accept All'")
        time.sleep(1.0)
        return

    if _click_by_text(sb, ["accept cookies"]):
        print("[LuckyLand] Closed cookies via 'Accept Cookies'")
        time.sleep(1.0)
        return

    # Optional: template-based click if you have a cookies button image
    if cookies_tmpl is not None:
        try:
            bgr = _grab_bgr(sb)
            match = _match_template(bgr, cookies_tmpl, COOKIES_THRESH)
            if match:
                top_left, bottom_right, _ = match
                cx = (top_left[0] + bottom_right[0]) // 2
                cy = (top_left[1] + bottom_right[1]) // 2

                h_img, w_img = bgr.shape[:2]
                vw = sb.execute_script(
                    "return window.innerWidth || document.documentElement.clientWidth || document.body.clientWidth || 0;"
                )
                vh = sb.execute_script(
                    "return window.innerHeight || document.documentElement.clientHeight || document.body.clientHeight || 0;"
                )
                scale_x = vw / w_img if w_img else 1
                scale_y = vh / h_img if h_img else 1
                css_x = int(cx * scale_x)
                css_y = int(cy * scale_y)

                print(f"[LuckyLand] Cookies tmpl click at CSS ({css_x},{css_y})")
                _click_at_css_point(sb, css_x, css_y)
                time.sleep(1.0)
                return
        except Exception as e:
            print(f"[LuckyLand] Cookies template click failed: {e}")

    print("[LuckyLand] Cookies banner may still be present; continuing anyway.")


# ────────────────────────────────────────────
# Template click with bounding-box overlay
# ────────────────────────────────────────────

async def _click_template_on_canvas(
    sb: SB,
    tmpl: np.ndarray,
    thresh: float,
    label: str,
    channel: discord.abc.Messageable,
) -> bool:
    """
    1. Uses OpenCV to find the template in a full screenshot.
    2. Draws a green rectangle + red dot at the detected center.
    3. Sends that overlay screenshot to Discord.
    4. Maps screenshot coordinates -> CSS coords using viewport size.
    5. Clicks via document.elementFromPoint(x,y).
    6. Takes another screenshot right after click and sends it.

    Returns True if click was attempted at a matched location.
    """
    for attempt in range(1, FIND_RETRIES + 1):
        print(f"[LuckyLand] {label}: template attempt {attempt}/{FIND_RETRIES}")
        bgr = _grab_bgr(sb)
        h_img, w_img = bgr.shape[:2]

        match = _match_template(bgr, tmpl, thresh)
        if not match:
            time.sleep(FIND_DELAY)
            continue

        top_left, bottom_right, score = match
        cx_img = (top_left[0] + bottom_right[0]) // 2
        cy_img = (top_left[1] + bottom_right[1]) // 2

        # Get viewport size in CSS pixels
        vw = sb.execute_script(
            "return window.innerWidth || document.documentElement.clientWidth || document.body.clientWidth || 0;"
        )
        vh = sb.execute_script(
            "return window.innerHeight || document.documentElement.clientHeight || document.body.clientHeight || 0;"
        )
        vw = float(vw or 1)
        vh = float(vh or 1)

        scale_x = vw / float(w_img or 1)
        scale_y = vh / float(h_img or 1)

        css_x = int(cx_img * scale_x)
        css_y = int(cy_img * scale_y)

        print(
            f"[LuckyLand] {label}: screenshot center=({cx_img},{cy_img}), "
            f"viewport=({vw}x{vh}), css=({css_x},{css_y}), score={score:.3f}"
        )

        # Create overlay: green rectangle + red dot where we think the button is
        dbg = bgr.copy()
        cv2.rectangle(dbg, top_left, bottom_right, (0, 255, 0), 3)
        cv2.circle(dbg, (cx_img, cy_img), 8, (0, 0, 255), -1)
        overlay_path = f"/tmp/{label}_detect_overlay.png"
        cv2.imwrite(overlay_path, dbg)
        print(f"[LuckyLand] {label}: overlay saved to {overlay_path}")

        await _send_shot(
            channel,
            f"[LuckyLand] {label}: detection overlay (green box = match, red dot = click center).",
            overlay_path,
        )

        # Click on that CSS point using JS
        _click_at_css_point(sb, css_x, css_y)

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

    # No match
    fail_path = _save_debug(sb, f"{label}_not_found")
    await _send_shot(
        channel,
        f"[LuckyLand][ERROR] {label}: template not found after {FIND_RETRIES} attempts.",
        fail_path,
    )
    return False


# ────────────────────────────────────────────
# Canvas-based typing for login popup
# ────────────────────────────────────────────

def _canvas_type_login(sb: SB, email: str, password: str) -> dict:
    """
    When the login popup is drawn on the canvas (no HTML inputs),
    we:
      1) Click the approximate center of the E-Mail field.
      2) Type the email via synthetic KeyboardEvents.
      3) Press Tab to jump to the Password field.
      4) Type the password.
      5) Press Enter to submit.

    Email/password field centers are expressed as fractions of viewport.
    Tuned for 1920x1080 but scaled dynamically.
    """
    # Fractions based on your screenshot (rough but centered)
    EMAIL_X_FRACTION = 0.50
    EMAIL_Y_FRACTION = 0.44
    # We only need Tab to reach password, so no direct click on password box.

    # Get viewport size in CSS pixels
    vw = float(
        sb.execute_script(
            "return window.innerWidth || document.documentElement.clientWidth || document.body.clientWidth || 0;"
        ) or 0
    )
    vh = float(
        sb.execute_script(
            "return window.innerHeight || document.documentElement.clientHeight || document.body.clientHeight || 0;"
        ) or 0
    )

    if vw <= 0 or vh <= 0:
        return {"mode": "canvas", "error": "bad_viewport", "vw": vw, "vh": vh}

    email_x = int(vw * EMAIL_X_FRACTION)
    email_y = int(vh * EMAIL_Y_FRACTION)

    print(f"[LuckyLand] Canvas login: clicking email at CSS ({email_x},{email_y})")
    _click_at_css_point(sb, email_x, email_y)
    time.sleep(0.5)

    # JS helpers to type text and press a single key (Tab/Enter)
    js_type = r"""
      (function(text){
        const target = document.activeElement || document.body;
        for (let i = 0; i < text.length; i++) {
          const ch = text[i];
          const code = ch;
          const keyCode = ch.charCodeAt(0);
          const evtInit = {
            key: ch,
            code: code,
            keyCode: keyCode,
            which: keyCode,
            bubbles: true,
            cancelable: true
          };
          try {
            target.dispatchEvent(new KeyboardEvent('keydown',  evtInit));
            target.dispatchEvent(new KeyboardEvent('keyup',    evtInit));
          } catch (e) {}
        }
      })(arguments[0]);
    """

    js_key = r"""
      (function(key){
        const target = document.activeElement || document.body;
        let keyCode = 0;
        if (key === 'Tab')   keyCode = 9;
        if (key === 'Enter') keyCode = 13;
        const evtInit = {
          key: key,
          code: key,
          keyCode: keyCode,
          which: keyCode,
          bubbles: true,
          cancelable: true
        };
        try {
          target.dispatchEvent(new KeyboardEvent('keydown', evtInit));
          target.dispatchEvent(new KeyboardEvent('keyup',   evtInit));
        } catch (e) {}
      })(arguments[0]);
    """

    # Type email
    print("[LuckyLand] Canvas login: typing email…")
    sb.execute_script(js_type, email)
    time.sleep(0.4)

    # Tab to password field
    print("[LuckyLand] Canvas login: sending Tab to reach password field…")
    sb.execute_script(js_key, "Tab")
    time.sleep(0.4)

    # Type password
    print("[LuckyLand] Canvas login: typing password…")
    sb.execute_script(js_type, password)
    time.sleep(0.4)

    # Press Enter to submit
    print("[LuckyLand] Canvas login: sending Enter to submit…")
    sb.execute_script(js_key, "Enter")

    return {
        "mode": "canvas",
        "vw": vw,
        "vh": vh,
        "email_x": email_x,
        "email_y": email_y,
    }


# ────────────────────────────────────────────
# Login popup: fill creds + submit
# ────────────────────────────────────────────

def _fill_login_and_submit(sb: SB, email: str, password: str) -> dict:
    """
    First tries to find real HTML <input> elements for E-Mail / Password.
    If none are found (canvas-only UI), falls back to _canvas_type_login().
    """
    js = r"""
      return (function(emailVal, passVal){
        const lower = s => (s || "").toLowerCase();
        const inputs = Array.from(document.querySelectorAll('input'));
        let emailEl = null;
        let passEl  = null;

        for (const el of inputs) {
          const type = lower(el.type);
          const name = lower(el.name);
          const ph   = lower(el.placeholder);

          if (!emailEl && (type === 'email' || name.includes('email') || ph.includes('mail'))) {
            emailEl = el;
          }
          if (!passEl && (type === 'password' || name.includes('pass') || ph.includes('pass'))) {
            passEl = el;
          }
        }

        if (!emailEl && !passEl) {
          return {
            hasEmail: false,
            hasPass : false,
            emailType: null,
            passType : null
          };
        }

        if (emailEl) {
          emailEl.focus();
          emailEl.value = emailVal;
          emailEl.dispatchEvent(new Event('input', {bubbles:true}));
          emailEl.dispatchEvent(new Event('change', {bubbles:true}));
        }

        if (passEl) {
          passEl.focus();
          passEl.value = passVal;
          passEl.dispatchEvent(new Event('input', {bubbles:true}));
          passEl.dispatchEvent(new Event('change', {bubbles:true}));
        }

        // Try to submit via form
        if (passEl && passEl.form) {
          try {
            passEl.form.dispatchEvent(new Event('submit', {bubbles:true, cancelable:true}));
          } catch (e) {}
          try {
            passEl.form.submit();
          } catch (e2) {}
        }

        // Also simulate Enter key on password field
        if (passEl) {
          const evtInit = {
            key: 'Enter',
            code: 'Enter',
            keyCode: 13,
            which: 13,
            bubbles: true,
            cancelable: true
          };
          try {
            passEl.dispatchEvent(new KeyboardEvent('keydown', evtInit));
            passEl.dispatchEvent(new KeyboardEvent('keyup',   evtInit));
          } catch (e) {}
        }

        return {
          hasEmail: !!emailEl,
          hasPass : !!passEl,
          emailType: emailEl ? emailEl.type : null,
          passType : passEl ? passEl.type : null,
          mode: 'html'
        };
      })(arguments[0], arguments[1]);
    """
    try:
        result = sb.execute_script(js, email, password) or {}
    except Exception as e:
        result = {"error": str(e), "mode": "html_js_error"}

    # If no HTML inputs, fall back to canvas typing
    if not result.get("hasEmail") and not result.get("hasPass"):
        print("[LuckyLand] No HTML inputs detected; switching to canvas typing mode.")
        canvas_result = _canvas_type_login(sb, email, password)
        # merge / annotate
        out = {"mode": "canvas"}
        out.update(canvas_result)
        return out

    print(f"[LuckyLand] _fill_login_and_submit HTML result: {result}")
    return result


# ────────────────────────────────────────────
# Main entry
# ────────────────────────────────────────────

async def luckyland_uc(ctx, channel: discord.abc.Messageable):
    """
    LuckyLand flow:
      1. Open LuckyLand.
      2. Close cookies if present.
      3. (Optional) Click any pre-login image/button.
      4. Click purple 'Log into Existing Account' button on canvas.
      5. When login popup appears, fill creds from .env and submit
         (HTML inputs if present; otherwise canvas typing).
      6. Screenshot a few seconds after submitting.
    """
    if ":" not in LUCKYLAND_CRED:
        await channel.send("[LuckyLand][ERROR] LUCKYLAND env var must be 'email:password'")
        return

    email, password = LUCKYLAND_CRED.split(":", 1)

    login_tmpl = _load_template(LOGIN_BTN_IMG)
    cookies_tmpl = _load_template(COOKIES_IMG)        # optional
    prelogin_tmpl = _load_template(PRELOGIN_BTN_IMG)  # optional

    if login_tmpl is None:
        await channel.send("[LuckyLand][ERROR] Missing luckylandloginbtn.png template.")
        return

    await channel.send("Starting LuckyLand (canvas login + credential submit)…")

    try:
        with SB(uc=True) as sb:
            sb.set_window_size(1920, 1080)
            sb.uc_open(LOGIN_URL)
            sb.wait_for_ready_state_complete()
            sb.scroll_to_top()

            # Handle cookies so we can actually see the game
            _close_luckyland_cookies(sb, cookies_tmpl)

            # Optional: pre-login click if you still need it
            if prelogin_tmpl is not None:
                try:
                    await _click_template_on_canvas(
                        sb,
                        prelogin_tmpl,
                        PRELOGIN_THRESH,
                        "luckyland_prelogin",
                        channel,
                    )
                    time.sleep(3.0)
                except Exception as e:
                    print(f"[LuckyLand] Prelogin template click error: {e}")

            # Click the purple "Log into Existing Account" canvas button
            await channel.send(
                "[LuckyLand] Looking for the purple 'Log into Existing Account' button…"
            )
            clicked = await _click_template_on_canvas(
                sb,
                login_tmpl,
                LOGIN_THRESH,
                "luckyland_login",
                channel,
            )

            if not clicked:
                await channel.send("❌ LuckyLand: login button template never found.")
                return

            # We should now be on the login popup you screenshotted.
            await channel.send("[LuckyLand] Detected login popup — filling credentials from .env…")
            fill_result = _fill_login_and_submit(sb, email, password)
            await channel.send(f"[LuckyLand] Login fields located / mode: {fill_result}")

            # Wait a few seconds for the login request + transition
            time.sleep(AFTER_CLICK_WAIT)
            final_path = _save_debug(sb, "luckyland_after_login_submit")
            await _send_shot(
                channel,
                "[LuckyLand] State a few seconds after submitting login:",
                final_path,
            )
            await channel.send("✅ LuckyLand: login flow (canvas click + credential submit) complete.")

    except Exception as e:
        await channel.send(f"[LuckyLand][ERROR] Exception: {e}")
