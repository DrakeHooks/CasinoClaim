# Drake Hooks + WaterTrooper
# Casino Claim 2
# Sportzino API (SeleniumBase UC) — ALWAYS post a final screenshot (success or failure)

import os
import discord
from dotenv import load_dotenv
from seleniumbase import SB

load_dotenv()

# Expect "email:password" in SPORTZINO
SPORTZINO_CRED = os.getenv("SPORTZINO", "")

# ───────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────
async def _send_screenshot(
    sb: SB,
    channel: discord.abc.Messageable,
    path: str,
    caption: str,
):
    """Save -> send -> cleanup. Used for both success and failure paths."""
    try:
        sb.save_screenshot(path)
        await channel.send(caption, file=discord.File(path))
    finally:
        try:
            if os.path.exists(path):
                os.remove(path)
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


def _close_popups_before_rewards(sb: SB):
    """Close known Sportzino popups BEFORE opening Rewards."""
    popup_xpaths = [
        "/html/body/div[3]/div/div[1]/div/div/div/div[1]/div[2]/button",
        "/html/body/div[3]/div/div[1]/div/div/button",
        "/html/body/div[4]/div/div[1]/div/div/button",
        "/html/body/div[5]/div/div[1]/div/div/button",
        "/html/body/div[6]/div/div[1]/div/div/div/div[2]/button",
        "//button[contains(.,'Close') or contains(.,'Dismiss') or contains(.,'Got it')]",
        "//div[contains(@class,'modal')]//button[@aria-label='Close']",
        "//div[contains(@class,'modal')]//button[contains(@class,'close')]",
    ]
    if _try_click_any(sb, popup_xpaths, timeout_each=6):
        print("[Sportzino] Closed a popup.")
    try:
        sb.press_keys("body", "ESCAPE")
    except Exception:
        pass


# ───────────────────────────────────────────────────────────
# Main UC-based flow
# ───────────────────────────────────────────────────────────
async def Sportzino(ctx, driver, channel: discord.abc.Messageable):
    """
    Sportzino via SeleniumBase (uc=True).
    ALWAYS sends a screenshot to Discord at the end with a single-line caption:
      - Success: "Sportzino Daily Bonus Claimed!"
      - Unavailable: "Sportzino: no claim available (likely already claimed)."
      - Rewards missing: "Sportzino: Rewards/Coins section not found."
      - Login fail / exception: Single-line reason.
    """

    # Basic env sanity
    if ":" not in SPORTZINO_CRED:
        await channel.send("[Sportzino][ERROR] Missing SPORTZINO 'email:password' in .env")
        return

    username, password = SPORTZINO_CRED.split(":", 1)

    try:
        with SB(uc=True, headed=True) as sb:
            # 1) Login
            sb.uc_open_with_reconnect("https://sportzino.com/login", 4)
            sb.wait_for_ready_state_complete()
            print("[Sportzino] Login page loaded.")

            # Type creds
            try:
                # Try common selectors first
                typed = False
                for sel in [
                    "input#emailAddress", "input[id='emailAddress']",
                    "input[name='email']", "input[type='email']",
                ]:
                    try:
                        sb.type(sel, username)
                        typed = True
                        break
                    except Exception:
                        continue
                if not typed:
                    raise Exception("Email field not found")
                sb.wait(10)
                typed = False
                for sel in [
                    "input#password", "input[id='password']",
                    "input[name='password']", "input[type='password']",
                ]:
                    try:
                        sb.type(sel, password)
                        typed = True
                        pwd_sel = sel
                        break
                    except Exception:
                        continue
                if not typed:
                    raise Exception("Password field not found")

                # Attempt GUI captcha click if present (best effort)
                try:
                    sb.uc_gui_click_captcha()
                    sb.wait(10)
                except Exception:
                    pass

            except Exception as e:
                print(f"[Sportzino][ERROR] Login fields/captcha error: {e}")
                await _send_screenshot(sb, channel, "sportzino_login_error.png",
                                       "Sportzino: login fields not found / captcha gating.")
                return

            # Submit (Enter on password first; fallback to explicit button)
            submitted = False
            try:
                sb.press_keys(pwd_sel, "\n")
                submitted = True
            except Exception:
                pass
            if not submitted:
                submitted = _try_click_any(
                    sb,
                    ["//button[@type='submit']", "//button[contains(.,'Log in') or contains(.,'Sign in')]"],
                    timeout_each=10,
                )
            if not submitted:
                await _send_screenshot(sb, channel, "sportzino_submit_fail.png",
                                       "Sportzino: could not submit login.")
                return

            # Post-login settle
            sb.wait(8)
            sb.refresh_page()
            sb.wait_for_ready_state_complete()
            print("[Sportzino] Post-login refresh complete.")

            # 2) Close popups BEFORE Rewards
            _close_popups_before_rewards(sb)

            # 3) Open Rewards / Free Coins / Get Coins
            opened_rewards = _try_click_any(
                sb,
                [
                    # Known header locations (try a few)
                    "/html/body/div[1]/div/nav/div/div[4]/div[1]/button",
                    "/html/body/div[1]/div[1]/div/nav/div/div[4]/div[1]/button",
                    # Text-based fallbacks
                    "//button[contains(.,'Free Coins') or contains(.,'Rewards') or contains(.,'Get Coins')]",
                    "//a[contains(.,'Free Coins') or contains(.,'Rewards') or contains(.,'Get Coins')]",
                    # Heuristic: header area with a span text
                    "//div[contains(@class,'header')]//button[.//span[contains(.,'Coins') or contains(.,'Rewards')]]",
                ],
                timeout_each=12,
            )
            if not opened_rewards:
                print("[Sportzino] Rewards/Coins section not found.")
                await _send_screenshot(sb, channel, "sportzino_rewards_missing.png",
                                       "Sportzino: Rewards/Coins section not found.")
                return

            sb.wait(10)  # Give rewards UI time to render
            print("[Sportzino] Rewards UI should be open (proceeding).")

            # 4) Click Collect (only if enabled)
            collected = _try_click_any(
                sb,
                [
                    # Common modal/button guesses
                    "/html/body/div[5]/div/div[1]/div/div/div[2]/div[2]/div[2]/div[1]/div/div[3]/div/div[1]/button",
                    "/html/body/div[4]/div/div[1]/div/div/div[2]/div[2]/div[2]/div[1]/div/div[3]/div/div[1]/button",
                    "//button[contains(.,'Collect') and not(@disabled)]",
                    "//button[.//span[contains(.,'Collect')] and not(@disabled)]",
                    "//button[contains(.,'Claim') and not(@disabled)]",
                ],
                timeout_each=12,
            )

            if collected:
                sb.wait(3)
                await _send_screenshot(sb, channel, "sportzino_claimed.png",
                                       "Sportzino Daily Bonus Claimed!")
                print("[Sportzino] Claimed successfully.")
                return
            else:
                print("[Sportzino] No claim available (likely already claimed).")
                await _send_screenshot(sb, channel, "sportzino_unavailable.png",
                                       "Sportzino: no claim available (likely already claimed).")
                return

    except Exception as e:
        # Last-resort screenshot; try to capture whatever state exists
        try:
            with SB(uc=True, headed=True) as sb_fallback:
                await _send_screenshot(sb_fallback, channel, "sportzino_exception.png",
                                       f"Sportzino: exception during automation — {e}")
        except Exception:
            # If even fallback browser fails, at least send text.
            await channel.send(f"[Sportzino][ERROR] Exception during automation: {e}")
