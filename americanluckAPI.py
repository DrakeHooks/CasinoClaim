# Drake Hooks + WaterTrooper
# Casino Claim 3
# American Luck API — SeleniumBase UC
#
# Discord output policy:
# - Send the single Launching message.
# - Send one final standardized status with its screenshot.
# - Print detailed diagnostics to the console only.
#
# Behavior:
# 1. Logs in.
# 2. Clears the cookie/privacy panel.
# 3. Detects "YOUR DAILY BONUS IS READY!".
# 4. Clicks "GO TO COIN STORE" inside that popup.
# 5. If that fails, closes blocking popups and clicks GET COINS.
# 6. Finds the card titled exactly "Daily Bonus".
# 7. Clicks Collect only inside that card.
#
# It will not click:
# - Google Grab
# - Connect with Google
# - More Coins
# - Purchase buttons
# - A random global Collect button

import os
from typing import List, Optional

import discord
from dotenv import load_dotenv
from seleniumbase import SB
from claim_state import accept_cookie_banner, reward_success_signatures, wait_for_daily_confirmation
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
)


# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

load_dotenv()

LOGIN_URL = "https://americanluck.com/login"
LOBBY_URL = "https://americanluck.com/lobby"

LOGIN_BUTTON_XP = (
    "/html/body/div[1]/div[2]/main/div/div/div/div[2]/form/div[4]/button"
)

# Keep the inspected header XPath, but also use text-based fallbacks.
GET_COINS_BTN_XP = "/html/body/div[1]/div[2]/header/div[2]/button[1]"

# Previous known popup close XPath.
# It is used only as a guarded fallback after a blocker has been detected.
KNOWN_POPUP_CLOSE_XP = "/html/body/div[5]/div/button"

# Previous known Daily Bonus Collect XPath.
# It is guarded by card-title verification before being clicked.
DAILY_BONUS_EXACT_COLLECT_XP = (
    "/html/body/div[7]/div/div/section[3]/div/div/"
    "div[1]/div/div[3]/button[1]"
)

UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LOWER = "abcdefghijklmnopqrstuvwxyz"

POPUP_ROOT_XP = (
    "//div["
    "contains(@class,'rag-popup') or "
    "contains(@class,'popup') or "
    "contains(@class,'modal') or "
    "@role='dialog'"
    "]"
)

STORE_DIALOG_CSS = "div.free-coin-dialog"
REWARD_CARD_CSS = "div.free-reward-card"
REWARD_CARD_TITLE_CSS = ".free-reward-card__title"

COOKIE_MARKERS = (
    "we value your privacy",
    "manage cookies",
    "accept all",
    "privacy policy",
)

DAILY_READY_MARKERS = (
    "your daily bonus is ready",
    "go to coin store",
    "go to the coin store",
    "uncover and collect your reward",
)

GOOGLE_POPUP_MARKERS = (
    "connect with google",
    "connect your google account",
    "google rewards",
    "lucrative bonus",
)

STORE_MARKERS = (
    "claim free rewards",
    "purchase store packs",
)

CLAIMED_MARKERS = (
    "already claimed",
    "bonus is claimed",
    "daily bonus claimed",
    "today's bonus is claimed",
    "todays bonus is claimed",
)


# ─────────────────────────────────────────────────────────────
# Discord and screenshot helpers
# ─────────────────────────────────────────────────────────────

async def _send_shot(
    sb: SB,
    channel: discord.abc.Messageable,
    path: str,
    caption: str,
) -> None:
    """Print diagnostics locally and send one concise status with the screenshot."""
    print(caption)
    if caption == "American Luck Daily Bonus Claimed!":
        status = caption
    elif path == "americanluck_already_claimed.png":
        status = "American Luck Daily Bonus Unavailable."
    elif path == "americanluck_login_failed.png":
        status = "American Luck Login Failed."
    else:
        status = "American Luck Daily Bonus Unverified."

    try:
        sb.save_screenshot(path)
        await channel.send(status, file=discord.File(path))
    except Exception as error:
        print(f"[American Luck][SCREENSHOT ERROR] {error}")
        await channel.send(status)
    finally:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as cleanup_error:
            print(
                "[American Luck][SCREENSHOT CLEANUP ERROR] "
                f"{cleanup_error}"
            )


# ─────────────────────────────────────────────────────────────
# Generic DOM helpers
# ─────────────────────────────────────────────────────────────

def _norm(value: str) -> str:
    return " ".join((value or "").lower().split())


def _safe_text(sb: SB, element: WebElement) -> str:
    try:
        text = element.text
        if text:
            return text
    except Exception:
        pass

    try:
        return (
            sb.execute_script(
                """
                return arguments[0].innerText ||
                       arguments[0].textContent ||
                       '';
                """,
                element,
            )
            or ""
        )
    except Exception:
        return ""


def _page_text(sb: SB) -> str:
    try:
        return (
            sb.execute_script(
                "return document.body ? document.body.innerText : '';"
            )
            or ""
        )
    except Exception:
        try:
            return sb.get_text("body")
        except Exception:
            return ""


def _is_visible(element: WebElement) -> bool:
    try:
        return element.is_displayed()
    except Exception:
        return False


def _is_enabled(element: WebElement) -> bool:
    try:
        return element.is_enabled()
    except Exception:
        return False


def _is_disabled(element: WebElement) -> bool:
    try:
        if element.get_attribute("disabled") is not None:
            return True

        if _norm(element.get_attribute("aria-disabled") or "") == "true":
            return True

        classes = _norm(element.get_attribute("class") or "")
        if "disabled" in classes:
            return True
    except Exception:
        pass

    return False


def _find_xpath(sb: SB, xpath: str) -> List[WebElement]:
    try:
        return sb.driver.find_elements(By.XPATH, xpath)
    except Exception:
        return []


def _find_css(sb: SB, css: str) -> List[WebElement]:
    try:
        return sb.driver.find_elements(By.CSS_SELECTOR, css)
    except Exception:
        return []


def _button_from_element(element: WebElement) -> WebElement:
    """Return the nearest button when passed a child such as button-content."""
    try:
        if (element.tag_name or "").lower() == "button":
            return element
    except Exception:
        return element

    try:
        return element.find_element(By.XPATH, "./ancestor::button[1]")
    except Exception:
        return element


def _element_area(element: WebElement) -> float:
    try:
        rect = element.rect
        return max(float(rect["width"]) * float(rect["height"]), 1.0)
    except Exception:
        return float("inf")


def _element_depth(sb: SB, element: WebElement) -> int:
    try:
        return int(
            sb.execute_script(
                """
                let depth = 0;
                let node = arguments[0];

                while (node && node.parentElement) {
                    depth++;
                    node = node.parentElement;
                }

                return depth;
                """,
                element,
            )
        )
    except Exception:
        return 0


def _hard_click(sb: SB, element: WebElement) -> bool:
    """Click using native, ActionChains, JavaScript, and event fallbacks."""
    try:
        element = _button_from_element(element)
    except Exception:
        pass

    if not _is_visible(element):
        return False

    if _is_disabled(element):
        return False

    try:
        sb.execute_script(
            """
            arguments[0].scrollIntoView({
                block: 'center',
                inline: 'center'
            });
            """,
            element,
        )
        sb.wait(0.35)
    except Exception:
        pass

    # Normal Selenium click.
    try:
        element.click()
        return True
    except (
        ElementClickInterceptedException,
        StaleElementReferenceException,
    ):
        pass
    except Exception:
        pass

    # SeleniumBase ActionChains click.
    try:
        sb.driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});",
            element,
        )
        sb.driver.switch_to.active_element
        sb.wait(0.2)

        from selenium.webdriver.common.action_chains import ActionChains

        ActionChains(sb.driver).move_to_element(element).pause(0.2).click().perform()
        return True
    except Exception:
        pass

    # JavaScript click.
    try:
        sb.execute_script("arguments[0].click();", element)
        return True
    except Exception:
        pass

    # Full pointer/mouse event sequence.
    try:
        sb.execute_script(
            """
            const el = arguments[0];

            const events = [
                'pointerover',
                'mouseover',
                'pointerenter',
                'mouseenter',
                'pointerdown',
                'mousedown',
                'pointerup',
                'mouseup',
                'click'
            ];

            for (const type of events) {
                const EventClass = type.startsWith('pointer')
                    ? PointerEvent
                    : MouseEvent;

                el.dispatchEvent(
                    new EventClass(type, {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    })
                );
            }
            """,
            element,
        )
        return True
    except Exception:
        return False


def _click_xpath(
    sb: SB,
    xpath: str,
    timeout: float = 5,
) -> bool:
    try:
        sb.wait_for_element_visible(xpath, timeout=timeout)
    except Exception:
        return False

    for element in _find_xpath(sb, xpath):
        if _is_visible(element) and _is_enabled(element):
            if _hard_click(sb, element):
                return True

    return False


# ─────────────────────────────────────────────────────────────
# Popup discovery
# ─────────────────────────────────────────────────────────────

def _popup_matches(
    sb: SB,
    popup: WebElement,
    markers: tuple[str, ...],
) -> bool:
    try:
        if not _is_visible(popup):
            return False

        classes = _norm(popup.get_attribute("class") or "")

        # Never mistake the actual coin-store dialog for a blocker.
        if "free-coin-dialog" in classes:
            return False

        text = _norm(_safe_text(sb, popup))
        return any(marker in text for marker in markers)
    except Exception:
        return False


def _find_matching_popup(
    sb: SB,
    markers: tuple[str, ...],
) -> Optional[WebElement]:
    """
    Find the most specific visible popup containing one of the supplied markers.

    Smallest area and deepest DOM node are preferred so a large parent
    container is not selected instead of the actual popup.
    """
    candidates: List[WebElement] = []

    for popup in _find_xpath(sb, POPUP_ROOT_XP):
        try:
            if _popup_matches(sb, popup, markers):
                candidates.append(popup)
        except StaleElementReferenceException:
            continue
        except Exception:
            continue

    if not candidates:
        return None

    candidates.sort(
        key=lambda element: (
            _element_area(element),
            -_element_depth(sb, element),
        )
    )

    return candidates[0]


def _popup_button_by_text(
    sb: SB,
    popup: WebElement,
    phrases: tuple[str, ...],
    exact: bool = False,
) -> Optional[WebElement]:
    try:
        buttons = popup.find_elements(By.TAG_NAME, "button")
    except Exception:
        buttons = []

    for button in buttons:
        try:
            if not _is_visible(button):
                continue

            if _is_disabled(button):
                continue

            text = _norm(_safe_text(sb, button))

            if exact:
                if text in phrases:
                    return button
            elif any(phrase in text for phrase in phrases):
                return button
        except Exception:
            continue

    return None


def _popup_close_button(
    sb: SB,
    popup: WebElement,
) -> Optional[WebElement]:
    try:
        buttons = popup.find_elements(By.TAG_NAME, "button")
    except Exception:
        buttons = []

    explicit: List[WebElement] = []
    icon_buttons: List[WebElement] = []

    for button in buttons:
        try:
            if not _is_visible(button):
                continue

            classes = _norm(button.get_attribute("class") or "")
            aria = _norm(button.get_attribute("aria-label") or "")
            title = _norm(button.get_attribute("title") or "")
            text = _norm(_safe_text(sb, button))

            if (
                "close" in classes
                or "close" in aria
                or "close" in title
                or text in {"x", "×", "✕", "✖"}
            ):
                explicit.append(button)
                continue

            try:
                if button.find_elements(By.TAG_NAME, "svg"):
                    icon_buttons.append(button)
            except Exception:
                pass
        except Exception:
            continue

    if explicit:
        return explicit[0]

    # Select an icon-only button near the popup's upper-right corner.
    try:
        popup_rect = popup.rect
        popup_top = float(popup_rect["y"])
        popup_right = float(popup_rect["x"]) + float(popup_rect["width"])

        for button in icon_buttons:
            rect = button.rect
            button_top = float(rect["y"])
            button_right = float(rect["x"]) + float(rect["width"])

            near_top = button_top <= popup_top + 120
            near_right = button_right >= popup_right - 150

            if near_top and near_right:
                return button
    except Exception:
        pass

    return None


def _close_popup(
    sb: SB,
    popup: WebElement,
) -> bool:
    button = _popup_close_button(sb, popup)

    if button is not None and _hard_click(sb, button):
        sb.wait(0.8)
        return True

    # Guarded fallback using the previously inspected close XPath.
    try:
        if _click_xpath(sb, KNOWN_POPUP_CLOSE_XP, timeout=1):
            sb.wait(0.8)
            return True
    except Exception:
        pass

    try:
        sb.press_keys("body", "ESCAPE")
        sb.wait(0.8)
        return not _is_visible(popup)
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
# Cookie/privacy popup
# ─────────────────────────────────────────────────────────────

def _handle_cookie_popup(sb: SB) -> bool:
    if accept_cookie_banner(sb, passes=1):
        return True
    popup = _find_matching_popup(sb, COOKIE_MARKERS)

    if popup is None:
        return False

    # Prefer accepting so it does not return on subsequent runs.
    accept_button = _popup_button_by_text(
        sb,
        popup,
        (
            "accept all",
            "accept cookies",
            "allow all",
            "agree",
        ),
    )

    if accept_button is not None:
        if _hard_click(sb, accept_button):
            sb.wait(1)
            return True

    return _close_popup(sb, popup)


# ─────────────────────────────────────────────────────────────
# Daily Bonus Ready popup
# ─────────────────────────────────────────────────────────────

def _handle_daily_ready_popup(sb: SB) -> str:
    """
    Returns:
        "none"         — popup not present
        "store_clicked" — Go To Coin Store clicked
        "closed"       — popup could not open store, but was closed
        "blocked"      — popup could not be handled
    """
    popup = _find_matching_popup(sb, DAILY_READY_MARKERS)

    if popup is None:
        return "none"

    # This is the preferred route. Do not close the modal first.
    store_button = _popup_button_by_text(
        sb,
        popup,
        (
            "go to coin store",
            "go to the coin store",
            "coin store",
        ),
    )

    if store_button is not None:
        if _hard_click(sb, store_button):
            sb.wait(2)
            return "store_clicked"

    # Global text-anchored fallback, still requiring the ready-popup text.
    global_store_xp = (
        "//button["
        "contains("
        f"translate(normalize-space(.),'{UPPER}','{LOWER}'),"
        "'go to coin store'"
        ")"
        "]"
    )

    if _click_xpath(sb, global_store_xp, timeout=2):
        sb.wait(2)
        return "store_clicked"

    # If the button itself cannot be used, remove the popup so GET COINS
    # can be clicked normally.
    if _close_popup(sb, popup):
        return "closed"

    return "blocked"


# ─────────────────────────────────────────────────────────────
# Connect with Google popup
# ─────────────────────────────────────────────────────────────

def _handle_google_popup(sb: SB) -> bool:
    popup = _find_matching_popup(sb, GOOGLE_POPUP_MARKERS)

    if popup is None:
        return False

    return _close_popup(sb, popup)


# ─────────────────────────────────────────────────────────────
# Store detection and opening
# ─────────────────────────────────────────────────────────────

def _store_dialog_open(sb: SB) -> bool:
    for dialog in _find_css(sb, STORE_DIALOG_CSS):
        try:
            if _is_visible(dialog):
                return True
        except Exception:
            continue

    text = _norm(_page_text(sb))

    return all(marker in text for marker in STORE_MARKERS)


def _get_coins_button(sb: SB) -> Optional[WebElement]:
    # First use the inspected XPath.
    for element in _find_xpath(sb, GET_COINS_BTN_XP):
        try:
            if (
                _is_visible(element)
                and _is_enabled(element)
                and not _is_disabled(element)
            ):
                return element
        except Exception:
            continue

    # Stable text-anchored header selector.
    xpath = (
        "//header//button["
        "contains("
        f"translate(normalize-space(.),'{UPPER}','{LOWER}'),"
        "'get coins'"
        ")"
        "]"
    )

    for element in _find_xpath(sb, xpath):
        try:
            if (
                _is_visible(element)
                and _is_enabled(element)
                and not _is_disabled(element)
            ):
                return element
        except Exception:
            continue

    # Last text-based fallback outside the header.
    xpath = (
        "//button["
        "translate("
        f"normalize-space(.),'{UPPER}','{LOWER}'"
        ")='get coins'"
        "]"
    )

    for element in _find_xpath(sb, xpath):
        try:
            if (
                _is_visible(element)
                and _is_enabled(element)
                and not _is_disabled(element)
            ):
                return element
        except Exception:
            continue

    return None


def _click_get_coins(sb: SB) -> bool:
    button = _get_coins_button(sb)

    if button is None:
        return False

    return _hard_click(sb, button)


def _refresh_lobby(sb: SB) -> None:
    try:
        sb.refresh_page()
    except Exception:
        try:
            sb.execute_script("window.location.reload();")
        except Exception:
            return

    sb.wait(5)

    try:
        sb.wait_for_ready_state_complete()
    except Exception:
        pass


def _open_coin_store(sb: SB) -> bool:
    """
    Intelligent store-opening state machine.

    Priority:
    1. Accept cookie banner.
    2. Click Go To Coin Store in the ready popup.
    3. Close Connect with Google.
    4. Click header GET COINS.
    5. Refresh and repeat as a limited fallback.
    """
    refreshes_used = 0

    for attempt in range(1, 9):
        try:
            sb.wait_for_ready_state_complete()
        except Exception:
            pass

        if _store_dialog_open(sb):
            return True

        changed = False

        # Cookie consent can overlap the lower-right area and intercept clicks.
        if _handle_cookie_popup(sb):
            changed = True
            sb.wait(0.8)

        if _store_dialog_open(sb):
            return True

        # The daily-ready popup is not an error. Use its store button.
        ready_result = _handle_daily_ready_popup(sb)

        if ready_result == "store_clicked":
            sb.wait(2)

            if _store_dialog_open(sb):
                return True

            changed = True

        elif ready_result == "closed":
            changed = True
            sb.wait(0.8)

        elif ready_result == "blocked":
            changed = True

        if _store_dialog_open(sb):
            return True

        # Remove Google promotion popup when present.
        if _handle_google_popup(sb):
            changed = True
            sb.wait(0.8)

        if _store_dialog_open(sb):
            return True

        # After blockers are gone, use the normal header button.
        if _click_get_coins(sb):
            changed = True
            sb.wait(2)

            if _store_dialog_open(sb):
                return True

            # Clicking GET COINS may reveal another popup. The next loop
            # handles that popup instead of immediately failing.
            continue

        # If DOM changed during popup dismissal, wait before rescanning.
        if changed:
            sb.wait(1)
            continue

        # Limited refresh fallback. Do not refresh indefinitely.
        if attempt in {3, 6} and refreshes_used < 2:
            refreshes_used += 1
            _refresh_lobby(sb)
            continue

        sb.wait(1)

    return _store_dialog_open(sb)


# ─────────────────────────────────────────────────────────────
# Daily Bonus card and Collect button
# ─────────────────────────────────────────────────────────────

def _scroll_store_to_rewards(sb: SB) -> None:
    try:
        sb.execute_script(
            """
            const dialog =
                document.querySelector('.free-coin-dialog') ||
                document.querySelector('.dialog-container');

            const rewardTitle = [...document.querySelectorAll('h2,h3')]
                .find(el =>
                    /claim free rewards/i.test(
                        el.innerText || el.textContent || ''
                    )
                );

            if (rewardTitle) {
                rewardTitle.scrollIntoView({
                    block: 'center',
                    inline: 'center'
                });
            }

            if (dialog) {
                const scrollContainers = [
                    dialog,
                    ...dialog.querySelectorAll(
                        "[class*='scroll'], [style*='overflow']"
                    )
                ];

                for (const container of scrollContainers) {
                    if (container.scrollHeight > container.clientHeight) {
                        container.scrollTop = container.scrollHeight;
                    }
                }
            }
            """
        )
        sb.wait(1)
    except Exception:
        pass


def _reward_card_title(
    sb: SB,
    card: WebElement,
) -> str:
    try:
        title = card.find_element(By.CSS_SELECTOR, REWARD_CARD_TITLE_CSS)
        return _norm(_safe_text(sb, title))
    except Exception:
        pass

    # Class fallback if title class changes.
    try:
        headings = card.find_elements(By.XPATH, ".//h1 | .//h2 | .//h3 | .//h4")

        for heading in headings:
            text = _norm(_safe_text(sb, heading))
            if text:
                return text
    except Exception:
        pass

    return ""


def _daily_bonus_card(sb: SB) -> Optional[WebElement]:
    for card in _find_css(sb, REWARD_CARD_CSS):
        try:
            if not _is_visible(card):
                continue

            title = _reward_card_title(sb, card)

            # Require the actual card title.
            if title == "daily bonus":
                return card
        except StaleElementReferenceException:
            continue
        except Exception:
            continue

    # XPath title fallback.
    xpath = (
        "//div[contains(@class,'free-reward-card')]"
        "[.//*[contains(@class,'free-reward-card__title') "
        "and translate("
        f"normalize-space(.),'{UPPER}','{LOWER}'"
        ")='daily bonus']]"
    )

    for card in _find_xpath(sb, xpath):
        try:
            if _is_visible(card):
                return card
        except Exception:
            continue

    return None


def _collect_button_inside_card(
    sb: SB,
    card: WebElement,
) -> Optional[WebElement]:
    try:
        buttons = card.find_elements(By.TAG_NAME, "button")
    except Exception:
        buttons = []

    for button in buttons:
        try:
            if not _is_visible(button):
                continue

            if not _is_enabled(button) or _is_disabled(button):
                continue

            text = _norm(_safe_text(sb, button))

            # Exact Collect only.
            if text != "collect":
                continue

            return button
        except StaleElementReferenceException:
            continue
        except Exception:
            continue

    return None


def _exact_collect_xpath_guarded(sb: SB) -> Optional[WebElement]:
    """
    Use today's inspected XPath only when it belongs to a card whose title
    is exactly Daily Bonus.
    """
    for element in _find_xpath(sb, DAILY_BONUS_EXACT_COLLECT_XP):
        try:
            button = _button_from_element(element)

            if not _is_visible(button):
                continue

            if _norm(_safe_text(sb, button)) != "collect":
                continue

            card = button.find_element(
                By.XPATH,
                "./ancestor::div[contains(@class,'free-reward-card')][1]",
            )

            if _reward_card_title(sb, card) != "daily bonus":
                continue

            return button
        except Exception:
            continue

    return None


def _click_daily_bonus_collect(sb: SB) -> bool:
    if not _store_dialog_open(sb):
        return False

    _scroll_store_to_rewards(sb)

    # Preferred approach: locate card title first.
    card = _daily_bonus_card(sb)

    if card is not None:
        button = _collect_button_inside_card(sb, card)

        if button is not None:
            return _hard_click(sb, button)

    # Guarded inspected XPath fallback.
    button = _exact_collect_xpath_guarded(sb)

    if button is not None:
        return _hard_click(sb, button)

    return False


# ─────────────────────────────────────────────────────────────
# Debugging
# ─────────────────────────────────────────────────────────────

def _debug_state(sb: SB) -> str:
    lines: List[str] = []

    try:
        lines.append(f"url: {sb.get_current_url()}")
    except Exception:
        pass

    lines.append(f"store_dialog_open: {_store_dialog_open(sb)}")

    cookie_popup = _find_matching_popup(sb, COOKIE_MARKERS)
    ready_popup = _find_matching_popup(sb, DAILY_READY_MARKERS)
    google_popup = _find_matching_popup(sb, GOOGLE_POPUP_MARKERS)

    lines.append(f"cookie_popup: {cookie_popup is not None}")
    lines.append(f"daily_ready_popup: {ready_popup is not None}")
    lines.append(f"google_popup: {google_popup is not None}")
    lines.append(f"get_coins_button: {_get_coins_button(sb) is not None}")

    cards = _find_css(sb, REWARD_CARD_CSS)
    lines.append(f"reward_cards: {len(cards)}")

    for index, card in enumerate(cards[:6], start=1):
        try:
            title = _reward_card_title(sb, card)
            button_texts = []

            for button in card.find_elements(By.TAG_NAME, "button"):
                button_texts.append(_norm(_safe_text(sb, button)))

            lines.append(
                f"card_{index}: title={title!r}, buttons={button_texts!r}"
            )
        except Exception as error:
            lines.append(f"card_{index}: debug_error={error}")

    return "\n".join(lines)


def _appears_already_claimed(sb: SB) -> bool:
    card = _daily_bonus_card(sb)
    if card is None:
        return False
    text = _norm(_safe_text(sb, card))
    return any(marker in text for marker in CLAIMED_MARKERS + (
        "come back tomorrow", "see you tomorrow", "daily bonus unavailable",
        "next daily bonus", "available in",
    )) and _collect_button_inside_card(sb, card) is None


# ─────────────────────────────────────────────────────────────
# Main American Luck flow
# ─────────────────────────────────────────────────────────────

async def americanluck_uc(
    ctx,
    channel: discord.abc.Messageable,
) -> None:
    await channel.send("Launching **American Luck (UC)**…")

    creds = os.getenv("AMERICANLUCK")

    if not creds or ":" not in creds:
        print(
            "[American Luck][ERROR] AMERICANLUCK is missing from .env. "
            "Expected email:password."
        )
        return

    username, password = creds.split(":", 1)

    sb: Optional[SB] = None

    try:
        with SB(uc=True, headed=True) as sb:
            # ── Step 1: login ──

            sb.uc_open_with_reconnect(LOGIN_URL, 8)
            sb.wait_for_ready_state_complete()
            sb.wait(1)
            accept_cookie_banner(sb)

            sb.type("input[id='emailAddress']", username)
            sb.type("input[id='password']", password)

            try:
                sb.uc_gui_click_captcha()
            except Exception:
                pass

            sb.wait(1.5)
            accept_cookie_banner(sb, passes=2)

            login_clicked = _click_xpath(
                sb,
                LOGIN_BUTTON_XP,
                timeout=10,
            )

            if not login_clicked:
                # Text-based login fallback.
                login_xp = (
                    "//button["
                    "contains("
                    f"translate(normalize-space(.),'{UPPER}','{LOWER}'),"
                    "'login'"
                    ") or contains("
                    f"translate(normalize-space(.),'{UPPER}','{LOWER}'),"
                    "'log in'"
                    ")"
                    "]"
                )

                _click_xpath(sb, login_xp, timeout=4)

            sb.wait(6)

            try:
                sb.wait_for_ready_state_complete()
            except Exception:
                pass

            # ── Step 2: verify lobby ──

            login_ok = False

            try:
                current_url = sb.get_current_url()
                login_ok = current_url.startswith(LOBBY_URL)
            except Exception:
                pass

            if not login_ok and _get_coins_button(sb) is not None:
                login_ok = True

            if not login_ok:
                await _send_shot(
                    sb,
                    channel,
                    "americanluck_login_failed.png",
                    "[American Luck] Login failed or the lobby did not load.",
                )
                return

            # ── Step 3: enter store intelligently ──

            store_opened = _open_coin_store(sb)

            if not store_opened:
                debug = _debug_state(sb)

                await _send_shot(
                    sb,
                    channel,
                    "americanluck_store_blocked.png",
                    "[American Luck] Could not enter the Coin Store after "
                    "handling the cookie panel, Daily Bonus popup, Google popup, "
                    "GET COINS button, and refresh fallbacks.\n\n"
                    f"```text\n{debug[:1700]}\n```",
                )
                return

            sb.wait(2)

            # ── Step 4: claim only Daily Bonus ──

            before_signatures = reward_success_signatures(sb)
            before_unavailable = _appears_already_claimed(sb)
            collected = False
            if not before_unavailable:
                collected = _click_daily_bonus_collect(sb)
                if not collected:
                    sb.wait(2)
                    collected = _click_daily_bonus_collect(sb)
                if not collected:
                    _scroll_store_to_rewards(sb)
                    sb.wait(1)
                    collected = _click_daily_bonus_collect(sb)

            if collected:
                verified = wait_for_daily_confirmation(
                    sb, before_signatures,
                    lambda: not before_unavailable and _appears_already_claimed(sb),
                )
                await _send_shot(
                    sb,
                    channel,
                    "americanluck_claimed.png" if verified else "americanluck_unverified.png",
                    "American Luck Daily Bonus Claimed!" if verified else
                    "[American Luck] Collect clicked, but no new confirmation observed.",
                )
                return

            if _appears_already_claimed(sb):
                await _send_shot(
                    sb,
                    channel,
                    "americanluck_already_claimed.png",
                    "[American Luck] The Daily Bonus appears to already be claimed.",
                )
                return

            debug = _debug_state(sb)

            await _send_shot(
                sb,
                channel,
                "americanluck_collect_failed.png",
                "[American Luck] The Coin Store opened, but I could not click "
                "**Daily Bonus → Collect**. I refused all non-Daily Bonus "
                "buttons.\n\n"
                f"```text\n{debug[:1700]}\n```",
            )

    except Exception as error:
        try:
            if sb is not None:
                await _send_shot(
                    sb,
                    channel,
                    "americanluck_error.png",
                    f"⚠️ American Luck crashed: `{error}`",
                )
            else:
                print(
                    "[American Luck][ERROR] Crashed before the browser "
                    f"started: {error}"
                )
        except Exception as reporting_error:
            print(
                "[American Luck][ERROR] Failed while reporting crash: "
                f"{reporting_error}"
            )