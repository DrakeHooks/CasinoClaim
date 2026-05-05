# Drake Hooks
# Casino Claim 3
# Luck Party API (SeleniumBase UC)
#
# Sportzino-style flow:
#   - async function
#   - with SB(uc=True, headed=True) directly inside the async function
#   - no executor / no thread wrapper
#   - sends only a final screenshot:
#       * success screenshot, or
#       * unavailable/error screenshot
#
# Exposes:
#   async def luckparty_casino(ctx, driver, channel)
#   async def claim_luckparty(channel=None, ctx=None, driver=None, headless=None)
#   async def claim_bonus(channel=None, headless=None)
#   async def run(channel=None, headless=None)
#   async def main(channel=None, headless=None)

import os
import time
import contextlib
from pathlib import Path
from typing import Optional, Tuple, List

import discord
from dotenv import load_dotenv
from seleniumbase import SB


load_dotenv()


SITE_NAME = "Luck Party"
LOGIN_URL = "https://luckparty.com/login"
LOBBY_URL = "https://luckparty.com/lobby"

SCREENSHOT_DIR = Path("screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)


# ───────────────────────────────────────────────────────────
# ENV
# ───────────────────────────────────────────────────────────

def first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def get_luckparty_credentials() -> Tuple[str, str]:
    """
    Supports either:

      LUCKPARTY_LOGIN=email:password

    or:

      LUCKPARTY_EMAIL=email
      LUCKPARTY_PASSWORD=password

    Also accepts LUCKYPARTY_* variants for compatibility.
    """
    combined = first_env(
        "LUCKPARTY_LOGIN",
        "LUCK_PARTY_LOGIN",
        "LUCKYPARTY_LOGIN",
        "LUCKY_PARTY_LOGIN",
    )

    if combined and ":" in combined:
        email, password = combined.split(":", 1)
        return email.strip(), password.strip()

    email = first_env(
        "LUCKPARTY_EMAIL",
        "LUCK_PARTY_EMAIL",
        "LUCKYPARTY_EMAIL",
        "LUCKY_PARTY_EMAIL",
        "LUCKPARTYEMAIL",
        "LUCKYPARTYEMAIL",
    )

    password = first_env(
        "LUCKPARTY_PASSWORD",
        "LUCK_PARTY_PASSWORD",
        "LUCKYPARTY_PASSWORD",
        "LUCKY_PARTY_PASSWORD",
        "LUCKPARTYPASSWORD",
        "LUCKYPARTYPASSWORD",
    )

    return email, password


# ───────────────────────────────────────────────────────────
# DISCORD HELPERS
# ───────────────────────────────────────────────────────────

async def _send_screenshot(
    sb: SB,
    channel: discord.abc.Messageable,
    path: str,
    caption: str,
):
    """
    Save -> send -> cleanup.
    """
    try:
        sb.save_screenshot(path)
        await channel.send(caption, file=discord.File(path))
    finally:
        with contextlib.suppress(Exception):
            if os.path.exists(path):
                os.remove(path)


async def _send_text(channel: discord.abc.Messageable, message: str):
    if channel:
        await channel.send(message)


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

    try:
        sb.scroll_to(selector)
    except Exception:
        pass

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

    try:
        sb.scroll_to(xpath, by="xpath")
    except Exception:
        pass

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
            if (cls.includes("get-coins")) s += 5;

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

    if element_exists(sb, "button.get-coins-btn"):
        return True

    if "get coins" in text and ("continue playing" in text or "lobby" in text):
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

        if "CLAIM FREE REWARDS" in text:
            return True

        if "DAILY BONUS" in text and "COLLECT" in text:
            return True

        try:
            found = sb.execute_script(
                """
                return !!(
                    document.querySelector(".free-coins-dialog") ||
                    document.querySelector(".free-reward") ||
                    document.querySelector("[data-sentry-component='FreeReward']")
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

    return "luckparty.com" in get_current_url(sb).lower()


def login_luckparty(sb: SB) -> bool:
    if not open_login_page(sb):
        return False

    if is_logged_in(sb):
        return True

    email, password = get_luckparty_credentials()

    email_selectors = [
        "#field-email",
        "input#field-email",
        "input[name='email']",
        "input[type='email']",
        "input[placeholder='Email']",
        "input[autocomplete='email']",
    ]

    password_selectors = [
        "#field-password",
        "input#field-password",
        "input[name='password']",
        "input[type='password']",
        "input[placeholder='Password']",
        "input[autocomplete='current-password']",
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
            "/html/body/div[5]/div/div[1]/div/div/button",
            "/html/body/div[4]/div/div[1]/div/div/button",
            "/html/body/div[6]/div/div[1]/div/div/button",
            "//button[contains(., 'Accept All')]",
            "//button[contains(., 'ACCEPT ALL')]",
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
        "button.get-coins-btn",
        "button[data-sentry-component='GetCoinsButton']",
        "button[class*='get-coins']",
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


def click_collect_reward_js(sb: SB, prefer_daily: bool = True) -> Optional[str]:
    script = """
    const preferDaily = arguments[0];

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

    const cards = Array.from(document.querySelectorAll(
        ".free-reward, [data-sentry-component='FreeReward']"
    )).filter(visible);

    const candidates = [];

    for (const card of cards) {
        const titleEl =
            card.querySelector(".free-reward__title") ||
            card.querySelector("[class*='title']");

        const title = clean(titleEl ? titleEl.innerText : card.innerText);

        const buttons = Array.from(card.querySelectorAll("button")).filter(button => {
            const txt = clean(button.innerText).toUpperCase();
            const cls = String(button.className || "").toLowerCase();

            return (
                visible(button) &&
                !button.disabled &&
                (
                    txt === "COLLECT" ||
                    txt.includes("COLLECT") ||
                    cls.includes("collect")
                )
            );
        });

        for (const button of buttons) {
            candidates.push({ title, button });
        }
    }

    if (!candidates.length) {
        const directButtons = Array.from(document.querySelectorAll(
            "button.free-reward__button.collect, button[class*='free-reward'][class*='collect']"
        )).filter(button => visible(button) && !button.disabled);

        for (const button of directButtons) {
            const card =
                button.closest(".free-reward") ||
                button.closest("[data-sentry-component='FreeReward']") ||
                button.parentElement;

            const titleEl =
                card?.querySelector(".free-reward__title") ||
                card?.querySelector("[class*='title']");

            const title = clean(titleEl ? titleEl.innerText : card?.innerText);
            candidates.push({ title, button });
        }
    }

    if (!candidates.length) {
        const textButtons = Array.from(document.querySelectorAll("button")).filter(button => {
            const txt = clean(button.innerText).toUpperCase();
            return visible(button) && !button.disabled && txt.includes("COLLECT");
        });

        for (const button of textButtons) {
            const card =
                button.closest(".free-reward") ||
                button.closest("[data-sentry-component='FreeReward']") ||
                button.parentElement;

            const titleEl =
                card?.querySelector(".free-reward__title") ||
                card?.querySelector("[class*='title']");

            const title = clean(titleEl ? titleEl.innerText : card?.innerText);
            candidates.push({ title, button });
        }
    }

    if (!candidates.length) return "";

    let chosen = candidates[0];

    if (preferDaily) {
        const daily = candidates.find(item =>
            clean(item.title).toUpperCase().includes("DAILY BONUS")
        );

        if (daily) chosen = daily;
    }

    chosen.button.scrollIntoView({ block: "center", inline: "center" });

    ["pointerdown", "mousedown", "pointerup", "mouseup", "click"].forEach(type => {
        chosen.button.dispatchEvent(new MouseEvent(type, {
            bubbles: true,
            cancelable: true,
            view: window
        }));
    });

    try { chosen.button.click(); } catch (e) {}

    return chosen.title || "Free Reward";
    """

    try:
        title = sb.execute_script(script, bool(prefer_daily))
        title = (title or "").strip()
        return title or None
    except Exception:
        return None


def click_collect_xpath_fallback(sb: SB) -> Optional[str]:
    xpaths = [
        "/html/body/div[5]/div/div[2]/div/div[2]/div[2]/div[1]/div[4]/button[1]",
        "//button[contains(@class, 'free-reward__button') and contains(@class, 'collect')]",
        "//button[contains(translate(., 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'COLLECT')]",
    ]

    for xpath in xpaths:
        if click_xpath(sb, xpath, timeout=4):
            sleep(2)
            return "Free Reward"

    return None


def collect_available_rewards(sb: SB, max_clicks: int = 2) -> List[str]:
    claimed = []

    for i in range(max_clicks):
        title = click_collect_reward_js(sb, prefer_daily=(i == 0))

        if not title:
            title = click_collect_xpath_fallback(sb)

        if not title:
            break

        claimed.append(title)
        sleep(3)

    return claimed


def run_claim_flow(sb: SB) -> str:
    """
    Returns:
      claimed
      unavailable
      login_failed
      store_failed
      open_failed
    """
    if not open_login_page(sb):
        return "open_failed"

    if not login_luckparty(sb):
        return "login_failed"

    wait_ready(sb)
    sleep(2)

    close_popups(sb)

    if not open_coin_store(sb):
        return "store_failed"

    sleep(2)

    claimed = collect_available_rewards(sb, max_clicks=2)

    if claimed:
        return "claimed"

    return "unavailable"


# ───────────────────────────────────────────────────────────
# PUBLIC RUNNERS
# ───────────────────────────────────────────────────────────

async def luckparty_casino(ctx=None, driver=None, channel: Optional[discord.abc.Messageable] = None):
    """
    Public runner.

    Sends only one final screenshot:
      - success screenshot, or
      - unavailable/error screenshot
    """
    if channel is None and ctx is not None:
        channel = ctx.channel

    if channel is None:
        raise RuntimeError("luckparty_casino needs a Discord channel or ctx.")

    email, password = get_luckparty_credentials()

    if not email or not password:
        await channel.send(
            "❌ Missing Luck Party credentials in `.env`.\n\n"
            "Supported formats:\n"
            "`LUCKPARTY_LOGIN=email:password`\n\n"
            "or:\n"
            "`LUCKPARTY_EMAIL=email`\n"
            "`LUCKPARTY_PASSWORD=password`"
        )
        return

    try:
        with SB(uc=True, headed=True) as sb:
            result = run_claim_flow(sb)

            if result == "claimed":
                await _send_screenshot(
                    sb,
                    channel,
                    "luckparty_claimed.png",
                    "Luck Party Daily Bonus Claimed!",
                )
                return

            if result == "unavailable":
                await _send_screenshot(
                    sb,
                    channel,
                    "luckparty_unavailable.png",
                    "[Luck Party] Bonus unavailable (likely already claimed).",
                )
                return

            if result == "open_failed":
                await _send_screenshot(
                    sb,
                    channel,
                    "luckparty_open_failed.png",
                    "[Luck Party] Could not open the login page.",
                )
                return

            if result == "login_failed":
                await _send_screenshot(
                    sb,
                    channel,
                    "luckparty_login_failed.png",
                    "[Luck Party] Login failed.",
                )
                return

            if result == "store_failed":
                await _send_screenshot(
                    sb,
                    channel,
                    "luckparty_store_failed.png",
                    "[Luck Party] Could not open the coin store or rewards modal.",
                )
                return

            await _send_screenshot(
                sb,
                channel,
                "luckparty_unknown.png",
                f"[Luck Party] Unknown result: {result}",
            )

    except Exception as e:
        await channel.send(f"[Luck Party] Claim error: `{type(e).__name__}: {e}`")


# Main.py compatibility
async def luckparty_uc(ctx=None, channel: Optional[discord.abc.Messageable] = None):
    await luckparty_casino(ctx=ctx, channel=channel)


async def claim_luckparty(
    channel: Optional[discord.abc.Messageable] = None,
    ctx=None,
    driver=None,
    headless=None,
):
    await luckparty_casino(ctx=ctx, driver=driver, channel=channel)


async def claim_bonus(channel=None, headless=None):
    await claim_luckparty(channel=channel)


async def run(channel=None, headless=None):
    await claim_luckparty(channel=channel)


async def main(channel=None, headless=None):
    await claim_luckparty(channel=channel)


# Backward-compatible aliases in case main.py still references old names.
async def claim_luckyparty(
    channel: Optional[discord.abc.Messageable] = None,
    ctx=None,
    driver=None,
    headless=None,
):
    await claim_luckparty(channel=channel, ctx=ctx, driver=driver, headless=headless)


async def luckyparty_casino(ctx=None, driver=None, channel: Optional[discord.abc.Messageable] = None):
    await luckparty_casino(ctx=ctx, driver=driver, channel=channel)


async def luckyparty_uc(ctx=None, channel: Optional[discord.abc.Messageable] = None):
    await luckparty_uc(ctx=ctx, channel=channel)


if __name__ == "__main__":
    with SB(uc=True, headed=True) as sb:
        opened = open_login_page(sb)
        print("Opened:", opened, get_current_url(sb))
        sleep(10)