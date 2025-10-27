# Drake Hooks + WaterTrooper
# Casino Claim
# Modo — UC/CDP auth + claim-or-countdown in SAME session
# Output rules:
#   - Countdown success => ONLY text "Next Modo Bonus Available in: HH:MM:SS" (no screenshot)
#   - Claim success     => text + ONE screenshot (post-login)
#   - Auth success      => "✅ Modo auth OK." + ONE screenshot
#   - Any failure       => failure line + ONE screenshot
#   - Never include URLs in messages

import os
import re
import json
import time
import tempfile
import concurrent.futures
import datetime as dt
from typing import Tuple, List, Optional

import asyncio
import discord
from dotenv import load_dotenv
from seleniumbase import SB
from urllib.parse import urlparse

load_dotenv()

MODO_CRED = os.getenv("MODO", "")  # "email:password"

LOGIN_URL = "https://login.modo.us/login"
LOBBY_URL = "https://modo.us/lobby/"
LOBBY_URL_BARE = "https://modo.us/lobby"

# Optional persistent profile for SeleniumBase UC
SB_USER_DATA_DIR = os.getenv("MODO_SB_USER_DATA_DIR", "").strip()
SB_PROFILE_DIR   = os.getenv("MODO_SB_PROFILE_DIR", "Default").strip()

# Persistent auth-state on disk
STATE_DIR   = os.getenv("STATE_DIR", "/data").strip() or "/data"
os.makedirs(STATE_DIR, exist_ok=True)
AUTH_STATE_PATH = os.path.join(STATE_DIR, "modo_auth_state.json")

# Auth freshness knobs
AUTH_MAX_AGE_HOURS = int(os.getenv("MODO_AUTH_MAX_AGE_HOURS", "72"))
AUTH_REFRESH_EVERY_HOURS = int(os.getenv("MODO_REFRESH_EVERY_HOURS", "3"))

# Elements
EMAIL_SELECTORS = [
    "/html/body/main/div/div[2]/form/div/div/div/div/div[2]/div[2]/span/div/div/div/div/div/div/div/div/div[2]/div[3]/div[1]/div/input",
    "input[type='email']","input[name='email']","input#email",
    "//input[@placeholder='Email' or @placeholder='E-mail']",
]
PASS_SELECTORS = [
    "/html/body/main/div/div[2]/form/div/div/div/div/div[2]/div[2]/span/div/div/div/div/div/div/div/div/div[2]/div[3]/div[2]/div/div/input",
    "input[type='password']","input[name='password']","input#password",
    "//input[@placeholder='Password']",
]
LOGIN_BUTTON_SELECTORS = [
    "/html/body/main/div/div[2]/form/div/div/div/button",
    "button[type='submit']","//button[normalize-space()='Log In']",
    "//button[contains(., 'Log In') or contains(., 'LOG IN')]",
]

# Captcha (best-effort helper)
RECAPTCHA_IFRAME = os.getenv("MODO_CAPCHA_IFRAME", "iframe[src*='/recaptcha/']")
HCAPTCHA_IFRAME  = os.getenv("MODO_HCAPTCHA_IFRAME", "iframe[src*='hcaptcha']")

# Claim & countdown
CLAIM_XPATHS = [
    "/html/body/div[6]/div[3]/div/div[2]/button",
    "/html/body/div[6]/div[3]/div/div[3]/div/button",
    "/html/body/div[4]/div[3]/div/div[3]/button",
    "/html/body/div[8]/div[3]/div/div[3]/div/button",
    "/html/body/div[5]/div[3]/div[3]/button",
    "/html/body/div[5]/div[3]/div/div[3]/div/button",
    "/html/body/div[6]/div[3]/div/div[3]/div/button",
    "/html/body/div[7]/div[3]/div/div[3]/div/button",
]
COUNTDOWN_XPATH = "/html/body/div[1]/div[1]/div/div[3]/div/div[1]/div/div[1]/button/div/div[2]/div[1]/div/span"

# Single-thread executor for SB sync work
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

# ---------- tiny helpers ----------
def _shot_path() -> str:
    return os.path.join(tempfile.gettempdir(), f"modo_post_login_{int(time.time()*1000)}.png")

def _type_first(sb: SB, selectors: list, text: str) -> str:
    for sel in selectors:
        try:
            by = "xpath" if sel.startswith("/") or sel.startswith("(") else "css selector"
            if sb.is_element_visible(sel, by=by):
                sb.type(sel, text, by=by)
                return sel
        except Exception:
            continue
    raise Exception("No matching input field found")

def _click_first(sb: SB, selectors: list) -> str:
    for sel in selectors:
        try:
            by = "xpath" if sel.startswith("/") or sel.startswith("(") else "css selector"
            if sb.is_element_visible(sel, by=by):
                sb.click(sel, by=by)
                return sel
        except Exception:
            continue
    raise Exception("No matching login button found")

def _is_true_lobby(url: str) -> bool:
    try:
        u = urlparse(url)
    except Exception:
        return False
    host = (u.netloc or "").lower()
    path = (u.path or "").rstrip("/")
    return host.endswith("modo.us") and path == "/lobby"

def _looks_guest_lobby(sb: SB) -> bool:
    # Guest markers
    if sb.is_text_visible("Log in", timeout=0.6) or sb.is_text_visible("LOG IN", timeout=0.2):
        return True
    if sb.is_text_visible("Sign up", timeout=0.3) or sb.is_text_visible("SIGN UP", timeout=0.3):
        return True
    # Strong authed hints
    for t in ("Daily Login", "My profile", "Balance", "My bonuses", "Recent winners"):
        if sb.is_text_visible(t, timeout=0.3):
            return False
    return True

def _wait_for_authed_lobby(sb: SB, max_wait_s: float = 45.0) -> bool:
    end = time.time() + max_wait_s
    while time.time() < end:
        cur = sb.get_current_url() or ""
        if _is_true_lobby(cur):
            sb.sleep(0.5)
            if not _looks_guest_lobby(sb):
                return True
        sb.sleep(0.5)
    return False

def _load_auth_state() -> Optional[dt.datetime]:
    try:
        with open(AUTH_STATE_PATH, "r", encoding="utf-8") as f:
            obj = json.load(f)
        ts = obj.get("last_success_iso")
        return dt.datetime.fromisoformat(ts) if ts else None
    except Exception:
        return None

def _save_auth_state(now: Optional[dt.datetime] = None) -> None:
    now = now or dt.datetime.utcnow()
    try:
        with open(AUTH_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump({"last_success_iso": now.isoformat()}, f)
    except Exception:
        pass

def auth_is_fresh(max_age_hours: int = AUTH_MAX_AGE_HOURS) -> bool:
    ts = _load_auth_state()
    if not ts:
        return False
    age = dt.datetime.utcnow() - ts
    return age.total_seconds() <= max_age_hours * 3600

# ---------- single UC/CDP session flow ----------
def _sb_session_flow(perform: str) -> Tuple[bool, str, Optional[str], str]:
    """
    perform: 'claim' or 'countdown'
    returns: (ok, final_url, detail_text_or_none, post_login_screenshot_path)
    """
    if ":" not in (MODO_CRED or ""):
        shot = _shot_path()
        with SB(uc=True, test=True) as sb:
            sb.set_window_size(1920, 1080)
            sb.save_screenshot(shot)
        return False, "", None, shot

    email, password = MODO_CRED.split(":", 1)
    sb_kwargs = dict(uc=True, test=True)
    if SB_USER_DATA_DIR:
        sb_kwargs["uc_user_data_dir"] = SB_USER_DATA_DIR
        sb_kwargs["uc_profile"] = SB_PROFILE_DIR

    shot = _shot_path()

    with SB(**sb_kwargs) as sb:
        sb.set_window_size(1920, 1080)

        # Fast-path if cache is fresh
        if auth_is_fresh():
            sb.open(LOBBY_URL)
            sb.sleep(6)
            if not _wait_for_authed_lobby(sb, 10):
                pass  # proceed to login

        # If not on authed lobby, log in
        if not _wait_for_authed_lobby(sb, 2):
            sb.open(LOGIN_URL)
            sb.sleep(2)
            try:
                sb.activate_cdp_mode(sb.get_current_url() or LOGIN_URL)
                sb.sleep(1)
            except Exception:
                pass
            try:
                _type_first(sb, EMAIL_SELECTORS, email)
                _type_first(sb, PASS_SELECTORS, password)
            except Exception:
                sb.save_screenshot(shot)
                return False, sb.get_current_url() or "", None, shot

            try:
                sb.uc_gui_handle_captcha()
                sb.sleep(8)
            except Exception:
                pass

            try:
                _click_first(sb, LOGIN_BUTTON_SELECTORS)
                sb.sleep(3)
            except Exception:
                sb.save_screenshot(shot)
                return False, sb.get_current_url() or "", None, shot

            if not _wait_for_authed_lobby(sb, 45):
                sb.save_screenshot(shot)
                return False, sb.get_current_url() or "", None, shot

            _save_auth_state()

        # We’re on authed lobby in THIS session — take the single post-login screenshot now
        sb.save_screenshot(shot)

        # Perform action
        if perform == "claim":
            for xp in CLAIM_XPATHS:
                try:
                    sb.wait_for_element_visible(xp, timeout=5)
                    sb.click(xp)
                    sb.sleep(1.4)
                    return True, sb.get_current_url() or "", "Modo Daily Bonus Claimed!", shot
                except Exception:
                    continue
            perform = "countdown"  # fall through

        if perform == "countdown":
            try:
                sb.wait_for_element_present(COUNTDOWN_XPATH, timeout=10)
                txt = (sb.get_text(COUNTDOWN_XPATH) or "").strip()
                m = re.search(r"\b(\d{1,2}:\d{2}:\d{2})\b", txt)
                clock = m.group(1) if m else (txt or "Unknown")
                return True, sb.get_current_url() or "", f"Next Modo Bonus Available in: {clock}", shot
            except Exception:
                return False, sb.get_current_url() or "", None, shot

        return False, sb.get_current_url() or "", None, shot


# ---------- public async wrappers ----------
async def authenticate_modo(_driver, _bot, _ctx, channel) -> bool:
    loop = asyncio.get_running_loop()
    def _go():
        # auth + light check via "countdown" path
        return _sb_session_flow("countdown")
    ok, _url, text, shot = await loop.run_in_executor(_executor, _go)

    # Auth uses screenshot; concise text without URL
    msg = "✅ Modo auth OK." if ok and text else "Modo: countdown not available (or auth failed)."

    if os.path.exists(shot):
        try:
            await channel.send(msg, file=discord.File(shot))
        finally:
            try: os.remove(shot)
            except Exception: pass
    else:
        await channel.send(msg)

    return ok


async def claim_modo_bonus(_driver, _bot, _ctx, channel) -> bool:
    loop = asyncio.get_running_loop()
    def _go():
        return _sb_session_flow("claim")
    ok, _url, text, shot = await loop.run_in_executor(_executor, _go)

    # Decide message + whether to attach screenshot
    attach_shot = True
    if ok and text and "Claimed" in text:
        msg = "Modo Daily Bonus Claimed!"
        sent_ok = True
    elif ok and text:
        # Countdown: text only, NO screenshot
        msg = text
        sent_ok = False
        attach_shot = False
    else:
        msg = "Modo: countdown not available (or auth failed)."
        sent_ok = False

    if attach_shot and os.path.exists(shot):
        try:
            await channel.send(msg, file=discord.File(shot))
        finally:
            try: os.remove(shot)
            except Exception: pass
    else:
        await channel.send(msg)
        if os.path.exists(shot):
            try: os.remove(shot)
            except Exception: pass

    return sent_ok


async def check_modo_countdown(_driver, _bot, _ctx, channel) -> bool:
    loop = asyncio.get_running_loop()
    def _go():
        return _sb_session_flow("countdown")
    ok, _url, text, shot = await loop.run_in_executor(_executor, _go)

    # Countdown path: on success send ONLY text; no screenshot
    if ok and text:
        await channel.send(text)
        if os.path.exists(shot):
            try: os.remove(shot)
            except Exception: pass
        return True

    # Failure: one liner + screenshot
    msg = "Modo: countdown not available (or auth failed)."
    if os.path.exists(shot):
        try:
            await channel.send(msg, file=discord.File(shot))
        finally:
            try: os.remove(shot)
            except Exception: pass
    else:
        await channel.send(msg)

    return False


def modo_auth_needs_refresh() -> bool:
    last = _load_auth_state()
    if not last:
        return True
    age_h = (dt.datetime.utcnow() - last).total_seconds() / 3600.0
    return age_h >= AUTH_REFRESH_EVERY_HOURS or age_h >= AUTH_MAX_AGE_HOURS
