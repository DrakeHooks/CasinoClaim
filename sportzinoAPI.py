# Drake Hooks + WaterTrooper
# Casino Claim 3
# Sportzino API (SeleniumBase UC)
# Simple login, intelligent Progressive Daily Bonus candidacy, and verified claiming.

import os
import re
import tempfile
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

import discord
from dotenv import load_dotenv
from seleniumbase import SB

load_dotenv()

# Expect "email:password" in SPORTZINO
SPORTZINO_CRED = os.getenv("SPORTZINO", "")

LOGIN_URL = "https://sportzino.com/login"
HOME_URL = "https://sportzino.com/"
# Observed Nov 16, 2026. Layout-based XPath: diagnostic fallback only, never
# enough on its own to authorize a claim click.
CURRENT_DAILY_CLAIM_XPATH = (
    "/html/body/div[1]/div[1]/div/div/div[2]/div[3]/div[2]/"
    "div/div[1]/div/div[3]/div/div[1]/button"
)

EMAIL_LOCATORS: Tuple[str, ...] = (
    # Exact current Sportzino login field from the supplied DevTools markup.
    "#emailAddress",
    "input#emailAddress",
    "input[data-testid='login-email-input']",
    "input[name='username']",
    "input[autocomplete='username']",
    "input[placeholder='@email']",
    "input[type='email']",
    # Absolute XPath is retained only as a final fallback.
    "/html/body/div[1]/div/main/div/div[3]/div/form/div[1]/div/input",
)

PASSWORD_LOCATORS: Tuple[str, ...] = (
    # Exact current Sportzino login field from the supplied DevTools markup.
    "#password",
    "input#password",
    "input[data-testid='login-password-input']",
    "input[name='password']",
    "input[autocomplete='current-password']",
    "input[type='password']",
    # Absolute XPath is retained only as a final fallback.
    "/html/body/div[1]/div/main/div/div[3]/div/form/div[2]/div/input",
)

SUBMIT_LOCATORS: Tuple[str, ...] = (
    # Scope the click to the actual login form so another page button cannot win.
    "form.login-form .login-form-login-button-container button",
    ".login-form-login-button-container button",
    "form.login-form button[type='submit']",
    "form.login-form button[data-testid='login-submit-button']",
    "button[data-testid='login-submit-button']",
    "//form[contains(@class,'login-form')]//button[normalize-space()='Log In']",
    "//form[contains(@class,'login-form')]//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'log in')]",
)

COOKIE_ACCEPT_LOCATORS: Tuple[str, ...] = (
    "#onetrust-accept-btn-handler",
    "button[data-testid='cookie-accept-all']",
    "button[data-testid='accept-all-cookies']",
    "button[aria-label*='Accept All']",
    "button[aria-label*='accept all']",
    "//button[normalize-space()='Accept All']",
    "//button[normalize-space()='Allow All']",
    "//button[normalize-space()='Accept Cookies']",
    "//button[normalize-space()='I Agree']",
    "//button[normalize-space()='Agree']",
    "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept all')]",
    "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'allow all')]",
)


CLAIMED_MARKERS: Tuple[str, ...] = (
    "TODAY'S BONUS IS CLAIMED",
    "TODAYS BONUS IS CLAIMED",
    "TODAY’S BONUS IS CLAIMED",
    "DAILY BONUS CLAIMED",
    "BONUS IS CLAIMED",
    "ALREADY CLAIMED",
    "COME BACK TOMORROW",
    "SEE YOU TOMORROW",
)

SUCCESS_MARKERS: Tuple[str, ...] = (
    "CONGRATULATIONS",
    "DAILY BONUS CLAIMED",
    "TODAY'S BONUS IS CLAIMED",
    "TODAYS BONUS IS CLAIMED",
    "START PLAYING",
    "REWARD CLAIMED",
    "BONUS CLAIMED",
)

LOGIN_ERROR_MARKERS: Tuple[str, ...] = (
    "INVALID EMAIL",
    "INVALID PASSWORD",
    "INVALID CREDENTIALS",
    "EMAIL OR PASSWORD",
    "INCORRECT PASSWORD",
    "ACCOUNT NOT FOUND",
    "PLEASE COMPLETE THE CAPTCHA",
    "CAPTCHA IS REQUIRED",
    "SOMETHING WENT WRONG",
    "TOO MANY ATTEMPTS",
)

CHECKOUT_MARKERS: Tuple[str, ...] = (
    "CHECKOUT",
    "ORDER SUMMARY",
    "PAYMENT METHOD",
    "TOTAL AMOUNT TO PAY",
    "CREDIT/DEBIT",
    "PAY USING",
)


# ───────────────────────────────────────────────────────────
# Generic helpers
# ───────────────────────────────────────────────────────────

def _norm(value: Any) -> str:
    value = "" if value is None else str(value)
    value = value.replace("\xa0", " ").replace("’", "'").replace("`", "'")
    return re.sub(r"\s+", " ", value).strip()


def _up(value: Any) -> str:
    return _norm(value).upper()


def _contains_any(text: Any, markers: Iterable[str]) -> bool:
    upper = _up(text)
    return any(marker in upper for marker in markers)


def _first_marker(text: Any, markers: Iterable[str]) -> str:
    upper = _up(text)
    for marker in markers:
        if marker in upper:
            return marker
    return ""


def _short(text: Any, limit: int = 180) -> str:
    text = _norm(text)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _safe_js(sb: SB, script: str, *args, default=None):
    try:
        return sb.execute_script(script, *args)
    except Exception as exc:
        print(f"[Sportzino][JS WARN] {exc}")
        return default


def _page_snapshot(sb: SB) -> Dict[str, str]:
    data = _safe_js(
        sb,
        """
        const visible = (el) => {
            if (!el) return false;
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style.display !== 'none'
                && style.visibility !== 'hidden'
                && style.opacity !== '0'
                && rect.width > 0
                && rect.height > 0;
        };

        const visibleText = Array.from(document.querySelectorAll('body *'))
            .filter(visible)
            .map((el) => [
                el.innerText || el.textContent || el.value || '',
                el.getAttribute('aria-label') || '',
                el.getAttribute('title') || '',
                el.getAttribute('placeholder') || '',
                el.getAttribute('data-testid') || ''
            ].join(' '))
            .join(' ');

        return {
            url: window.location.href || '',
            title: document.title || '',
            body: document.body ? (document.body.innerText || document.body.textContent || '') : '',
            visibleText
        };
        """,
        default={},
    )

    if not isinstance(data, dict):
        return {"url": "", "title": "", "text": ""}

    return {
        "url": _norm(data.get("url", "")),
        "title": _norm(data.get("title", "")),
        "text": _norm(
            " ".join(
                [
                    data.get("title", ""),
                    data.get("visibleText", ""),
                ]
            )
        ),
    }


def _locator_visible(sb: SB, locator: str, timeout: float = 1.0) -> bool:
    try:
        sb.wait_for_element_visible(locator, timeout=timeout)
        return True
    except Exception:
        return False


def _first_visible_locator(
    sb: SB,
    locators: Sequence[str],
    timeout_each: float = 1.5,
) -> Optional[str]:
    for locator in locators:
        if _locator_visible(sb, locator, timeout=timeout_each):
            return locator
    return None


def _is_login_page(sb: SB) -> bool:
    snapshot = _page_snapshot(sb)
    url_upper = snapshot["url"].upper()

    email_visible = _first_visible_locator(sb, EMAIL_LOCATORS, timeout_each=0.2) is not None
    password_visible = _first_visible_locator(sb, PASSWORD_LOCATORS, timeout_each=0.2) is not None

    return (
        "/LOGIN" in url_upper
        or (email_visible and password_visible)
        or (
            "LOG IN WITH GOOGLE" in _up(snapshot["text"])
            and "PASSWORD" in _up(snapshot["text"])
        )
    )


def _is_authenticated(sb: SB) -> bool:
    snapshot = _page_snapshot(sb)
    upper = _up(snapshot["text"])
    url_upper = snapshot["url"].upper()

    # Visible login controls always override URL/text guesses.
    email_visible = _first_visible_locator(sb, EMAIL_LOCATORS, timeout_each=0.15) is not None
    password_visible = _first_visible_locator(sb, PASSWORD_LOCATORS, timeout_each=0.15) is not None
    if email_visible or password_visible:
        return False

    if any(
        token in url_upper
        for token in (
            "/LOGIN",
            "/AUTH/CALLBACK",
            "/CONNECT/AUTHORIZE",
            "/ERROR",
            "/ACCESSDENIED",
        )
    ):
        return False

    authenticated_markers = (
        "COIN STORE",
        "GET COINS",
        "REWARDS",
        "MY ACCOUNT",
        "LOG OUT",
        "LOGOUT",
        "WALLET",
    )

    if any(marker in upper for marker in authenticated_markers):
        return True

    # Sportzino normally redirects to the lobby after a successful login. A
    # non-login Sportzino URL with no visible login fields is therefore valid.
    return "SPORTZINO.COM" in url_upper and "/LOGIN" not in url_upper


# ───────────────────────────────────────────────────────────
# Screenshot helper
# ───────────────────────────────────────────────────────────

async def _send_screenshot(
    sb: SB,
    channel: discord.abc.Messageable,
    caption: str,
    prefix: str,
    discord_message: Optional[str] = None,
):
    """
    Print all status/debug information to the worker console.

    When discord_message is provided, send that exact final status to Discord,
    followed by the screenshot. Other internal details remain console-only.
    """
    print(caption)

    fd, path = tempfile.mkstemp(
        prefix=f"{prefix}_",
        suffix=".png",
        dir="/tmp",
    )
    os.close(fd)

    try:
        sb.save_screenshot(path)

        if discord_message:
            await channel.send(discord_message)

        await channel.send(file=discord.File(path))
    except Exception as error:
        print(f"[Sportzino][SCREENSHOT ERROR] {error}")
    finally:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as cleanup_error:
            print(
                "[Sportzino][SCREENSHOT CLEANUP ERROR] "
                f"{cleanup_error}"
            )


# ───────────────────────────────────────────────────────────
# Click and typing helpers
# ───────────────────────────────────────────────────────────

def _force_click(sb: SB, locator: str, timeout: float = 8) -> bool:
    try:
        sb.wait_for_element_visible(locator, timeout=timeout)
    except Exception:
        return False

    try:
        sb.scroll_to(locator)
    except Exception:
        pass

    for mode in ("normal", "slow", "js", "directjs"):
        try:
            if mode == "normal":
                sb.click(locator, timeout=2)
            elif mode == "slow":
                sb.slow_click(locator)
            elif mode == "js":
                sb.js_click(locator)
            else:
                element = sb.find_element(locator)
                sb.execute_script("arguments[0].click();", element)
            return True
        except Exception:
            continue

    return False


def _try_click_any(sb: SB, locators: Sequence[str], timeout_each: float = 5) -> bool:
    for locator in locators:
        if locator and _force_click(sb, locator, timeout=timeout_each):
            return True
    return False


def _fill_input(
    sb: SB,
    locators: Sequence[str],
    value: str,
    field_name: str,
) -> Optional[str]:
    """Fill the first visible input without scrolling the page."""
    for locator in locators:
        try:
            sb.wait_for_element_visible(locator, timeout=4)
            element = sb.find_element(locator)

            # React/Sentry controlled inputs can ignore a plain JS assignment.
            # Use the native HTMLInputElement setter and dispatch the same events
            # a real user action generates.
            actual = _safe_js(
                sb,
                r"""
                const el = arguments[0];
                const value = arguments[1];
                if (!el) return '';

                el.focus({preventScroll: true});
                const descriptor = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype,
                    'value'
                );
                descriptor.set.call(el, '');
                el.dispatchEvent(new Event('input', {bubbles: true}));
                descriptor.set.call(el, value);
                el.dispatchEvent(new InputEvent('input', {
                    bubbles: true,
                    inputType: 'insertText',
                    data: value
                }));
                el.dispatchEvent(new Event('change', {bubbles: true}));
                el.blur();
                return el.value || '';
                """,
                element,
                value,
                default="",
            )

            # Selenium keystrokes are a fallback if the framework rewrites the
            # value after the native setter/events above.
            if actual != value:
                try:
                    element.click()
                    element.clear()
                    element.send_keys(value)
                except Exception:
                    pass

                actual = _safe_js(
                    sb,
                    "return arguments[0] ? (arguments[0].value || '') : '';",
                    element,
                    default="",
                )

            if actual == value:
                print(
                    f"[Sportzino] Filled {field_name} using {locator} "
                    f"({len(value)} characters)."
                )
                return locator

        except Exception as exc:
            print(f"[Sportzino] {field_name} locator failed ({locator}): {exc}")

    print(f"[Sportzino] Could not fill {field_name} using any known locator.")
    return None


# ───────────────────────────────────────────────────────────
# Cookie handling
# ───────────────────────────────────────────────────────────

def _js_click_cookie_accept(sb: SB) -> bool:
    """Click Accept only inside a genuine cookie dialog/banner overlay."""
    return bool(
        _safe_js(
            sb,
            r"""
            const visible = (el) => {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== 'none'
                    && style.visibility !== 'hidden'
                    && style.opacity !== '0'
                    && rect.width > 0
                    && rect.height > 0
                    && rect.bottom > 0
                    && rect.top < window.innerHeight;
            };

            const normalize = (value) => (value || '')
                .replace(/\s+/g, ' ')
                .trim()
                .toLowerCase();

            const isOverlay = (node) => {
                if (!visible(node)) return false;
                const style = window.getComputedStyle(node);
                const rect = node.getBoundingClientRect();
                const role = normalize(node.getAttribute('role'));
                const cookieText = normalize([
                    node.innerText,
                    node.textContent,
                    node.getAttribute('aria-label'),
                    node.id,
                    node.className
                ].join(' '));

                const mentionsCookies =
                    cookieText.includes('cookie') ||
                    cookieText.includes('privacy preferences') ||
                    cookieText.includes('we value your privacy');

                const positionedOverlay =
                    style.position === 'fixed' ||
                    style.position === 'sticky' ||
                    role === 'dialog' ||
                    role === 'alertdialog';

                const overlapsViewport =
                    rect.bottom > 0 &&
                    rect.top < window.innerHeight &&
                    rect.right > 0 &&
                    rect.left < window.innerWidth;

                return mentionsCookies && positionedOverlay && overlapsViewport;
            };

            const roots = Array.from(new Set([
                ...document.querySelectorAll(
                    '#onetrust-banner-sdk, #onetrust-pc-sdk, ' +
                    '#CybotCookiebotDialog, .cky-consent-container, ' +
                    '.osano-cm-window, [role="dialog"], [role="alertdialog"], ' +
                    '[data-testid*="cookie" i], [id*="cookie" i], [class*="cookie" i]'
                ),
                ...Array.from(document.querySelectorAll('div, section, aside')).filter(isOverlay)
            ])).filter(isOverlay);

            const preferred = [
                'accept all',
                'allow all',
                'accept cookies',
                'agree and continue',
                'save and accept',
                'i agree',
                'accept'
            ];

            for (const root of roots) {
                // Buttons only. Never click a footer/link named Manage Cookies.
                const controls = Array.from(root.querySelectorAll(
                    'button, input[type="button"], input[type="submit"], [role="button"]'
                )).filter(visible);

                for (const phrase of preferred) {
                    const match = controls.find((el) => {
                        const text = normalize([
                            el.innerText,
                            el.textContent,
                            el.value,
                            el.getAttribute('aria-label'),
                            el.getAttribute('title')
                        ].join(' '));
                        return text === phrase || text.startsWith(`${phrase} `);
                    });

                    if (match) {
                        match.click();
                        return true;
                    }
                }
            }

            return false;
            """,
            default=False,
        )
    )


def _neutralize_cookie_overlay(sb: SB) -> bool:
    """Hide only a fixed/sticky cookie overlay that blocks the login form."""
    return bool(
        _safe_js(
            sb,
            r"""
            const visible = (el) => {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== 'none'
                    && style.visibility !== 'hidden'
                    && rect.width > 0
                    && rect.height > 0
                    && rect.bottom > 0
                    && rect.top < window.innerHeight;
            };

            const normalize = (value) => (value || '')
                .replace(/\s+/g, ' ')
                .trim()
                .toLowerCase();

            let changed = false;
            const nodes = Array.from(document.querySelectorAll(
                '#onetrust-banner-sdk, #onetrust-pc-sdk, #CybotCookiebotDialog, ' +
                '.cky-consent-container, .osano-cm-window, [role="dialog"], ' +
                '[role="alertdialog"], div, section, aside'
            ));

            for (const node of nodes) {
                if (!visible(node)) continue;

                const style = window.getComputedStyle(node);
                const role = normalize(node.getAttribute('role'));
                const text = normalize([
                    node.innerText,
                    node.textContent,
                    node.getAttribute('aria-label'),
                    node.id,
                    node.className
                ].join(' '));

                const looksLikeCookie =
                    text.includes('cookie') ||
                    text.includes('privacy preferences') ||
                    text.includes('we value your privacy');

                const overlayLike =
                    style.position === 'fixed' ||
                    style.position === 'sticky' ||
                    role === 'dialog' ||
                    role === 'alertdialog';

                if (looksLikeCookie && overlayLike) {
                    node.style.setProperty('display', 'none', 'important');
                    node.style.setProperty('visibility', 'hidden', 'important');
                    node.style.setProperty('pointer-events', 'none', 'important');
                    changed = true;
                }
            }

            if (changed) {
                document.documentElement.style.removeProperty('overflow');
                document.body && document.body.style.removeProperty('overflow');
            }
            return changed;
            """,
            default=False,
        )
    )


def _handle_cookie_consent(sb: SB) -> bool:
    """Handle only an on-screen cookie overlay; never touch footer links."""
    accepted = _js_click_cookie_accept(sb)
    if accepted:
        print("[Sportzino] Cookie consent accepted from an active overlay.")
        sb.wait(0.4)
        return True

    neutralized = _neutralize_cookie_overlay(sb)
    if neutralized:
        print("[Sportzino] Blocking cookie overlay neutralized.")
        sb.wait(0.2)

    return neutralized


# ───────────────────────────────────────────────────────────
# Login flow
# ───────────────────────────────────────────────────────────

def _simple_login_button_enabled(sb: SB) -> bool:
    """Return True when the real Sportzino Log In button is enabled."""
    try:
        return bool(
            sb.execute_script(
                """
                const button = document.querySelector(
                    'form.login-form .login-form-login-button-container button'
                );

                return Boolean(
                    button &&
                    !button.disabled &&
                    button.getAttribute('aria-disabled') !== 'true'
                );
                """
            )
        )
    except Exception:
        return False


def _simple_click_login_button(sb: SB) -> bool:
    """
    Click only the Log In button inside Sportzino's email/password form.

    This intentionally follows the same simple approach used by the working
    American Luck login instead of changing React input values through JS.
    """
    locators = (
        "form.login-form .login-form-login-button-container button",
        ".login-form-login-button-container button",
        "//form[contains(@class,'login-form')]"
        "//div[contains(@class,'login-form-login-button-container')]//button",
        "//form[contains(@class,'login-form')]"
        "//button[normalize-space()='Log In']",
    )

    for locator in locators:
        try:
            sb.wait_for_element_visible(locator, timeout=4)
            sb.click(locator)
            print(f"[Sportzino] Clicked Log In using: {locator}")
            return True
        except Exception as error:
            print(
                f"[Sportzino] Login click locator failed "
                f"({locator}): {error}"
            )

    # Same hard-click fallback style used by American Luck.
    try:
        button = sb.find_element(
            "form.login-form .login-form-login-button-container button"
        )
        sb.execute_script(
            "arguments[0].scrollIntoView({block:'center'});",
            button,
        )
        sb.wait(0.3)
        button.click()
        print("[Sportzino] Clicked Log In with WebElement fallback.")
        return True
    except Exception:
        pass

    try:
        button = sb.find_element(
            "form.login-form .login-form-login-button-container button"
        )
        sb.execute_script("arguments[0].click();", button)
        print("[Sportzino] Clicked Log In with JS fallback.")
        return True
    except Exception:
        return False


def _simple_login_error(sb: SB) -> str:
    snapshot = _page_snapshot(sb)
    return _first_marker(snapshot["text"], LOGIN_ERROR_MARKERS)


def _login(sb: SB, username: str, password: str) -> Dict[str, str]:
    """
    Simple Sportzino login modeled after the working American Luck login:

    1. Open the login page.
    2. Type directly into #emailAddress and #password with SeleniumBase.
    3. Click the Cloudflare challenge when needed.
    4. Click the form's real Log In button.
    5. Wait for the login form to disappear or the URL to leave /login.

    No JavaScript value injection is used for the credentials.
    """
    sb.uc_open_with_reconnect(LOGIN_URL, 8)

    try:
        sb.wait_for_ready_state_complete()
    except Exception:
        pass

    sb.wait(2)
    print("[Sportzino] Login page loaded.")

    # Handle only a real on-screen cookie overlay. This cannot click the
    # footer's Manage Cookies link.
    _handle_cookie_consent(sb)

    try:
        sb.wait_for_element_visible("#emailAddress", timeout=20)
        sb.wait_for_element_visible("#password", timeout=20)
    except Exception as error:
        return {
            "status": "login_fields_missing",
            "reason": "The Sportzino email/password fields did not appear",
            "evidence": str(error),
        }

    # Keep the form in view before typing.
    try:
        sb.execute_script(
            """
            const email = document.querySelector('#emailAddress');
            if (email) {
                email.scrollIntoView({
                    block: 'center',
                    inline: 'nearest'
                });
            }
            """
        )
    except Exception:
        pass

    # IMPORTANT: Use normal SeleniumBase typing exactly like American Luck.
    # The previous JS/React setter could make the fields look populated while
    # Sportzino's form state still submitted blank values.
    try:
        sb.click("#emailAddress")
        sb.type("#emailAddress", username)
        print(
            "[Sportzino] Typed email directly into #emailAddress "
            f"({len(username)} characters)."
        )

        sb.click("#password")
        sb.type("#password", password)
        print(
            "[Sportzino] Typed password directly into #password "
            f"({len(password)} characters)."
        )
    except Exception as error:
        return {
            "status": "login_typing_failed",
            "reason": "Could not type into the Sportzino login fields",
            "evidence": str(error),
        }

    # Confirm the browser truly contains the credentials before touching
    # Cloudflare or the submit button.
    try:
        typed_email = sb.get_attribute("#emailAddress", "value") or ""
        typed_password = sb.get_attribute("#password", "value") or ""
    except Exception:
        typed_email = ""
        typed_password = ""

    print(
        "[Sportzino] Field check before captcha: "
        f"email_chars={len(typed_email)} "
        f"password_chars={len(typed_password)}"
    )

    if typed_email != username or typed_password != password:
        return {
            "status": "login_fields_rejected",
            "reason": "Sportzino did not retain the typed credentials",
            "evidence": (
                f"email_chars={len(typed_email)} "
                f"password_chars={len(typed_password)}"
            ),
        }

    # Same Cloudflare handling sequence as American Luck.
    try:
        sb.uc_gui_click_captcha()
        print("[Sportzino] Cloudflare click attempted.")
    except Exception as error:
        print(
            "[Sportzino] Cloudflare click was unnecessary or unavailable: "
            f"{error}"
        )

    sb.wait(1.5)

    # Give Turnstile a reasonable amount of time to enable the form button.
    # Do not repeatedly submit or rewrite the fields.
    for second_half in range(30):
        if _simple_login_button_enabled(sb):
            break

        if second_half == 15:
            try:
                sb.uc_gui_click_captcha()
                print("[Sportzino] Retried the Cloudflare click once.")
            except Exception:
                pass

        sb.wait(0.5)

    # A GUI captcha interaction may have moved the viewport. Return only to
    # the login form, then click its exact Log In button.
    try:
        sb.execute_script(
            """
            const button = document.querySelector(
                'form.login-form .login-form-login-button-container button'
            );
            if (button) {
                button.scrollIntoView({
                    block: 'center',
                    inline: 'nearest'
                });
            }
            """
        )
    except Exception:
        pass

    # Verify that Cloudflare interaction did not erase the inputs.
    try:
        typed_email = sb.get_attribute("#emailAddress", "value") or ""
        typed_password = sb.get_attribute("#password", "value") or ""
    except Exception:
        typed_email = ""
        typed_password = ""

    print(
        "[Sportzino] Field check before submit: "
        f"email_chars={len(typed_email)} "
        f"password_chars={len(typed_password)}"
    )

    if typed_email != username or typed_password != password:
        # One simple normal-typing retry, still with no JS value injection.
        try:
            sb.type("#emailAddress", username)
            sb.type("#password", password)
            typed_email = sb.get_attribute("#emailAddress", "value") or ""
            typed_password = sb.get_attribute("#password", "value") or ""
        except Exception:
            pass

    if typed_email != username or typed_password != password:
        return {
            "status": "login_fields_lost",
            "reason": "The credentials disappeared before Log In was clicked",
            "evidence": (
                f"email_chars={len(typed_email)} "
                f"password_chars={len(typed_password)}"
            ),
        }

    if not _simple_click_login_button(sb):
        # Final American-Luck-style Enter fallback.
        try:
            sb.press_keys("#password", "\n")
            print("[Sportzino] Submitted login with Enter fallback.")
        except Exception as error:
            return {
                "status": "submit_failed",
                "reason": "Could not click or submit the Sportzino login form",
                "evidence": str(error),
            }

    # Wait for either success, a visible login error, or timeout.
    for index in range(60):
        error_hit = _simple_login_error(sb)
        if error_hit:
            return {
                "status": "login_error",
                "reason": "Sportzino displayed a login error",
                "evidence": error_hit,
            }

        if _is_authenticated(sb):
            snapshot = _page_snapshot(sb)
            return {
                "status": "authenticated",
                "reason": "Sportzino left the login page",
                "evidence": snapshot["url"],
            }

        # Some Turnstile forms accept the first click only after the token
        # settles. Retry the exact button once, without retyping anything.
        if index == 20 and _simple_login_button_enabled(sb):
            _simple_click_login_button(sb)

        sb.wait(0.5)

    snapshot = _page_snapshot(sb)
    return {
        "status": "login_pending",
        "reason": "Still on the login page after the simple login attempt",
        "evidence": snapshot["url"],
    }


# ───────────────────────────────────────────────────────────
# Lobby/rewards helpers
# ───────────────────────────────────────────────────────────

def _close_popups_before_rewards(sb: SB):
    popup_locators = (
        "/html/body/div[3]/div/div[1]/div/div/div/div[1]/div[2]/button",
        "/html/body/div[3]/div/div[1]/div/div/button",
        "/html/body/div[4]/div/div[1]/div/div/button",
        "/html/body/div[5]/div/div[1]/div/div/button",
        "/html/body/div[6]/div/div[1]/div/div/div/div[2]/button",
        "//button[@aria-label='Close' or @aria-label='close']",
        "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'close')]",
        "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'dismiss')]",
        "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'got it')]",
        "//div[contains(@class,'modal')]//button[contains(@class,'close')]",
    )

    closed = 0
    for _ in range(3):
        if _try_click_any(sb, popup_locators, timeout_each=1.5):
            closed += 1
            sb.wait(0.4)
        else:
            break

    if closed:
        print(f"[Sportzino] Closed {closed} lobby popup(s).")

    _handle_cookie_consent(sb)

    try:
        sb.press_keys("body", "ESCAPE")
    except Exception:
        pass


def _inbox_panel_open(sb: SB) -> bool:
    """Detect the new header inbox panel (not merely its mail icon)."""
    return bool(_safe_js(sb, r"""
        const visible = e => {
            if (!e) return false;
            const s = getComputedStyle(e), r = e.getBoundingClientRect();
            return s.display !== 'none' && s.visibility !== 'hidden' &&
                r.width > 0 && r.height > 0;
        };
        const panels = document.querySelectorAll(
            '[class*="header-inbox" i], [class*="inbox-panel" i], ' +
            '[class*="inbox-modal" i], [data-sentry-component*="Inbox" i]'
        );
        return [...panels].some(el => {
            if (!visible(el)) return false;
            // Header icon itself does not constitute an opened inbox.
            if (el.matches('button, a, [role="button"]')) return false;
            if (el.closest('header') && el.getBoundingClientRect().height < 100)
                return false;
            const t = (el.innerText || '').toLowerCase();
            return t.includes('inbox') || t.includes('message') ||
                t.includes('notification') || el.getBoundingClientRect().height > 160;
        });
    """, default=False))


def _close_inbox(sb: SB) -> bool:
    """Try closing only the inbox; never click the header inbox button."""
    if not _inbox_panel_open(sb):
        return True
    print('[Sportzino] New header inbox is open; closing before Coin Store.')
    closed = bool(_safe_js(sb, r"""
        const visible = e => {
            const r = e.getBoundingClientRect(), s = getComputedStyle(e);
            return r.width > 0 && r.height > 0 && s.display !== 'none';
        };
        const roots = [...document.querySelectorAll(
            '[class*="inbox-panel" i], [class*="inbox-modal" i], ' +
            '[class*="header-auth-inbox" i], [class*="header-inbox" i]'
        )].filter(e => visible(e) && e.getBoundingClientRect().height > 100);
        for (const root of roots) {
            const button = [...root.querySelectorAll('button, [role="button"]')]
                .find(e => visible(e) && /^(close|dismiss|x|×)$/i.test(
                    [e.getAttribute('aria-label'), e.title, e.innerText]
                    .filter(Boolean).join(' ').trim()
                ));
            if (button) { button.click(); return true; }
        }
        return false;
    """, default=False))
    if closed:
        sb.wait(0.5)
    if _inbox_panel_open(sb):
        try:
            sb.press_keys('body', 'ESCAPE')
            sb.wait(0.5)
        except Exception:
            pass
    return not _inbox_panel_open(sb)


def _coin_store_candidates(sb: SB) -> list[Dict[str, Any]]:
    """Select the *actual* Coin Store control, never a neighboring inbox button.

    The screenshot identifies a DIV with the stable class
    header-auth-coin-store-button-hide-on-mobile. Do not use absolute header
    XPaths; insertion of the inbox shifted their positions.
    """
    result = _safe_js(sb, r"""
        const visible = el => {
            if (!el) return false;
            const s = getComputedStyle(el), r = el.getBoundingClientRect();
            return s.display !== 'none' && s.visibility !== 'hidden' &&
                r.width > 0 && r.height > 0;
        };
        const norm = x => (x || '').replace(/\s+/g, ' ').trim().toLowerCase();
        const nodes = [...document.querySelectorAll(
            '[class*="header-auth-coin-store-button" i], ' +
            'header button, header a, header [role="button"], ' +
            'nav button, nav a, [data-sentry-component*="CoinStore" i]'
        )];
        const seen = new Set(), candidates = [];
        for (const node of nodes) {
            const target = node.closest('[class*="header-auth-coin-store-button" i]') || node;
            if (seen.has(target) || !visible(target)) continue;
            seen.add(target);
            const cls = norm(typeof target.className === 'string' ? target.className : '');
            const own = norm(target.innerText || target.textContent ||
                target.getAttribute('aria-label') || target.getAttribute('title') || '');
            const component = norm(target.getAttribute('data-sentry-component'));
            const combined = norm([cls, own, component].join(' '));
            if (target.closest('[class*="inbox" i]') ||
                /inbox|message|notification|add friend|hamburger|burger|menu/.test(combined)) continue;
            const hasHeaderClass = cls.includes('header-auth-coin-store-button');
            const explicitlyNamed = own.includes('coin store') ||
                own.includes('get coins') || own.includes('free coins');
            if (!hasHeaderClass && !explicitlyNamed) continue;
            let score = 0, reasons = [];
            if (hasHeaderClass) { score += 900; reasons.push('specific header Coin Store class'); }
            if (own.includes('coin store')) { score += 500; reasons.push('Coin Store own label'); }
            if (own.includes('get coins')) { score += 180; reasons.push('Get Coins own label'); }
            if (component.includes('coinstore')) { score += 240; reasons.push('CoinStore component'); }
            if (target.closest('header,nav,[class*="header-auth" i]')) score += 100;
            if (/purchase|checkout|pay now/.test(own)) score -= 2000;
            if (target.disabled || target.getAttribute('aria-disabled') === 'true') score -= 2000;
            const id = `sportzino-store-${candidates.length}`;
            target.setAttribute('data-sportzino-coin-store-id', id);
            candidates.push({id,score,own:own.slice(0,100),reasons});
        }
        return candidates.sort((a,b) => b.score - a.score);
    """, default=[])
    return result if isinstance(result, list) else []


def _open_rewards(sb: SB) -> bool:
    """Open Coin Store and verify it opened, with one guarded recovery."""
    if _rewards_dialog_open(sb):
        return True

    for attempt in range(2):
        if _inbox_panel_open(sb) and not _close_inbox(sb):
            print('[Sportzino] Inbox could not be dismissed. Returning to lobby.')
            sb.open(HOME_URL)
            sb.wait(2)
        candidates = _coin_store_candidates(sb)
        print('[Sportzino] Coin Store candidate ranking:', candidates[:4])
        for candidate in candidates:
            if int(candidate.get('score', 0)) < 500:
                continue
            target = f"[data-sportzino-coin-store-id='{candidate['id']}']"
            if not _force_click(sb, target, timeout=3):
                continue
            sb.wait(1.2)
            if _rewards_dialog_open(sb):
                print('[Sportzino] Confirmed Coin Store / free rewards view.')
                return True
            if _inbox_panel_open(sb):
                print('[Sportzino] Unexpected inbox after store click: closing it.')
                _close_inbox(sb)
                break
            print('[Sportzino] Click did not open a confirmed Coin Store.')
        if attempt == 0:
            print('[Sportzino] Recovering Coin Store navigation once from lobby.')
            sb.open(HOME_URL)
            sb.wait(2)
            _handle_cookie_consent(sb)

    return False

def _rewards_dialog_open(sb: SB) -> bool:
    """Detect the visible Sportzino Coin Store / Claim Free Rewards dialog."""
    return bool(
        _safe_js(
            sb,
            r"""
            const visible = (el) => {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();

                return (
                    style.display !== 'none' &&
                    style.visibility !== 'hidden' &&
                    style.opacity !== '0' &&
                    rect.width > 0 &&
                    rect.height > 0
                );
            };

            const normalize = (value) => (value || '')
                .replace(/\s+/g, ' ')
                .trim()
                .toLowerCase();

            const roots = Array.from(document.querySelectorAll(
                '.coin-store, .dialog-modal, [role="dialog"], ' +
                '[class*="coin-store" i]'
            )).filter(visible);

            return roots.some((root) => {
                const text = normalize(
                    root.innerText || root.textContent || ''
                );

                return (
                    text.includes('claim free rewards') ||
                    (
                        text.includes('coin store') &&
                        text.includes('purchase store packs')
                    ) || (
                        text.includes('daily bonus') &&
                        (text.includes('collect') || text.includes('claim')) &&
                        root.querySelector('button, [role="button"]')
                    )
                );
            });
            """,
            default=False,
        )
    )


def _visible_checkout_detected(sb: SB) -> bool:
    """
    Detect only a visible checkout/payment dialog.

    The previous implementation searched all body text, including hidden
    application markup, which falsely classified the open Coin Store as
    checkout.
    """
    return bool(
        _safe_js(
            sb,
            r"""
            const visible = (el) => {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();

                return (
                    style.display !== 'none' &&
                    style.visibility !== 'hidden' &&
                    style.opacity !== '0' &&
                    rect.width > 0 &&
                    rect.height > 0
                );
            };

            const normalize = (value) => (value || '')
                .replace(/\s+/g, ' ')
                .trim()
                .toLowerCase();

            const roots = Array.from(document.querySelectorAll(
                '[role="dialog"], .dialog-modal, ' +
                '[class*="checkout" i], [class*="payment" i], ' +
                '[class*="order-summary" i]'
            )).filter(visible);

            return roots.some((root) => {
                const text = normalize(
                    root.innerText || root.textContent || ''
                );

                const isCoinStore =
                    text.includes('claim free rewards') &&
                    text.includes('purchase store packs');

                if (isCoinStore) return false;

                const checkoutSignals = [
                    'order summary',
                    'payment method',
                    'total amount to pay',
                    'credit/debit',
                    'pay using',
                    'complete purchase',
                    'billing information'
                ];

                return checkoutSignals.some(
                    (signal) => text.includes(signal)
                );
            });
            """,
            default=False,
        )
    )


def _daily_claim_candidates(sb: SB) -> list[Dict[str, Any]]:
    """Rank visible *daily* claim buttons only inside an opened Coin Store.

    Absolute XPath is included as a candidate source but never bypasses
    contextual scoring. Header/inbox/checkout controls are always rejected.
    """
    if not _rewards_dialog_open(sb) or _inbox_panel_open(sb):
        print('[Sportzino] Claim scan blocked: Coin Store not confirmed or inbox open.')
        return []

    result = _safe_js(sb, r"""
        const xpath = arguments[0];
        const visible = el => {
            if (!el) return false;
            const s = getComputedStyle(el), r = el.getBoundingClientRect();
            return s.display !== 'none' && s.visibility !== 'hidden' &&
                r.width > 0 && r.height > 0;
        };
        const norm = x => (x || '').replace(/\s+/g, ' ').trim().toLowerCase();
        const controls = new Set([...document.querySelectorAll('button, [role="button"]')]);
        let inspected = null;
        try { inspected = document.evaluate(xpath, document, null,
            XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue; }
        catch (_) { /* changed DOM; dynamic candidate discovery still works */ }
        if (inspected && inspected.matches('button, [role="button"]')) controls.add(inspected);
        const candidates = [];
        for (const button of controls) {
            if (!visible(button)) continue;
            if (button.closest('header, nav, [class*="inbox" i], ' +
                '[class*="checkout" i], [class*="payment" i]')) continue;
            const own = norm(button.innerText || button.textContent ||
                button.getAttribute('aria-label') || button.getAttribute('title') || '');
            if (!/^(collect|claim)(\s|$)/.test(own)) continue;
            const disabled = Boolean(button.disabled ||
                button.getAttribute('aria-disabled') === 'true' ||
                norm(button.className).includes('disabled'));
            const coinRoot = button.closest('.coin-store, .coin-store-content, ' +
                '[class*="coin-store-section" i], [class*="coin-store-free-rewards" i], ' +
                '[role="dialog"], .dialog-modal');
            if (!coinRoot) continue;
            const dailyRoot = button.closest(
                '.coin-store-free-rewards-row-item.daily-bonus, [class~="daily-bonus"], ' +
                '[class*="serial-daily-bonus" i], [class*="progressive-daily" i]');
            const rewardCard = button.closest(
                '.coin-store-free-rewards-card, .coin-store-free-rewards-row-item, ' +
                '[class*="free-rewards-card" i]');
            // React can change wrappers. Look only at compact ancestors,
            // not the entire store, to avoid borrowing another card's label.
            let contextual = null;
            for (let node = button.parentElement, depth = 0;
                 node && depth < 10 && node !== coinRoot; node = node.parentElement, depth++) {
                const t = norm(node.innerText || node.textContent || '');
                if (t.length <= 800 && /(?:progressive\s+)?daily\s+bonus/.test(t)) {
                    contextual = node; break;
                }
            }
            const root = dailyRoot || contextual || rewardCard || button.parentElement;
            const local = norm(root?.innerText || root?.textContent || '');
            const cls = norm(button.className);
            const component = norm(button.getAttribute('data-sentry-component'));
            const hasDaily = Boolean(dailyRoot || contextual);
            const inspectedPath = button === inspected;
            const reasons = [];
            let score = own === 'collect' ? 120 : own === 'claim' ? 100 : 50;
            if (cls.includes('coin-store-collect-button')) {
                score += 220; reasons.push('Coin Store collect class');
            }
            if (component.includes('coinstorecollectbutton')) {
                score += 220; reasons.push('Coin Store component');
            }
            if (dailyRoot) { score += 650; reasons.push('daily bonus DOM ancestor'); }
            if (contextual) { score += 400; reasons.push('compact daily context'); }
            if (local.includes('progressive daily bonus')) {
                score += 320; reasons.push('Progressive Daily Bonus label');
            } else if (local.includes('daily bonus')) {
                score += 250; reasons.push('Daily Bonus label');
            }
            if (inspectedPath) { score += 80; reasons.push('user-inspected XPath match'); }
            if (/\bday [1-7]\b/.test(local)) { score += 60; reasons.push('daily progression'); }
            if (/facebook|google grab|connect with google|purchase|checkout|pay using|buy now|\$\s*\d/.test(local)) {
                score -= 1500; reasons.push('unrelated/purchase context');
            }
            if (disabled) { score -= 2000; reasons.push('disabled'); }
            const id = `sportzino-daily-claim-${candidates.length}`;
            button.setAttribute('data-sportzino-daily-claim-id', id);
            candidates.push({ id, score, text:own, localText:local.slice(0,260),
                className:cls, component, disabled, hasDailyRoot:Boolean(dailyRoot),
                hasDailyContext:hasDaily, inspectedPath, reasons });
        }
        return candidates.sort((a,b) => b.score - a.score);
    """, CURRENT_DAILY_CLAIM_XPATH, default=[])
    return result if isinstance(result, list) else []

def _select_daily_claim_candidate(sb: SB) -> Optional[Dict[str, Any]]:
    candidates = _daily_claim_candidates(sb)
    if not candidates:
        print('[Sportzino] No eligible visible Daily Bonus claim candidates.')
        return None
    print('[Sportzino] Daily claim candidate ranking:')
    for index, candidate in enumerate(candidates[:8], 1):
        print(f"  #{index} score={candidate.get('score')} "
              f"text={candidate.get('text')!r} "
              f"context={_short(candidate.get('localText', ''), 130)!r} "
              f"reasons={candidate.get('reasons')}")

    best = candidates[0]
    if int(best.get('score', 0)) < 800 or not best.get('hasDailyContext'):
        print('[Sportzino] Rejected candidate without strong local daily evidence.')
        return None
    if len(candidates) > 1:
        runner_up = int(candidates[1].get('score', 0))
        if int(best.get('score', 0)) - runner_up < 100:
            print('[Sportzino] Ambiguous top candidates; refusing to click.')
            return None
    return best


def _click_daily_collect(sb: SB) -> Optional[Dict[str, Any]]:
    candidate = _select_daily_claim_candidate(sb)
    if not candidate:
        return None
    locator = f"[data-sportzino-daily-claim-id='{candidate['id']}']"
    # Revalidate before acting: stale controls / a different modal may now exist.
    if not _rewards_dialog_open(sb) or _inbox_panel_open(sb):
        print('[Sportzino] Claim canceled: Coin Store no longer exclusively open.')
        return None
    if _force_click(sb, locator, timeout=3):
        print('[Sportzino] Clicked the verified Progressive Daily Bonus candidate.')
        return candidate
    print('[Sportzino] Candidate click did not complete; not clicking a random XPath.')
    return None

def _daily_claim_observation(sb: SB) -> Dict[str, Any]:
    """Visible daily card metrics, never inferred from unrelated body text."""
    data = _safe_js(sb, r"""
        const visible = el => {
            const s = getComputedStyle(el), r = el.getBoundingClientRect();
            return s.display !== 'none' && s.visibility !== 'hidden' &&
                r.width > 0 && r.height > 0;
        };
        const norm = x => (x || '').replace(/\s+/g, ' ').trim();
        const containers = [...document.querySelectorAll(
            '.coin-store-free-rewards-row-item.daily-bonus, [class~="daily-bonus"], ' +
            '[class*="serial-daily-bonus" i], [class*="progressive-daily" i]'
        )].filter(visible);
        const outerRoots = containers.filter(el => !containers.some(
            parent => parent !== el && parent.contains(el)));
        // React can rename the daily-bonus wrapper. Recover a compact card
        // containing 'Daily Bonus' and an action button, without ever using
        // the whole Coin Store or the page body as the daily card.
        const fallbacks = [...document.querySelectorAll(
            '.coin-store-free-rewards-row-item, .coin-store-free-rewards-card, ' +
            '[class*="free-rewards-card" i], [class*="daily" i]'
        )].filter(visible).filter(el => {
            const t = norm(el.innerText || el.textContent || '');
            return t.length <= 800 && /daily bonus/i.test(t) &&
                el.querySelector('button, [role="button"]');
        });
        const roots = outerRoots.length ? outerRoots : fallbacks.filter(
            el => !fallbacks.some(parent => parent !== el && parent.contains(el)));
        const txt = roots.map(el => norm(el.innerText || el.textContent || '')).join(' | ');
        const buttons = roots.flatMap(root => [...root.querySelectorAll('button, [role="button"]')])
            .filter(visible).filter(el => /^(collect|claim)(\s|$)/i.test(norm(el.innerText || el.textContent || '')));
        const enabled = buttons.filter(b => !b.disabled &&
            b.getAttribute('aria-disabled') !== 'true');
        const notices = [...document.querySelectorAll(
            '[role="status"], [role="alert"], [class*="toast" i], ' +
            '[class*="notification" i]'
        )].filter(visible).map(e => norm(e.innerText || e.textContent || '')).join(' | ');
        return { dailyRootCount:roots.length, dailyText:txt, collectCount:buttons.length,
            enabledCollectCount:enabled.length, disabledCollectCount:buttons.length-enabled.length,
            visibleMessageText:notices };
    """, default={})
    if not isinstance(data, dict):
        return { 'dailyRootCount': 0, 'dailyText': '', 'collectCount': 0,
                 'enabledCollectCount': 0, 'disabledCollectCount': 0,
                 'visibleMessageText': '' }
    return data

def _current_state(sb: SB) -> Dict[str, str]:
    snapshot = _page_snapshot(sb)
    if _is_login_page(sb):
        return { 'status':'login', 'reason':'Login page still visible',
                 'evidence':snapshot['url'] }
    if _inbox_panel_open(sb):
        return { 'status':'inbox', 'reason':'New inbox panel is open, not Coin Store',
                 'evidence':snapshot['url'] }
    if _visible_checkout_detected(sb):
        return { 'status':'checkout', 'reason':'Visible checkout/payment dialog',
                 'evidence':'VISIBLE CHECKOUT DIALOG' }

    observation = _daily_claim_observation(sb)
    daily = observation.get('dailyText', '')
    notices = observation.get('visibleMessageText', '')
    claimed = _first_marker(daily, CLAIMED_MARKERS)
    if claimed:
        return {'status':'claimed', 'reason':'Daily Bonus card says claimed',
                'evidence':claimed}
    # Only accept a claim success notification explicitly linked to a bonus.
    notice_upper = _up(notices)
    if ('BONUS' in notice_upper or 'REWARD' in notice_upper) and _contains_any(
        notices, ('CLAIMED', 'COLLECTED', 'SUCCESSFULLY CLAIMED')):
        return {'status':'success', 'reason':'Visible bonus claim notification',
                'evidence':_short(notices, 140)}
    if _contains_any(daily, ('UNAVAILABLE', 'COME BACK TOMORROW', 'ALREADY CLAIMED')):
        return {'status':'unavailable', 'reason':'Daily Bonus card says unavailable',
                'evidence':_short(daily, 140)}
    if _rewards_dialog_open(sb):
        return {'status':'rewards', 'reason':'Coin Store rewards view is open',
                'evidence':_short(daily, 140)}
    return {'status':'unknown', 'reason':'No recognizable rewards interface open',
            'evidence':snapshot['url']}

def _wait_for_claim_result(
    sb: SB, before: Dict[str, Any], timeout: float = 18
) -> Dict[str, str]:
    """Conservative one-shot verification. Never resend a possible claim."""
    step = 0.5
    loops = max(1, int(timeout / step))
    stable_disabled = 0
    before_enabled = int(before.get('enabledCollectCount', 0))
    before_roots = int(before.get('dailyRootCount', 0))
    for _ in range(loops):
        state = _current_state(sb)
        obs = _daily_claim_observation(sb)
        if state['status'] in ('claimed', 'success', 'login', 'checkout', 'inbox'):
            return state
        after_enabled = int(obs.get('enabledCollectCount', 0))
        after_roots = int(obs.get('dailyRootCount', 0))
        # Require both before/after daily card presence. An inbox/closed Coin
        # Store also makes Collect disappear, but does NOT prove a claim.
        if (before_enabled > 0 and before_roots > 0 and after_roots > 0 and
                after_enabled == 0 and state['status'] == 'rewards'):
            stable_disabled += 1
        else:
            stable_disabled = 0
        print('[Sportzino] Claim verification:', state['status'],
              'daily_roots=', after_roots, 'enabled=', after_enabled,
              'stable_disabled=', stable_disabled)
        if stable_disabled >= 3:
            return {'status':'success',
                    'reason':'Daily Bonus card remained visible with Collect disabled',
                    'evidence':f'before_enabled={before_enabled} after_enabled={after_enabled}'}
        if state['status'] == 'unavailable':
            # Could mean a successful claim was just processed or today's
            # reward was unavailable. Do not repeat the request.
            return state
        sb.wait(step)
    return {'status':'unverified',
            'reason':'Claim clicked, but no reliable confirmation was observed',
            'evidence':'No automatic second click was performed'}

async def Sportzino(ctx, driver, channel: discord.abc.Messageable):
    """
    Sportzino via SeleniumBase UC.

    Discord behavior:
    - The surrounding command/worker may send its normal launch messages.
    - On success, send: Sportzino Daily Bonus Claimed!
    - When unavailable, send: Sportzino Daily Bonus Unavailable.
    - Send the final screenshot after the status message.
    - All other claim details, scoring, and errors are printed locally.

    Claim safety:
    - Scores every visible Collect/Claim control.
    - Requires a strong Progressive Daily Bonus / daily-bonus DOM signal.
    - Rejects Facebook, Google, purchase, checkout, and ambiguous candidates.
    - Verifies success using a scoped confirmation or a persistent daily card change.
    - Never retries a claim merely because a result timed out.
    """
    del ctx, driver

    if ":" not in SPORTZINO_CRED:
        print(
            "[Sportzino][ERROR] SPORTZINO is missing from .env. "
            "Expected email:password."
        )
        return

    username, password = SPORTZINO_CRED.split(":", 1)
    sb: Optional[SB] = None

    try:
        with SB(uc=True, headed=True) as sb:
            # ── Step 1: login ──

            login_result = _login(sb, username, password)
            print(f"[Sportzino] Login result: {login_result}")

            if login_result["status"] != "authenticated":
                await _send_screenshot(
                    sb,
                    channel,
                    (
                        "[Sportzino] Login did not complete — "
                        f"{login_result['reason']}. "
                        "Not attempting a claim."
                    ),
                    "sportzino_login_failed",
                )
                return

            # ── Step 2: normalize to lobby and open Coin Store ──

            current_url = _page_snapshot(sb)["url"]

            if (
                not current_url or
                any(
                    token in current_url.lower()
                    for token in (
                        "/auth/callback",
                        "/connect/authorize",
                        "/login",
                    )
                )
            ):
                sb.open(HOME_URL)

            try:
                sb.wait_for_ready_state_complete()
            except Exception:
                pass

            sb.wait(4)
            _handle_cookie_consent(sb)
            _close_popups_before_rewards(sb)

            if _is_login_page(sb):
                await _send_screenshot(
                    sb,
                    channel,
                    (
                        "[Sportzino] Login session did not persist after "
                        "the lobby redirect."
                    ),
                    "sportzino_session_lost",
                )
                return

            opened_rewards = _open_rewards(sb)

            if not opened_rewards:
                state = _current_state(sb)
                print(
                    "[Sportzino] Could not open Coin Store. "
                    f"Current state: {state}"
                )

                await _send_screenshot(
                    sb,
                    channel,
                    (
                        "[Sportzino] Coin Store was not found after "
                        "confirmed login."
                    ),
                    "sportzino_rewards_missing",
                )
                return

            sb.wait(4)
            _handle_cookie_consent(sb)

            if not _rewards_dialog_open(sb):
                await _send_screenshot(sb, channel,
                    '[Sportzino] Coin Store is not visible; aborting safely.',
                    'sportzino_store_unconfirmed')
                return

            print("[Sportzino] Coin Store / rewards interface confirmed.")

            # ── Step 3: inspect the Progressive Daily Bonus ──

            pre_state = _current_state(sb)
            before = _daily_claim_observation(sb)

            print(f"[Sportzino] Pre-claim state: {pre_state}")
            print(
                "[Sportzino] Pre-claim daily observation: "
                f"{before}"
            )

            if pre_state["status"] == "login":
                await _send_screenshot(
                    sb,
                    channel,
                    "[Sportzino] Login expired before the claim could run.",
                    "sportzino_login_expired",
                )
                return

            # Checkout is now based only on an actually visible payment dialog.
            if pre_state["status"] == "checkout":
                await _send_screenshot(
                    sb,
                    channel,
                    (
                        "[Sportzino] A visible checkout/payment dialog was "
                        "detected. No claim button was clicked."
                    ),
                    "sportzino_checkout_pre",
                )
                return

            if pre_state["status"] == "inbox":
                await _send_screenshot(sb, channel,
                    '[Sportzino] Inbox interrupted rewards navigation. No claim attempted.',
                    'sportzino_inbox_interrupted')
                return

            if pre_state["status"] in ("claimed", "unavailable"):
                await _send_screenshot(
                    sb,
                    channel,
                    "Sportzino Daily Bonus Unavailable.",
                    "sportzino_already_claimed",
                    discord_message="Sportzino Daily Bonus Unavailable.",
                )
                return

            # ── Step 4: candidate scoring and guarded click ──

            clicked_candidate = _click_daily_collect(sb)

            if clicked_candidate is None:
                after_scan = _daily_claim_observation(sb)

                print(
                    "[Sportzino] No safe Progressive Daily Bonus Collect "
                    "candidate was available."
                )
                print(
                    "[Sportzino] Daily observation after failed scan: "
                    f"{after_scan}"
                )

                status = _current_state(sb)
                if status['status'] in ('claimed', 'unavailable') or (
                    after_scan.get('dailyRootCount', 0) > 0 and
                    after_scan.get('collectCount', 0) > 0 and
                    after_scan.get('enabledCollectCount', 0) == 0
                ):
                    await _send_screenshot(sb, channel,
                        'Sportzino Daily Bonus Unavailable.',
                        'sportzino_no_safe_claim',
                        discord_message='Sportzino Daily Bonus Unavailable.')
                else:
                    await _send_screenshot(sb, channel,
                        '[Sportzino] No verified daily bonus button found; check screenshot.',
                        'sportzino_no_verified_claim')
                return

            # ── Step 5: verify the result ──

            result = _wait_for_claim_result(
                sb,
                before=before,
                timeout=18,
            )

            print(f"[Sportzino] Final claim result: {result}")

            if result["status"] in ("success", "claimed"):
                await _send_screenshot(
                    sb,
                    channel,
                    "Sportzino Daily Bonus Claimed!",
                    "sportzino_claimed",
                    discord_message="Sportzino Daily Bonus Claimed!",
                )
                return

            if result["status"] in ('inbox', 'unavailable'):
                await _send_screenshot(sb, channel,
                    '[Sportzino] Claim result not confirmed; state: ' + result['status'],
                    'sportzino_post_claim_uncertain')
                return

            if result["status"] == "checkout":
                await _send_screenshot(
                    sb,
                    channel,
                    (
                        "[Sportzino] Claim interaction opened a visible "
                        "checkout/payment dialog. Not marking as claimed."
                    ),
                    "sportzino_checkout_false_positive",
                )
                return

            if result["status"] == "login":
                await _send_screenshot(
                    sb,
                    channel,
                    (
                        "[Sportzino] Login expired immediately after the "
                        "claim interaction."
                    ),
                    "sportzino_post_click_login",
                )
                return

            await _send_screenshot(
                sb,
                channel,
                (
                    "[Sportzino] The Progressive Daily Bonus button was "
                    "clicked, but the claim could not be verified."
                ),
                "sportzino_unverified",
            )

    except Exception as error:
        print(f"[Sportzino][ERROR] Exception during automation: {error}")

        try:
            if sb is not None:
                await _send_screenshot(
                    sb,
                    channel,
                    f"[Sportzino][ERROR] Automation crashed: {error}",
                    "sportzino_error",
                )
        except Exception as reporting_error:
            print(
                "[Sportzino][ERROR] Failed while reporting crash: "
                f"{reporting_error}"
            )

