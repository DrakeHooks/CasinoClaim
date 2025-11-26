# Drake Hooks + WaterTrooper
# Casino Claim 2
# Rolling Riches — robust Daily Bonus opener + UC thread runner
# Changes for non-blocking main loop:
# - All core logic is now sync (no async/await in the claim flow).
# - New entrypoint: rollingriches_uc_blocking(bot, channel_id, loop)
# - Uses its own SeleniumBase UC driver instead of the shared driver.
# - Discord messages/files are scheduled back onto the main loop.

import os
import re
import time
import tempfile
import traceback
import asyncio

import discord
from dotenv import load_dotenv

# ───────────────────────────────────────────────────────────
# PyAutoGUI / OpenCV
# ───────────────────────────────────────────────────────────

import pyautogui
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

import cv2
import numpy as np

# ───────────────────────────────────────────────────────────
# Selenium / SeleniumBase
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
from seleniumbase import SB

load_dotenv()

# ───────────────────────────────────────────────────────────
# Config and Constants
# ───────────────────────────────────────────────────────────

LOGIN_URL = "https://www.rollingriches.com/login"
LOBBY_URL = "https://www.rollingriches.com/lobby"

HEADER_RICHES_BTN = "/html/body/app-root/app-main-header/div/div/div/div/header/div[1]/nav/div[2]/div/div[2]/nav/div/div[2]/button"
POPUP_CLOSE_XPATH = "/html/body/div[2]/div/div[2]/div/div/a"

# Daily Bonus menu targets (multiple options; we try all)
XPATH_DAILY_BONUS_TEXTS = [
    "//*[normalize-space()='Daily Bonus']",
    "//div[contains(@class,'menu')]//*[normalize-space()='Daily Bonus']",
    "//aside//*[contains(@class,'menu') or contains(@class,'nav')]//*[normalize-space()='Daily Bonus']",
    "//button[.//*[normalize-space()='Daily Bonus'] or normalize-space()='Daily Bonus']",
]

XPATH_CLAIM_BTN = (
    "//button[(contains(@class,'btn') and contains(@class,'red')) or "
    "contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'claim')]"
)

COUNTDOWN_XPATH = "/html/body/div/div[3]/div/div[1]/div[3]/div[3]/div[1]/div/div[3]/div/div/div[2]"

DAILY_BONUS_ICON     = os.environ.get("DAILY_BONUS_ICON",     "daily_bonus_icon.png")
RR_CLAIM_TEMPLATE    = os.environ.get("RR_CLAIM_TEMPLATE",    "rr_claim_btn.png")
RR_FINAL_TEMPLATE    = os.environ.get("RR_FINAL_TEMPLATE",    "rr_final_claim.png")
TEMPLATE_THRESHOLD   = float(os.environ.get("DAILY_BONUS_THRESHOLD", "0.60"))  # relaxed

# Popup templates + thresholds
RR_POPUP_TEMPLATE      = os.environ.get("RR_POPUP_TEMPLATE",      "rr_popup1.png")
RR_POPUPCLOSE_TEMPLATE = os.environ.get("RR_POPUPCLOSE_TEMPLATE", "rr_popup1close.png")
POPUP_DETECT_THRESHOLD = float(os.environ.get("POPUP_DETECT_THRESHOLD", "0.80"))
POPUP_CLOSE_THRESHOLD  = float(os.environ.get("POPUP_CLOSE_THRESHOLD",  "0.80"))

# ───────────────────────────────────────────────────────────
# Print/log helpers (sync)
# ───────────────────────────────────────────────────────────

def _log(msg: str):
    print(msg, flush=True)

def _driver_shot(driver, caption: str = "") -> str:
    """Take a Selenium screenshot; return path or '' on failure."""
    try:
        fd, path = tempfile.mkstemp(prefix="rr_driver_", suffix=".png", dir="/tmp")
        os.close(fd)
        driver.save_screenshot(path)
        _log(f"{caption or '📸 Selenium'} saved: {path}\nURL: {driver.current_url}")
        return path
    except Exception as e:
        _log(f"⚠️ _driver_shot error: {e}")
        return ""

def _pyauto_shot(caption: str = "") -> str:
    """Full-screen screenshot via PyAutoGUI; return path."""
    try:
        fd, path = tempfile.mkstemp(prefix="rr_pyauto_", suffix=".png", dir="/tmp")
        os.close(fd)
        pyautogui.screenshot(path)
        _log(f"{caption or '🖥️ Screen'} saved: {path}")
        return path
    except Exception as e:
        _log(f"⚠️ _pyauto_shot error: {e}")
        return ""

def _ensure_viewport(driver):
    """Normalize viewport for consistent CV templates & DOM layout."""
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
# OpenCV helpers
# ───────────────────────────────────────────────────────────

def _screenshot_bgr() -> np.ndarray:
    im = pyautogui.screenshot()
    arr = np.array(im)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

def _draw_box(img_bgr: np.ndarray, top_left: tuple, w: int, h: int, text: str = "") -> np.ndarray:
    out = img_bgr.copy()
    cv2.rectangle(out, top_left, (top_left[0] + w, top_left[1] + h), (0, 255, 0), 2)
    if text:
        cv2.putText(
            out,
            text,
            (top_left[0], max(0, top_left[1] - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
    return out

def _save_debug(img_bgr: np.ndarray, prefix: str = "cv_debug") -> str:
    fd, path = tempfile.mkstemp(prefix=f"{prefix}_", suffix=".png", dir="/tmp")
    os.close(fd)
    cv2.imwrite(path, img_bgr)
    return path

def _match_template_multiscale(
    screen_bgr: np.ndarray,
    templ_bgr: np.ndarray,
    method=cv2.TM_CCOEFF_NORMED,
    scales=None,
):
    if scales is None:
        scales = [0.75, 0.8, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.2]

    screen_gray = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)
    templ_gray0 = cv2.cvtColor(templ_bgr, cv2.COLOR_BGR2GRAY)

    best_score, best_rect, best_scale = -1.0, None, None
    for s in scales:
        if s == 1.0:
            tmpl = templ_gray0
        else:
            new_w = max(6, int(templ_bgr.shape[1] * s))
            new_h = max(6, int(templ_bgr.shape[0] * s))
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

def click_daily_bonus_by_template(
    template_path: str,
    threshold: float = 0.80,
    extra_offsets=None,
    move_duration: float = 0.25,
):
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
        dbg_img = _draw_box(
            screen_bgr,
            tl,
            rect[2],
            rect[3],
            f"{score:.3f}@{scale:.2f}",
        )
        dbg_path = _save_debug(dbg_img, "daily_bonus_match")

    if rect and score >= threshold:
        x, y, w, h = rect
        cx, cy = x + w // 2, y + h // 2
        pyautogui.moveTo(cx, cy, duration=move_duration)
        pyautogui.click()
        time.sleep(0.2)
        if extra_offsets:
            for dx, dy in extra_offsets:
                pyautogui.moveTo(cx + dx, cy + dy, duration=0.15)
                pyautogui.click()
                time.sleep(0.12)
        return True, score, dbg_path

    return False, score, dbg_path

def _click_template_with_retries(
    template_path: str,
    tries: int = 3,
    delay: float = 0.8,
    threshold: float | None = None,
):
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
# OpenCV popup detect & close with refresh fallback
# ───────────────────────────────────────────────────────────

def _close_rr_popup_via_cv(
    driver,
    popup_tmpl: str = RR_POPUP_TEMPLATE,
    close_tmpl: str = RR_POPUPCLOSE_TEMPLATE,
    detect_thr: float = POPUP_DETECT_THRESHOLD,
    close_thr: float = POPUP_CLOSE_THRESHOLD,
    tries: int = 3,
) -> bool:
    if not os.path.exists(popup_tmpl) or not os.path.exists(close_tmpl):
        _log("ℹ️ RR popup templates missing; skipping CV close.")
        return False

    scr = _screenshot_bgr()
    pop_bgr = cv2.imread(popup_tmpl, cv2.IMREAD_COLOR)
    if pop_bgr is None:
        return False
    pop_score, pop_rect, pop_scale = _match_template_multiscale(scr, pop_bgr)
    if not pop_rect or pop_score < detect_thr:
        _log(f"ℹ️ CV popup not detected (score={pop_score:.3f}).")
        return False

    for i in range(tries):
        ok, conf, dbg = _click_template_with_retries(
            close_tmpl,
            tries=1,
            delay=0.3,
            threshold=close_thr,
        )
        if dbg:
            _log(
                f"🧪 RR popup close match (try {i+1}/{tries}) "
                f"conf={conf:.3f}, debug={dbg}"
            )
        if ok:
            time.sleep(0.5)
            _log("✅ RR popup closed via OpenCV.")
            return True
        time.sleep(0.3)

    _log("⚠️ RR popup CV close failed after retries.")
    return False

# ───────────────────────────────────────────────────────────
# Countdown helpers
# ───────────────────────────────────────────────────────────

def _normalize_hms_text(txt: str) -> str | None:
    if not txt:
        return None
    m = re.search(r"(\d{1,2}\s*:\s*\d{2}\s*:\s*\d{2})", txt)
    if not m:
        return None
    hh, mm, ss = [p.strip() for p in m.group(1).split(":")]
    return f"{hh.zfill(2)}:{mm.zfill(2)}:{ss.zfill(2)}"

def _read_rr_countdown(driver):
    XPATHS = [
        COUNTDOWN_XPATH,
        "/html/body/div/div[3]/div/div[1]"
        "//div[contains(text(),':')][1]",
        "//div[contains(@class,'modal') or contains(@class,'popup') "
        "or contains(@class,'drawer') or contains(@class,'dialog')]"
        "//div[contains(text(),':')]",
        "//*[contains(text(),':')]",
    ]
    for xp in XPATHS:
        try:
            el = WebDriverWait(driver, 4).until(
                EC.presence_of_element_located((By.XPATH, xp))
            )
            hms = _normalize_hms_text((el.text or "").strip())
            if hms:
                return hms
        except Exception:
            continue
    return None

# ───────────────────────────────────────────────────────────
# Auth helpers (6 tries)
# ───────────────────────────────────────────────────────────

def _is_logged_in(driver) -> bool:
    try:
        WebDriverWait(driver, 1.0).until(
            EC.presence_of_element_located((By.XPATH, HEADER_RICHES_BTN))
        )
        return True
    except Exception:
        return False

def _close_popup(driver):
    try:
        btn = WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((By.XPATH, POPUP_CLOSE_XPATH))
        )
        driver.execute_script("arguments[0].click();", btn)
        time.sleep(0.2)
        _log("🧹 Popup closed (if present).")
    except Exception:
        pass

def _login_six_tries(driver, username: str, password: str) -> bool:
    for attempt in range(1, 7):
        _log(f"🚪 Navigating to /login (attempt {attempt}/6)…")
        driver.get(LOGIN_URL)
        time.sleep(4)

        if _is_logged_in(driver):
            _log("🔓 Already logged in (header button present).")
            return True

        try:
            email = WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            pwd = driver.find_element(By.ID, "password")
            email.clear()
            email.send_keys(username)
            pwd.clear()
            pwd.send_keys(password)
            pwd.send_keys(Keys.ENTER)
            _log("🔑 Submitted login (attempt {attempt}/6). Waiting 10s then screenshot…")
        except Exception as e:
            _log(f"⚠️ Couldn’t submit login on attempt {attempt}: {e}")
            continue

        time.sleep(10)
        _driver_shot(driver, f"📸 10s after submit (attempt {attempt}/6)")
        _close_popup(driver)

        if _is_logged_in(driver):
            _log("✅ Login successful — header button detected.")
            return True

        time.sleep(3)
        if _is_logged_in(driver):
            _log("✅ Login successful (late hydrate).")
            return True

        _log("↩️ Not logged in yet. Will retry…")

    _log("⛔ All 6 login attempts failed.")
    _driver_shot(driver, "⛔ Final login state")
    return False

# ───────────────────────────────────────────────────────────
# Daily Bonus opener — DOM-first, then CV
# ───────────────────────────────────────────────────────────

def _scroll_into_view_and_click(driver, el):
    driver.execute_script(
        "arguments[0].scrollIntoView({block:'center'});",
        el,
    )
    driver.execute_script("arguments[0].click();", el)

def _find_clickable_ancestor(driver, el):
    # Walk up to a button/div with click handler
    ancestor = el
    for _ in range(6):
        try:
            if ancestor.tag_name.lower() in ("button", "a"):
                return ancestor
            try:
                role = ancestor.get_attribute("role") or ""
            except Exception:
                role = ""
            onclick = (ancestor.get_attribute("onclick") or "")
            if "button" in role or onclick:
                return ancestor
            ancestor = ancestor.find_element(By.XPATH, "..")
        except Exception:
            break
    return el

def _open_daily_bonus_dom_first(driver) -> bool:
    # 1) Try a handful of direct text XPaths
    for xp in XPATH_DAILY_BONUS_TEXTS:
        try:
            el = WebDriverWait(driver, 2).until(
                EC.presence_of_element_located((By.XPATH, xp))
            )
            el = _find_clickable_ancestor(driver, el)
            _scroll_into_view_and_click(driver, el)
            time.sleep(1.2)
            return True
        except Exception:
            continue

    # 2) JS text-scan: find any visible element whose innerText is "Daily Bonus"
    try:
        js = """
        const matches = [];
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
        while (walker.nextNode()) {
          const el = walker.currentNode;
          if (!el || !el.getBoundingClientRect) continue;
          const r = el.getBoundingClientRect();
          const visible = r.width>2 && r.height>2 && r.bottom>0 && r.right>0;
          if (!visible) continue;
          const txt = (el.innerText||'').trim();
          if (txt === 'Daily Bonus') { matches.push(el); }
        }
        return matches.slice(0,4);
        """
        elems = driver.execute_script(js) or []
        if elems:
            _scroll_into_view_and_click(driver, elems[0])
            time.sleep(1.2)
            return True
    except Exception:
        pass

    return False

# ───────────────────────────────────────────────────────────
# Discord helpers for threaded runner
# ───────────────────────────────────────────────────────────

def _schedule_coro(loop: asyncio.AbstractEventLoop, coro):
    """Schedule a coroutine safely from the UC worker thread."""
    loop.call_soon_threadsafe(asyncio.create_task, coro)

async def _send_msg(bot: discord.Client, channel_id: int, text: str):
    channel = bot.get_channel(channel_id)
    if channel:
        await channel.send(text)

async def _send_file(bot: discord.Client, channel_id: int, path: str, caption: str = ""):
    channel = bot.get_channel(channel_id)
    if not channel:
        return
    if not os.path.exists(path):
        await channel.send(f"{caption} (screenshot missing: `{os.path.basename(path)}`)")
        return
    await channel.send(caption, file=discord.File(path))

# ───────────────────────────────────────────────────────────
# Main entrypoint — sync, for run_in_executor
# ───────────────────────────────────────────────────────────

def rollingriches_uc_blocking(
    bot: discord.Client,
    channel_id: int,
    loop: asyncio.AbstractEventLoop,
):
    """
    Sync runner for Rolling Riches.

    Called from main.py as:
        await loop.run_in_executor(_executor, rollingriches_uc_blocking, bot, channel.id, loop)
    """

    creds = os.getenv("ROLLING_RICHES")
    if not creds or ":" not in creds:
        _log("⚠️ ROLLING_RICHES not set (email:pass).")
        _schedule_coro(loop, _send_msg(bot, channel_id, "⚠️ `ROLLING_RICHES` credentials not configured."))
        return
    username, password = creds.split(":", 1)

    _schedule_coro(loop, _send_msg(bot, channel_id, "🎲 Starting Rolling Riches (UC thread)…"))

    # Use SeleniumBase UC for its own browser instance
    with SB(uc=True, test=True) as sb:
        driver = sb.driver
        try:
            _ensure_viewport(driver)

            # ── Auth ──────────────────────────────────────────────────
            ok = _login_six_tries(driver, username, password)
            if not ok:
                _schedule_coro(loop, _send_msg(bot, channel_id, "⛔ Rolling Riches login failed."))
                shot = _driver_shot(driver, "⛔ Login failed")
                if shot:
                    _schedule_coro(
                        loop,
                        _send_file(bot, channel_id, shot, "📸 Rolling Riches login failure:"),
                    )
                return

            # Normalize to /lobby
            if not driver.current_url.startswith(LOBBY_URL):
                driver.get(LOBBY_URL)
                time.sleep(2)

            # Two pre-Riches refreshes
            for n in range(1, 3):
                _log(f"🔁 Pre-Riches refresh {n}/2…")
                driver.refresh()
                time.sleep(2.8)
                _close_popup(driver)
            _driver_shot(driver, "📸 After 2× pre-Riches refresh")

            # Open Your Riches
            _log("💰 Opening Your Riches panel…")
            riches_btn = WebDriverWait(driver, 12).until(
                EC.element_to_be_clickable((By.XPATH, HEADER_RICHES_BTN))
            )
            driver.execute_script("arguments[0].click();", riches_btn)
            time.sleep(2.2)
            _driver_shot(driver, "📸 Your Riches panel")

            # CV popup close (if any)
            try_cv_close = _close_rr_popup_via_cv(driver)
            if not try_cv_close:
                _close_popup(driver)

            # If popup still looks present, one refresh fallback
            if not try_cv_close and os.path.exists(RR_POPUP_TEMPLATE):
                scr = _screenshot_bgr()
                pop_bgr = cv2.imread(RR_POPUP_TEMPLATE, cv2.IMREAD_COLOR)
                if pop_bgr is not None:
                    score, rect, _ = _match_template_multiscale(scr, pop_bgr)
                    if rect and score >= POPUP_DETECT_THRESHOLD:
                        _log("🔁 Refreshing page as popup-close fallback…")
                        driver.refresh()
                        time.sleep(3.5)
                        _close_popup(driver)
                        # reopen Your Riches to restore panel
                        riches_btn = WebDriverWait(driver, 12).until(
                            EC.element_to_be_clickable((By.XPATH, HEADER_RICHES_BTN))
                        )
                        driver.execute_script("arguments[0].click();", riches_btn)
                        time.sleep(2)
                        _driver_shot(driver, "📸 Your Riches after fallback refresh")

            # ── Strong DOM-first Daily Bonus open ─────────────────────
            _log("🎯 Ensuring we are inside the Daily Bonus panel (DOM-first)…")
            opened_dom = _open_daily_bonus_dom_first(driver)
            _driver_shot(driver, "📸 After DOM-first Daily Bonus open attempt")

            if not opened_dom:
                _log("⚠️ DOM open failed; switching to OpenCV template for Daily Bonus icon/text.")
                ok_icon, conf_icon, debug_path = click_daily_bonus_by_template(
                    DAILY_BONUS_ICON,
                    threshold=TEMPLATE_THRESHOLD,
                    extra_offsets=[(24, 0)],
                )
                if debug_path:
                    _log(
                        f"🧪 Template match (daily bonus icon) "
                        f"conf={conf_icon:.3f}, debug={debug_path}"
                    )
                time.sleep(2.0)
                _driver_shot(driver, "📸 After CV Daily Bonus open attempt")

            # Probe countdown / presence (don’t bail if missing)
            cd_probe = _read_rr_countdown(driver)
            if cd_probe:
                _log(f"✅ Daily Bonus section detected (countdown {cd_probe}).")
            else:
                _log("ℹ️ Could not positively confirm Daily Bonus; proceeding with claim attempts.")

            # ── Claim step 1: primary claim ───────────────────────────
            clicked_primary = False
            try:
                claim = WebDriverWait(driver, 4).until(
                    EC.element_to_be_clickable((By.XPATH, XPATH_CLAIM_BTN))
                )
                driver.execute_script("arguments[0].click();", claim)
                clicked_primary = True
                time.sleep(1.0)
                _log("🖱️ Clicked primary claim (DOM).")
            except TimeoutException:
                ok1, conf1, dbg1 = _click_template_with_retries(
                    RR_CLAIM_TEMPLATE,
                    tries=3,
                    delay=0.8,
                )
                if dbg1:
                    _log(
                        f"🧪 Claim button template conf={conf1:.3f}, debug={dbg1}"
                    )
                if ok1:
                    clicked_primary = True
                    time.sleep(1.0)
                    _log("🖱️ Clicked primary claim (template).")

            # ── Claim step 2: final confirm ───────────────────────────
            claimed = False
            if clicked_primary:
                ok2, conf2, dbg2 = _click_template_with_retries(
                    RR_FINAL_TEMPLATE,
                    tries=4,
                    delay=0.9,
                )
                if dbg2:
                    _log(
                        f"🧪 Final claim template conf={conf2:.3f}, debug={dbg2}"
                    )
                if ok2:
                    claimed = True
                    time.sleep(1.0)
                    _log("✅ Final confirm clicked (template).")

            # ── Outcome ───────────────────────────────────────────────
            if claimed:
                shot = _driver_shot(driver, "✅ Claimed — final state")
                _schedule_coro(
                    loop,
                    _send_msg(bot, channel_id, "Rolling Riches Daily Bonus Claimed!"),
                )
                if shot:
                    _schedule_coro(
                        loop,
                        _send_file(
                            bot,
                            channel_id,
                            shot,
                            "📸 Rolling Riches claim state:",
                        ),
                    )
                cd = _read_rr_countdown(driver)
                if cd:
                    _log(f"🕒 Next bonus in: {cd}")
            else:
                cd = _read_rr_countdown(driver)
                shot = _driver_shot(driver, "ℹ️ Bonus unavailable — current state")
                if cd:
                    _schedule_coro(
                        loop,
                        _send_msg(
                            bot,
                            channel_id,
                            f"[Rolling Riches] Bonus unavailable. Next bonus in: {cd}",
                        ),
                    )
                else:
                    _schedule_coro(
                        loop,
                        _send_msg(
                            bot,
                            channel_id,
                            "[Rolling Riches] Bonus unavailable.",
                        ),
                    )
                if shot:
                    _schedule_coro(
                        loop,
                        _send_file(
                            bot,
                            channel_id,
                            shot,
                            "📸 Rolling Riches bonus state:",
                        ),
                    )

        except Exception as e:
            tb = "".join(traceback.format_exception_only(type(e), e)).strip()
            _log(f"💥 Error: {tb}")
            shot = _driver_shot(driver, "💥 Failure point")
            _schedule_coro(
                loop,
                _send_msg(bot, channel_id, f"Rolling Riches: Error — {tb}"),
            )
            if shot:
                _schedule_coro(
                    loop,
                    _send_file(
                        bot,
                        channel_id,
                        shot,
                        "📸 Rolling Riches error state:",
                    ),
                )
