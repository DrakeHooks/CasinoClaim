# Drake Hooks + WaterTrooper
# Casino Claim 3 - Cashoomo API
# Version 5.0 | 2026-11-18
# Conservative, observable state machine for the current Cashoomo login and
# seven-day Daily Reward experience. Never retries an ambiguous claim.
# Public callable compatibility: cashoomo_casino(ctx, driver, channel)
#                                claim_cashoomo_bonus(ctx, driver, channel)

import asyncio
import io
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import discord
from dotenv import load_dotenv
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    InvalidSessionIdException,
    NoSuchElementException,
    NoSuchWindowException,
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.common.by import By

load_dotenv()
LOG = logging.getLogger("CasinoClaim.Cashoomo")
SITE_URL = "https://cashoomo.com/"
MAIN_URL = "https://cashoomo.com/main"
CASHOOMO_CRED = os.getenv("CASHOOMO")  # Compatibility with older code.

# Keep the original selectors for compatibility and controlled fallbacks.
LOGIN_BUTTON_XPATH = "//div[@class='btn-secondary size-lg']"
EMAIL_INPUT_XPATH = "//input[@type='email']"
PASSWORD_INPUT_XPATH = "//input[@type='password']"
LOGIN_SUBMIT_XPATH = "//div[@data-event_name='Submit Login']"
REWARD_WIDGET_XPATH = "//div[@class='widget widget__daily-reward']"
CLAIM_BUTTON_XPATH = "//div[contains(@class, 'modal-daily-bonus-claim__button')]"

LOGIN_TIMEOUT = max(15, int(os.getenv("CASHOOMO_LOGIN_TIMEOUT", "45")))
REWARD_TIMEOUT = max(8, int(os.getenv("CASHOOMO_REWARD_TIMEOUT", "18")))
VERIFY_TIMEOUT = max(8, int(os.getenv("CASHOOMO_VERIFY_TIMEOUT", "18")))
SCREENSHOTS = os.getenv("CASHOOMO_SCREENSHOTS", "1").lower() not in {"0", "false", "no"}
POLL_INTERVAL = 0.6

FATAL_BROWSER_PHRASES = (
    "invalid session id", "session deleted", "not attached to an active page",
    "aborted by navigation", "chrome not reachable", "disconnected: not connected",
    "not connected to devtools", "target window already closed", "no such window",
    "tab crashed", "chrome failed to start", "session not created",
)


def _propagate_browser_failure(exc: Exception) -> None:
    """Leave broken Chrome sessions visible to main.py's driver recovery."""
    if isinstance(exc, (InvalidSessionIdException, NoSuchWindowException)):
        raise exc
    if isinstance(exc, WebDriverException) and any(
        phrase in str(exc).lower() for phrase in FATAL_BROWSER_PHRASES
    ):
        raise exc


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _safe_reason(value: str, limit: int = 110) -> str:
    """A short, non-sensitive description; never include credentials in Discord."""
    value = _norm(value)
    value = re.sub(r"[\w.+%-]+@[\w.-]+\.[A-Za-z]{2,}", "[email hidden]", value)
    value = re.sub(r"(?i)(password|token|otp|verification code)\s*[:=]\s*\S+", r"\1=[hidden]", value)
    return value[:limit]


def _script(driver, script: str, *args, default=None):
    try:
        return driver.execute_script(script, *args)
    except Exception as exc:
        _propagate_browser_failure(exc)
        LOG.warning("DOM inspection failed: %s", type(exc).__name__)
        return default


def _navigate(driver, address: str) -> bool:
    try:
        driver.get(address)
        return True
    except Exception as exc:
        _propagate_browser_failure(exc)
        LOG.warning("Navigation failed: %s", type(exc).__name__)
        return False


# This JavaScript returns a small, safe-to-log UI snapshot. It intentionally
# does not return email/password field values or hidden page markup.
# Both page classification and candidate selection use the same DOM conventions.
UI_JS = r"""
const norm = s => String(s || '').replace(/\s+/g,' ').trim().toLowerCase();
const shown = e => {
  if (!e) return false;
  const r = e.getBoundingClientRect(), s = getComputedStyle(e);
  return r.width > 0 && r.height > 0 && s.display !== 'none' &&
    s.visibility !== 'hidden' && Number(s.opacity) > 0;
};
const text = e => (e && (e.innerText || e.textContent) || '').replace(/\s+/g,' ').trim();
const visible = sel => Array.from(document.querySelectorAll(sel)).filter(shown);
const emailSelector = 'input[type="email"], input[autocomplete="username"], '+
  'input[name*="email" i], input[placeholder*="email" i], input[id*="email" i]';
const passwords = visible('input[type="password"]');
const emailFields = visible(emailSelector);
function loginRoot() {
  for (const p of passwords) {
    const form = p.closest('form');
    if (form && form.querySelector(emailSelector)) return form;
    for (let n=p.parentElement, i=0; n && i<10; n=n.parentElement,i++) {
      if (n.querySelector(emailSelector) &&
          n.querySelector('button,[role="button"],[data-event_name]')) return n;
    }
  }
  return null;
}
function rewardRoot() {
  const headings=visible('h1,h2,h3,h4,[role="heading"],span,div').filter(e =>
     norm(text(e)) === 'daily reward' &&
     (e.children.length <= 2 || e.matches('h1,h2,h3,h4,[role="heading"]')));
  for (const h of headings) {
    for (let n=h.parentElement,i=0; n && i<10; n=n.parentElement,i++) {
      const t=norm(text(n));
      if (t.length >= 35 && t.length <= 4000 && t.includes('day 1') &&
          (t.includes('day 7') || t.includes('claim reward') || t.includes('boost rewards'))) return n;
    }
  }
  // Old modal classes remain valid when the exact new heading changes.
  for (const e of visible('[class*="modal-daily-bonus" i],[class*="daily-reward-modal" i]')) {
    const t=norm(text(e));
    if (t.includes('day 1') && (t.includes('claim') || t.includes('claimed'))) return e;
  }
  return null;
}
const login=loginRoot(), reward=rewardRoot();
const pageText=text(document.body).slice(0,5500);
const accountSelectors='.coins__toggler,button.btn-deposit,[class*="coins__toggler"],'+
  '[class*="account-balance" i], [class*="balance__" i]';
const currency=visible(accountSelectors).length > 0;
const profile=visible('[class*="profile" i],[class*="user-menu" i],[class*="user-info" i]')
 .some(e => norm(text(e)).length > 0 && norm(text(e)).length < 250);
const buyCoins=visible('button,a,[role="button"],div[class*="btn-"]').some(e =>
  /^(buy|buy coins)$/.test(norm(text(e)).slice(0,30)));
const dailyTile=visible('.widget__daily-reward,[class*="widget__daily-reward" i],'+
  '[class*="widget__daily-bonus" i]').length > 0 ||
  visible('button,a,[role="button"],[class*="widget" i]').some(e =>
    ['daily bonus','daily reward'].includes(norm(text(e))) && norm(text(e)).length < 28);
// Requiring multiple independent signals prevents the public page from being
// mistaken for an authenticated lobby. An open login dialog takes precedence.
const signedIn=!login && !passwords.length &&
  ((currency && (profile || buyCoins || dailyTile || location.pathname.startsWith('/main'))) ||
   (location.pathname.startsWith('/main') && dailyTile && (profile || buyCoins)));
const alerts=visible('[role="alert"],[role="status"],[class*="error" i],'+
  '[class*="validation" i],[class*="toast" i]')
 .map(text).filter(t => t.length>0 && t.length<220).slice(0,8);
const frames=visible('iframe');
const challenge=frames.some(f => /captcha|turnstile|challenge|recaptcha|hcaptcha/i.test(
  (f.title||'')+' '+(f.getAttribute('src')||''))) ||
  visible('[class*="captcha" i],[class*="turnstile" i],input[autocomplete="one-time-code"]').length>0;
const overlays=visible('[role="dialog"],[aria-modal="true"],'+
   '[class*="modal" i],[class*="popup" i],[class*="overlay" i]')
 .filter(e => { const t=norm(text(e)); return t.length>5 && t.length<1800; })
 .map(e=>({name:norm((e.getAttribute('aria-label')||'')+' '+(e.className||'')).slice(0,85),
           text:norm(text(e)).slice(0,150)})).slice(0,8);
const rewardText=reward ? text(reward).slice(0,2200) : '';
const rewardButtons=reward ? Array.from(reward.querySelectorAll(
  'button,[role="button"],[data-event_name],[class*="button" i]')).filter(shown) : [];
const claimControls=rewardButtons.filter(e => {
  const own=norm(e.getAttribute('aria-label')||text(e));
  return own === 'claim reward' || own === 'collect' || own === 'claim' ||
    (norm(e.className).includes('modal-daily-bonus-claim__button') &&
     !/boost|buy|purchase|checkout/i.test(own));
});
const disabled=e => !!e.disabled || e.getAttribute('aria-disabled')==='true' ||
  norm(e.className).includes('disabled');
const toasts=visible('[role="alert"],[role="status"],[class*="toast" i],'+
  '[class*="snackbar" i]').map(text).filter(t=>t.length>0&&t.length<260);
return {
  url: location.href, pageReady: document.readyState, loginVisible: !!login,
  emailVisible: emailFields.length>0, passwordVisible: passwords.length>0,
  authenticated:signedIn, challengeVisible:challenge, currency, profile,
  buyCoins, dailyTile, rewardOpen: !!reward, rewardText,
  claimCount:claimControls.length,
  enabledClaimCount:claimControls.filter(e=>!disabled(e)).length,
  alerts:alerts.join(' | ').slice(0,550), toasts:toasts.join(' | ').slice(0,400),
  overlays, pageSummary:pageText.slice(0,300)
};
"""


# Candidate scores are recalculated on the live page, and click targets are
# limited to the expected scope for that stage. The ID tags aren't durable;
# callers must use them immediately and re-check state before a critical click.
CANDIDATES_JS = r"""
const stage = arguments[0];
const norm = s => String(s || '').replace(/\s+/g,' ').trim().toLowerCase();
const shown = e => {
  if (!e) return false;
  const r=e.getBoundingClientRect(),s=getComputedStyle(e);
  return r.width>0 && r.height>0 && s.display!=='none' &&
    s.visibility!=='hidden' && Number(s.opacity)>0;
};
const text=e => (e && (e.innerText || e.textContent) || '').replace(/\s+/g,' ').trim();
const controls='button,a,[role="button"],[data-event_name],'+
  'div[class*="btn-"],div[class*="button"],div[class*="widget"],'+
  'div[class*="daily-bonus"],div[class*="daily-reward"]';
const password=Array.from(document.querySelectorAll('input[type="password"]')).find(shown);
const emailSel='input[type="email"],input[autocomplete="username"],'+
    'input[name*="email" i],input[placeholder*="email" i],input[id*="email" i]';
function loginRoot() {
  if (!password) return null;
  const form=password.closest('form');
  if (form && form.querySelector(emailSel) &&
      form.querySelector('button,[role="button"],[data-event_name]')) return form;
  for(let n=password.parentElement,i=0; n&&i<10;n=n.parentElement,i++){
    if(n.querySelector(emailSel)&&n.querySelector('button,[role="button"],[data-event_name]'))return n;
  }
  return null;
}
function rewardRoot(){
 const heading=Array.from(document.querySelectorAll('h1,h2,h3,h4,span,div,[role="heading"]'))
   .find(e=>shown(e)&&norm(text(e))==='daily reward'&&
     (e.children.length<=2||e.matches('h1,h2,h3,h4,[role="heading"]')));
 if(heading){for(let n=heading.parentElement,i=0;n&&i<10;n=n.parentElement,i++){
   const t=norm(text(n));
   if(t.length>=35&&t.length<=4000&&t.includes('day 1')&&
      (t.includes('day 7')||t.includes('claim reward')||t.includes('boost rewards')))return n;
 }}
 return Array.from(document.querySelectorAll('[class*="modal-daily-bonus" i]'))
   .find(e=>shown(e)&&norm(text(e)).includes('day 1'))||null;
}
const login=loginRoot(), reward=rewardRoot();
let scope=document;
if(stage==='login_submit')scope=login;
if(stage==='claim')scope=reward;
if(!scope)return [];
if(stage==='login_open'&&password)return [];
let pop=null;
if(stage==='dismiss_popup') {
  const all=Array.from(document.querySelectorAll('[role="dialog"],[aria-modal="true"],'+
    '[class*="modal" i],[class*="popup" i]')).filter(shown);
  pop=all.find(e=> {
    if(login&&e.contains(login))return false;
    if(reward&&e.contains(reward))return false;
    const t=norm(text(e)).slice(0,1500);
    if(/captcha|verify|verification|security|payment|checkout|account/i.test(t))return false;
    if(/daily reward|claim reward|day 1.*day 7/.test(t))return false;
    return /promotion|special offer|welcome|congratulations|bonus offer|deal|discount/i.test(t);
  });
  if(!pop)return [];
  scope=pop;
}
const all=Array.from(scope.querySelectorAll(controls)).filter(shown);
const results=[];
for(let i=0;i<all.length;i++) {
 const el=all[i];
 // Don't treat a generic wrapper as a safe button unless it has strong evidence.
 const actualText=norm(text(el));
 const own=(actualText || norm(el.getAttribute('aria-label') ||
   el.getAttribute('title') || el.getAttribute('value'))).slice(0,140);
 const cls=norm(el.className), event=norm(el.getAttribute('data-event_name'));
 const disabled=!!el.disabled||el.getAttribute('aria-disabled')==='true'||
   cls.includes('disabled');
 let score=0;const why=[];
 const add=(n,label)=>{score+=n;why.push(label);};
 if(stage==='login_open'){
   if(['log in','login','sign in'].includes(own)) add(850,'exact login label');
   else if(/^log in\s{1,2}$/.test(own))add(800,'login label');
   if(event==='login'||event==='open login')add(350,'login event');
   if(cls.includes('btn-secondary')&&own.includes('log in'))add(140,'legacy login class');
 }else if(stage==='login_submit'){
   if(['log in','login','sign in'].includes(own))add(1000,'exact submit text');
   if(event==='submit login')add(700,'submit-login event');
   if(el.getAttribute('type')==='submit')add(180,'submit type');
   if(el.closest('form'))add(100,'within login form');
 }else if(stage==='daily_tile'){
   if(cls.includes('widget__daily-reward')||cls.includes('widget__daily-bonus'))add(1000,'daily widget class');
   if(['daily bonus','daily reward'].includes(own))add(900,'exact daily label');
   else if(own.includes('daily bonus')&&own.length<65)add(550,'daily bonus label');
   if(cls.includes('widget'))add(100,'widget');
   const parent=norm(text(el.parentElement)).slice(0,170);
   if(parent.includes('daily bonus'))add(120,'local daily context');
   if(/daily quest|daily spin|lucky wheel|boost rewards/i.test(parent))add(-1800,'unrelated daily item');
 }else if(stage==='claim'){
   if(own==='claim reward')add(1100,'exact Claim Reward');
   if(own==='claim'||own==='collect')add(450,'claim action');
   if(cls.includes('modal-daily-bonus-claim__button'))add(620,'legacy claim class');
   if(event.includes('claim')&&event.includes('reward'))add(350,'claim event');
   add(300,'verified Daily Reward modal');
 }else if(stage==='dismiss_popup'){
   if(['close','dismiss','×','x'].includes(own))add(900,'close popup');
   if(/close/i.test(el.getAttribute('aria-label')||''))add(750,'close aria label');
   if(/(?:^|[-_ ])close(?:$|[-_ ])/i.test(cls))add(550,'close class');
   if(el.getAttribute('type')==='submit')add(-900,'submit is not close');
 }
 if(/buy|purchase|checkout|boost|deposit|sign up|register|google|facebook|apple|claim my gift|pay|subscribe/i.test(own))
   add(-2500,'unrelated or purchase action');
 if(stage==='claim'&&(/purchase|order summary|payment method|checkout/i.test(norm(text(reward)).slice(0,500))))
   add(-1600,'purchase overlay');
 if(disabled)add(-2500,'disabled');
 if(score<400)continue;
 // Prefer native click targets when scores are otherwise comparable.
 if(el.matches('button,[role="button"]'))add(60,'interactive control');
 const id='cc-'+stage+'-'+Date.now()+'-'+i;
 el.setAttribute('data-cashoomo-candidate',id);
 results.push({id,score,text:own.slice(0,70),reasons:why,disabled});
}
results.sort((a,b)=>b.score-a.score);
const distinct=[];
for(const c of results){
 const e=document.querySelector('[data-cashoomo-candidate="'+c.id+'"]');
 if(distinct.some(other=>{
  const o=document.querySelector('[data-cashoomo-candidate="'+other.id+'"]');
  return e&&o&&(o.contains(e)||e.contains(o));
 }))continue;
 distinct.push(c);
}
return distinct.slice(0,8);
"""


# CSS hiding, not value clearing: user inputs remain intact. The change is
# temporary and restored in a finally block following screenshot capture.
REDACT_JS = r"""
window.__cashoomo_redactions = [];
const fields=document.querySelectorAll('input[type="email"],input[type="password"],'+
  'input[autocomplete="username"],input[name*="email" i],'+
  'input[placeholder*="email" i],input[autocomplete="one-time-code"]');
for(const field of fields){
 window.__cashoomo_redactions.push([field,field.getAttribute('style')]);
 field.style.setProperty('filter','blur(18px)','important');
 field.style.setProperty('-webkit-filter','blur(18px)','important');
}
return window.__cashoomo_redactions.length;
"""
RESTORE_JS = r"""
for(const [field, original] of (window.__cashoomo_redactions||[])){
 if(original===null)field.removeAttribute('style');else field.setAttribute('style',original);
}
window.__cashoomo_redactions=[];
"""


@dataclass
class RunState:
    phase: str = "initial"
    claim_clicked: bool = False
    last_page_state: str = "unknown"
    transitions: List[str] = field(default_factory=list)

    def transition(self, phase: str, snapshot: Dict[str, Any]) -> None:
        description = _classify(snapshot)
        if (phase, description) != (self.phase, self.last_page_state):
            LOG.info("Cashoomo state: %s -> %s (url=%s)", phase, description,
                     str(snapshot.get("url", "")).split("?")[0])
            self.transitions.append(f"{phase}:{description}")
        self.phase, self.last_page_state = phase, description


def _observe(driver) -> Dict[str, Any]:
    value = _script(driver, UI_JS, default={})
    return value if isinstance(value, dict) else {}


def _classify(state: Dict[str, Any]) -> str:
    """Page-state classification with priority for actionable overlays."""
    if not state:
        return "unknown"
    if state.get("challengeVisible"):
        return "verification_challenge"
    if state.get("loginVisible") or state.get("passwordVisible"):
        return "login_dialog"
    if state.get("rewardOpen"):
        return "daily_reward_modal"
    if state.get("authenticated") and state.get("dailyTile"):
        return "authenticated_lobby_daily_tile"
    if state.get("authenticated"):
        return "authenticated_lobby"
    if state.get("pageReady") == "loading":
        return "loading"
    return "public_or_unknown"


def _is_logged_in(driver) -> bool:
    state = _observe(driver)
    return bool(state.get("authenticated")) and not state.get("loginVisible")


def _candidates(driver, stage: str, minimum: int) -> List[Dict[str, Any]]:
    found = _script(driver, CANDIDATES_JS, stage, default=[]) or []
    if not isinstance(found, list):
        return []
    for candidate in found[:4]:
        LOG.info("Candidate %s: score=%s label=%r evidence=%s", stage,
                 candidate.get("score"), candidate.get("text"), candidate.get("reasons"))
    accepted = [x for x in found if not x.get("disabled") and x.get("score", 0) >= minimum]
    if len(accepted) > 1 and accepted[0]["score"] - accepted[1]["score"] < 100:
        LOG.warning("Ambiguous %s candidates; no click", stage)
        return []
    return accepted


def _click(driver, stage: str, minimum: int) -> bool:
    choices = _candidates(driver, stage, minimum)
    if not choices:
        return False
    identifier = choices[0].get("id", "")
    if not identifier:
        return False
    try:
        element = driver.find_element(
            By.CSS_SELECTOR, '[data-cashoomo-candidate="' + identifier + '"]'
        )
        if not element.is_displayed() or not element.is_enabled():
            return False
        driver.execute_script("arguments[0].scrollIntoView({block:'center',inline:'nearest'});", element)
        # Do not bypass a blocking overlay with JS for a claim or login submit.
        element.click()
        LOG.info("Clicked %s (score=%s)", stage, choices[0].get("score"))
        return True
    except (ElementClickInterceptedException, StaleElementReferenceException,
            NoSuchElementException, WebDriverException) as exc:
        _propagate_browser_failure(exc)
        LOG.warning("Click %s blocked/failed: %s", stage, type(exc).__name__)
        return False


def _fields(driver) -> Optional[Tuple[Any, Any]]:
    """Find a visible matching email/password pair in the same login form."""
    try:
        inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="password"]')
        for pwd in inputs:
            if not pwd.is_displayed():
                continue
            root = _script(driver, r"""
              const p=arguments[0];
              const sel='input[type="email"],input[autocomplete="username"],'+
                'input[name*="email" i],input[placeholder*="email" i],input[id*="email" i]';
              const form=p.closest('form');
              if(form&&form.querySelector(sel))return form;
              for(let n=p.parentElement,i=0;n&&i<10;n=n.parentElement,i++){
                if(n.querySelector(sel))return n;
              }
              return null;
            """, pwd)
            if root is None:
                continue
            for email in root.find_elements(By.CSS_SELECTOR,
                'input[type="email"],input[autocomplete="username"],'
                'input[name*="email" i],input[placeholder*="email" i],input[id*="email" i]'):
                if email.is_displayed():
                    return email, pwd
    except (StaleElementReferenceException, WebDriverException) as exc:
        _propagate_browser_failure(exc)
        LOG.info("Login form rerendered while locating fields")
    return None


def _fill_credentials(driver, username: str, password: str) -> bool:
    for attempt in range(2):
        pair = _fields(driver)
        if not pair:
            return False
        email, pwd = pair
        try:
            email.clear()
            email.send_keys(username)
            pwd.clear()
            pwd.send_keys(password)
            # Compare without logging or sending any entered values.
            return (email.get_attribute("value") == username and
                    pwd.get_attribute("value") == password)
        except (StaleElementReferenceException, WebDriverException) as exc:
            _propagate_browser_failure(exc)
            LOG.warning("Login form changed while typing, attempt %d", attempt + 1)
    return False


def _login_problem(state: Dict[str, Any]) -> str:
    errors = _norm(state.get("alerts", ""))
    if errors and re.search(r"invalid|incorrect|wrong|failed|locked|suspended|try again|error", errors, re.I):
        # Avoid echoing arbitrary site text or any embedded sensitive fields.
        return "The login form reported an error"
    if state.get("challengeVisible"):
        return "A verification step is visible"
    if state.get("passwordVisible") or state.get("loginVisible"):
        return "The login form is still open"
    return "An authenticated session could not be confirmed"


def _claim_state(state: Dict[str, Any], *, clicked: bool = False) -> Optional[str]:
    """Conservative result classifier; no success based only on modal removal."""
    rewards = _norm(state.get("rewardText", "")).lower()
    toasts = _norm(state.get("toasts", "")).lower()
    all_evidence = rewards + " | " + toasts
    confirmations = (
        "reward claimed", "reward collected", "claimed successfully",
        "successfully claimed", "claim successful", "you have claimed",
        "daily bonus claimed", "already claimed", "come back tomorrow",
    )
    if any(term in all_evidence for term in confirmations):
        return "claimed"
    if not clicked and state.get("rewardOpen"):
        pending = (
            "available in", "next reward in", "next claim in",
            "available tomorrow", "next reward", "come back in",
        )
        if any(term in rewards for term in pending):
            return "unavailable"
    return None


async def _poll(driver, predicate, duration: float, interval: float = POLL_INTERVAL):
    """Bounded polling without unnecessary fixed 10-second sleeps."""
    stop = time.monotonic() + duration
    latest = _observe(driver)
    while True:
        result = predicate(latest)
        if result:
            return latest, result
        if time.monotonic() >= stop:
            return latest, None
        await asyncio.sleep(interval)
        latest = _observe(driver)


def _capture_screenshot(driver) -> Optional[bytes]:
    """Blur visible credential inputs, then return PNG without persisting a file."""
    if not SCREENSHOTS or driver is None:
        return None
    redacted = False
    try:
        _script(driver, REDACT_JS)
        redacted = True
        return driver.get_screenshot_as_png()
    except Exception as exc:
        _propagate_browser_failure(exc)
        LOG.warning("Screenshot failed: %s", type(exc).__name__)
        return None
    finally:
        if redacted:
            _script(driver, RESTORE_JS)


async def _report(channel, description: str, driver=None) -> None:
    """Exactly one plain Discord message per completed run, with an attachment."""
    if channel is None:
        return
    message = "Cashoomo: " + _safe_reason(description, 170)
    screenshot = _capture_screenshot(driver)
    try:
        if screenshot:
            await channel.send(message, file=discord.File(io.BytesIO(screenshot),
                                                          filename="cashoomo_state.png"))
        else:
            await channel.send(message)
    except Exception as exc:
        # Network/Discord errors don't justify repeating a claim.
        LOG.warning("Couldn't send Cashoomo Discord status: %s", type(exc).__name__)


async def _prepare_page(driver, runner: RunState) -> Dict[str, Any]:
    """Resolve initial page loading and recognise popups before login or reward."""
    state, _ = await _poll(driver, lambda s: (
        s.get("authenticated") or s.get("loginVisible") or s.get("rewardOpen") or
        (s.get("pageReady") == "complete" and len(s.get("pageSummary", "")) > 45)
    ), 10)
    runner.transition("initial", state)
    return state


async def _login(driver, runner: RunState) -> Tuple[bool, str]:
    credentials = os.getenv("CASHOOMO", "").strip()
    if ":" not in credentials:
        return False, "Missing CASHOOMO=email:password in the environment"
    username, password = credentials.split(":", 1)
    if not username or not password:
        return False, "Login credentials are incomplete"

    state = _observe(driver)
    if state.get("authenticated") and not state.get("loginVisible"):
        return True, "Authenticated"
    runner.transition("login", state)
    if not state.get("loginVisible"):
        if not _click(driver, "login_open", 750):
            return False, "Log In control not found"
        state, ready = await _poll(driver, lambda s: s.get("loginVisible"), 12)
        runner.transition("login_form", state)
        if not ready:
            return False, "Login form did not open"

    if not _fill_credentials(driver, username, password):
        return False, "Login fields could not be completed"
    # At most one submit; a pending challenge or ambiguous response stops here.
    if not _click(driver, "login_submit", 800):
        return False, "Login submit button could not be identified"
    runner.transition("login_submitted", _observe(driver))

    state, done = await _poll(
        driver,
        lambda s: "authenticated" if s.get("authenticated") and not s.get("loginVisible")
        else "error" if re.search(r"invalid|incorrect|wrong|failed|locked|suspended|try again",
                                  _norm(s.get("alerts", "")), re.I)
        else None,
        LOGIN_TIMEOUT,
    )
    runner.transition("login_result", state)
    if done == "authenticated":
        return True, "Authenticated"
    return False, _login_problem(state)


async def _open_reward(driver, runner: RunState) -> bool:
    state = _observe(driver)
    if state.get("rewardOpen"):
        runner.transition("daily_reward", state)
        return True
    if not state.get("authenticated"):
        return False

    # Sometimes a non-reward promotional popup blocks the tile. Only close
    # an explicitly identified promo popup. Never close login/reward/challenge.
    if not _click(driver, "daily_tile", 750):
        # One guarded popup dismissal attempt, then one fresh tile click.
        # Never dismiss login, Daily Reward, security or checkout dialogs.
        if not _click(driver, "dismiss_popup", 850):
            LOG.info("Daily Bonus tile not confidently identified")
            return False
        LOG.info("Dismissed an unrelated promotional popup")
        await asyncio.sleep(0.4)
        if not _click(driver, "daily_tile", 750):
            LOG.info("Daily Bonus tile still unavailable after popup dismissal")
            return False
    state, ready = await _poll(driver, lambda s: s.get("rewardOpen"), REWARD_TIMEOUT)
    runner.transition("reward_open", state)
    return bool(ready)


async def claim_cashoomo_bonus(ctx, driver, channel, runner: Optional[RunState] = None):
    """Daily claim entry point. Safe to call directly; no duplicate attempts."""
    runner = runner or RunState()
    state = _observe(driver)
    runner.transition("rewards_check", state)
    if not state.get("authenticated") or state.get("loginVisible"):
        await _report(channel, "Not authenticated. Reward was not attempted.", driver)
        return "login_required"
    if not await _open_reward(driver, runner):
        state = _observe(driver)
        await _report(channel,
                      "Daily Reward could not be opened. No claim attempted.", driver)
        return "unverified"

    before = _observe(driver)
    status = _claim_state(before)
    if status == "claimed":
        await _report(channel, "Daily Reward is already claimed.", driver)
        return status
    if status == "unavailable":
        await _report(channel, "Daily Reward is not available yet.", driver)
        return status

    candidates = _candidates(driver, "claim", 1050)
    if not candidates:
        await _report(channel, "Daily Reward is open but no enabled Claim Reward button was verified.", driver)
        return "unverified"
    runner.transition("claim_ready", before)
    if not _click(driver, "claim", 1050):
        await _report(channel, "Claim Reward could not be clicked. No claim confirmed.", driver)
        return "unverified"
    runner.claim_clicked = True
    LOG.info("Clicked Claim Reward once; never automatically retrying")
    state, status = await _poll(driver,
                                lambda s: _claim_state(s, clicked=True),
                                VERIFY_TIMEOUT)
    runner.transition("claim_result", state)
    if status == "claimed":
        await _report(channel, "Daily Reward claimed and confirmed.", driver)
        return "claimed"
    await _report(channel, "Claim Reward was clicked, but confirmation was not visible. Check the site.", driver)
    return "unverified"


async def cashoomo_casino(ctx, driver, channel):
    """Main CasinoClaim scheduler entry point; send one final message only."""
    runner = RunState()
    LOG.info("Cashoomo check started")
    try:
        if not _navigate(driver, SITE_URL):
            await _report(channel, "Site did not load. No claim attempted.", driver)
            return "navigation_failed"
        state = await _prepare_page(driver, runner)
        if not state.get("authenticated"):
            ok, explanation = await _login(driver, runner)
            if not ok:
                await _report(channel, "Login incomplete. " + explanation + ". No claim attempted.", driver)
                return "login_incomplete"
        state = _observe(driver)
        runner.transition("authenticated", state)
        if not state.get("authenticated"):
            await _report(channel, "Authenticated session could not be verified. No claim attempted.", driver)
            return "login_incomplete"

        if not state.get("dailyTile") and not state.get("rewardOpen"):
            # The lobby is the only supported fallback path. Login success may
            # already show the Daily Reward modal; don't navigate away from it.
            if not _navigate(driver, MAIN_URL):
                await _report(channel, "Could not open the main lobby. No claim attempted.", driver)
                return "navigation_failed"
            state, _ = await _poll(driver,
                lambda s: s.get("dailyTile") or s.get("rewardOpen") or s.get("loginVisible"), 10)
            runner.transition("main_lobby", state)
            if state.get("loginVisible") or not state.get("authenticated"):
                await _report(channel, "Authentication was lost when opening the lobby. No claim attempted.", driver)
                return "login_incomplete"

        return await claim_cashoomo_bonus(ctx, driver, channel, runner)
    except (InvalidSessionIdException, NoSuchWindowException):
        LOG.exception("Chrome session lost during Cashoomo")
        raise  # Let main.py recover the shared browser before the next casino.
    except WebDriverException as exc:
        _propagate_browser_failure(exc)
        LOG.exception("Nonfatal WebDriver error during Cashoomo")
        await _report(channel, "Browser interaction failed. Claim status is unknown.", driver)
        return "browser_error"
    except Exception:
        LOG.exception("Unexpected error during Cashoomo")
        await _report(channel, "Unexpected error. Claim status is unknown.", driver)
        return "error"
