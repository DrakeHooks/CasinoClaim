# Drake Hooks + WaterTrooper
# Casino Claim 2
# Fortune Coins API (SeleniumBase UC)
# Exposes: async def fortunecoins_uc(ctx, channel)

import os
from dotenv import load_dotenv
from seleniumbase import SB
import discord

load_dotenv()

FC_EMAIL = os.getenv("FORTUNECOINSEMAIL", "")
FC_PASSWORD = os.getenv("FORTUNECOINSPASSWORD", "")

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

async def fortunecoins_uc(ctx, channel: discord.abc.Messageable):
    """
    Fortune Coins via SeleniumBase (uc=True).
    Sends **only** a post-claim screenshot if the claim succeeds.
    Otherwise sends a short text note (no images).
    """
    await channel.send("Launching **Fortune Coins** (UC)…")

    if not FC_EMAIL or not FC_PASSWORD:
        await channel.send("❌ Missing `FORTUNECOINSEMAIL` or `FORTUNECOINSPASSWORD` in your .env.")
        return

    try:
        with SB(uc=True, headed=True) as sb:
            # Login
            sb.uc_open_with_reconnect("https://fortunecoins.com/login", 4)
            sb.wait_for_ready_state_complete()
            sb.type("input[id='emailAddress']", FC_EMAIL)
            sb.type("input[id='password']", FC_PASSWORD)
            try:
                sb.uc_gui_click_captcha()
                sb.wait(10)
            except Exception:
                pass
            _force_click_xpath(sb, "/html/body/div[1]/div[5]/div/div/div/div[2]/form/div[4]/button", timeout=12)
            sb.wait(6)
            sb.refresh_page()
            sb.wait_for_ready_state_complete()

            # Close any modal/popups
            _try_click_any(
                sb,
                [
                    "/html/body/div[5]/div/div[1]/div/div/button",
                    "/html/body/div[4]/div/div[1]/div/div/div[3]/div/button[2]",
                    "/html/body/div[4]/div/div[1]/div/div/button",
                ],
                timeout_each=6,
            )
            try:
                sb.press_keys("body", "ESCAPE")
            except Exception:
                pass

            # Open Rewards/Get Coins
            _try_click_any(
                sb,
                [
                    "/html/body/div[1]/div[2]/div[1]/div/nav/div[2]/div[3]/button",
                    "/html/body/div[1]/div[2]/div/nav/div[2]/div[3]/button",
                    "/html/body/div[1]/div[2]/div[1]/div/nav/div[2]/div[3]/button",
                ],
                timeout_each=10,
            )
            sb.wait_for_ready_state_complete()
            sb.wait(5)

            # Click Collect
            collected = _try_click_any(
                sb,
                [
                    "/html/body/div[4]/div/div[1]/div/div/div[2]/div/div[2]/div[2]/div[1]/div/div[3]/button[1]",
                    "/html/body/div[4]/div/div[1]/div/div/div[2]/div/div[1]/div[2]/div[1]/div/div[3]/button[1]",
                ],
                timeout_each=8,
            )

            if not collected:
                # quick retry (modal often re-renders)
                sb.wait(5)
                collected = _try_click_any(
                    sb,
                    [
                        "/html/body/div[4]/div/div[1]/div/div/div[2]/div/div[2]/div[2]/div[1]/div/div[3]/button[1]",
                        "/html/body/div[4]/div/div[1]/div/div/div[2]/div/div[1]/div[2]/div[1]/div/div[3]/button[1]",
                    ],
                    timeout_each=5,
                )

            if collected:
                sb.wait(3)
                await _send_post_claim(sb, channel, "fc_uc_claimed.png", "Fortune Coins Daily Bonus Claimed!")
            else:
                print("Fortune Coins: no claim available (likely already collected).")

    except Exception as e:
        await channel.send(f"⚠️ Fortune Coins (UC) error")
