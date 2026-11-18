# Drake Hooks + WaterTrooper
# Casino Claim 3 - Cashoomo API
# Version 4.0 | 2026-11-18
# Login -> verified authentication -> Daily Bonus -> Daily Reward -> one claim.
# Preserves main.py's callable signatures and original selectors as fallbacks.

import asyncio
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import discord
from dotenv import load_dotenv
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    InvalidSessionIdException,
    NoSuchWindowException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

load_dotenv()
LOG = logging.getLogger("CasinoClaim.Cashoomo")
CASHOOMO_CRED = os.getenv("CASHOOMO")  # Retained for compatibility.

SITE_URL = "https://cashoomo.com/"
MAIN_URL = "https://cashoomo.com/main"

# Retained for compatibility; the new flow prefers semantic candidates.
LOGIN_BUTTON_XPATH = "//div[@class='btn-secondary size-lg']"
EMAIL_INPUT_XPATH = "//input[@type='email']"
PASSWORD_INPUT_XPATH = "//input[@type='password']"
LOGIN_SUBMIT_XPATH = "//div[@data-event_name='Submit Login']"
REWARD_WIDGET_XPATH = "//div[@class='widget widget__daily-reward']"
CLAIM_BUTTON_XPATH = "//div[contains(@class,'modal-daily-bonus-claim__button')]"

LOGIN_TIMEOUT = max(10, int(os.getenv("CASHOOMO_LOGIN_TIMEOUT", "45")))
REWARD_TIMEOUT = max(5, int(os.getenv("CASHOOMO_REWARD_TIMEOUT", "15")))
VERIFY_TIMEOUT = max(5, int(os.getenv("CASHOOMO_VERIFY_TIMEOUT", "12")))
SEND_SCREENSHOTS = os.getenv("CASHOOMO_SCREENSHOTS", "1").lower() not in ("0", "false", "no")

FATAL_BROWSER_PHRASES = (
    "invalid session id", "session deleted", "not attached to an active page",
    "aborted by navigation", "chrome not reachable", "disconnected: not connected",
    "not connected to devtools", "target window already closed", "no such window",
    "session not created", "chrome failed to start", "tab crashed",
)


def _maybe_raise_browser_error(exc: Exception) -> None:
    """Let main.py's session recovery see a broken WebDriver."""
    if isinstance(exc, (InvalidSessionIdException, NoSuchWindowException)):
        raise exc
    if isinstance(exc, WebDriverException) and any(
        phrase in str(exc).lower() for phrase in FATAL_BROWSER_PHRASES
    ):
        raise exc


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _visible(element) -> bool:
    try:
        return bool(element.is_displayed())
    except (StaleElementReferenceException, WebDriverException) as exc:
        _maybe_raise_browser_error(exc)
        return False


def _js(driver, script: str, *args, fallback=None):
    try:
        return driver.execute_script(script, *args)
    except Exception as exc:
        _maybe_raise_browser_error(exc)
        LOG.warning("DOM inspection failed: %s", type(exc).__name__)
        return fallback


def _navigate(driver, url: str) -> bool:
    try:
        driver.get(url)
        WebDriverWait(driver, 18, poll_frequency=0.5).until(
            lambda d: d.execute_script("return document.readyState") in ("interactive", "complete")
        )
        return True
    except Exception as exc:
        _maybe_raise_browser_error(exc)
        LOG.warning("Navigation failed to %s: %s", url, exc)
        return False


# This does not read passwords or return hidden inputs; only visible UI text.
UI_STATE_JS = r"""
const shown = e => {
  if (!e) return false;
  const r = e.getBoundingClientRect(), s = getComputedStyle(e);
  return r.width > 0 && r.height > 0 && s.display !== 'none' &&
         s.visibility !== 'hidden' && s.opacity !== '0';
};
const txt = e => (e && (e.innerText || e.textContent) || '').replace(/\s+/g,' ').trim();
const fields = Array.from(document.querySelectorAll('input[type="password"]')).filter(shown);
const authModal = fields.length > 0;
const pageText = txt(document.body).slice(0,5500);
const currency = Array.from(document.querySelectorAll('.coins__toggler, button.btn-deposit, [class*="coins__toggler"]')).some(shown);
const tile = Array.from(document.querySelectorAll(
  '.widget__daily-reward, [class*="widget__daily-reward"], [class*="widget__daily-bonus"]'
)).some(shown);
// On the new authenticated page, the Daily Bonus tile and Buy Coins/navigation
// are together with account balances. The public login page lacks this combination.
const dailyName = Array.from(document.querySelectorAll('button,a,[role="button"], [class*="widget"], [class*="daily-bonus"], [class*="daily-reward"]'))
  .some(e => shown(e) && txt(e).toLowerCase() === 'daily bonus' && txt(e).length < 40);
const pageAuthenticated = !authModal && (currency || (
  (location.pathname.startsWith('/main') || dailyName) &&
  /\bbuy coins\b/i.test(pageText) && /\b(?:sc|gc)\b/i.test(pageText)
));
const errors = Array.from(document.querySelectorAll(
  '[role="alert"], [class*="error" i], [class*="validation" i]'
)).filter(shown).map(txt).filter(x => x.length > 0 && x.length < 300);
const alerts = errors.join(' | ').slice(0,700);
return {
  url: location.href,
  authModal, pageAuthenticated,
  currency, tile, dailyName,
  alerts,
  pageText: pageText.slice(0,1800)
};
"""


# Candidate scoring is computed on live visible DOM, not old absolute XPaths.
# Scores are attached to DOM nodes to allow a later Selenium click on that node.
CANDIDATES_JS = r"""
const stage = arguments[0];
const shown = e => {
  if (!e) return false;
  const r = e.getBoundingClientRect(), s = getComputedStyle(e);
  return r.width > 0 && r.height > 0 && s.display !== 'none' &&
         s.visibility !== 'hidden' && s.opacity !== '0';
};
const norm = s => String(s || '').replace(/\s+/g,' ').trim().toLowerCase();
const direct = el => Array.from(el.childNodes || [])
  .filter(n => n.nodeType === Node.TEXT_NODE)
  .map(n => n.textContent || '').join(' ').trim();
const label = el => {
  const own = norm(direct(el) || el.getAttribute('aria-label') ||
    el.getAttribute('title') || el.getAttribute('value') || el.innerText || '');
  return own.slice(0,120);
};
const password = Array.from(document.querySelectorAll('input[type="password"]')).find(shown);
let loginRoot = password && (password.closest('form') || password.closest('[role="dialog"]') ||
  password.closest('[class*="modal" i]'));
if (password && (!loginRoot || !loginRoot.querySelector('button,[role="button"],[data-event_name]'))) {
  let n = password.parentElement;
  for (let i=0; n && i<9; i++, n=n.parentElement) {
    if (n.querySelectorAll('input[type="password"]').length &&
        n.querySelector('button,[role="button"],[data-event_name]') &&
        norm(n.innerText).length < 1600) { loginRoot=n; break; }
  }
}
const heading = Array.from(document.querySelectorAll('h1,h2,h3,h4,[role="heading"],div,span'))
  .find(e => shown(e) && norm(e.innerText) === 'daily reward' &&
    (e.children.length <= 2 || e.matches('h1,h2,h3,h4,[role="heading"]')));
let rewardRoot = null;
if (heading) {
  for (let n=heading.parentElement, i=0; n && i<10; n=n.parentElement, i++) {
    const t=norm(n.innerText);
    if (t.length > 60 && t.length < 2600 && t.includes('day 1') &&
        (t.includes('claim reward') || t.includes('boost rewards') || t.includes('claimed'))) {
      rewardRoot=n; break;
    }
  }
}
const all = Array.from(document.querySelectorAll(
  'button,a,[role="button"],[data-event_name],div[class*="btn-"],'+
  'div[class*="button"],div[class*="widget"],div[class*="daily-bonus"],'+
  'div[class*="daily-reward"],span[class*="button"]'
));
const results=[];
all.forEach((el, i) => {
  if (!shown(el)) return;
  if (stage === 'login_submit' && (!loginRoot || !loginRoot.contains(el))) return;
  if (stage === 'reward_claim' && (!rewardRoot || !rewardRoot.contains(el))) return;
  const own=label(el), cls=norm(el.className), event=norm(el.getAttribute('data-event_name'));
  const ctx=norm((el.closest('[class*="widget"], [class*="daily-reward"], [class*="modal"], [role="dialog"]') || el.parentElement || el).innerText).slice(0,500);
  const disabled=!!el.disabled || el.getAttribute('aria-disabled') === 'true';
  let score=0; const reasons=[];
  const add=(points,why) => { score+=points; reasons.push(why); };
  if (stage === 'login_open') {
    if (own==='log in' || own==='login' || own==='sign in') add(620,'exact login label');
    if (event==='login' || event==='open login') add(350,'login event');
    if (cls.includes('btn-secondary') && own.includes('log')) add(120,'legacy login class');
    if (password) add(-1000,'login form already open');
  } else if (stage === 'login_submit') {
    if (own==='log in' || own==='login') add(750,'login form submit');
    if (event==='submit login') add(600,'legacy Submit Login event');
    if (el.getAttribute('type')==='submit') add(190,'form submit');
  } else if (stage === 'daily_tile') {
    if (cls.includes('widget__daily-reward') || cls.includes('widget__daily-bonus')) add(850,'known daily widget');
    if (own==='daily bonus' || own==='daily reward') add(650,'exact daily tile label');
    else if (own.includes('daily bonus') && own.length<65) add(350,'daily bonus label');
    if (cls.includes('widget')) add(100,'widget');
    if (ctx.includes('daily bonus') && ctx.length<170) add(100,'local daily context');
  } else if (stage === 'reward_claim') {
    if (own==='claim reward') add(1000,'exact Claim Reward');
    if (own==='claim' || own==='collect') add(360,'claim label');
    if (cls.includes('modal-daily-bonus-claim__button')) add(580,'legacy claim class');
    if (event.includes('claim') && event.includes('reward')) add(250,'claim reward event');
    if (rewardRoot) add(280,'Daily Reward modal');
  }
  const dangerous = /buy coins|purchase|checkout|boost rewards|boost|payment|subscribe|deposit|sign up|register|google|facebook|apple|claim my gift|daily quest/i;
  if (dangerous.test(own)) add(-2000,'unsafe/unrelated action');
  if (stage==='daily_tile' && /daily quest|daily spin|daily challenge/i.test(ctx)) add(-800,'not daily bonus');
  if (stage==='reward_claim' && /purchase|checkout|order|payment/i.test(ctx)) add(-1500,'purchase context');
  if (disabled) add(-2000,'disabled');
  if (score < 200) return;
  const id='cc-cashoomo-'+stage+'-'+i;
  el.setAttribute('data-cc-cashoomo', id);
  results.push({ id, score, text:own, reasons, disabled, cls:cls.slice(0,120) });
});
results.sort((a,b) => b.score-a.score);
// Nested text spans/button wrappers often describe the SAME action. Collapse
// ancestor/descendant duplicates before ambiguity checks.
const distinct=[];
for (const candidate of results) {
  const e=document.querySelector('[data-cc-cashoomo="'+candidate.id+'"]');
  if (distinct.some(other => {
    const o=document.querySelector('[data-cc-cashoomo="'+other.id+'"]');
    return e && o && (e.contains(o) || o.contains(e));
  })) continue;
  distinct.push(candidate);
}
return distinct.slice(0,12);
"""


REWARD_STATE_JS = r"""
const norm = s => String(s || '').replace(/\s+/g,' ').trim().toLowerCase();
const shown = e => {
  if (!e) return false;
  const r=e.getBoundingClientRect(), s=getComputedStyle(e);
  return r.width>0 && r.height>0 && s.display!=='none' && s.visibility!=='hidden';
};
const heading = Array.from(document.querySelectorAll('h1,h2,h3,h4,[role="heading"],div,span'))
  .find(e => shown(e) && norm(e.innerText)==='daily reward' &&
    (e.children.length<=2 || e.matches('h1,h2,h3,h4,[role="heading"]')));
let root = null;
if (heading) {
  for (let e=heading.parentElement,i=0; e && i<10; e=e.parentElement,i++) {
    const t=norm(e.innerText);
    if (t.length>60 && t.length<2600 && t.includes('day 1') &&
        (t.includes('claim reward') || t.includes('boost rewards') || t.includes('claimed'))) {
       root=e; break;
    }
  }
}
const text = root ? norm(root.innerText).slice(0,2400) : '';
const buttons = root ? Array.from(root.querySelectorAll('button,[role="button"],[data-event_name],div[class*="button"]')).filter(shown) : [];
const claimButtons=buttons.filter(e => {
  const s=norm(e.innerText || e.getAttribute('aria-label'));
  return s==='claim reward' || s==='claim' || norm(e.className).includes('modal-daily-bonus-claim__button');
});
return {
  open:!!root,
  text,
  claimCount:claimButtons.length,
  enabledClaimCount:claimButtons.filter(e => !e.disabled && e.getAttribute('aria-disabled')!=='true').length,
  // Do not include hidden alerts: those may describe stale UI state.
  alerts:Array.from(document.querySelectorAll('[role="alert"],[role="status"],[class*="toast" i]'))
    .filter(shown).map(e=>norm(e.innerText)).filter(s=>s.length<250).join(' | ').slice(0,500)
};
"""


def _state(driver) -> Dict[str, Any]:
    return _js(driver, UI_STATE_JS, fallback={}) or {}


def _reward_state(driver) -> Dict[str, Any]:
    return _js(driver, REWARD_STATE_JS, fallback={}) or {}


def _is_logged_in(driver) -> bool:
    """Do not equate submitted credentials with a successful login."""
    s = _state(driver)
    return bool(s.get('pageAuthenticated')) and not s.get('authModal')


def _ranked(driver, stage: str, minimum: int) -> List[Dict[str, Any]]:
    candidates = _js(driver, CANDIDATES_JS, stage, fallback=[]) or []
    if not isinstance(candidates, list):
        return []
    for c in candidates[:4]:
        LOG.info("%s candidate score=%s text=%r reasons=%s", stage,
                 c.get('score'), c.get('text'), c.get('reasons'))
    safe = [c for c in candidates if c.get('score', 0) >= minimum and not c.get('disabled')]
    if len(safe) >= 2 and safe[0]['score'] - safe[1]['score'] < 80:
        LOG.warning("Ambiguous %s candidates; refusing to guess", stage)
        return []
    return safe


def _click_candidate(driver, stage: str, minimum: int, *, allow_js: bool = True) -> bool:
    ranked = _ranked(driver, stage, minimum)
    if not ranked:
        return False
    selector = '[data-cc-cashoomo="' + ranked[0]['id'] + '"]'
    try:
        element = driver.find_element(By.CSS_SELECTOR, selector)
        if not _visible(element) or not element.is_enabled():
            return False
        driver.execute_script("arguments[0].scrollIntoView({block:'center',inline:'nearest'});", element)
        try:
            element.click()
        except ElementClickInterceptedException:
            if not allow_js:
                return False
            # Same verified element only; never fall back to a random page button.
            if not _visible(element):
                return False
            driver.execute_script('arguments[0].click();', element)
        LOG.info("Clicked %s candidate (%s)", stage, ranked[0]['reasons'])
        return True
    except (StaleElementReferenceException, WebDriverException) as exc:
        _maybe_raise_browser_error(exc)
        LOG.warning("%s click failed: %s", stage, type(exc).__name__)
        return False


def _login_fields(driver) -> Optional[Tuple[Any, Any]]:
    """Locate email and password inside the visible sign-in dialog."""
    try:
        passwords = [p for p in driver.find_elements(By.CSS_SELECTOR, 'input[type="password"]') if _visible(p)]
        for password in passwords:
            container = driver.execute_script(r"""
              const p=arguments[0]; let root=p.closest('form,[role="dialog"],[class*="modal" i]');
              if (root && root.querySelector('input[type="email"],input[autocomplete="username"],input[placeholder*="email" i]')) return root;
              for (let n=p.parentElement,i=0; n && i<9; n=n.parentElement,i++) {
                if (n.querySelector('input[type="email"],input[autocomplete="username"],input[placeholder*="email" i]')) return n;
              }
              return null;
            """, password)
            if container is None:
                continue
            for email in container.find_elements(By.CSS_SELECTOR,
                'input[type="email"],input[autocomplete="username"],input[placeholder*="email" i],input[name="email"]'):
                if _visible(email):
                    return email, password
    except (StaleElementReferenceException, WebDriverException) as exc:
        _maybe_raise_browser_error(exc)
        LOG.warning("Login-field discovery failed: %s", type(exc).__name__)
    return None


def _fill_login(driver, username: str, password: str) -> bool:
    for attempt in range(2):
        fields = _login_fields(driver)
        if not fields:
            return False
        email_field, password_field = fields
        try:
            email_field.clear()
            email_field.send_keys(username)
            password_field.clear()
            password_field.send_keys(password)
            # Never log or return the password. Check only that both were entered.
            email_ok = email_field.get_attribute('value') == username
            password_ok = bool(password_field.get_attribute('value'))
            if email_ok and password_ok:
                return True
        except (StaleElementReferenceException, WebDriverException) as exc:
            _maybe_raise_browser_error(exc)
            LOG.info("Login form rerendered during typing; trying fresh fields (attempt %d)", attempt + 1)
    return False


def _login_error(driver) -> str:
    state = _state(driver)
    alerts = _norm(state.get('alerts'))
    if alerts and re.search(r'invalid|incorrect|failed|error|wrong password|try again|locked|suspended', alerts, re.I):
        return alerts[:180]
    # Do not interpret generic site text as a login error.
    return ''


async def _notify(channel, message: str, driver=None, screenshot: bool = False) -> None:
    if channel is None:
        return
    path = None
    try:
        if screenshot and SEND_SCREENSHOTS and driver is not None:
            fd, path = tempfile.mkstemp(prefix='cashoomo_', suffix='.png', dir='/tmp')
            os.close(fd)
            try:
                driver.save_screenshot(path)
            except Exception as exc:
                _maybe_raise_browser_error(exc)
                LOG.warning('Screenshot unavailable: %s', exc)
                Path(path).unlink(missing_ok=True)
                path = None
        if path:
            await channel.send(message, file=discord.File(path))
        else:
            await channel.send(message)
    except Exception as exc:
        _maybe_raise_browser_error(exc)
        LOG.warning('Discord notification failed: %s', exc)
    finally:
        if path:
            Path(path).unlink(missing_ok=True)


async def _login(driver) -> Tuple[bool, str]:
    if _is_logged_in(driver):
        return True, 'Already authenticated'
    fields = _login_fields(driver)
    if fields is None:
        if not _click_candidate(driver, 'login_open', 500):
            return False, 'Could not find the Log In control'
        try:
            WebDriverWait(driver, 12, poll_frequency=0.4).until(lambda d: _login_fields(d) is not None)
        except TimeoutException:
            return False, 'Log In dialog did not open'
    credentials = os.getenv('CASHOOMO', '').strip()
    if ':' not in credentials:
        return False, 'Missing CASHOOMO=email:password in .env'
    username, password = credentials.split(':', 1)
    if not username or not password:
        return False, 'CASHOOMO credentials are empty'
    if not _fill_login(driver, username, password):
        return False, 'Could not populate the visible login form'
    if not _click_candidate(driver, 'login_submit', 600):
        return False, 'Could not identify the actual Log In submit button'
    LOG.info('Login submitted. Waiting for authenticated session.')
    end = asyncio.get_running_loop().time() + LOGIN_TIMEOUT
    while asyncio.get_running_loop().time() < end:
        if _is_logged_in(driver):
            return True, 'Authenticated session verified'
        err = _login_error(driver)
        if err:
            return False, 'Login was rejected: ' + err
        # No forced re-submit. A captcha, email code, or account challenge may
        # need manual completion and must not be bypassed.
        await asyncio.sleep(0.7)
    return False, 'Login did not complete; review CAPTCHA, 2FA, or site message manually'


def _claim_outcome(modal: Dict[str, Any], clicked: bool, was_open: bool) -> Optional[str]:
    """Pure status classifier used by polls and isolated tests."""
    text = _norm(modal.get('text', '') + ' ' + modal.get('alerts', '')).lower()
    confirmed = ('reward claimed', 'successfully claimed', 'claimed successfully',
                 'already claimed', 'come back tomorrow', 'claim successful',
                 'you have claimed', 'reward collected')
    if any(s in text for s in confirmed):
        return 'claimed'
    if not clicked and was_open and (
        'available in' in text or 'next reward in' in text or 'next claim in' in text
    ):
        return 'unavailable'
    if clicked:
        # An unmounted modal is NOT proof that a claim succeeded.
        if not modal.get('open'):
            return None
        if modal.get('open') and modal.get('claimCount', 0) == 0:
            return None
    return None


async def claim_cashoomo_bonus(ctx, driver, channel):
    """Claim at most once. Return 'claimed', 'unavailable', or 'unverified'."""
    if not _is_logged_in(driver):
        await _notify(channel, '⚠️ Cashoomo: Not authenticated; reward check skipped.')
        return 'login_required'

    # The new website may display Daily Reward immediately after login.
    modal = _reward_state(driver)
    if not modal.get('open'):
        if not _click_candidate(driver, 'daily_tile', 600):
            LOG.info('Daily Bonus tile unavailable; legacy fallback considered.')
            # Old selector is still supported, but only after checking its text.
            try:
                for tile in driver.find_elements(By.XPATH, REWARD_WIDGET_XPATH):
                    if _visible(tile) and 'daily' in _norm(tile.text).lower():
                        tile.click()
                        break
            except WebDriverException as exc:
                _maybe_raise_browser_error(exc)
                LOG.warning('Legacy widget fallback failed: %s', type(exc).__name__)
        end = asyncio.get_running_loop().time() + REWARD_TIMEOUT
        while asyncio.get_running_loop().time() < end:
            modal = _reward_state(driver)
            if modal.get('open'):
                break
            await asyncio.sleep(0.5)

    if not modal.get('open'):
        await _notify(channel,
            '⚠️ Cashoomo: Daily Reward dialog not found. Claim was not attempted.',
            driver, screenshot=True)
        return 'unverified'

    prior = _claim_outcome(modal, clicked=False, was_open=True)
    if prior == 'claimed':
        await _notify(channel, 'Cashoomo Daily Reward is already claimed.', driver, screenshot=True)
        return 'claimed'
    if prior == 'unavailable':
        await _notify(channel, 'Cashoomo Daily Reward is not available yet.', driver, screenshot=True)
        return 'unavailable'

    if not _click_candidate(driver, 'reward_claim', 850, allow_js=True):
        # Disabled/unavailable without a visible confirmation is NOT a claimed bonus.
        await _notify(channel,
            '⚠️ Cashoomo: Daily Reward opened, but no safe enabled Claim Reward button was found.',
            driver, screenshot=True)
        return 'unverified'

    LOG.info('Clicked Claim Reward once; verifying result without another click')
    end = asyncio.get_running_loop().time() + VERIFY_TIMEOUT
    while asyncio.get_running_loop().time() < end:
        modal = _reward_state(driver)
        result = _claim_outcome(modal, clicked=True, was_open=True)
        if result == 'claimed':
            await _notify(channel, '✅ Cashoomo Daily Bonus Claimed!', driver, screenshot=True)
            return 'claimed'
        await asyncio.sleep(0.6)

    # If the modal disappeared or updated without explicit confirmation, do not
    # claim success and do not retry the button blindly.
    await _notify(channel,
        '⚠️ Cashoomo: Claim Reward was clicked, but the result could not be verified. Please check the site.',
        driver, screenshot=True)
    return 'unverified'


async def cashoomo_casino(ctx, driver, channel):
    """Main entry point used by existing main.py; no signature changes."""
    LOG.info('Starting Cashoomo daily check')
    try:
        if not _navigate(driver, SITE_URL):
            await _notify(channel, '⚠️ Cashoomo: Site navigation failed; claim not attempted.')
            return
        if not _is_logged_in(driver):
            ok, reason = await _login(driver)
            LOG.info('Login outcome: %s', reason)
            if not ok:
                # No screenshot by default: sign-in page may display personal email.
                await _notify(channel, '⚠️ Cashoomo login incomplete: ' + reason)
                return
        if not _is_logged_in(driver):
            await _notify(channel, '⚠️ Cashoomo: Login could not be verified; claim skipped.')
            return

        # Stay on the authenticated page if the widget is already present.
        # /main is a fallback for installations that do not redirect after login.
        s = _state(driver)
        if not s.get('tile') and not s.get('dailyName') and not _reward_state(driver).get('open'):
            if not _navigate(driver, MAIN_URL):
                await _notify(channel, '⚠️ Cashoomo: Could not open rewards page.')
                return
            if not _is_logged_in(driver):
                await _notify(channel, '⚠️ Cashoomo: Authentication lost when opening rewards page.')
                return

        await claim_cashoomo_bonus(ctx, driver, channel)
    except (InvalidSessionIdException, NoSuchWindowException):
        # main.py's upgraded Chrome recovery must observe these failures.
        LOG.exception('Chrome session became invalid during Cashoomo')
        raise
    except WebDriverException as exc:
        _maybe_raise_browser_error(exc)
        LOG.exception('WebDriver error during Cashoomo')
        await _notify(channel, '⚠️ Cashoomo browser error; claim not verified.')
    except Exception:
        LOG.exception('Unexpected error in Cashoomo')
        await _notify(channel, '⚠️ Cashoomo encountered an unexpected error; claim not verified.')
