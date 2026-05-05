# Drake Hooks
# Casino Claim 3
# WinBonanza API (SeleniumBase UC)
#
# Exposes:
#   async def winbonanza_casino(ctx=None, driver=None, channel=None)
#   async def winbonanza_uc(ctx=None, channel=None)
#   async def claim_winbonanza(channel=None, ctx=None, driver=None, headless=None)
#
# ENV:
#   WINBONANZA=email:password

import os
import time
import contextlib
from pathlib import Path
from typing import Optional, Tuple, List

import discord
from dotenv import load_dotenv
from seleniumbase import SB


load_dotenv()


SITE_NAME = "WinBonanza"
LOGIN_URL = "https://winbonanza.com/login"
LOBBY_URL = "https://winbonanza.com/lobby"

SCREENSHOT_DIR = Path("screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)


# ───────────────────────────────────────────────────────────
# ENV
# ───────────────────────────────────────────────────────────

def get_winbonanza_credentials() -> Tuple[str, str]:
    raw = os.getenv("WINBONANZA", "").strip()

    if ":" not in raw:
        return "", ""

    email, password = raw.split(":", 1)
    return email.strip(), password.strip()


# ───────────────────────────────────────────────────────────
# DISCORD HELPERS
# ───────────────────────────────────────────────────────────

async def _send_screenshot(
    sb: SB,
    channel: discord.abc.Messageable,
    path: str,
    caption: str,
):
    try:
        sb.save_screenshot(path)
        await channel.send(caption, file=discord.File(path))
    finally:
        with contextlib.suppress(Exception):
            if os.path.exists(path):
                os.remove(path)


# ───────────────────────────────────────────────────────────
# BASIC HELPERS
# ───────────────────────────────────────────────────────────

def sleep(seconds: float):
    time.sleep(seconds)


def wait_ready(sb: SB):
    with contextlib.suppress(Exception):
        sb.wait_for_ready_state_complete()


def get_current_url(sb: SB) -> str:
    try:
        return sb.get_current_url()
    except Exception:
        with contextlib.suppress(Exception):
            return sb.driver.current_url
    return ""


def get_body_text(sb: SB) -> str:
    try:
        return sb.execute_script("return document.body ? document.body.innerText : '';") or ""
    except Exception:
        return ""


def visible(sb: SB, selector: str, timeout: int = 8) -> bool:
    try:
        sb.wait_for_element_visible(selector, timeout=timeout)
        return True
    except Exception:
        return False


def element_exists(sb: SB, selector: str) -> bool:
    try:
        return bool(sb.execute_script("return !!document.querySelector(arguments[0]);", selector))
    except Exception:
        return False


def click_css(sb: SB, selector: str, timeout: int = 8) -> bool:
    try:
        sb.wait_for_element_visible(selector, timeout=timeout)
    except Exception:
        return False

    with contextlib.suppress(Exception):
        sb.scroll_to(selector)

    for mode in ("click", "slow", "js", "directjs"):
        try:
            if mode == "click":
                sb.click(selector, timeout=2)
            elif mode == "slow":
                sb.slow_click(selector)
            elif mode == "js":
                sb.js_click(selector)
            else:
                el = sb.find_element(selector)
                sb.execute_script("arguments[0].click();", el)
            return True
        except Exception:
            continue

    return False


def click_xpath(sb: SB, xpath: str, timeout: int = 8) -> bool:
    try:
        sb.wait_for_element_visible(xpath, by="xpath", timeout=timeout)
    except Exception:
        return False

    with contextlib.suppress(Exception):
        sb.scroll_to(xpath, by="xpath")

    for mode in ("click", "slow", "js", "directjs"):
        try:
            if mode == "click":
                sb.click_xpath(xpath, timeout=2)
            elif mode == "slow":
                sb.slow_click(xpath)
            elif mode == "js":
                sb.js_click(xpath)
            else:
                el = sb.find_element(xpath, by="xpath")
                sb.execute_script("arguments[0].click();", el)
            return True
        except Exception:
            continue

    return False


def click_any_xpath(sb: SB, xpaths: List[str], timeout_each: int = 5) -> bool:
    for xpath in xpaths:
        if click_xpath(sb, xpath, timeout=timeout_each):
            return True
    return False


def click_by_text(
    sb: SB,
    text_options,
    selectors: str = "button, [role='button'], a, div, span",
) -> bool:
    script = """
    const wanted = arguments[0].map(t => String(t).trim().toUpperCase());
    const selectors = arguments[1];

    const els = Array.from(document.querySelectorAll(selectors));

    function visible(el) {
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();

        return (
            style.display !== "none" &&
            style.visibility !== "hidden" &&
            style.opacity !== "0" &&
            rect.width > 0 &&
            rect.height > 0
        );
    }

    const matches = els.filter(el => {
        if (!visible(el)) return false;

        const text = (el.innerText || el.textContent || "")
            .replace(/\\s+/g, " ")
            .trim()
            .toUpperCase();

        if (!text) return false;

        return wanted.some(w => text.includes(w));
    });

    if (!matches.length) return false;

    matches.sort((a, b) => {
        const score = el => {
            let s = 0;
            const tag = el.tagName || "";
            const cls = (el.className || "").toString().toLowerCase();

            if (tag === "BUTTON") s += 40;
            if (cls.includes("btn")) s += 10;
            if (cls.includes("button")) s += 10;
            if (cls.includes("submit")) s += 10;
            if (cls.includes("active")) s += 5;
            if (cls.includes("collect")) s += 5;
            if (cls.includes("coin-store")) s += 5;

            return s;
        };

        return score(b) - score(a);
    });

    const el = matches[0];

    el.scrollIntoView({ block: "center", inline: "center" });

    ["pointerdown", "mousedown", "pointerup", "mouseup", "click"].forEach(type => {
        el.dispatchEvent(new MouseEvent(type, {
            bubbles: true,
            cancelable: true,
            view: window
        }));
    });

    try { el.click(); } catch (e) {}

    return true;
    """

    try:
        return bool(sb.execute_script(script, list(text_options), selectors))
    except Exception:
        return False


# ───────────────────────────────────────────────────────────
# REACT-SAFE INPUTS
# ───────────────────────────────────────────────────────────

def set_react_input(sb: SB, selector: str, value: str, timeout: int = 15) -> bool:
    try:
        sb.wait_for_element_visible(selector, timeout=timeout)

        ok = sb.execute_script(
            """
            const selector = arguments[0];
            const value = arguments[1];

            const input = document.querySelector(selector);
            if (!input) return false;

            input.scrollIntoView({ block: "center", inline: "center" });
            input.focus();

            const nativeSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype,
                "value"
            ).set;

            nativeSetter.call(input, value);

            input.dispatchEvent(new InputEvent("input", {
                bubbles: true,
                inputType: "insertText",
                data: value
            }));

            input.dispatchEvent(new Event("change", { bubbles: true }));

            return input.value === value;
            """,
            selector,
            value,
        )

        sleep(0.4)

        if ok:
            return True

        with contextlib.suppress(Exception):
            sb.clear(selector)
            sb.type(selector, value)
            sleep(0.4)
            return True

        return False

    except Exception:
        return False


def set_react_input_any(sb: SB, selectors: List[str], value: str, timeout_each: int = 6) -> bool:
    for selector in selectors:
        if set_react_input(sb, selector, value, timeout=timeout_each):
            return True
    return False


# ───────────────────────────────────────────────────────────
# PAGE STATE
# ───────────────────────────────────────────────────────────

def is_logged_in(sb: SB) -> bool:
    url = get_current_url(sb).lower()
    text = get_body_text(sb).lower()

    if "/lobby" in url:
        return True

    if element_exists(sb, "button[data-testid='coin-store-entry']"):
        return True

    if element_exists(sb, "button.coin-store-button"):
        return True

    if "get coins" in text and ("continue playing" in text or "special offers" in text):
        return True

    return False


def wait_for_logged_in(sb: SB, timeout: int = 45) -> bool:
    end = time.time() + timeout

    while time.time() < end:
        if is_logged_in(sb):
            return True

        text = get_body_text(sb).lower()

        if "invalid" in text or "incorrect" in text or "wrong password" in text:
            return False

        sleep(1)

    return False


def wait_for_coin_store(sb: SB, timeout: int = 25) -> bool:
    end = time.time() + timeout

    while time.time() < end:
        text = get_body_text(sb).upper()

        if "COIN STORE" in text and "CLAIM FREE REWARDS" in text:
            return True

        if "DAILY BONUS" in text and "COLLECT" in text:
            return True

        try:
            found = sb.execute_script(
                """
                return !!(
                    document.querySelector("[data-testid='new-daily-bonus']") ||
                    document.querySelector(".daily-bonus-collect-button") ||
                    document.querySelector(".free-rewards-section") ||
                    document.querySelector(".coin-store-section")
                );
                """
            )

            if found:
                return True

        except Exception:
            pass

        sleep(0.5)

    return False


# ───────────────────────────────────────────────────────────
# LOGIN FLOW
# ───────────────────────────────────────────────────────────

def open_login_page(sb: SB) -> bool:
    try:
        sb.uc_open_with_reconnect(LOGIN_URL, 4)
    except Exception:
        try:
            sb.open(LOGIN_URL)
        except Exception:
            return False

    wait_ready(sb)
    sleep(3)

    return "winbonanza.com" in get_current_url(sb).lower()


def login_winbonanza(sb: SB) -> bool:
    if not open_login_page(sb):
        return False

    if is_logged_in(sb):
        return True

    email, password = get_winbonanza_credentials()

    email_selectors = [
        "#emailAddress",
        "input#emailAddress",
        "input[name='username']",
        "input[name='email']",
        "input[type='email']",
        "input[placeholder='Email']",
        "input[data-testid='login-email-input']",
    ]

    password_selectors = [
        "#password",
        "input#password",
        "input[name='password']",
        "input[type='password']",
        "input[placeholder='Password']",
        "input[data-testid='login-password-input']",
    ]

    email_ok = set_react_input_any(sb, email_selectors, email)
    pass_ok = set_react_input_any(sb, password_selectors, password)

    if not email_ok or not pass_ok:
        return False

    with contextlib.suppress(Exception):
        sb.uc_gui_click_captcha()
        sb.wait(10)

    submitted = False

    for pwd_sel in password_selectors:
        try:
            if visible(sb, pwd_sel, timeout=2):
                sb.press_keys(pwd_sel, "\n")
                submitted = True
                break
        except Exception:
            continue

    if submitted:
        sleep(6)
        wait_ready(sb)
        if wait_for_logged_in(sb, timeout=25):
            return True

    if click_css(sb, "form button[type='submit']", timeout=5):
        sleep(6)
        wait_ready(sb)
        return wait_for_logged_in(sb, timeout=30)

    if click_by_text(sb, ["LOG IN", "LOGIN", "SIGN IN"], selectors="button, [role='button']"):
        sleep(6)
        wait_ready(sb)
        return wait_for_logged_in(sb, timeout=30)

    clicked = click_any_xpath(
        sb,
        [
            "//form//button[contains(translate(., 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'LOG IN')]",
            "//form//button[contains(translate(., 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'LOGIN')]",
            "//button[contains(translate(., 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'LOG IN')]",
            "//button[contains(translate(., 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'LOGIN')]",
        ],
        timeout_each=5,
    )

    if not clicked:
        return False

    sleep(6)
    wait_ready(sb)

    return wait_for_logged_in(sb, timeout=30)


# ───────────────────────────────────────────────────────────
# POST-LOGIN FLOW
# ───────────────────────────────────────────────────────────

def close_popups(sb: SB):
    sleep(1)

    click_any_xpath(
        sb,
        [
            "//button[contains(@class, 'close')]",
            "//button[contains(@aria-label, 'close')]",
            "//button[contains(@aria-label, 'Close')]",
            "//button[contains(text(), '×')]",
            "//button[contains(., 'Accept All')]",
            "//button[contains(., 'ACCEPT ALL')]",
            "//button[contains(., 'Got it')]",
            "//button[contains(., 'Dismiss')]",
            "/html/body/div[5]/div/div[1]/div/div/button",
            "/html/body/div[4]/div/div[1]/div/div/button",
            "/html/body/div[6]/div/div[1]/div/div/button",
        ],
        timeout_each=2,
    )

    with contextlib.suppress(Exception):
        sb.press_keys("body", "\ue00c")
        sleep(0.5)


def open_lobby_if_needed(sb: SB):
    if "/lobby" in get_current_url(sb).lower():
        return

    try:
        sb.uc_open_with_reconnect(LOBBY_URL, 2)
    except Exception:
        with contextlib.suppress(Exception):
            sb.open(LOBBY_URL)

    wait_ready(sb)
    sleep(3)


def open_coin_store(sb: SB) -> bool:
    open_lobby_if_needed(sb)
    close_popups(sb)
    sleep(1)

    selectors = [
        "button[data-testid='coin-store-entry']",
        "button.coin-store-button",
        "button[class*='coin-store-button']",
        "button.app-button--primary.coin-store-button",
        "[data-testid='coin-store-entry']",
    ]

    for selector in selectors:
        if click_css(sb, selector, timeout=6):
            sleep(2)
            return wait_for_coin_store(sb, timeout=20)

    for text_group in (
        ["GET COINS"],
        ["COIN STORE"],
        ["STORE"],
        ["REWARDS"],
        ["BUY COINS"],
    ):
        if click_by_text(sb, text_group, selectors="button, [role='button'], a, div"):
            sleep(2)
            return wait_for_coin_store(sb, timeout=20)

    return False


def click_collect_reward_js(sb: SB) -> Optional[str]:
    script = """
    function clean(s) {
        return String(s || "").replace(/\\s+/g, " ").trim();
    }

    function visible(el) {
        if (!el) return false;
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();

        return (
            style.display !== "none" &&
            style.visibility !== "hidden" &&
            style.opacity !== "0" &&
            rect.width > 0 &&
            rect.height > 0
        );
    }

    const preferredSelectors = [
        "[data-testid='new-daily-bonus'] button.daily-bonus-collect-button",
        "[data-testid='new-daily-bonus'] button[class*='collect']",
        ".serial-daily-bonus-box button.daily-bonus-collect-button",
        "button.daily-bonus-collect-button",
        "button[class*='daily-bonus'][class*='collect']",
        "button[class*='collect']"
    ];

    const candidates = [];

    for (const selector of preferredSelectors) {
        const buttons = Array.from(document.querySelectorAll(selector))
            .filter(button => visible(button) && !button.disabled);

        for (const button of buttons) {
            const card =
                button.closest("[data-testid='new-daily-bonus']") ||
                button.closest(".serial-daily-bonus-box") ||
                button.parentElement;

            const title = clean(card ? card.innerText : button.innerText);
            candidates.push({ title, button });
        }
    }

    if (!candidates.length) {
        const textButtons = Array.from(document.querySelectorAll("button"))
            .filter(button => {
                const txt = clean(button.innerText).toUpperCase();
                return visible(button) && !button.disabled && txt.includes("COLLECT");
            });

        for (const button of textButtons) {
            const card =
                button.closest("[data-testid='new-daily-bonus']") ||
                button.closest(".serial-daily-bonus-box") ||
                button.parentElement;

            const title = clean(card ? card.innerText : button.innerText);
            candidates.push({ title, button });
        }
    }

    if (!candidates.length) return "";

    candidates.sort((a, b) => {
        const score = item => {
            const title = clean(item.title).toUpperCase();
            const cls = String(item.button.className || "").toLowerCase();
            let s = 0;

            if (title.includes("DAILY BONUS")) s += 50;
            if (cls.includes("daily-bonus-collect-button")) s += 40;
            if (cls.includes("collect")) s += 10;

            return s;
        };

        return score(b) - score(a);
    });

    const chosen = candidates[0];

    chosen.button.scrollIntoView({ block: "center", inline: "center" });

    ["pointerdown", "mousedown", "pointerup", "mouseup", "click"].forEach(type => {
        chosen.button.dispatchEvent(new MouseEvent(type, {
            bubbles: true,
            cancelable: true,
            view: window
        }));
    });

    try { chosen.button.click(); } catch (e) {}

    return chosen.title || "Daily Bonus";
    """

    try:
        title = sb.execute_script(script)
        title = (title or "").strip()
        return title or None
    except Exception:
        return None


def click_collect_xpath_fallback(sb: SB) -> Optional[str]:
    xpaths = [
        "/html/body/div[5]/div/div[2]/div/div[2]/div[2]/div/div/div[3]/button[1]",
        "/html/body/div[5]/div/div[2]/div/div[2]/div[2]/div/div/div[3]/button[1]/div[1]",
        "//button[contains(@class, 'daily-bonus-collect-button')]",
        "//button[contains(@class, 'collect')]",
        "//button[contains(translate(., 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'COLLECT')]",
    ]

    for xpath in xpaths:
        if click_xpath(sb, xpath, timeout=4):
            sleep(2)
            return "Daily Bonus"

    return None


def collect_daily_bonus(sb: SB) -> bool:
    title = click_collect_reward_js(sb)

    if not title:
        title = click_collect_xpath_fallback(sb)

    if not title:
        return False

    sleep(4)
    return True


def run_claim_flow(sb: SB) -> str:
    """
    Returns:
      claimed
      unavailable
      login_failed
      store_failed
      open_failed
    """
    if not login_winbonanza(sb):
        return "login_failed"

    wait_ready(sb)
    sleep(2)

    close_popups(sb)

    if not open_coin_store(sb):
        return "store_failed"

    sleep(2)

    if collect_daily_bonus(sb):
        return "claimed"

    return "unavailable"


# ───────────────────────────────────────────────────────────
# PUBLIC RUNNERS
# ───────────────────────────────────────────────────────────

async def winbonanza_casino(ctx=None, driver=None, channel: Optional[discord.abc.Messageable] = None):
    """
    Public runner.

    Sends:
      - launch notice
      - final success/unavailable/error screenshot
    """
    if channel is None and ctx is not None:
        channel = ctx.channel

    if channel is None:
        raise RuntimeError("winbonanza_casino needs a Discord channel or ctx.")

    email, password = get_winbonanza_credentials()

    if not email or not password:
        await channel.send(
            "❌ Missing WinBonanza credentials in `.env`.\n\n"
            "Use:\n"
            "`WINBONANZA=email:password`"
        )
        return

    await channel.send("Launching **WinBonanza** (UC)...")

    try:
        with SB(uc=True, headed=True) as sb:
            try:
                result = run_claim_flow(sb)

                if result == "claimed":
                    await _send_screenshot(
                        sb,
                        channel,
                        "winbonanza_claimed.png",
                        "WinBonanza Daily Bonus Claimed!",
                    )
                    return

                if result == "unavailable":
                    await _send_screenshot(
                        sb,
                        channel,
                        "winbonanza_unavailable.png",
                        "[WinBonanza] Bonus unavailable (likely already claimed).",
                    )
                    return

                if result == "open_failed":
                    await _send_screenshot(
                        sb,
                        channel,
                        "winbonanza_open_failed.png",
                        "[WinBonanza] Could not open the login page.",
                    )
                    return

                if result == "login_failed":
                    await _send_screenshot(
                        sb,
                        channel,
                        "winbonanza_login_failed.png",
                        "[WinBonanza] Login failed.",
                    )
                    return

                if result == "store_failed":
                    await _send_screenshot(
                        sb,
                        channel,
                        "winbonanza_store_failed.png",
                        "[WinBonanza] Could not open the coin store or rewards modal.",
                    )
                    return

                await _send_screenshot(
                    sb,
                    channel,
                    "winbonanza_unknown.png",
                    f"[WinBonanza] Unknown result: {result}",
                )

            except Exception as e:
                await _send_screenshot(
                    sb,
                    channel,
                    "winbonanza_error.png",
                    f"[WinBonanza] Claim error: {type(e).__name__}: {e}",
                )

    except Exception as e:
        await channel.send(f"[WinBonanza] Browser error: `{type(e).__name__}: {e}`")


async def winbonanza_uc(ctx=None, channel: Optional[discord.abc.Messageable] = None):
    await winbonanza_casino(ctx=ctx, channel=channel)


async def claim_winbonanza(
    channel: Optional[discord.abc.Messageable] = None,
    ctx=None,
    driver=None,
    headless=None,
):
    await winbonanza_casino(ctx=ctx, driver=driver, channel=channel)


if __name__ == "__main__":
    with SB(uc=True, headed=True) as sb:
        opened = open_login_page(sb)
        print("Opened:", opened, get_current_url(sb))
        sleep(10)