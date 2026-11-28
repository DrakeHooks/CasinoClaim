# Drake Hooks + WaterTrooper
# Casino Claim 2
# YayCasino API (SeleniumBase UC) — modeled after Zula flow
# Exposes: async def yaycasino_uc(ctx, channel)

import os
import tempfile
import discord
from dotenv import load_dotenv
from seleniumbase import SB
from claim_state import (
    accept_cookie_banner, close_google_prompt, daily_card_snapshot,
    login_form_visible, reward_success_signatures, wait_for_daily_confirmation,
)

load_dotenv()

# Expect "email:password" in YAYCASINO
YAY_CRED = os.getenv("YAYCASINO", "")

# ───────────────────────────────────────────────────────────
# Constants
# ───────────────────────────────────────────────────────────
LOGIN_URL = "https://www.yaycasino.com/login"
LOBBY_URL = "https://www.yaycasino.com/lobby"

# Auth fields
EMAIL_ID = "emailAddress"
PASSWORD_ID = "password"

# Buttons / XPaths
LOGIN_BTN_XPATH = "/html/body/div[1]/div[2]/div[1]/div[2]/div/div/div[1]/form/div[5]/button"
COIN_STORE_BTN_XPATH = "/html/body/div[1]/div[2]/main/div[1]/div/nav/div[2]/button"
COLLECT_BTN_XPATH = "/html/body/div[5]/div/div[1]/div/div/div[2]/div[1]/div[2]/div[1]/div/div[5]/button[1]"
COMMON_POPUP_CLOSE_XPATH = "/html/body/div[1]/div[1]/div/div/div[1]/button"

# ───────────────────────────────────────────────────────────
# YAY Casino Helpers 
# ───────────────────────────────────────────────────────────
async def _send_post_claim(sb: SB, channel: discord.abc.Messageable, path: str, caption: str):
    """Only used on successful claim to avoid screenshot spam."""
    try:
        sb.save_screenshot(path)
        await channel.send(caption, file=discord.File(path))
    finally:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

async def _send_status_shot(sb: SB, channel: discord.abc.Messageable, caption: str, prefix: str):
    """
    One-off screenshot for 'unavailable' or 'error' states.
    Creates a temp file, attaches it, and cleans up.
    """
    fd, tmp_path = tempfile.mkstemp(prefix=f"{prefix}_", suffix=".png", dir="/tmp")
    os.close(fd)
    try:
        sb.save_screenshot(tmp_path)
        await channel.send(caption, file=discord.File(tmp_path))
    except Exception:
        # Fallback to text-only if screenshot fails
        try:
            await channel.send(caption)
        except Exception:
            pass
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

def _force_click_xpath(sb: SB, xpath: str, timeout: float = 12) -> bool:
    """Robust click chain for stubborn elements."""
    try:
        sb.wait_for_element_visible(xpath, timeout=timeout)
    except Exception:
        return False
    try:
        sb.scroll_to(xpath)
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
                el = sb.find_element(xpath)
                sb.execute_script("arguments[0].click();", el)
            return True
        except Exception:
            continue
    return False

def _try_click_any(sb: SB, xpaths, timeout_each=10) -> bool:
    for xp in xpaths:
        if _force_click_xpath(sb, xp, timeout=timeout_each):
            return True
    return False

def _close_popups_flexible(sb: SB):
    """Dismiss consent and unrelated Google offers, not reward receipts."""
    for _ in range(3):
        accepted = accept_cookie_banner(sb, passes=1)
        closed = close_google_prompt(sb)
        if not accepted and not closed:
            break


# ───────────────────────────────────────────────────────────
# Daily Bonus candidacy and verification
# ───────────────────────────────────────────────────────────

def _daily_unavailable(sb: SB) -> bool:
    card = daily_card_snapshot(sb).get("card")
    return bool(card and card["unavailable"] and not card["enabled"])


def _find_daily_card(sb: SB):
    for _ in range(8):
        observation = daily_card_snapshot(sb)
        card = observation.get("card")
        if card is not None:
            return card
        _close_popups_flexible(sb)
        sb.wait(0.5)
    return None


# ───────────────────────────────────────────────────────────
# Main UC-based flow (Zula-style)
# ───────────────────────────────────────────────────────────
async def yaycasino_uc(ctx, channel: discord.abc.Messageable):
    """
    YayCasino via SeleniumBase (uc=True).
    - Zula-style behavior:
      • Sends one concise final status with a screenshot.
      • Separates verified claims, unavailable rewards, and unverified results.
    """
    await channel.send("Launching **YayCasino** (UC)…")

    if ":" not in YAY_CRED:
        await channel.send("❌ Missing `YAYCASINO` as 'email:password' in your .env.")
        return

    username, password = YAY_CRED.split(":", 1)

    try:
        with SB(uc=True, headed=True) as sb:
            # 1) Login
            sb.uc_open_with_reconnect(LOGIN_URL, 4)
            sb.wait_for_ready_state_complete()
            print("[YayCasino] Login page loaded.")
            accept_cookie_banner(sb)

            try:
                sb.type(f"input[id='{EMAIL_ID}']", username)
                sb.wait(5)
                sb.type(f"input[id='{PASSWORD_ID}']", password)
                try:
                    sb.wait(5)
                    sb.uc_gui_click_captcha()
                    sb.wait(5)
                except Exception:
                    pass
            except Exception as e:
                print(f"[YayCasino][ERROR] Login fields not found: {e}")
                await _send_status_shot(sb, channel, "Yay Casino Login Failed.", "yaycasino_unavailable")
                return

            # Submit login (Enter on password; fallback to explicit button)
            submitted = False
            try:
                sb.press_keys(f"input[id='{PASSWORD_ID}']", "\n")
                submitted = True
            except Exception:
                pass
            if not submitted:
                submitted = _try_click_any(sb, [LOGIN_BTN_XPATH, "//button[@type='submit']"], timeout_each=10)

            if not submitted:
                print("[YayCasino][ERROR] Could not submit login.")
                await _send_status_shot(sb, channel, "Yay Casino Login Failed.", "yaycasino_unavailable")
                return


            # 2) Post login settle breaking Yay Casino claim function, so commented out for now.


            # 2) Post-login settle and refresh into lobby
            # sb.wait(8)
            # sb.refresh_page()
            # sb.wait_for_ready_state_complete()
            # print("[YayCasino] Post-login refresh complete (lobby expected).")

            # # (Optional) Force open lobby URL
            # try:
            #     sb.open(LOBBY_URL)
            #     sb.wait_for_ready_state_complete()
            # except Exception:
            #     pass

            # 3) Close popups
            sb.wait(3)
            _close_popups_flexible(sb)
            if login_form_visible(sb):
                await _send_status_shot(sb, channel, "Yay Casino Login Failed.", "yaycasino_login_failed")
                return

            # 4) Open Rewards / Get Coins
            opened_rewards = _try_click_any(
                sb,
                [
                    COIN_STORE_BTN_XPATH,
                    "//button[contains(.,'Free Coins') or contains(.,'Rewards') or contains(.,'Get Coins')]",
                ],
                timeout_each=12,
            )
            if not opened_rewards:
                print("[YayCasino] Rewards/Coins button not found.")
                await _send_status_shot(sb, channel, "Yay Casino Daily Bonus Unverified.", "yaycasino_unavailable")
                return

            sb.wait(10)  # allow the rewards modal to render fully
            print("[YayCasino] Rewards modal should be open (proceeding).")

            # 5) Click Collect / Claim only inside an identified Daily Bonus card
            _close_popups_flexible(sb)
            card = _find_daily_card(sb)
            if card is None:
                print("[YayCasino] No unique Daily Bonus card identified.")
                await _send_status_shot(sb, channel, "Yay Casino Daily Bonus Unverified.", "yaycasino_no_card")
                return
            if card["unavailable"] and not card["enabled"]:
                await _send_status_shot(sb, channel, "Yay Casino Daily Bonus Unavailable.", "yaycasino_unavailable")
                return
            if card["button"] is None or card["unavailable"]:
                print("[YayCasino] No uniquely enabled Daily Bonus action.")
                await _send_status_shot(sb, channel, "Yay Casino Daily Bonus Unverified.", "yaycasino_no_candidate")
                return

            before = reward_success_signatures(sb)
            try:
                # A real Selenium click respects an obstructing overlay.
                card["button"].click()
            except Exception as error:
                print(f"[YayCasino] Daily Bonus click failed: {type(error).__name__}")
                await _send_status_shot(sb, channel, "Yay Casino Daily Bonus Unverified.", "yaycasino_click_failed")
                return

            # 6) Require actual confirmation, not merely a successful click.
            verified = wait_for_daily_confirmation(sb, before, _daily_unavailable)
            if verified:
                await _send_post_claim(sb, channel, "yaycasino_claimed.png", "Yay Casino Daily Bonus Claimed!")
                print("[YayCasino] Daily Bonus confirmed.")
            else:
                print("[YayCasino] Daily Bonus click had no verified confirmation.")
                await _send_status_shot(sb, channel, "Yay Casino Daily Bonus Unverified.", "yaycasino_unverified")

    except Exception as e:
        print(f"[YayCasino][ERROR] Exception during automation: {e}")
        try:
            with SB(uc=True, headed=True) as sb_fallback:
                await _send_status_shot(sb_fallback, channel, "Yay Casino Daily Bonus Unverified.", "yaycasino_error")
        except Exception:
            await channel.send("Yay Casino Daily Bonus Unverified.")
