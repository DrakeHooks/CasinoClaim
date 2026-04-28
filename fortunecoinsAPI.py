# Drake Hooks + WaterTrooper
# Casino Claim 2
# Fortune Wins API - SeleniumBase UC
#
# Exposes:
#   def fortunewins_uc_blocking(bot, channel_id: int, main_loop)
#   async def fortunewins_uc(ctx, channel)
#
# Backwards-compatible aliases:
#   fortunecoins_uc_blocking(...)
#   fortunecoins_uc(...)

import os
import time
import asyncio
import contextlib
from pathlib import Path

import discord
from dotenv import load_dotenv
from seleniumbase import SB


load_dotenv()


LOGIN_URL = "https://fortunewins.com/login"
SCREENSHOT_DIR = Path("screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────────────────────
# ENV
# ─────────────────────────────────────────────────────────────

def first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


FW_EMAIL = first_env(
    "FORTUNEWINSEMAIL",
    "FORTUNEWINS_EMAIL",
    "FORTUNECOINSEMAIL",
    "FORTUNECOINS_EMAIL",
)

FW_PASSWORD = first_env(
    "FORTUNEWINSPASSWORD",
    "FORTUNEWINS_PASSWORD",
    "FORTUNECOINSPASSWORD",
    "FORTUNECOINS_PASSWORD",
)


# ─────────────────────────────────────────────────────────────
# DISCORD HELPERS
# ─────────────────────────────────────────────────────────────

def send_text(main_loop: asyncio.AbstractEventLoop, channel: discord.abc.Messageable, text: str):
    future = asyncio.run_coroutine_threadsafe(channel.send(text), main_loop)
    with contextlib.suppress(Exception):
        future.result(timeout=20)


def send_file(
    main_loop: asyncio.AbstractEventLoop,
    channel: discord.abc.Messageable,
    path: str,
    caption: str,
):
    async def _send():
        try:
            await channel.send(caption, file=discord.File(path))
        finally:
            with contextlib.suppress(Exception):
                os.remove(path)

    future = asyncio.run_coroutine_threadsafe(_send(), main_loop)
    with contextlib.suppress(Exception):
        future.result(timeout=60)


def notify(main_loop, channel, message: str):
    if channel:
        send_text(main_loop, channel, message)


def screenshot_and_send(sb, main_loop, channel, filename: str, caption: str):
    if not channel:
        return

    path = str(SCREENSHOT_DIR / filename)

    with contextlib.suppress(Exception):
        sb.save_screenshot(path)

    if os.path.exists(path):
        send_file(main_loop, channel, path, caption)
    else:
        send_text(main_loop, channel, caption)


# ─────────────────────────────────────────────────────────────
# BASIC SELENIUM HELPERS
# ─────────────────────────────────────────────────────────────

def sleep(seconds: float):
    time.sleep(seconds)


def wait_ready(sb):
    with contextlib.suppress(Exception):
        sb.wait_for_ready_state_complete()


def visible(sb, selector: str, timeout: int = 8) -> bool:
    try:
        sb.wait_for_element_visible(selector, timeout=timeout)
        return True
    except Exception:
        return False


def click_css(sb, selector: str, timeout: int = 8) -> bool:
    try:
        sb.wait_for_element_visible(selector, timeout=timeout)
        sb.scroll_to(selector)
        sleep(0.3)
        sb.click(selector)
        return True
    except Exception:
        return False


def js_click_element(sb, element) -> bool:
    try:
        sb.execute_script(
            """
            const el = arguments[0];
            el.scrollIntoView({ block: "center", inline: "center" });

            ["pointerdown", "mousedown", "pointerup", "mouseup", "click"].forEach(type => {
                el.dispatchEvent(new MouseEvent(type, {
                    bubbles: true,
                    cancelable: true,
                    view: window
                }));
            });

            try { el.click(); } catch (e) {}
            """,
            element,
        )
        return True
    except Exception:
        return False


def click_xpath(sb, xpath: str, timeout: int = 8) -> bool:
    try:
        sb.wait_for_element_visible(xpath, by="xpath", timeout=timeout)
        element = sb.find_element(xpath, by="xpath")
        return js_click_element(sb, element)
    except Exception:
        return False


def click_any_xpath(sb, xpaths, timeout: int = 5) -> bool:
    for xpath in xpaths:
        if click_xpath(sb, xpath, timeout=timeout):
            return True
    return False


def click_by_text(sb, text_options, selectors="button, [role='button'], a, div, span") -> bool:
    """
    Clicks the first visible element whose text contains one of the given strings.
    """
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
            if (el.tagName === "BUTTON") s += 20;
            if ((el.className || "").toString().toLowerCase().includes("active")) s += 5;
            if ((el.className || "").toString().toLowerCase().includes("tab")) s += 5;
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


# ─────────────────────────────────────────────────────────────
# REACT-SAFE INPUT FIX
# ─────────────────────────────────────────────────────────────

def set_react_input(sb, selector: str, value: str, timeout: int = 15) -> bool:
    """
    Fortune Wins uses React-controlled inputs.
    Plain sb.type() can visually fail or not update React state.

    This uses the native HTMLInputElement value setter and dispatches
    input/change events so React sees the value.
    """
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

        # Fallback: clear and type normally.
        with contextlib.suppress(Exception):
            sb.clear(selector)
            sb.type(selector, value)
            sleep(0.4)

        return True

    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
# LOGIN FLOW
# ─────────────────────────────────────────────────────────────

def login_fortunewins(sb) -> bool:
    sb.uc_open_with_reconnect(LOGIN_URL, 4)
    wait_ready(sb)
    sleep(2)

    email_ok = set_react_input(sb, "#emailAddress", FW_EMAIL)
    pass_ok = set_react_input(sb, "#password", FW_PASSWORD)

    if not email_ok or not pass_ok:
        return False

    # Cloudflare / Turnstile checkbox.
    with contextlib.suppress(Exception):
        sb.uc_gui_click_captcha()
        sleep(2)

    # Try clean selectors first.
    if click_css(sb, "form button[type='submit']", timeout=5):
        sleep(6)
        wait_ready(sb)
        return True

    # Text fallback.
    if click_by_text(sb, ["LOG IN", "LOGIN", "SIGN IN"], selectors="button, [role='button']"):
        sleep(6)
        wait_ready(sb)
        return True

    # Last XPath fallback.
    clicked = click_any_xpath(
        sb,
        [
            "//form//button[contains(translate(., 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'LOG IN')]",
            "//form//button[contains(translate(., 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'LOGIN')]",
            "//form//button[contains(translate(., 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'SIGN IN')]",
        ],
        timeout=5,
    )

    sleep(6)
    wait_ready(sb)
    return clicked


# ─────────────────────────────────────────────────────────────
# POST-LOGIN FLOW
# ─────────────────────────────────────────────────────────────

def close_popups(sb):
    """
    Kills normal popups after login.
    """
    sleep(1)

    click_any_xpath(
        sb,
        [
            "//button[contains(@class, 'close')]",
            "//button[contains(@aria-label, 'close')]",
            "//button[contains(@aria-label, 'Close')]",
            "/html/body/div[5]/div/div[1]/div/div/button",
            "/html/body/div[4]/div/div[1]/div/div/button",
            "/html/body/div[4]/div/div[1]/div/div/div[3]/div/button[2]",
        ],
        timeout=3,
    )

    with contextlib.suppress(Exception):
        sb.press_keys("body", "\ue00c")  # ESC
        sleep(1)


def open_coin_store(sb) -> bool:
    """
    Opens the coin store/rewards modal.
    Prefer text/semantic clicks over brittle giant XPaths.
    """
    sleep(1)

    # Text-based attempts.
    for text_group in (
        ["GET COINS"],
        ["COIN STORE"],
        ["STORE"],
        ["REWARDS"],
        ["BUY COINS"],
    ):
        if click_by_text(sb, text_group, selectors="button, [role='button'], a, div"):
            sleep(2)
            return True

    # Known nav fallback.
    return click_any_xpath(
        sb,
        [
            "/html/body/div[1]/div[2]/div[1]/div/nav/div[2]/div[3]/button",
            "/html/body/div[1]/div[2]/div/nav/div[2]/div[3]/button",
            "/html/body/div[1]/div[2]/div[1]/div/nav/div[2]/div[3]/button",
        ],
        timeout=5,
    )


def free_coins_tab_active(sb) -> bool:
    script = """
    const buttons = Array.from(document.querySelectorAll("button, [role='button']"));

    const tab = buttons.find(el => {
        const text = (el.innerText || el.textContent || "")
            .replace(/\\s+/g, " ")
            .trim()
            .toUpperCase();

        return text.includes("FREE COINS");
    });

    if (!tab) return false;

    const cls = (tab.className || "").toString().toLowerCase();
    const ariaSelected = tab.getAttribute("aria-selected");
    const ariaPressed = tab.getAttribute("aria-pressed");

    if (cls.includes("active")) return true;
    if (ariaSelected === "true") return true;
    if (ariaPressed === "true") return true;

    const pageText = document.body.innerText.toUpperCase();
    return pageText.includes("COLLECT") || pageText.includes("CLAIM");
    """

    try:
        return bool(sb.execute_script(script))
    except Exception:
        return False


def keyboard_tab_enter(sb, tabs: int = 4) -> bool:
    """
    Requested fallback: TAB 4 times, ENTER.
    """
    try:
        with contextlib.suppress(Exception):
            sb.execute_script("document.body.focus();")

        sleep(0.5)

        for _ in range(tabs):
            sb.press_keys("body", "\ue004")  # TAB
            sleep(0.25)

        sb.press_keys("body", "\ue007")  # ENTER
        sleep(1.2)
        return True

    except Exception:
        return False


def click_free_coins_tab(sb) -> bool:
    """
    Clicks FREE COINS tab in the coin store modal.
    """
    sleep(2)

    # Most likely current structure.
    try:
        tabs = sb.find_elements("button.coin-store-tab")
        for tab in tabs:
            text = (tab.text or "").strip().upper()
            if "FREE COINS" in text:
                if js_click_element(sb, tab):
                    sleep(1)
                    return True
    except Exception:
        pass

    # More generic button text click.
    for _ in range(2):
        if click_by_text(sb, ["FREE COINS"], selectors="button, [role='button'], div, span"):
            sleep(1)
            return True

    # XPath fallback.
    if click_any_xpath(
        sb,
        [
            "//button[contains(translate(., 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'FREE COINS')]",
            "//*[contains(@class, 'coin-store-tab')][contains(translate(., 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'FREE COINS')]",
        ],
        timeout=4,
    ):
        sleep(1)
        return True

    # Last resort.
    keyboard_tab_enter(sb, tabs=4)
    return free_coins_tab_active(sb)


def click_collect_or_claim(sb) -> bool:
    """
    Clicks the collect/claim button once the FREE COINS tab is open.
    """
    sleep(2)

    for text_group in (
        ["COLLECT NOW", "COLLECT"],
        ["CLAIM NOW", "CLAIM"],
        ["GET NOW", "GET"],
        ["DAILY BONUS"],
    ):
        if click_by_text(sb, text_group, selectors="button, [role='button']"):
            sleep(2)
            return True

    # Old structure fallback.
    return click_any_xpath(
        sb,
        [
            "/html/body/div[5]/div/div/div/div/div[3]/div/div[1]/div[2]/div[1]/div/div[3]/button[2]",
            "/html/body/div[4]/div/div/div/div/div[3]/div/div[1]/div[2]/div[1]/div/div[3]/button[2]",
            "/html/body/div[6]/div/div/div/div/div[3]/div/div[1]/div[2]/div[1]/div/div[3]/button[2]",
            "/html/body/div[4]/div/div[1]/div/div/div[2]/div/div[2]/div[2]/div[1]/div/div[3]/button[1]",
            "/html/body/div[4]/div/div[1]/div/div/div[2]/div/div[1]/div[2]/div[1]/div/div[3]/button[1]",
        ],
        timeout=4,
    )


def run_claim_flow(sb) -> str:
    """
    Returns:
      claimed
      unavailable
      login_failed
      store_failed
      free_tab_failed
    """
    if not login_fortunewins(sb):
        return "login_failed"

    # Refresh after login helps if it lands on auth callback weirdness.
    with contextlib.suppress(Exception):
        sb.refresh_page()
        wait_ready(sb)
        sleep(3)

    close_popups(sb)

    if not open_coin_store(sb):
        return "store_failed"

    sleep(2)

    if not click_free_coins_tab(sb):
        return "free_tab_failed"

    sleep(3)

    if click_collect_or_claim(sb):
        return "claimed"

    return "unavailable"


# ─────────────────────────────────────────────────────────────
# PUBLIC RUNNERS
# ─────────────────────────────────────────────────────────────

def fortunewins_uc_blocking(
    bot,
    channel_id: int,
    main_loop: asyncio.AbstractEventLoop,
):
    channel = bot.get_channel(channel_id) if bot else None

    if not FW_EMAIL or not FW_PASSWORD:
        notify(
            main_loop,
            channel,
            "❌ Missing Fortune Wins credentials in `.env`.\n\n"
            "Supported keys:\n"
            "`FORTUNEWINSEMAIL` / `FORTUNEWINSPASSWORD`\n"
            "`FORTUNEWINS_EMAIL` / `FORTUNEWINS_PASSWORD`\n"
            "`FORTUNECOINSEMAIL` / `FORTUNECOINSPASSWORD`\n"
            "`FORTUNECOINS_EMAIL` / `FORTUNECOINS_PASSWORD`",
        )
        return

    notify(main_loop, channel, "Launching **Fortune Wins** UC...")

    try:
        with SB(uc=True, headed=True) as sb:
            result = run_claim_flow(sb)

            if result == "claimed":
                screenshot_and_send(
                    sb,
                    main_loop,
                    channel,
                    "fortunewins_claimed.png",
                    "Fortune Wins Daily Bonus Claimed!",
                )

            elif result == "unavailable":
                screenshot_and_send(
                    sb,
                    main_loop,
                    channel,
                    "fortunewins_unavailable.png",
                    "[Fortune Wins] Bonus unavailable, likely already collected.",
                )

            elif result == "login_failed":
                screenshot_and_send(
                    sb,
                    main_loop,
                    channel,
                    "fortunewins_login_failed.png",
                    "⚠️ Fortune Wins: login failed. Inputs/captcha/login button did not complete.",
                )

            elif result == "store_failed":
                screenshot_and_send(
                    sb,
                    main_loop,
                    channel,
                    "fortunewins_store_failed.png",
                    "⚠️ Fortune Wins: could not open the coin store/rewards modal.",
                )

            elif result == "free_tab_failed":
                screenshot_and_send(
                    sb,
                    main_loop,
                    channel,
                    "fortunewins_free_tab_failed.png",
                    "⚠️ Fortune Wins: could not switch to the FREE COINS tab.",
                )

            else:
                screenshot_and_send(
                    sb,
                    main_loop,
                    channel,
                    "fortunewins_unknown.png",
                    f"⚠️ Fortune Wins: unknown result: {result}",
                )

    except Exception as e:
        notify(
            main_loop,
            channel,
            f"⚠️ Fortune Wins UC error: `{type(e).__name__}: {e}`",
        )


async def fortunewins_uc(ctx, channel: discord.abc.Messageable):
    bot = channel.guild._state._get_client() if hasattr(channel, "guild") else None
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, fortunewins_uc_blocking, bot, channel.id, loop)


# Backwards-compatible aliases in case main.py still imports old names.
def fortunecoins_uc_blocking(
    bot,
    channel_id: int,
    main_loop: asyncio.AbstractEventLoop,
):
    return fortunewins_uc_blocking(bot, channel_id, main_loop)


async def fortunecoins_uc(ctx, channel: discord.abc.Messageable):
    await fortunewins_uc(ctx, channel)