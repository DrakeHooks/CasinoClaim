# Fortune Coins API (SeleniumBase UC)
# Exposes: async def fortunecoins_uc(ctx, channel)

import os
import asyncio
from dotenv import load_dotenv
from seleniumbase import SB
import discord

load_dotenv()

FC_EMAIL = os.getenv("FORTUNECOINSEMAIL", "")
FC_PASSWORD = os.getenv("FORTUNECOINSPASSWORD", "")


async def _snap_and_send(sb, channel: discord.abc.Messageable, path: str, caption: str = ""):
    """Consistent screenshot -> send -> cleanup."""
    try:
        sb.save_screenshot(path)
        if os.path.exists(path):
            await channel.send(caption, file=discord.File(path))
        else:
            await channel.send(caption)
    finally:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


def _force_click_xpath(sb: SB, xpath: str, timeout: float = 12) -> bool:
    """
    Robust click for stubborn elements:
    1) wait visible
    2) scroll into view
    3) regular click
    4) slow_click
    5) js_click
    6) direct JS on element
    Returns True if any strategy works.
    """
    try:
        sb.wait_for_element_visible(xpath, timeout=timeout)
    except Exception:
        return False

    try:
        sb.scroll_to(xpath)
    except Exception:
        pass

    # Try a few strategies
    for attempt in ("click", "slow", "js", "directjs"):
        try:
            if attempt == "click":
                sb.click_xpath(xpath, timeout=2)
            elif attempt == "slow":
                sb.slow_click(xpath)
            elif attempt == "js":
                sb.js_click(xpath)
            else:
                # direct JS on the element node (more forceful than js_click on selector)
                el = sb.find_element(xpath)
                sb.execute_script("arguments[0].click();", el)
            return True
        except Exception:
            continue
    return False


def _try_click_any_xpath(sb: SB, xpaths, timeout_each=8, snap_tag: str = "") -> bool:
    """Try a list of XPaths with the robust click routine."""
    for xp in xpaths:
        if _force_click_xpath(sb, xp, timeout=timeout_each):
            return True
    # Optional: small diagnostic highlight
    try:
        if xpaths:
            sb.highlight(xpaths[0], loops=1)
    except Exception:
        pass
    return False


async def fortunecoins_uc(ctx, channel: discord.abc.Messageable):
    """
    Fortune Coins via SeleniumBase (uc=True). Uses FORTUNECOINSEMAIL / FORTUNECOINSPASSWORD.
    Sends screenshots & messages back to the Discord channel.
    """
    await channel.send("🧪 Running **Fortune Coins (UC mode)**…")

    if not FC_EMAIL or not FC_PASSWORD:
        await channel.send("❌ Missing `FORTUNECOINSEMAIL` or `FORTUNECOINSPASSWORD` in your .env.")
        return

    try:
        with SB(uc=True, headed=True) as sb:
            # Make sure document is ready between actions
            sb.uc_open_with_reconnect("https://fortunecoins.com/login", 4)
            sb.wait_for_ready_state_complete()
            await _snap_and_send(sb, channel, "fc_uc_login.png", "🔐 Fortune Coins login page")

            # Credentials (and optional captcha)
            sb.type("input[id='emailAddress']", FC_EMAIL)
            sb.type("input[id='password']", FC_PASSWORD)
            try:
                sb.uc_gui_click_captcha()
            except Exception:
                pass

            # Submit login
            _force_click_xpath(sb, "/html/body/div[1]/div[5]/div/div/div/div[2]/form/div[4]/button", timeout=12)
            sb.wait(6)
            sb.refresh_page()
            sb.wait_for_ready_state_complete()
            await _snap_and_send(sb, channel, "fc_uc_after_login.png", "✅ Logged in (UC)")

            # --- Step 5: Close popups/overlays if present (several variants) ---
            closed_popup = _try_click_any_xpath(
                sb,
                xpaths=[
                    "/html/body/div[5]/div/div[1]/div/div/button",
                    "/html/body/div[4]/div/div[1]/div/div/div[3]/div/button[2]",
                    "/html/body/div[4]/div/div[1]/div/div/button",
                ],
                timeout_each=6,
            )
            if closed_popup:
                sb.wait(1)

            # Extra nudge: press ESC to dismiss any stray overlays
            try:
                sb.press_keys("body", "ESCAPE")
            except Exception:
                pass

            # --- Step 6: Open Rewards / Get Coins (header variants) ---
            opened_rewards = _try_click_any_xpath(
                sb,
                xpaths=[
                    "/html/body/div[1]/div[2]/div[1]/div/nav/div[2]/div[3]/button",
                    "/html/body/div[1]/div[2]/div/nav/div[2]/div[3]/button",
                    "/html/body/div[1]/div[2]/div[1]/div/nav/div[2]/div[3]/button",
                ],
                timeout_each=10,
            )
            sb.wait_for_ready_state_complete()
            sb.wait(2)
            await _snap_and_send(sb, channel, "fc_uc_rewards.png",
                                 "🎁 Rewards/Get Coins view (after open attempt)")

            # --- Step 7: Click “Collect” (various modal layouts) ---
            collected = _try_click_any_xpath(
                sb,
                xpaths=[
                    "/html/body/div[4]/div/div[1]/div/div/div[2]/div/div[2]/div[2]/div[1]/div/div[3]/button[1]",
                    "/html/body/div[4]/div/div[1]/div/div/div[2]/div/div[1]/div[2]/div[1]/div/div[3]/button[1]",
                ],
                timeout_each=8,
            )

            if collected:
                sb.wait(3)
                await channel.send("Fortune Coins Daily Bonus Claimed!")
                await _snap_and_send(sb, channel, "fc_uc_claimed.png", "📸 Post-claim")
            else:
                # One more pass: sometimes the modal re-renders; try again quickly
                sb.wait(2)
                collected_retry = _try_click_any_xpath(
                    sb,
                    xpaths=[
                        "/html/body/div[4]/div/div[1]/div/div/div[2]/div/div[2]/div[2]/div[1]/div/div[3]/button[1]",
                        "/html/body/div[4]/div/div[1]/div/div/div[2]/div/div[1]/div[2]/div[1]/div/div[3]/button[1]",
                    ],
                    timeout_each=4,
                )
                if collected_retry:
                    sb.wait(2)
                    await channel.send("Fortune Coins Daily Bonus Claimed!")
                    await _snap_and_send(sb, channel, "fc_uc_claimed.png", "📸 Post-claim")
                else:
                    await channel.send("ℹ️ Claim button not clickable (maybe already claimed).")
                    await _snap_and_send(sb, channel, "fc_uc_no_claim.png", "📸 Claim not available")

    except Exception as e:
        # Best-effort context if something blew up before we could screenshot
        try:
            with SB(uc=True, headed=True) as sb:
                await _snap_and_send(sb, channel, "fc_uc_error.png", "⚠️ Fortune Coins (UC) error")
        except Exception:
            pass
        await channel.send(f"⚠️ Fortune Coins (UC) error: {e}")
