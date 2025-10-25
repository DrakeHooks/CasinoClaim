# Drake Hooks + WaterTrooper
# Casino Claim 2
# Sportzino API (SeleniumBase UC) 

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
    # Close known Sportzino popups BEFORE Rewards only.
    popup_xpaths = [
        "/html/body/div[3]/div/div[1]/div/div/div/div[1]/div[2]/button",
        "/html/body/div[3]/div/div[1]/div/div/button",
        "/html/body/div[4]/div/div[1]/div/div/button",
        "/html/body/div[5]/div/div[1]/div/div/button",
        "/html/body/div[6]/div/div[1]/div/div/div/div[2]/button",
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
    
    # Sportzino via SeleniumBase (uc=True).
    # Sends **only** a post-claim screenshot if the claim succeeds.
    # Otherwise prints concise logs/errors (no Discord text).
    
    if ":" not in SPORTZINO_CRED:
        print("[Sportzino][ERROR] Missing SPORTZINO 'email:password' in .env")
        return

    username, password = SPORTZINO_CRED.split(":", 1)

    try:
        with SB(uc=True, headed=True) as sb:
            # 1) Login
            sb.uc_open_with_reconnect("https://sportzino.com/login", 4)
            sb.wait_for_ready_state_complete()
            print("[Sportzino] Login page loaded.")

            try:
                sb.type("input[id='emailAddress']", username)
                sb.type("input[id='password']", password)
                try:
                    sb.uc_gui_click_captcha()
                except Exception:
                    pass
            except Exception as e:
                print(f"[Sportzino][ERROR] Login fields not found: {e}")
                return

            # Submit
            submitted = False
            try:
                sb.press_keys("input[id='password']", "\n")
                submitted = True
            except Exception:
                pass
            if not submitted:
                submitted = _try_click_any(
                    sb,
                    ["//button[@type='submit']", "//button[contains(.,'Log in')]"],
                    timeout_each=10,
                )
            if not submitted:
                print("[Sportzino][ERROR] Could not submit login.")
                return

            # Post-login settle
            sb.wait(8)
            sb.refresh_page()
            sb.wait_for_ready_state_complete()
            print("[Sportzino] Post-login refresh complete.")

            # 2) Close popups BEFORE Rewards
            _close_popups_before_rewards(sb)

            # 3) Open Rewards / Free Coins
            opened_rewards = _try_click_any(
                sb,
                [
                    "/html/body/div[1]/div/nav/div/div[4]/div[1]/button",
                    "/html/body/div[1]/div[1]/div/nav/div/div[4]/div[1]/button",
                    "//button[contains(.,'Free Coins') or contains(.,'Rewards') or contains(.,'Get Coins')]",
                ],
                timeout_each=12,
            )
            if not opened_rewards:
                print("[Sportzino] Rewards/Coins section not found.")
                return

            sb.wait(10)  # give modal time to render
            print("[Sportzino] Rewards modal should be open (proceeding).")

            # 4) Click Collect (do NOT close popups anymore)
            collected = _try_click_any(
                sb,
                [
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
                await _send_post_claim(sb, channel, "sportzino_claimed.png", "Sportzino Daily Bonus Claimed!")
                print("[Sportzino] Claimed successfully.")
            else:
                print("[Sportzino] No claim available (likely already claimed).")

    except Exception as e:
        print(f"[Sportzino][ERROR] Exception during automation: {e}")
