# Drake Hooks + WaterTrooper
# Casino Claim 2
# Fortune Wins API (SeleniumBase UC) — thread-offloaded sync runner
# Exposes:
#   def fortunewins_uc_blocking(bot, channel_id: int, main_loop):  # call from executor
#   async def fortunewins_uc(ctx, channel):  # optional thin async wrapper if you want it
#
# Notes:
# - Accepts either Fortune Coins or Fortune Wins credentials from .env
# - Much more reliable "FREE COINS" tab click logic
# - Last-resort keyboard fallback: TAB x4, then ENTER

import os
import time
import contextlib
import asyncio

from dotenv import load_dotenv
from seleniumbase import SB
import discord

load_dotenv()


def _first_env(*names: str) -> str:
    """
    Return the first non-empty environment variable from the provided names.
    Accepts both Fortune Coins and Fortune Wins naming conventions.
    """
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


# ───────────────────────────────────────────────────────────
# Accept old fortunecoins creds or new fortunewins creds
# ───────────────────────────────────────────────────────────
FC_EMAIL = _first_env(
    "FORTUNECOINSEMAIL",
    "FORTUNECOINS_EMAIL",
    "FORTUNEWINSEMAIL",
    "FORTUNEWINS_EMAIL",
)

FC_PASSWORD = _first_env(
    "FORTUNECOINSPASSWORD",
    "FORTUNECOINS_PASSWORD",
    "FORTUNEWINSPASSWORD",
    "FORTUNEWINS_PASSWORD",
)


# ───────────────────────────────────────────────────────────
# Discord helpers (safe to call from a worker thread)
# ───────────────────────────────────────────────────────────
def _send_text_threadsafe(
    main_loop: asyncio.AbstractEventLoop,
    channel: discord.abc.Messageable,
    text: str,
):
    fut = asyncio.run_coroutine_threadsafe(channel.send(text), main_loop)
    with contextlib.suppress(Exception):
        fut.result(timeout=20)


def _send_file_threadsafe(
    main_loop: asyncio.AbstractEventLoop,
    channel: discord.abc.Messageable,
    path: str,
    caption: str,
):
    async def _do():
        try:
            await channel.send(caption, file=discord.File(path))
        finally:
            with contextlib.suppress(Exception):
                os.remove(path)

    fut = asyncio.run_coroutine_threadsafe(_do(), main_loop)
    with contextlib.suppress(Exception):
        fut.result(timeout=60)


# ───────────────────────────────────────────────────────────
# Generic Selenium helpers
# ───────────────────────────────────────────────────────────
def _wait_small(seconds: float):
    time.sleep(seconds)


def _xpath_exists(sb: SB, xpath: str) -> bool:
    try:
        return bool(sb.is_element_present(xpath))
    except Exception:
        return False


def _css_exists(sb: SB, selector: str) -> bool:
    try:
        return bool(sb.is_element_present(selector))
    except Exception:
        return False


def _safe_scroll_into_view(sb: SB, selector_or_xpath: str, by_xpath: bool = False):
    try:
        if by_xpath:
            el = sb.find_element(selector_or_xpath, by="xpath")
        else:
            el = sb.find_element(selector_or_xpath)
        sb.execute_script(
            """
            arguments[0].scrollIntoView({
                block: 'center',
                inline: 'center',
                behavior: 'instant'
            });
            """,
            el,
        )
        _wait_small(0.4)
    except Exception:
        pass


def _real_click_element(sb: SB, element) -> bool:
    """
    Tries several increasingly forceful click styles on a specific element.
    """
    try:
        sb.execute_script(
            """
            arguments[0].scrollIntoView({
                block: 'center',
                inline: 'center',
                behavior: 'instant'
            });
            """,
            element,
        )
    except Exception:
        pass

    click_scripts = [
        # Native click
        "arguments[0].click();",
        # Mouse event sequence
        """
        const el = arguments[0];
        ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(type => {
            el.dispatchEvent(new MouseEvent(type, {
                bubbles: true,
                cancelable: true,
                view: window
            }));
        });
        """,
    ]

    # First attempt: Selenium native click
    with contextlib.suppress(Exception):
        element.click()
        return True

    # Then JS methods
    for script in click_scripts:
        try:
            sb.execute_script(script, element)
            return True
        except Exception:
            continue

    return False


def _force_click_xpath(sb: SB, xpath: str, timeout: float = 12) -> bool:
    try:
        sb.wait_for_element_visible(xpath, by="xpath", timeout=timeout)
    except Exception:
        return False

    _safe_scroll_into_view(sb, xpath, by_xpath=True)

    for mode in ("click_xpath", "slow_click_xpath", "js_click_xpath", "direct_js"):
        try:
            if mode == "click_xpath":
                sb.click(xpath, by="xpath", timeout=2)
            elif mode == "slow_click_xpath":
                el = sb.find_element(xpath, by="xpath")
                _real_click_element(sb, el)
            elif mode == "js_click_xpath":
                el = sb.find_element(xpath, by="xpath")
                sb.execute_script("arguments[0].click();", el)
            else:
                el = sb.find_element(xpath, by="xpath")
                sb.execute_script(
                    """
                    ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(type => {
                        arguments[0].dispatchEvent(new MouseEvent(type, {
                            bubbles: true,
                            cancelable: true,
                            view: window
                        }));
                    });
                    """,
                    el,
                )
            return True
        except Exception:
            continue

    return False


def _try_click_any_xpath(sb: SB, xpaths, timeout_each=8) -> bool:
    for xp in xpaths:
        if _force_click_xpath(sb, xp, timeout=timeout_each):
            return True
    return False


def _click_first_visible_css(sb: SB, selectors, timeout_each=6) -> bool:
    for selector in selectors:
        try:
            sb.wait_for_element_visible(selector, timeout=timeout_each)
            _safe_scroll_into_view(sb, selector, by_xpath=False)
            el = sb.find_element(selector)
            if _real_click_element(sb, el):
                return True
        except Exception:
            continue
    return False


def _js_find_button_by_text_and_click(sb: SB, text_snippets) -> bool:
    """
    Find a visible button-like element whose text contains any provided snippet.
    """
    script = """
    const snippets = arguments[0].map(s => String(s).toUpperCase());
    const els = Array.from(document.querySelectorAll('button, [role="button"], div, span, a'));

    function isVisible(el) {
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return (
            style.display !== 'none' &&
            style.visibility !== 'hidden' &&
            style.opacity !== '0' &&
            rect.width > 0 &&
            rect.height > 0
        );
    }

    const candidates = els.filter(el => {
        if (!isVisible(el)) return false;
        const text = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim().toUpperCase();
        if (!text) return false;
        return snippets.some(s => text.includes(s));
    });

    // Prefer actual buttons first
    candidates.sort((a, b) => {
        const aScore = (a.tagName === 'BUTTON' ? 10 : 0) + (a.className.includes('coin-store-tab') ? 10 : 0);
        const bScore = (b.tagName === 'BUTTON' ? 10 : 0) + (b.className.includes('coin-store-tab') ? 10 : 0);
        return bScore - aScore;
    });

    if (!candidates.length) return false;

    const el = candidates[0];
    el.scrollIntoView({block: 'center', inline: 'center', behavior: 'instant'});

    ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(type => {
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
        return bool(sb.execute_script(script, list(text_snippets)))
    except Exception:
        return False


def _activate_modal_for_keyboard(sb: SB):
    """
    Try to focus the modal / document body so tabbing moves within the popup.
    """
    scripts = [
        """
        const modal = document.querySelector('.coin-store-popup-container');
        if (modal) {
            modal.setAttribute('tabindex', '-1');
            modal.focus();
            return true;
        }
        return false;
        """,
        """
        document.body.focus();
        return true;
        """,
    ]
    for script in scripts:
        with contextlib.suppress(Exception):
            sb.execute_script(script)
            _wait_small(0.25)


def _keyboard_tab_enter_fallback(sb: SB, tabs: int = 4) -> bool:
    """
    Last resort fallback requested by you:
    hit TAB 4 times and ENTER.
    """
    try:
        _activate_modal_for_keyboard(sb)
        _wait_small(0.4)
        for _ in range(tabs):
            sb.press_keys("body", "\ue004")  # TAB
            _wait_small(0.25)
        sb.press_keys("body", "\ue007")  # ENTER
        _wait_small(1.0)
        return True
    except Exception:
        return False


def _free_coins_tab_active(sb: SB) -> bool:
    """
    Detect whether FREE COINS tab is active / selected.
    """
    checks = [
        """
        const tabs = Array.from(document.querySelectorAll('button.coin-store-tab'));
        const tab = tabs.find(el => (el.innerText || el.textContent || '').toUpperCase().includes('FREE COINS'));
        if (!tab) return false;
        const cls = tab.className || '';
        const aria = tab.getAttribute('aria-selected') || '';
        const pressed = tab.getAttribute('aria-pressed') || '';
        const style = window.getComputedStyle(tab);
        return (
            cls.toLowerCase().includes('active') ||
            aria === 'true' ||
            pressed === 'true' ||
            style.fontWeight === '700' ||
            style.fontWeight === '800' ||
            style.fontWeight === '900'
        );
        """,
        """
        // If collect-style buttons appear, the FREE COINS content is probably open.
        const texts = Array.from(document.querySelectorAll('button, [role="button"]'))
          .map(el => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim().toUpperCase());
        return texts.some(t =>
            t.includes('COLLECT') ||
            t.includes('CLAIM') ||
            t.includes('FREE COINS') ||
            t.includes('DAILY')
        );
        """,
    ]

    for script in checks:
        try:
            if bool(sb.execute_script(script)):
                return True
        except Exception:
            continue
    return False


def _click_free_coins_tab(sb: SB) -> bool:
    """
    Robust handler for the 'FREE COINS' tab in the coin store modal.
    Based on your screenshot, the real element is:
      button.coin-store-tab
    with inner text:
      FREE COINS
    """
    # Let modal fully settle first
    _wait_small(1.5)

    # Strategy 1: direct CSS selector for the actual tab class
    css_candidates = [
        "button.coin-store-tab",
        ".coin-store-tabs button.coin-store-tab",
        ".coin-store-popup-container .coin-store-tabs .coin-store-tab",
    ]
    for selector in css_candidates:
        try:
            buttons = sb.find_elements(selector)
            for btn in buttons:
                text = ""
                with contextlib.suppress(Exception):
                    text = (btn.text or "").strip().upper()
                if "FREE COINS" in text:
                    if _real_click_element(sb, btn):
                        _wait_small(1.0)
                        if _free_coins_tab_active(sb):
                            return True
        except Exception:
            continue

    # Strategy 2: JS search by visible text
    for _ in range(3):
        if _js_find_button_by_text_and_click(sb, ["FREE COINS"]):
            _wait_small(1.0)
            if _free_coins_tab_active(sb):
                return True

    # Strategy 3: XPath text match
    xpath_candidates = [
        "//button[contains(@class,'coin-store-tab')][contains(normalize-space(.), 'FREE COINS')]",
        "//div[contains(@class,'coin-store-tabs')]//button[contains(., 'FREE COINS')]",
        "//button[.//text()[contains(., 'FREE COINS')]]",
    ]
    for xp in xpath_candidates:
        if _force_click_xpath(sb, xp, timeout=4):
            _wait_small(1.0)
            if _free_coins_tab_active(sb):
                return True

    # Strategy 4: keyboard fallback requested by user
    if _keyboard_tab_enter_fallback(sb, tabs=4):
        _wait_small(1.2)
        if _free_coins_tab_active(sb):
            return True

    return False


def _find_collect_buttons(sb):
    """
    Return possible collect/claim buttons in the current modal using text.
    """
    script = """
    const els = Array.from(document.querySelectorAll('button, [role="button"]'));

    function isVisible(el) {
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return (
            style.display !== 'none' &&
            style.visibility !== 'hidden' &&
            style.opacity !== '0' &&
            rect.width > 0 &&
            rect.height > 0
        );
    }

    const matches = els.filter(el => {
        if (!isVisible(el)) return false;
        const text = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim().toUpperCase();
        if (!text) return false;
        return (
            text.includes('COLLECT') ||
            text.includes('CLAIM') ||
            text === 'GET' ||
            text.includes('FREE')
        );
    });

    return matches;
    """
    try:
        return sb.execute_script(script)
    except Exception:
        return []


def _click_collect_button(sb: SB) -> bool:
    """
    Click the actual claim/collect button after FREE COINS tab is open.
    """
    # Strategy 1: JS text-based click
    text_sets = [
        ["COLLECT NOW", "COLLECT"],
        ["CLAIM NOW", "CLAIM"],
        ["DAILY BONUS", "FREE COINS"],
    ]
    for texts in text_sets:
        for _ in range(2):
            if _js_find_button_by_text_and_click(sb, texts):
                _wait_small(1.2)
                return True

    # Strategy 2: common xpath fallbacks from old structure
    xpath_candidates = [
        "/html/body/div[5]/div/div/div/div/div[3]/div/div[1]/div[2]/div[1]/div/div[3]/button[2]",
        "/html/body/div[4]/div/div/div/div/div[3]/div/div[1]/div[2]/div[1]/div/div[3]/button[2]",
        "/html/body/div[6]/div/div/div/div/div[3]/div/div[1]/div[2]/div[1]/div/div[3]/button[2]",
        "/html/body/div[4]/div/div[1]/div/div/div[2]/div/div[2]/div[2]/div[1]/div/div[3]/button[1]",
        "/html/body/div[4]/div/div[1]/div/div/div[2]/div/div[1]/div[2]/div[1]/div/div[3]/button[1]",
    ]
    if _try_click_any_xpath(sb, xpath_candidates, timeout_each=4):
        _wait_small(1.2)
        return True

    # Strategy 3: generic visible button with collect-ish text
    try:
        buttons = sb.find_elements("button, [role='button']")
        for btn in buttons:
            with contextlib.suppress(Exception):
                text = (btn.text or "").strip().upper()
                if any(word in text for word in ("COLLECT", "CLAIM", "GET")):
                    if _real_click_element(sb, btn):
                        _wait_small(1.0)
                        return True
    except Exception:
        pass

    return False


def _close_popups_if_any(sb: SB):
    _try_click_any_xpath(
        sb,
        [
            "/html/body/div[5]/div/div[1]/div/div/button",
            "/html/body/div[4]/div/div[1]/div/div/div[3]/div/button[2]",
            "/html/body/div[4]/div/div[1]/div/div/button",
        ],
        timeout_each=4,
    )
    with contextlib.suppress(Exception):
        sb.press_keys("body", "ESCAPE")
        _wait_small(1.5)


def _open_rewards_or_coin_store(sb: SB) -> bool:
    """
    Open the top nav button that leads to the rewards / coin store modal.
    """
    xpath_candidates = [
        "/html/body/div[1]/div[2]/div[1]/div/nav/div[2]/div[3]/button",
        "/html/body/div[1]/div[2]/div/nav/div[2]/div[3]/button",
        "/html/body/div[1]/div[2]/div[1]/div/nav/div[2]/div[3]/button",
    ]
    if _try_click_any_xpath(sb, xpath_candidates, timeout_each=6):
        _wait_small(2.0)
        return True

    # Generic text fallback
    for texts in (["GET COINS"], ["COIN STORE"], ["STORE"], ["REWARDS"]):
        if _js_find_button_by_text_and_click(sb, texts):
            _wait_small(2.0)
            return True

    return False


# ───────────────────────────────────────────────────────────
# Primary sync runner (to be called from a worker thread)
# ───────────────────────────────────────────────────────────
def fortunewins_uc_blocking(
    bot,
    channel_id: int,
    main_loop: asyncio.AbstractEventLoop,
):
    """
    Runs the entire Fortune Wins flow synchronously in a worker thread.
    Posts messages back to the main Discord loop thread-safely.
    Keeps SeleniumBase's sb.uc_gui_click_captcha() intact.
    """
    ch = bot.get_channel(channel_id)

    if not FC_EMAIL or not FC_PASSWORD:
        if ch:
            _send_text_threadsafe(
                main_loop,
                ch,
                "❌ Missing Fortune Coins/Fortune Wins credentials in your `.env`. "
                "Supported keys: `FORTUNECOINSEMAIL` / `FORTUNECOINSPASSWORD`, "
                "`FORTUNECOINS_EMAIL` / `FORTUNECOINS_PASSWORD`, "
                "`FORTUNEWINSEMAIL` / `FORTUNEWINSPASSWORD`, or "
                "`FORTUNEWINS_EMAIL` / `FORTUNEWINS_PASSWORD`."
            )
        return

    if ch:
        _send_text_threadsafe(main_loop, ch, "Launching **Fortune Wins** (UC)…")

    try:
        with SB(uc=True, headed=True) as sb:
            # ── Login
            sb.uc_open_with_reconnect("https://fortunewins.com/login", 4)
            sb.wait_for_ready_state_complete()
            _wait_small(1.0)

            sb.type("input[id='emailAddress']", FC_EMAIL)
            _wait_small(1.0)
            sb.type("input[id='password']", FC_PASSWORD)
            _wait_small(0.8)

            with contextlib.suppress(Exception):
                sb.uc_gui_click_captcha()
                _wait_small(1.0)

            _try_click_any_xpath(
                sb,
                [
                    "/html/body/div[1]/div[2]/div[5]/div/section/div[2]/div/div/div[2]/form/div[4]/button",
                    "//form//button[contains(., 'Login')]",
                    "//form//button[contains(., 'Sign In')]",
                ],
                timeout_each=10,
            )

            _wait_small(6.0)
            with contextlib.suppress(Exception):
                sb.refresh_page()
                sb.wait_for_ready_state_complete()
                _wait_small(3.0)

            # ── Dismiss any initial popups
            _close_popups_if_any(sb)

            # ── Open Rewards / Coin Store modal
            opened_store = _open_rewards_or_coin_store(sb)
            if not opened_store:
                snap = "fw_uc_store_not_opened.png"
                with contextlib.suppress(Exception):
                    sb.save_screenshot(snap)
                if ch and os.path.exists(snap):
                    _send_file_threadsafe(
                        main_loop,
                        ch,
                        snap,
                        "⚠️ Fortune Wins: could not open the coin store / rewards modal."
                    )
                elif ch:
                    _send_text_threadsafe(
                        main_loop,
                        ch,
                        "⚠️ Fortune Wins: could not open the coin store / rewards modal."
                    )
                return

            # ── Click FREE COINS tab (main fix)
            free_tab_ok = _click_free_coins_tab(sb)
            _wait_small(2.0)

            if not free_tab_ok:
                snap = "fw_uc_free_coins_tab_failed.png"
                with contextlib.suppress(Exception):
                    sb.save_screenshot(snap)
                if ch and os.path.exists(snap):
                    _send_file_threadsafe(
                        main_loop,
                        ch,
                        snap,
                        "⚠️ Fortune Wins: could not switch to the FREE COINS tab."
                    )
                elif ch:
                    _send_text_threadsafe(
                        main_loop,
                        ch,
                        "⚠️ Fortune Wins: could not switch to the FREE COINS tab."
                    )
                return

            # ── Let free coins content render
            sb.wait_for_ready_state_complete()
            _wait_small(3.0)

            # ── Click collect/claim
            collected = _click_collect_button(sb)

            # Give it another shot after a tiny pause if first attempt failed
            if not collected:
                _wait_small(2.0)
                collected = _click_collect_button(sb)

            # ── Final result / screenshots
            if ch:
                if collected:
                    snap = "fw_uc_claimed.png"
                    with contextlib.suppress(Exception):
                        sb.save_screenshot(snap)
                    if os.path.exists(snap):
                        _send_file_threadsafe(
                            main_loop,
                            ch,
                            snap,
                            "Fortune Wins Daily Bonus Claimed!"
                        )
                    else:
                        _send_text_threadsafe(
                            main_loop,
                            ch,
                            "Fortune Wins Daily Bonus Claimed!"
                        )
                else:
                    snap = "fw_uc_unavailable.png"
                    with contextlib.suppress(Exception):
                        sb.save_screenshot(snap)
                    if os.path.exists(snap):
                        _send_file_threadsafe(
                            main_loop,
                            ch,
                            snap,
                            "[Fortune Wins] Bonus Unavailable (likely already collected)."
                        )
                    else:
                        _send_text_threadsafe(
                            main_loop,
                            ch,
                            "[Fortune Wins] Bonus Unavailable (likely already collected)."
                        )

    except Exception as e:
        if ch:
            _send_text_threadsafe(
                main_loop,
                ch,
                f"⚠️ Fortune Wins (UC) error: {type(e).__name__}: {e}"
            )


# Backwards-compatible alias in case main.py still imports the old name
def fortunecoins_uc_blocking(
    bot,
    channel_id: int,
    main_loop: asyncio.AbstractEventLoop,
):
    return fortunewins_uc_blocking(bot, channel_id, main_loop)


# ───────────────────────────────────────────────────────────
# Optional thin async wrapper
# ───────────────────────────────────────────────────────────
async def fortunewins_uc(ctx, channel: discord.abc.Messageable):
    bot = channel.guild._state._get_client() if hasattr(channel, "guild") else None
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, fortunewins_uc_blocking, bot, channel.id, loop)


# Optional backwards-compatible async alias
async def fortunecoins_uc(ctx, channel: discord.abc.Messageable):
    await fortunewins_uc(ctx, channel)