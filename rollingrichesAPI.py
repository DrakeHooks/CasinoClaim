# Drake Hooks + WaterTrooper
# Casino Claim 2
# Rolling Riches API
# Update: never stop early; attempt claim even if confirm miss; robust countdown probe
# NEW (11/08): Hardened Daily Bonus opener that *always* drills into the claim panel

import os
import re
import time
import asyncio
import tempfile
import traceback
import discord
from dotenv import load_dotenv

# ───────────────────────────────────────────────────────────
# ── PyAutoGUI / OpenCV ──────────────────────────────────────
# ───────────────────────────────────────────────────────────

import pyautogui
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

import cv2
import numpy as np

# ───────────────────────────────────────────────────────────
# ── Selenium ───────────────────────────────────────────────
# ───────────────────────────────────────────────────────────

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
)

load_dotenv()

# ───────────────────────────────────────────────────────────
# Config and Constants
# ───────────────────────────────────────────────────────────
LOGIN_URL = "https://rollingriches.com/login"
LOBBY_URL = "https://rollingriches.com/"

HEADER_RICHES_BTN = "/html/body/app-root/app-main-header/div/div/div/div/header/div[1]/nav/div[2]/div/div[2]/nav/div/div[2]/button"
POPUP_CLOSE_XPATH = "/html/body/div[2]/div/div[2]/div/div/a"

# Several candidate hooks to open the Daily Bonus panel
XPATH_DAILY_BONUS_CANDIDATES = [
    # Sidebar item with icon + label
    "//div[contains(@class,'menu-item-content')][.//div[contains(@class,'menu-title') and normalize-space()='Daily Bonus']]",
    # Any clickable element whose text contains Daily Bonus
    "//*[self::button or self::a or self::div][contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'daily bonus')]",
    # Sometimes entries are rendered as <li> items
    "//li[.//*[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'daily bonus')]]",
]

# When the Daily Bonus panel is open, one of these should be present
XPATH_PANEL_READY = (
    "//div[contains(.,'Available in') or "
    ".//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'claim')]]"
)

# Primary claim button (DOM first)
XPATH_CLAIM_BTN = (
    "//button[(contains(@class,'btn') and contains(@class,'red')) or "
    "contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'claim')]"
)

COUNTDOWN_XPATH = "/html/body/div/div[3]/div/div[1]/div[3]/div[3]/div[1]/div/div[3]/div/div/div[2]"

DAILY_BONUS_ICON     = os.environ.get("DAILY_BONUS_ICON",     "daily_bonus_icon.png")
RR_CLAIM_TEMPLATE    = os.environ.get("RR_CLAIM_TEMPLATE",    "rr_claim_btn.png")
RR_FINAL_TEMPLATE    = os.environ.get("RR_FINAL_TEMPLATE",    "rr_final_claim.png")
TEMPLATE_THRESHOLD   = float(os.environ.get("DAILY_BONUS_THRESHOLD", "0.85"))

# NEW: Popup templates + thresholds
RR_POPUP_TEMPLATE      = os.environ.get("RR_POPUP_TEMPLATE",      "rr_popup1.png")
RR_POPUPCLOSE_TEMPLATE = os.environ.get("RR_POPUPCLOSE_TEMPLATE", "rr_popup1close.png")
POPUP_DETECT_THRESHOLD = float(os.environ.get("POPUP_DETECT_THRESHOLD", "0.80"))
POPUP_CLOSE_THRESHOLD  = float(os.environ.get("POPUP_CLOSE_THRESHOLD",  "0.80"))

# ───────────────────────────────────────────────────────────
# ── Print-only helpers ─────────────────────────────────────
# ───────────────────────────────────────────────────────────
async def _log(msg: str):
    print(msg, flush=True)

async def _driver_shot(driver, caption=""):
    try:
        fd, path = tempfile.mkstemp(prefix="rr_driver_", suffix=".png", dir="/tmp")
        os.close(fd)
        driver.save_screenshot(path)
        await _log(f"{caption or '📸 Selenium'} saved: {path}\nURL: {driver.current_url}")
        return path
    except Exception as e:
        await _log(f"⚠️ _driver_shot error: {e}")
        return ""

async def _pyauto_shot(caption=""):
    try:
        fd, path = tempfile.mkstemp(prefix="rr_pyauto_", suffix=".png", dir="/tmp")
        os.close(fd)
        pyautogui.screenshot(path)
        await _log(f"{caption or '🖥️ Screen'} saved: {path}")
        return path
    except Exception as e:
        await _log(f"⚠️ _pyauto_shot error: {e}")
        return ""

async def _send_one_shot(channel: discord.abc.Messageable, text: str, image_path: str):
    """Send one Discord message with an attached screenshot, then clean up."""
    if not image_path or not os.path.exists(image_path):
        await channel.send(text)
        return
    try:
        await channel.send(text, file=discord.File(image_path))
    finally:
        try:
            os.remove(image_path)
        except Exception:
            pass

def _ensure_viewport(driver):
    try:
        driver.set_window_position(0, 0)
        driver.set_window_size(1920, 1080)
    except Exception:
        pass
    try:
        driver.execute_cdp_cmd(
            "Emulation.setDeviceMetricsOverride",
            {"width": 1920, "height": 1080, "deviceScaleFactor": 1, "mobile": False},
        )
    except Exception:
        pass

# ───────────────────────────────────────────────────────────
# Dynamic popup closer (DOM; silent background)
# ───────────────────────────────────────────────────────────
async def _popup_closer_task(driver, stop_event: asyncio.Event,
                             xpath: str = POPUP_CLOSE_XPATH,
                             interval: float = 0.6):
    """
    Background task: every `interval` seconds, if the popup close button is present/visible,
    click it via JS (fallback to .click()). Quietly ignores errors.
    """
    while not stop_event.is_set():
        try:
            buttons = driver.find_elements(By.XPATH, xpath)
            for btn in buttons:
                try:
                    if btn.is_displayed():
                        try:
                            driver.execute_script("arguments[0].click();", btn)
                        except Exception:
                            try:
                                btn.click()
                            except Exception:
                                pass
                        await asyncio.sleep(0.15)
                        break
                except (StaleElementReferenceException, ElementClickInterceptedException, NoSuchElementException):
                    continue
        except Exception:
            pass
        await asyncio.sleep(interval)

async def _close_popup(driver):
    """One-shot attempt (kept from your original) to close the specific popup."""
    try:
        btn = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((By.XPATH, POPUP_CLOSE_XPATH)))
        driver.execute_script("arguments[0].click();", btn)
        await asyncio.sleep(0.2)
        await _log("🧹 Popup closed (if present).")
    except Exception:
        pass

# ───────────────────────────────────────────────────────────
# ── OpenCV helpers ─────────────────────────────────────────
# ───────────────────────────────────────────────────────────
def _screenshot_bgr() -> np.ndarray:
    im = pyautogui.screenshot()
    arr = np.array(im)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

def _draw_box(img_bgr: np.ndarray, top_left: tuple, w: int, h: int, text: str = "") -> np.ndarray:
    out = img_bgr.copy()
    cv2.rectangle(out, top_left, (top_left[0] + w, top_left[1] + h), (0, 255, 0), 2)
    if text:
        cv2.putText(out, text, (top_left[0], max(0, top_left[1]-6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0,255,0), 2, cv2.LINE_AA)
    return out

def _save_debug(img_bgr: np.ndarray, prefix: str = "cv_debug") -> str:
    fd, path = tempfile.mkstemp(prefix=f"{prefix}_", suffix=".png", dir="/tmp")
    os.close(fd)
    cv2.imwrite(path, img_bgr)
    return path

def _match_template_multiscale(screen_bgr: np.ndarray, templ_bgr: np.ndarray,
                               method=cv2.TM_CCOEFF_NORMED,
                               scales=None):
    if scales is None:
        scales = [0.75, 0.8, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.2]
    screen_gray = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)
    templ_gray0 = cv2.cvtColor(templ_bgr, cv2.COLOR_BGR2GRAY)

    best_score, best_rect, best_scale = -1.0, None, None
    for s in scales:
        if s == 1.0:
            tmpl = templ_gray0
        else:
            new_w = max(6, int(templ_bgr.shape[1]*s))
            new_h = max(6, int(templ_bgr.shape[0]*s))
            tmpl = cv2.resize(templ_gray0, (new_w, new_h), interpolation=cv2.INTER_AREA)
        h, w = tmpl.shape[:2]
        if h < 6 or w < 6:
            continue
        res = cv2.matchTemplate(screen_gray, tmpl, method)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val > best_score:
            best_score = max_val
            best_rect = (max_loc[0], max_loc[1], w, h)
            best_scale = s
    return best_score, best_rect, best_scale

def click_daily_bonus_by_template(template_path: str,
                                  threshold: float = 0.85,
                                  extra_offsets=None,
                                  move_duration: float = 0.25):
    """Generic template clicker (daily bonus icon, rr_claim_btn, rr_final_claim)."""
    if not os.path.exists(template_path):
        return False, -1.0, ""

    templ_bgr = cv2.imread(template_path, cv2.IMREAD_COLOR)
    if templ_bgr is None:
        return False, -1.0, ""

    screen_bgr = _screenshot_bgr()
    score, rect, scale = _match_template_multiscale(screen_bgr, templ_bgr)

    dbg_path = ""
    if rect:
        tl = (rect[0], rect[1])
        dbg_img = _draw_box(screen_bgr, tl, rect[2], rect[3], f"{score:.3f}@{scale:.2f}")
        dbg_path = _save_debug(dbg_img, "daily_bonus_match")

    if rect and score >= threshold:
        x, y, w, h = rect
        cx, cy = x + w//2, y + h//2
        pyautogui.moveTo(cx, cy, duration=move_duration)
        pyautogui.click()
        time.sleep(0.2)
        if extra_offsets:
            for dx, dy in extra_offsets:
                pyautogui.moveTo(cx+dx, cy+dy, duration=0.15)
                pyautogui.click()
                time.sleep(0.12)
        return True, score, dbg_path

    return False, score, dbg_path

def _click_template_with_retries(template_path: str, tries: int = 3, delay: float = 0.8, threshold: float | None = None):
    """Retry a template click a few times (UI can animate)."""
    last_dbg = ""
    last_conf = -1.0
    thr = TEMPLATE_THRESHOLD if threshold is None else threshold
    for _ in range(max(1, tries)):
        ok, conf, dbg = click_daily_bonus_by_template(template_path, threshold=thr)
        if dbg:
            last_dbg = dbg
        last_conf = conf
        if ok:
            return True, last_conf, last_dbg
        time.sleep(delay)
    return False, last_conf, last_dbg

# ───────────────────────────────────────────────────────────
# NEW — OpenCV popup detect & close with refresh fallback
# ───────────────────────────────────────────────────────────
async def _close_rr_popup_via_cv(driver,
                                 popup_tmpl: str = RR_POPUP_TEMPLATE,
                                 close_tmpl: str = RR_POPUPCLOSE_TEMPLATE,
                                 detect_thr: float = POPUP_DETECT_THRESHOLD,
                                 close_thr: float = POPUP_CLOSE_THRESHOLD,
                                 tries: int = 3) -> bool:
    """
    Detects the 'Your riches' popup by matching rr_popup1.png and then
    clicks the close control via rr_popup1close.png. If it cannot close
    after `tries`, returns False so caller can refresh() as fallback.

    Returns True if we believe the popup was closed; False otherwise.
    """
    if not os.path.exists(popup_tmpl) or not os.path.exists(close_tmpl):
        # If assets are missing, don't block the flow.
        await _log("ℹ️ RR popup templates missing; skipping CV close.")
        return False

    # First confirm popup exists.
    scr = _screenshot_bgr()
    pop_bgr = cv2.imread(popup_tmpl, cv2.IMREAD_COLOR)
    if pop_bgr is None:
        return False
    pop_score, pop_rect, pop_scale = _match_template_multiscale(scr, pop_bgr)
    if not pop_rect or pop_score < detect_thr:
        # No popup – totally fine.
        await _log(f"ℹ️ CV popup not detected (score={pop_score:.3f}).")
        return False

    # Try to click the close control a few times.
    for i in range(tries):
        ok, conf, dbg = _click_template_with_retries(close_tmpl, tries=1, delay=0.3, threshold=close_thr)
        if dbg:
            await _log(f"🧪 RR popup close match (try {i+1}/{tries}) conf={conf:.3f}, debug={dbg}")
        if ok:
            await asyncio.sleep(0.5)
            await _log("✅ RR popup closed via OpenCV.")
            return True
        time.sleep(0.3)

    await _log("⚠️ RR popup CV close failed after retries.")
    return False

# ───────────────────────────────────────────────────────────
# ── Countdown helpers ──────────────────────────────────────
# ───────────────────────────────────────────────────────────
def _normalize_hms_text(txt: str) -> str | None:
    """
    Accepts strings like 'Available in 15:08:10' or bare '15:08:10'
    and returns HH:MM:SS or None.
    """
    if not txt:
        return None
    m = re.search(r"(\d{1,2}\s*:\s*\d{2}\s*:\s*\d{2})", txt)
    if not m:
        return None
    hh, mm, ss = [p.strip() for p in m.group(1).split(":")]
    return f"{hh.zfill(2)}:{mm.zfill(2)}:{ss.zfill(2)}"

def _read_rr_countdown(driver):
    """
    Try the exact div first, then broader fallbacks.
    Returns normalized HH:MM:SS or None.
    """
    XPATHS = [
        COUNTDOWN_XPATH,
        "/html/body/div/div[3]/div/div[1]//div[contains(text(),':')][1]",
        "//div[contains(@class,'modal') or contains(@class,'popup') or contains(@class,'drawer') or contains(@class,'dialog')]//div[contains(text(),':')]",
        "//*[contains(text(),':')]",
    ]
    for xp in XPATHS:
        try:
            el = WebDriverWait(driver, 4).until(EC.presence_of_element_located((By.XPATH, xp)))
            hms = _normalize_hms_text((el.text or "").strip())
            if hms:
                return hms
        except Exception:
            continue
    return None

# ───────────────────────────────────────────────────────────
# ── Auth helpers (6 tries, screenshot after 10s) ───────────
# ───────────────────────────────────────────────────────────

def _is_logged_in(driver) -> bool:
    try:
        WebDriverWait(driver, 1.0).until(EC.presence_of_element_located((By.XPATH, HEADER_RICHES_BTN)))
        return True
    except Exception:
        return False

async def _login_six_tries(driver, username: str, password: str) -> bool:
    for attempt in range(1, 7):
        await _log(f"🚪 Navigating to /login (attempt {attempt}/6)…")
        driver.get(LOGIN_URL)
        await asyncio.sleep(4)

        if _is_logged_in(driver):
            await _log("🔓 Already logged in (header button present).")
            return True

        try:
            email = WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.ID, "email")))
            pwd   = driver.find_element(By.ID, "password")
            email.clear(); email.send_keys(username)
            pwd.clear();   pwd.send_keys(password); pwd.send_keys(Keys.ENTER)
            await _log(f"🔑 Submitted login (attempt {attempt}/6). Waiting 10s then screenshot…")
        except Exception as e:
            await _log(f"⚠️ Couldn’t submit login on attempt {attempt}: {e}")
            continue

        await asyncio.sleep(10)
        await _driver_shot(driver, f"📸 10s after submit (attempt {attempt}/6)")
        await _close_popup(driver)

        if _is_logged_in(driver):
            await _log("✅ Login successful — header button detected.")
            return True

        await asyncio.sleep(3)
        if _is_logged_in(driver):
            await _log("✅ Login successful (late hydrate).")
            return True

        await _log("↩️ Not logged in yet. Will retry…")

    await _log("⛔ All 6 login attempts failed.")
    await _driver_shot(driver, "⛔ Final login state")
    return

# ───────────────────────────────────────────────────────────
# ── Daily Bonus opener (hardened) ──────────────────────────
# ───────────────────────────────────────────────────────────
async def _open_daily_bonus(driver) -> bool:
    """
    Ensure we are *inside* the Daily Bonus panel (not just 'Your Riches').
    Returns True if we believe the panel is open, else False.
    """
    # 1) Try multiple DOM hooks
    for xp in XPATH_DAILY_BONUS_CANDIDATES:
        try:
            el = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, xp)))
            driver.execute_script(
                "try{arguments[0].scrollIntoView({block:'center'});}catch(e){}; arguments[0].click();", el
            )
            await asyncio.sleep(1.5)
            # panel sanity check
            try:
                WebDriverWait(driver, 2.0).until(EC.presence_of_element_located((By.XPATH, XPATH_PANEL_READY)))
                return True
            except Exception:
                # sometimes click didn't register; keep trying
                pass
        except Exception:
            continue

    # 2) JS text-scan (more aggressive)
    try:
        js_click = """
        const txt = 'daily bonus';
        const all = Array.from(document.querySelectorAll('*')).filter(n=>{
          if(!n) return false;
          if(!(n instanceof HTMLElement)) return false;
          const t=(n.innerText||'').trim().toLowerCase();
          return t.includes(txt);
        });
        for (const n of all){
          try{
            n.scrollIntoView({block:'center'});
            n.click();
            return true;
          }catch(e){}
        }
        return false;
        """
        if driver.execute_script(js_click):
            await asyncio.sleep(1.6)
            try:
                WebDriverWait(driver, 2.0).until(EC.presence_of_element_located((By.XPATH, XPATH_PANEL_READY)))
                return True
            except Exception:
                pass
    except Exception:
        pass

    # 3) Try scrolling the left menu container specifically and re-run candidate search
    try:
        scroll_js = """
        const menus = document.querySelectorAll('[class*="menu"], [class*="sidebar"]');
        for (const m of menus) {
          try {
            for(let i=0;i<6;i++){ m.scrollBy({top: 300, behavior:'instant'}); }
          } catch(e){}
        }
        """
        driver.execute_script(scroll_js)
        await asyncio.sleep(0.6)
        for xp in XPATH_DAILY_BONUS_CANDIDATES:
            try:
                el = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, xp)))
                driver.execute_script(
                    "try{arguments[0].scrollIntoView({block:'center'});}catch(e){}; arguments[0].click();", el
                )
                await asyncio.sleep(1.4)
                try:
                    WebDriverWait(driver, 2.0).until(EC.presence_of_element_located((By.XPATH, XPATH_PANEL_READY)))
                    return True
                except Exception:
                    pass
            except Exception:
                continue
    except Exception:
        pass

    # 4) Fallback — template click on Daily Bonus icon (OpenCV)
    ok, conf, debug_path = click_daily_bonus_by_template(
        DAILY_BONUS_ICON, threshold=TEMPLATE_THRESHOLD, extra_offsets=[(24, 0)]
    )
    if debug_path:
        await _log(f"🧪 Template match (daily bonus icon) conf={conf:.3f}, debug={debug_path}")
    await asyncio.sleep(2.0)
    try:
        WebDriverWait(driver, 2.0).until(EC.presence_of_element_located((By.XPATH, XPATH_PANEL_READY)))
        return True
    except Exception:
        return False

# ───────────────────────────────────────────────────────────
# ── Main flow ──────────────────────────────────────────────
# ───────────────────────────────────────────────────────────
async def rolling_riches_casino(ctx, driver, channel):
    # Start background popup-closer (shuts down in finally)
    stop_popup = asyncio.Event()
    popup_task = asyncio.create_task(_popup_closer_task(driver, stop_popup))

    try:
        creds = os.getenv("ROLLING_RICHES")
        if not creds or ":" not in creds:
            await _log("⚠️ ROLLING_RICHES not set (email:pass).")
            return
        username, password = creds.split(":", 1)

        _ensure_viewport(driver)

        # AUTH (6 tries + screenshot 10s after submit)
        ok = await _login_six_tries(driver, username, password)
        if not ok:
            return

        # Normalize to /lobby
        if not driver.current_url.startswith(LOBBY_URL):
            driver.get(LOBBY_URL)
            await asyncio.sleep(2)

        # ─────────────────────────────────────────────
        # Two page refreshes BEFORE opening Your Riches
        # ─────────────────────────────────────────────
        for n in range(1, 3):
            await _log(f"🔁 Pre-Riches refresh {n}/2…")
            driver.refresh()
            await asyncio.sleep(2.8)
            await _close_popup(driver)
        await _driver_shot(driver, "📸 After 2× pre-Riches refresh")

        # Open Your Riches
        await _log("💰 Opening Your Riches panel…")
        riches_btn = WebDriverWait(driver, 12).until(EC.element_to_be_clickable((By.XPATH, HEADER_RICHES_BTN)))
        driver.execute_script("arguments[0].click();", riches_btn)
        await asyncio.sleep(2.5)
        await _driver_shot(driver, "📸 Your Riches panel")

        # Handle the 'Your Riches' popup
        try_cv_close = await _close_rr_popup_via_cv(driver)
        if not try_cv_close:
            await _close_popup(driver)
        if not try_cv_close:
            # Confirm popup presence and hard refresh as last resort
            scr = _screenshot_bgr()
            if os.path.exists(RR_POPUP_TEMPLATE):
                pop_bgr = cv2.imread(RR_POPUP_TEMPLATE, cv2.IMREAD_COLOR)
                if pop_bgr is not None:
                    score, rect, _ = _match_template_multiscale(scr, pop_bgr)
                    if rect and score >= POPUP_DETECT_THRESHOLD:
                        await _log("🔁 Refreshing page as popup-close fallback…")
                        driver.refresh()
                        await asyncio.sleep(3.5)
                        await _close_popup(driver)

        # ── OPEN DAILY BONUS (new robust opener) ──
        await _log("🎯 Ensuring we are inside the Daily Bonus panel…")
        opened = await _open_daily_bonus(driver)
        await _driver_shot(driver, "📸 After Daily Bonus open attempt")
        if not opened:
            await _log("⚠️ Could not positively open Daily Bonus panel; continuing to attempt claim anyway.")

        # ── Claim step 1: DOM click, else template click (rr_claim_btn) ──
        clicked_primary = False
        try:
            claim = WebDriverWait(driver, 4).until(EC.element_to_be_clickable((By.XPATH, XPATH_CLAIM_BTN)))
            driver.execute_script("arguments[0].click();", claim)
            clicked_primary = True
            await asyncio.sleep(1.0)
            await _log("🖱️ Clicked primary claim (DOM).")
        except TimeoutException:
            ok1, conf1, dbg1 = _click_template_with_retries(RR_CLAIM_TEMPLATE, tries=3, delay=0.8)
            if dbg1:
                await _log(f"🧪 Claim button template conf={conf1:.3f}, debug={dbg1}")
            if ok1:
                clicked_primary = True
                await asyncio.sleep(1.0)
                await _log("🖱️ Clicked primary claim (template).")

        # ── Claim step 2: final confirm (rr_final_claim) ──
        claimed = False
        if clicked_primary:
            ok2, conf2, dbg2 = _click_template_with_retries(RR_FINAL_TEMPLATE, tries=4, delay=0.9)
            if dbg2:
                await _log(f"🧪 Final claim template conf={conf2:.3f}, debug={dbg2}")
            if ok2:
                claimed = True
                await asyncio.sleep(1.0)
                await _log("✅ Final confirm clicked (template).")

        # ── Outcome (now with Discord sends + screenshots) ──
        if claimed:
            shot = await _driver_shot(driver, "✅ Claimed — final state")
            await _send_one_shot(channel, "Rolling Riches Daily Bonus Claimed!", shot)

            cd = _read_rr_countdown(driver)
            if cd:
                await _log(f"🕒 Next bonus in: {cd}")
        else:
            cd = _read_rr_countdown(driver)
            shot = await _driver_shot(driver, "ℹ️ Bonus unavailable — current state")
            if cd:
                await _send_one_shot(channel, f"Rolling Riches: Bonus unavailable. Next bonus in: {cd}", shot)
            else:
                await _send_one_shot(channel, "Rolling Riches: Bonus unavailable.", shot)

    except Exception as e:
        tb = "".join(traceback.format_exception_only(type(e), e)).strip()
        await _log(f"💥 Error: {tb}")
        shot = await _driver_shot(driver, "💥 Failure point")
        await _send_one_shot(channel, f"Rolling Riches: Error — {tb}", shot)

    finally:
        # Stop the background popup closer
        try:
            stop_popup.set()
            await popup_task
        except Exception:
            pass
