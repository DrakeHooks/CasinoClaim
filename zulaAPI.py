# Drake Hooks + WaterTrooper
# Casino Claim 2
# Zula API (SeleniumBase UC; no timer scraping)
# Exposes: async def zula_uc(ctx, channel)

import os
import discord
from dotenv import load_dotenv
from seleniumbase import SB

load_dotenv()

# Expect "email:password" in ZULA
ZULA_CRED = os.getenv("ZULA", "")

# ───────────────────────────────────────────────────────────
# Helpers (FC/Sportzino-style)
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
    """Close known Zula popups that may block the Rewards/Get Coins button."""
    popup_xpaths = [
        "/html/body/div[4]/div/div[1]/div/div/button",
        "/html/body/div[4]/div/div/div[2]/button[4]",
        "/html/body/div[4]/div[4]/div/div/div/div[1]/div",
        "//button[contains(translate(., 'CLOSE', 'close'),'close')]",
        "//button[contains(.,'Close')]",
    ]
    if _try_click_any(sb, popup_xpaths, timeout_each=6):
        print("[Zula] Closed a popup.")
    try:
        sb.press_keys("body", "ESCAPE")
    except Exception:
        pass

# ───────────────────────────────────────────────────────────
# Main UC-based flow
# ───────────────────────────────────────────────────────────
async def zula_uc(ctx, channel: discord.abc.Messageable):
    """
    Zula via SeleniumBase (uc=True).
    - Sends exactly one screenshot only on successful claim.
    - If no claim available (or auth fails), sends one line: 'Zula: countdown not available (or auth failed).'
    """
    await channel.send("Launching **Zula** (UC)…")

    if ":" not in ZULA_CRED:
        await channel.send("❌ Missing `ZULA` as 'email:password' in your .env.")
        return

    username, password = ZULA_CRED.split(":", 1)

    try:
        with SB(uc=True, headed=True) as sb:
            # 1) Login
            sb.uc_open_with_reconnect("https://www.zulacasino.com/login", 4)
            sb.wait_for_ready_state_complete()
            print("[Zula] Login page loaded.")

            try:
                sb.type("input[id='emailAddress']", username)
                sb.type("input[id='password']", password)
                try:
                    sb.uc_gui_click_captcha()
                except Exception:
                    pass
            except Exception as e:
                print(f"[Zula][ERROR] Login fields not found: {e}")
                await channel.send("Zula: countdown not available (or auth failed).")
                return

            # Submit login
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
                print("[Zula][ERROR] Could not submit login.")
                await channel.send("Zula: countdown not available (or auth failed).")
                return

            # Post-login settle and clean up
            sb.wait(8)
            sb.refresh_page()
            sb.wait_for_ready_state_complete()
            print("[Zula] Post-login refresh complete.")

            _close_popups_before_rewards(sb)

            # 2) Open Rewards / Free Coins
            opened_rewards = _try_click_any(
                sb,
                [
                    "/html/body/div[1]/div[2]/div[1]/div/nav/div[2]/button[1]",
                    "/html/body/div[1]/div[2]/div/nav/div[2]/button[1]",
                    "//button[contains(.,'Free Coins') or contains(.,'Rewards') or contains(.,'Get Coins')]",
                ],
                timeout_each=12,
            )
            if not opened_rewards:
                print("[Zula] Rewards/Free Coins button not found.")
                await channel.send("Zula: countdown not available (or auth failed).")
                return

            sb.wait(10)  # allow modal to render
            print("[Zula] Rewards modal should be open (proceeding).")

            # 3) Click Collect / Claim inside Rewards modal
            collected = _try_click_any(
                sb,
                [
                    "/html/body/div[4]/div/div[1]/div/div/div[2]/div[1]/div[2]/div[1]/div/button",
                    "//button[contains(.,'Collect') and not(@disabled)]",
                    "//button[.//span[contains(.,'Collect')] and not(@disabled)]",
                    "//button[contains(.,'Claim') and not(@disabled)]",
                ],
                timeout_each=12,
            )

            if collected:
                sb.wait(3)
                await _send_post_claim(sb, channel, "zula_claimed.png", "Zula Daily Bonus Claimed!")
                print("[Zula] Claimed successfully.")
            else:
                print("[Zula] No claim available (likely already claimed).")
                await channel.send("Zula: countdown not available (or auth failed).")

    except Exception as e:
        print(f"[Zula][ERROR] Exception during automation: {e}")
        await channel.send("Zula: countdown not available (or auth failed).")
