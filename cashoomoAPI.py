# Drake Hooks + WaterTrooper
# Casino Claim 3 - Cashoomo API
# Version 6.0 | 2026-11-18
# Observable state machine, native login event diagnostics, and controlled
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
from selenium.webdriver.common.keys import Keys

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
# Optional: wait for a human to finish a CAPTCHA/2FA in the remote Chrome window.
# Off by default so a scheduled worker never gets stuck for minutes.
MANUAL_LOGIN_WAIT = min(300, max(0, int(os.getenv("CASHOOMO_MANUAL_LOGIN_WAIT_SECONDS", "0"))))
# Optional guarded Enter fallback ONLY if the first native click was not seen
# by the document and the login form remains unchanged. Off by default.
ENTER_FALLBACK = os.getenv("CASHOOMO_LOGIN_ENTER_FALLBACK", "0").lower() in {"1", "true", "yes"}

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
// Expose only categories and booleans. Never return credential values.
const submit=login ? Array.from(login.querySelectorAll(
  'button,[role="button"],input[type="submit"],[data-event_name],div[class*="btn-"],div[class*="button"]'))
  .filter(shown).filter(e=>{
    const label=norm(e.getAttribute('aria-label')||text(e));
    const ev=norm(e.getAttribute('data-event_name'));
    return /^(log in|login|sign in)$/.test(label) || ev==='submit login';
  }) : [];
const activeSubmit=submit.find(e => e.getAttribute('data-event_name')==='Submit Login')||submit[0];
const typedEmail=emailFields.find(e=>login&&login.contains(e));
const typedPassword=passwords.find(e=>login&&login.contains(e));
const validationErrors=login ? Array.from(login.querySelectorAll(
  '[role="alert"],[aria-live="assertive"],[class*="error" i],'+
  '[class*="invalid" i],[class*="validation" i]'))
  .filter(shown).map(text).filter(t=>t&&t.length<=180).slice(0,6) : [];
const trace=window.__cashoomoLoginTrace||{};
return {
  url: location.href, pageReady: document.readyState, loginVisible: !!login,
  emailVisible: emailFields.length>0, passwordVisible: passwords.length>0,
  authenticated:signedIn, challengeVisible:challenge, currency, profile,
  buyCoins, dailyTile, rewardOpen: !!reward, rewardText,
  claimCount:claimControls.length,
  enabledClaimCount:claimControls.filter(e=>!disabled(e)).length,
  alerts:alerts.join(' | ').slice(0,550), toasts:toasts.join(' | ').slice(0,400),
  overlays, pageSummary:pageText.slice(0,300),
  formErrors:validationErrors.join(' | ').slice(0,450),
  emailPopulated:Boolean(typedEmail&&typedEmail.value.length),
  passwordPopulated:Boolean(typedPassword&&typedPassword.value.length),
  emailValid:typedEmail ? typedEmail.validity.valid : null,
  passwordValid:typedPassword ? typedPassword.validity.valid : null,
  submitVisible:Boolean(activeSubmit),
  submitDisabled:activeSubmit ? Boolean(activeSubmit.disabled ||
     activeSubmit.getAttribute('aria-disabled')==='true' ||
     getComputedStyle(activeSubmit).pointerEvents==='none') : null,
  traceClicks:trace.clicks||0, traceSubmits:trace.submits||0,
  traceInvalid:trace.invalid||0
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


# Select the *actual submit control* within the visible email/password dialog.
# Avoid div wrappers whose combined text accidentally reads "LOG IN".
# Only a native user-style click is allowed (no form.submit() or JS click).
LOGIN_TARGET_JS = r"""
const norm=s=>String(s||'').replace(/\s+/g,' ').trim().toLowerCase();
const shown=e=>{if(!e)return false;const r=e.getBoundingClientRect();
 const s=getComputedStyle(e);return r.width>0&&r.height>0&&s.display!=='none'&&
 s.visibility!=='hidden'&&Number(s.opacity)>0;};
const password=Array.from(document.querySelectorAll('input[type="password"]')).find(shown);
const mail='input[type="email"],input[autocomplete="username"],'+
 'input[name*="email" i],input[placeholder*="email" i],input[id*="email" i]';
if(!password)return {element:null,reason:'no visible password field'};
let root=password.closest('form');
if(!root||!root.querySelector(mail)){
 root=null;
 for(let n=password.parentElement,i=0;n&&i<12;n=n.parentElement,i++){
   if(n.querySelector(mail)&&n.querySelector('button,[role="button"],'+
        '[data-event_name],div[class*="btn-"],div[class*="button"]')){root=n;break;}
 }
}
if(!root)return {element:null,reason:'login dialog scope missing'};
const nodes=Array.from(root.querySelectorAll('button,input[type="submit"],'+
 '[role="button"],[data-event_name],div[class*="btn-"],div[class*="button"]'))
 .filter(shown);
let best=null;
for(const el of nodes){
 let label=norm(el.getAttribute('aria-label')||el.innerText||el.textContent||el.value);
 const event=norm(el.getAttribute('data-event_name'));
 const cls=norm(el.className);
 const disabled=Boolean(el.disabled||el.getAttribute('aria-disabled')==='true'||
  getComputedStyle(el).pointerEvents==='none');
 let score=0;
 if(label==='log in'||label==='login')score+=950;
 if(label==='sign in')score+=850;
 if(event==='submit login')score+=1100;
 if(el.matches('button,input[type="submit"]'))score+=150;
 if(el.matches('[role="button"]'))score+=65;
 if(el.getAttribute('type')==='submit')score+=65;
 if(cls.includes('login')&&cls.includes('button'))score+=80;
 if(/google|facebook|apple|signup|sign up|create account|forgot|password reset|close|register/.test(label))score-=3000;
 if(/google|facebook|apple|signup|register|social/.test(event))score-=3000;
 if(disabled)score-=3000;
 if(!best||score>best.score)best={element:el,score,label,disabled,event,
    tag:el.tagName.toLowerCase()};
}
if(!best||best.score<900)return {element:null,reason:'no confident enabled login submit',
  candidates:nodes.length};
return best;
"""

# Event listeners observe whether Selenium's native click / browser validation
# reached the page. These are READ-ONLY diagnostics and never intercept requests.
LOGIN_TRACE_JS = r"""
window.__cashoomoLoginTrace={clicks:0,submits:0,invalid:0};
if(!window.__cashoomoLoginTraceInstalled){
 window.__cashoomoLoginTraceInstalled=true;
 document.addEventListener('click',e=>{
  const el=e.target&&e.target.closest && e.target.closest(
    'button,input[type="submit"],[role="button"],[data-event_name],div[class*="btn-"],div[class*="button"]');
  if(!el)return;
  const label=String(el.getAttribute('aria-label')||el.innerText||el.textContent||'')
    .replace(/\s+/g,' ').trim().toLowerCase();
  if(/^(log in|login|sign in)$/.test(label)||
     String(el.getAttribute('data-event_name')||'').toLowerCase()==='submit login'){
   window.__cashoomoLoginTrace.clicks++;
  }
 },true);
 document.addEventListener('submit',()=>{
   window.__cashoomoLoginTrace.submits++;
 },true);
 document.addEventListener('invalid',()=>{
   window.__cashoomoLoginTrace.invalid++;
 },true);
}
return true;
"""

# React and similar controlled fields can rerender after typing. The native
# setter is a fallback ONLY when ordinary Selenium typing fails its readback.
REACT_INPUT_FALLBACK_JS = r"""
const el=arguments[0], value=arguments[1];
if(!el||!(el instanceof HTMLInputElement))return false;
const d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');
if(!d||!d.set)return false;
d.set.call(el,value);
el.dispatchEvent(new Event('input',{bubbles:true}));
el.dispatchEvent(new Event('change',{bubbles:true}));
el.dispatchEvent(new Event('blur',{bubbles:true}));
return el.value===value;
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


def _type_field(driver, element, value: str, label: str) -> bool:
    """Type with browser keyboard events, then blur and check field retention."""
    try:
        element.click()
        element.clear()
        element.send_keys(value)
        # Validation libraries often update form state on change/blur.
        element.send_keys(Keys.TAB)
        actual = element.get_attribute('value')
        if actual == value:
            LOG.info("Cashoomo %s input retained typed value (%d chars)", label, len(value))
            return True
        LOG.info("Cashoomo %s field changed after typing; native setter fallback", label)
        if _script(driver, REACT_INPUT_FALLBACK_JS, element, value, default=False):
            return element.get_attribute('value') == value
        return False
    except (StaleElementReferenceException, WebDriverException) as exc:
        _propagate_browser_failure(exc)
        LOG.info("Cashoomo %s input was rerendered or became unavailable", label)
        return False


def _fill_credentials(driver, username: str, password: str) -> bool:
    """Never log secrets or place them into DOM debug payloads."""
    for attempt in range(2):
        pair = _fields(driver)
        if not pair:
            LOG.warning("Cashoomo: no matching visible email/password inputs")
            return False
        email, pwd = pair
        email_ok = _type_field(driver, email, username, 'email')
        # The email may trigger an entire form rerender; find fresh elements.
        fresh = _fields(driver)
        if fresh:
            email, pwd = fresh
        password_ok = _type_field(driver, pwd, password, 'password')
        refreshed = _fields(driver)
        if refreshed:
            email, pwd = refreshed
            try:
                values_ok = (email.get_attribute('value') == username and
                             pwd.get_attribute('value') == password)
            except (StaleElementReferenceException, WebDriverException) as exc:
                _propagate_browser_failure(exc)
                values_ok = False
            if values_ok and email_ok and password_ok:
                return True
        LOG.warning("Cashoomo inputs didn't retain values; retrying typing attempt %s",attempt+1)
    return False


def _submit_login(driver) -> Tuple[bool, str]:
    """Click the highest-confidence real Log In control once.

    Does not bypass CAPTCHA or call JS .click()/form.submit(). If a native
    click is blocked by an overlay, stops and reports the blocker instead.
    """
    _script(driver, LOGIN_TRACE_JS)
    item = _script(driver, LOGIN_TARGET_JS, default={})
    if not isinstance(item, dict) or item.get('element') is None:
        reason = (item or {}).get('reason', 'login submit not found') if isinstance(item,dict) else 'submit not found'
        LOG.warning('Cashoomo login submit discovery: %s', reason)
        return False, 'The Log In button could not be selected reliably'
    element = item['element']
    LOG.info('Cashoomo login submit selected: tag=%s score=%s event=%s',
             item.get('tag'), item.get('score'), item.get('event'))
    try:
        if not element.is_displayed() or not element.is_enabled():
            return False, 'The Log In button is disabled'
        driver.execute_script("arguments[0].scrollIntoView({block:'center',inline:'nearest'});", element)
        element.click()
        LOG.info('Cashoomo native login click dispatched')
        return True, 'Native login click performed'
    except ElementClickInterceptedException:
        LOG.warning('Cashoomo native login click blocked by a visible overlay')
        return False, 'The Log In button is obstructed by another element'
    except StaleElementReferenceException:
        LOG.warning('Cashoomo login button rerendered during click; no blind retry')
        return False, 'The Log In button changed while it was being clicked'
    except WebDriverException as exc:
        _propagate_browser_failure(exc)
        # A failed click may still have triggered the request. Do not send another.
        LOG.warning('Cashoomo login click failed: %s',type(exc).__name__)
        return False, 'The browser could not complete the login click'


def _login_problem(state: Dict[str, Any]) -> str:
    errors = _norm(state.get('formErrors', '')+' | '+state.get('alerts', '')).lower()
    if state.get('challengeVisible') or any(t in errors for t in
          ('captcha','verify you are human','verification required','two-factor','2fa')):
        return 'A verification step needs to be completed manually'
    if any(t in errors for t in ('invalid password','incorrect password','wrong password','invalid credentials')):
        return 'Cashoomo rejected the supplied credentials'
    if any(t in errors for t in ('too many attempts','rate limit','try again later','temporarily locked')):
        return 'Cashoomo is temporarily rate-limiting login'
    if any(t in errors for t in ('invalid email','enter a valid email','required field','please fill')):
        return 'The login form rejected an input value'
    if state.get('emailValid') is False or state.get('passwordValid') is False:
        return 'Browser form validation did not pass'
    if state.get('submitDisabled') is True:
        return 'The Log In button is disabled; review on-page requirements'
    if not state.get('emailPopulated') or not state.get('passwordPopulated'):
        return 'The site cleared one or both login fields after submission'
    if state.get('traceInvalid',0):
        return 'Browser input validation prevented login'
    if state.get('loginVisible'):
        if state.get('traceClicks',0):
            return 'Cashoomo kept the login form open after clicking Log In; check the screenshot for an on-page message'
        return 'No login click was observed by the page'
    return 'An authenticated session could not be confirmed'


def _log_login_diagnostics(state: Dict[str,Any]) -> None:
    """Log only non-secret structured facts. Never log form values."""
    LOG.warning('Cashoomo login diagnostics: phase=%s clicked=%s submits=%s invalid=%s '
        'fields_filled=%s/%s field_valid=%s/%s submit_visible=%s disabled=%s '
        'challenge=%s url=%s',
        _classify(state),state.get('traceClicks'),state.get('traceSubmits'),
        state.get('traceInvalid'),state.get('emailPopulated'),state.get('passwordPopulated'),
        state.get('emailValid'),state.get('passwordValid'),state.get('submitVisible'),
        state.get('submitDisabled'),state.get('challengeVisible'),
        str(state.get('url','')).split('?')[0])


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
    credentials = os.getenv('CASHOOMO', '').strip()
    if ':' not in credentials:
        return False, 'Missing CASHOOMO=email:password in the environment'
    username, password = credentials.split(':', 1)
    if not username or not password:
        return False, 'Login credentials are incomplete'

    state = _observe(driver)
    if state.get('authenticated') and not state.get('loginVisible'):
        return True, 'Authenticated'
    runner.transition('login', state)
    if not state.get('loginVisible'):
        if not _click(driver, 'login_open', 750):
            return False, 'Log In control not found'
        state, ready = await _poll(driver, lambda s: s.get('loginVisible'), 12)
        runner.transition('login_form', state)
        if not ready:
            return False, 'Login form did not open'

    # Be sure the actual visible form is populated and focus has left the input.
    if not _fill_credentials(driver, username, password):
        return False, 'The email/password fields did not retain their values'
    preflight = _observe(driver)
    runner.transition('login_ready', preflight)
    if preflight.get('challengeVisible'):
        return False, 'The site requires manual verification before login'
    if preflight.get('emailValid') is False or preflight.get('passwordValid') is False:
        return False, 'The login form reports an invalid field'
    if preflight.get('submitDisabled') is True:
        return False, 'The Log In button is disabled'

    submitted, reason = _submit_login(driver)
    if not submitted:
        _log_login_diagnostics(_observe(driver))
        return False, reason
    runner.transition('login_submitted', _observe(driver))

    # Never blindly submit again: a request can be pending even when the form
    # remains visible. Let the site finish, then expose the exact observed state.
    state, done = await _poll(
        driver,
        lambda s: 'authenticated' if s.get('authenticated') and not s.get('loginVisible')
        else 'challenge' if s.get('challengeVisible')
        else 'rejected' if re.search(
            r'invalid|incorrect|wrong password|credentials|locked|too many attempts|'
            r'try again later|verification required',
            _norm(s.get('formErrors','')+' | '+s.get('alerts','')),re.I)
        else None,
        LOGIN_TIMEOUT,
    )
    runner.transition('login_result',state)
    if done=='authenticated':
        LOG.info('Cashoomo confirmed authenticated session')
        return True,'Authenticated'

    # If the site demands a human verification step, an operator can finish it
    # in the remote Chrome browser. The script never bypasses the challenge.
    if done=='challenge' and MANUAL_LOGIN_WAIT:
        LOG.info('Cashoomo waiting up to %ds for manual verification', MANUAL_LOGIN_WAIT)
        state, manual_ok = await _poll(driver,
           lambda s: s.get('authenticated') and not s.get('loginVisible'),
           MANUAL_LOGIN_WAIT)
        if manual_ok:
            LOG.info('Cashoomo manual verification completed successfully')
            return True, 'Authenticated after manual verification'

    # Controlled fallback for unusual custom form handlers. It requires an
    # explicit opt-in and zero observed clicks, so it is not a blind retry.
    if (ENTER_FALLBACK and state.get('loginVisible') and
        not state.get('challengeVisible') and
        not state.get('traceClicks') and not state.get('traceSubmits') and
        state.get('emailPopulated') and state.get('passwordPopulated') and
        not state.get('formErrors')):
        try:
            pair = _fields(driver)
            if pair:
                pair[1].send_keys(Keys.RETURN)
                LOG.warning('Cashoomo attempted one keyboard Enter login fallback')
                state, keyboard_ok = await _poll(driver,
                    lambda s: s.get('authenticated') and not s.get('loginVisible'),
                    min(15, LOGIN_TIMEOUT))
                if keyboard_ok:
                    return True,'Authenticated using keyboard submit'
        except WebDriverException as exc:
            _propagate_browser_failure(exc)
            LOG.warning('Cashoomo keyboard submit fallback was unavailable')

    _log_login_diagnostics(state)
    return False,_login_problem(state)


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
