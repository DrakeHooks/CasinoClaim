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
    """Consistent screenshot -> send -> cleanup, matches your existing style."""
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

def _try_click_any_xpath(sb: SB, xpaths, timeout=4):
    """Try clicking the first available XPath from a list."""
    for xp in xpaths:
        try:
            sb.click_xpath(xp, timeout=timeout)
            return True
        except Exception:
            continue
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
        # Self-contained SB session; headed=True helps with visual debugging
        with SB(uc=True, headed=True) as sb:
            # 1) Login page
            sb.uc_open_with_reconnect("https://fortunecoins.com/login", 4)
            sb.wait(2)
            await _snap_and_send(sb, channel, "fc_uc_login.png", "🔐 Fortune Coins login page")

            # 2) Credentials + (optional) captcha
            sb.type("input[id='emailAddress']", FC_EMAIL)
            sb.type("input[id='password']", FC_PASSWORD)
            try:
                sb.uc_gui_click_captcha()
            except Exception:
                # Captcha might not show every time
                pass

            # 3) Submit login
            sb.click_xpath("/html/body/div[1]/div[5]/div/div/div/div[2]/form/div[4]/button")
            sb.wait(6)

            # 4) Land in lobby, refresh to stabilize
            sb.refresh_page()
            sb.wait(5)
            await _snap_and_send(sb, channel, "fc_uc_after_login.png", "✅ Logged in (UC)")

            # 5) Close popups if present (multiple variants)
            _try_click_any_xpath(
                sb,
                xpaths=[
                    "/html/body/div[5]/div/div[1]/div/div/button",
                    "/html/body/div[4]/div/div[1]/div/div/div[3]/div/button[2]",
                    "/html/body/div[4]/div/div[1]/div/div/button",
                ],
                timeout=2,
            )

            # 6) Open Rewards / Get Coins (header variants)
            _try_click_any_xpath(
                sb,
                xpaths=[
                    "/html/body/div[1]/div[2]/div/nav/div[2]/div[3]/button",
                    "/html/body/div[1]/div[2]/div[1]/div/nav/div[2]/div[3]/button",
                ],
                timeout=6,
            )
            sb.wait(3)
            await _snap_and_send(sb, channel, "fc_uc_rewards.png", "🎁 Rewards modal opened")

            # 7) Click “Collect” (try known layouts)
            clicked = _try_click_any_xpath(
                sb,
                xpaths=[
                    "/html/body/div[4]/div/div[1]/div/div/div[2]/div/div[2]/div[2]/div[1]/div/div[3]/button[1]",
                    "/html/body/div[4]/div/div[1]/div/div/div[2]/div/div[1]/div[2]/div[1]/div/div[3]/button[1]",
                ],
                timeout=5,
            )

            if clicked:
                sb.wait(3)
                await channel.send("🎉 **Fortune Coins Daily Bonus Claimed!**")
                await _snap_and_send(sb, channel, "fc_uc_claimed.png", "📸 Post-claim")
            else:
                await channel.send("ℹ️ Claim button not clickable (maybe already claimed).")
                await _snap_and_send(sb, channel, "fc_uc_no_claim.png", "📸 Claim not available")

    except Exception as e:
        # On failure, try to show context with a screenshot; fall back to text if needed
        try:
            with SB(uc=True, headed=True) as sb:
                await _snap_and_send(sb, channel, "fc_uc_error.png", f"⚠️ Fortune Coins (UC) error: `{e}`")
        except Exception:
            await channel.send(f"⚠️ Fortune Coins (UC) error: `{e}`")
