# Drake Hooks
# Casino Claim
# Never Miss a Casino Bonus Again! A discord app for claiming social casino bonuses.

import os
from datetime import datetime, timedelta
import time
import re
import sqlite3
import discord
import asyncio
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import datetime
from dotenv import load_dotenv
import undetected_chromedriver as uc
from discord import Intents, Client, Message
from discord.ext import commands, tasks
import asyncio
from seleniumbase import Driver
from selenium.webdriver.common.action_chains import ActionChains

#import custom API functions


import importlib

# Dynamically import API modules
api_modules = [
    "stakeAPI",
    "modoAPI",
    "googleauthAPI",
    "chancedAPI",
    "rollingrichesAPI",
    "jefebetAPI",
    "spinpalsAPI",
    "nolimitcoinsAPI",
    "globalpokerAPI",
    "dingdingdingAPI",
    "chumbaAPI",
    "crowncoinsAPI",
    "zulaAPI",
    "luckybirdAPI",
    "sportzinoAPI",
]

for module_name in api_modules:
    try:
        module = importlib.import_module(module_name)
        globals().update(vars(module))
    except Exception as e:
        print(f"Warning: Failed to import {module_name}: {e}")


load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL = int(os.getenv("DISCORD_CHANNEL"))

intents = Intents.default()
intents.message_content = True

caps = DesiredCapabilities.CHROME
caps["goog:loggingPrefs"] = {"performance": "ALL"}

# Setup our environment and Chrome options
options = Options()
options.add_argument('--ignore-certificate-errors')
options.add_argument('--ignore-ssl-errors')
options.add_argument("disable-infobars")
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_argument('--no-sandbox')
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
options.add_argument(f"--user-agent={user_agent}")

#IMPORTANT. YOU MAY WANT TO IMPORT A CUSTOM USER DATA DIRECTORY FOR CAPTCHA SOLVING EXTENSIONS. UNCOMMENT THIS OUT HERE AND IN THE DOCKERFILE.

# user_data_dir = "/temp/google-chrome/" 
# Change path for Linux environment
# options.add_argument(f"--user-data-dir={user_data_dir}")


options.set_capability("goog:loggingPrefs", caps["goog:loggingPrefs"])
options.add_argument("--allow-geolocation")
options.add_argument("--disable-features=DisableLoadExtensionCommandLineSwitch")
options.add_extension('/temp/CAPTCHA-Solver-auto-hCAPTCHA-reCAPTCHA-freely-Chrome-Web-Store.crx')
options.add_argument('--disable-notifications')

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

bot = commands.Bot(command_prefix='!', intents=intents, case_insensitive=True)
bot.remove_command("help")

bot.luckybird_2fa_code = None  
bot.chumba_2fa_code = None    

# Dictionary to manage authentication status for different casinos
auth_status = {
    "dingdingding": False,
    "modo": False,
    "stake": False,
    "luckybird": False,
}


# Tasks
chanced_casino_task = None
luckybird_task = None
globalpoker_task = None
CrownCoinsCasino_task = None
chumba_task = None
dingdingding_task = None
stake_task = None
zula_task = None
rollingriches_task = None
jefebet_task = None
spinpals_task = None
nolimitcoins_task = None
sportzino_task = None



# Flags to check if corresponding background tasks are running
chanced_casino_running = False
luckybird_running = False
globalpoker_running = False
CrownCoinsCasino_running = False
chumba_running = False
dingdingding_running = False
stake_running = False
zula_running = False
rollingriches_running = False
jefebet_running = False
spinpals_running = False
nolimitcoins_running = False
funrize_running = False
sportzino_running = False


@bot.event
async def on_ready():
    print(f"Bot has connected as {bot.user}")

    channel = bot.get_channel(DISCORD_CHANNEL)
    if channel:
        await channel.send("Discord bot has started...")
    else:
        print("Invalid DISCORD_CHANNEL")

    
    # Start main tasks loop.
    await asyncio.sleep(60)
    if not chanced_casino_loop.is_running():
        chanced_casino_loop.start()
    if not new_chanced_session.is_running():
        new_chanced_session.start()
    if not casino_loop.is_running():
        casino_loop.start()
    await asyncio.sleep(260)




@bot.command(name="ping")
async def ping(ctx):
    print("ponged")
    await ctx.send("Pong")


@bot.command(name="captcha")
async def captcha(ctx):
    """Open the captcha solver extension page and send a screenshot."""
    await ctx.send("Opening captcha solver page...")
    try:
        driver.get("chrome://extensions")
        time.sleep(5)
        driver.get("chrome-extension://hlifkpholllijblknnmbfagnkjneagid/popup/popup.html#/")
        time.sleep(5)
        screenshot_path = "captcha_screenshot.png"
        driver.save_screenshot(screenshot_path)
        await ctx.send(file=discord.File(screenshot_path))
        os.remove(screenshot_path)
    except Exception as e:
        await ctx.send("Failed to capture captcha solver page.")
        print(f"Captcha command error: {e}")


@bot.command(name="help")
async def help(ctx):
    await ctx.send("""Commands are not recommended. 
    🎰 Casino Commands: 
    !chanced - Check Chanced.com for bonus
    !luckybird - Check LuckyBird.io for bonus
    !globalpoker - Check GlobalPoker for bonus
    !crowncoins - Check CrownCoinsCasino for bonus
    !chumba - Check Chumba for bonus
    !modo - Check Modo for bonus
    !sweepslots - Check SweepSlots for bonus
    !zula - Check Zula for bonus
    !rollingriches - Check RollingRiches for bonus
    !jefebet - Check JefeBet for bonus
    !spinpals - Check SpinPals for bonus
    !nolimitcoins - Check NoLimitCoins for bonus
    !sportzino - Check Sportzino for bonus
    !fortunecoins - Check Fortunecoins for bonus

    ---------------------------------------
    ⚙️ General Commands:                             
    !ping - Check if the bot is online
    !restart - Restart the bot     
    !help - Display the available commands
    !captcha - Open the captcha solver extension page            
    !stop - Stop the bot               

    ---------------------------------------
    ✅ Auth Commands:
    !googleauth - Authenticate Google Account
    !auth <site> - Authenticate into a specific site           
    (e.g. Modo, DingDingDing, Stake, LuckyBird)

    !auth <site> <method> - Authenticate using a specific method
    (e.g. !auth crowncoins google, !auth crowncoins env)                   
                                    
    """)


async def action_notification(ctx, message):
    # Send a notification message to the Discord channel
    await ctx.send(f"Notification: {message}")

# Invalid command error handling
@bot.event
async def on_command_error(ctx, error):
    print(f"Command Error: {error}")
    await ctx.send(f"Command Error: {error}")
    # Print help command
    print("Type '!help' for a list of commands")
    await ctx.send("Type '!help' for a list of commands")

# Restart command
@bot.command(name="restart")
async def restart(ctx):
    print("Restarting...")
    await ctx.send("Restarting...")
    await bot.close()
    os._exit(0)  # Special exit code to restart docker container


@bot.command(name="googleauth")
async def googleauth(ctx):
    await ctx.send("Authenticating Google Account...")
    # Load credentials from environment variables
    google_credentials = os.getenv("GOOGLE_LOGIN")

    if google_credentials:
        google_username, google_password = google_credentials.split(':')
        credentials = (google_username, google_password)
    else:
        await ctx.send("Google credentials not found in .env file.")
        credentials = (None, None)  

    channel = bot.get_channel(DISCORD_CHANNEL)
    await google_auth(ctx, driver, channel, credentials)


@bot.event
async def on_message(message):
    """Capture 2FA codes for LuckyBird and Chumba."""
    if message.channel.id == DISCORD_CHANNEL:
        content = message.content.strip()
        if len(content) == 6 and content.isdigit():
            if "luckybird" in message.content.lower():  # Check if it's for LuckyBird
                bot.luckybird_2fa_code = content
                print(f"LuckyBird 2FA code {bot.luckybird_2fa_code} received.")
            elif "chumba" in message.content.lower():  # Check if it's for Chumba
                bot.chumba_2fa_code = content
                print(f"Chumba 2FA code {bot.chumba_2fa_code} received.")

    await bot.process_commands(message)


@bot.command(name="chumba")
async def chumba(ctx):
    """Starts the Chumba automation process."""
    await ctx.send("Checking Chumba for Bonus...")

    # Step 1: Go to the Chumba lobby
    driver.get("https://lobby.chumbacasino.com/")
    await asyncio.sleep(5)

    # Step 2: If we are on the login page, authenticate
    if driver.current_url.startswith("https://login.chumbacasino.com/"):

        # Reset 2FA code before authentication
        bot.chumba_2fa_code = None

        # Call authentication process and pass the bot object to share the two_fa_code
        authenticated = await authenticate_chumba(driver, bot, ctx)

        if not authenticated:
            await ctx.send("Chumba authentication failed.")
            return

    # Step 3: Proceed with claiming the bonus if authenticated
    if driver.current_url.startswith("https://lobby.chumbacasino.com/"):
        await claim_chumba_bonus(driver, ctx)
        await check_chumba_countdown(driver, ctx)
    else:
        await ctx.send("Failed to reach the Chumba lobby.")



@bot.command(name="RollingRiches")
async def rollingriches(ctx):
    global rollingriches_task
    if not rollingriches_task or rollingriches_task.done():
        await ctx.send("Checking Rolling Riches for Bonus...")
        channel = bot.get_channel(DISCORD_CHANNEL)
        await rolling_riches_casino(ctx, driver, channel)
    else:
        await ctx.send("RollingRiches automation is already running.")

@bot.command(name="JefeBet")
async def jefebet(ctx):
    global jefebet_task
    if not jefebet_task or jefebet_task.done():
        await ctx.send("Checking JefeBet for Bonus...")
        channel = bot.get_channel(DISCORD_CHANNEL)
        await jefebet_casino(ctx, driver, channel)
    else:
        await ctx.send("JefeBet automation is already running.")

@bot.command(name="SpinPals")
async def spinpals(ctx):
    global spinpals_task
    if not spinpals_task or spinpals_task.done():
        await ctx.send("Checking SpinPals for Bonus...")
        channel = bot.get_channel(DISCORD_CHANNEL)
        await spinpals_flow(ctx, driver, channel)
    else:
        await ctx.send("SpinPals automation is already running.")

@bot.command(name="NoLimitCoins")
async def nolimitcoins(ctx):
    global nolimitcoins_task
    if not nolimitcoins_task or nolimitcoins_task.done():
        await ctx.send("Checking NoLimitCoins for Bonus...")
        channel = bot.get_channel(DISCORD_CHANNEL)
        await nolimitcoins_flow(ctx, driver, channel)
    else:
        await ctx.send("NoLimitCoins automation is already running.")

@bot.command(name="Stake")
async def stake(ctx):
    global stake_task
    if not stake_task or stake_task.done():
        await ctx.send("Checking Stake for Bonus...")
        channel = bot.get_channel(DISCORD_CHANNEL)
        await stake_claim(driver, bot, ctx, channel)
    else:
        await ctx.send("Stake automation is already running.")


@bot.command(name="chanced")
async def chanced(ctx):
    await ctx.send("Checking Chanced.com for Bonus...")
    # Load credentials from environment variables
    chanced_credentials = os.getenv("CHANCED")

    if chanced_credentials:
        # Split the credentials into username and password using the ':' delimiter
        chanced_username, chanced_password = chanced_credentials.split(':')
        credentials = (chanced_username, chanced_password)
    else:
        credentials = (None, None)  # No credentials, will proceed with user data dir

    channel = bot.get_channel(DISCORD_CHANNEL)
    await chanced_casino(ctx, driver, channel, credentials)


@bot.command(name="luckybird")
async def luckybird(ctx):
    await ctx.send("Checking Luckybird for bonus...")
    channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL")))
    bonus_claimed = await luckyBird_claim(driver, bot, ctx, channel)

    # If claiming the bonus failed, always check the countdown
    if not bonus_claimed:
        print("Failed to claim LuckyBird bonus. Checking countdown timer...")
        await extract_countdown_info(driver, bot, ctx, channel)

# Command to run the Global Poker bonus checker
@bot.command(name="globalpoker")
async def global_poker_command(ctx):
    global globalpoker_running
    if not globalpoker_running:
        await ctx.send("Checking GlobalPoker for Bonus...")
        globalpoker_running = True

        # Get the channel and driver from the context
        channel = bot.get_channel(DISCORD_CHANNEL)
        # driver = ctx.driver  # Assuming driver is passed in the context

        # Call the main GlobalPoker function
        await global_poker(ctx, driver, channel)

        globalpoker_running = False
    else:
        await ctx.send("GlobalPoker automation is already running.")

@bot.command(name="CrownCoins")
async def crowncoinscasino(ctx):
    global CrownCoinsCasino_task
    if not CrownCoinsCasino_task or CrownCoinsCasino_task.done():
        await ctx.send("Checking Crown Coins Casino for Bonus...")
        channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL")))
        CrownCoinsCasino_task = asyncio.create_task(crowncoins_casino(driver, bot, ctx, channel))
    else:
        await ctx.send("CrownCoinsCasino automation is already running.")

@bot.command(name="dingdingding")
async def DingDingDing(ctx):
    await ctx.send("Checking DingDingDing for bonus...")
    channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL")))
    bonus_claimed = await claim_dingdingding_bonus(driver, bot, ctx, channel)

    # If claiming the bonus failed, always check the countdown
    if not bonus_claimed:
        print("Failed to claim DingDingDing bonus. Checking countdown timer...")
        await check_dingdingding_countdown(driver, bot, ctx, channel)

@bot.command(name="modo")
async def modo(ctx):
    await ctx.send("Checking Modo for bonus...")
    channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL")))

    # Attempt to claim the bonus
    bonus_claimed = await claim_modo_bonus(driver, bot, ctx, channel)

    # Check countdown if claiming fails
    if not bonus_claimed:
        print("Failed to claim Modo bonus. Checking countdown timer...")
        await check_modo_countdown(driver, bot, ctx, channel)

     

@bot.command(name="auth")
async def authenticate_command(ctx, site: str, method: str = None):
    channel = bot.get_channel(DISCORD_CHANNEL)

    # CrownCoins Authentication
    if site.lower() == "crowncoins":
        if method is None:
            await ctx.send("Please specify the authentication method: `google` or `env`.")
            return

        if method.lower() == "google":
            await ctx.send("Authenticating CrownCoins using Google...")
            auth_status["crowncoins_google"] = await auth_crown_google(driver, bot, ctx, channel)
            if auth_status["crowncoins_google"]:
                print("CrownCoins authentication via Google succeeded.")
            else:
                screenshot_path = "crowncoins_google_auth_failed.png"
                driver.save_screenshot(screenshot_path)
                await ctx.send("",
                               file=discord.File(screenshot_path))
                os.remove(screenshot_path)

        elif method.lower() == "env":
            await ctx.send("Authenticating CrownCoins using .env credentials...")
            auth_status["crowncoins_env"] = await auth_crown_env(driver, bot, ctx, channel)
            if auth_status["crowncoins_env"]:
                print("CrownCoins authentication via .env credentials succeeded.")
            else:
                screenshot_path = "crowncoins_env_auth_failed.png"
                driver.save_screenshot(screenshot_path)
                await ctx.send("",
                               file=discord.File(screenshot_path))
                os.remove(screenshot_path)

        else:
            await ctx.send("Invalid authentication method. Use `google` or `env`.")
    
    # Other Sites
    elif site.lower() == "dingdingding":
        await ctx.send("Authenticating DingDingDing...")
        auth_status["dingdingding"] = await authenticate_dingdingding(driver, bot, ctx, channel)
        if auth_status["dingdingding"]:
            print("DingDingDing authentication succeeded.")
        else:
            screenshot_path = "dingdingding_auth_failed.png"
            driver.save_screenshot(screenshot_path)
            await ctx.send("Authentication failed. Unable to proceed.",
                           file=discord.File(screenshot_path))
            os.remove(screenshot_path)

    elif site.lower() == "modo":
        await ctx.send("Authenticating Modo...")
        auth_status["modo"] = await authenticate_modo(driver, bot, ctx, channel)
        if auth_status["modo"]:
            print("Modo authentication succeeded.")
        else:
            screenshot_path = "modo_auth_failed.png"
            driver.save_screenshot(screenshot_path)
            await ctx.send("Modo authentication failed. Unable to proceed.",
                           file=discord.File(screenshot_path))
            os.remove(screenshot_path)

    elif site.lower() == "stake":
        await ctx.send("Authenticating Stake...")
        auth_status["stake"] = await stake_auth(driver, bot, ctx, channel)
        if auth_status["stake"]:
            print("Stake authentication succeeded.")
        else:
            screenshot_path = "stake_auth_failed.png"
            driver.save_screenshot(screenshot_path)
            await ctx.send("Stake authentication failed. Unable to proceed.",
                           file=discord.File(screenshot_path))
            os.remove(screenshot_path)

    elif site.lower() == "luckybird":
        await ctx.send("Authenticating LuckyBird...")
        auth_status["luckybird"] = await authenticate_luckybird(driver, bot, ctx, channel)
        if auth_status["luckybird"]:
            print("LuckyBird authentication succeeded.")
        else:
            screenshot_path = "luckybird_auth_failed.png"
            driver.save_screenshot(screenshot_path)
            await ctx.send("LuckyBird authentication failed. Unable to proceed.",
                           file=discord.File(screenshot_path))
            os.remove(screenshot_path)

    else:
        await ctx.send(f"Authentication for '{site}' is not implemented.")



     


@bot.command(name="Zula")
async def zula(ctx):
    global zula_task
    if not zula_task or zula_task.done():
        await ctx.send("Checking Zula Casino for Bonus...")
        zula_task = asyncio.create_task(zula_casino(driver, bot, ctx))
    else:
        await ctx.send("ZulaCasino automation is already running.")


@bot.command(name="Sportzino")
async def sportzino(ctx):
    global sportzino_task
    if not sportzino_task or sportzino_task.done():
        channel = bot.get_channel(DISCORD_CHANNEL)
        await ctx.send("Checking Sportzino for Bonus...")
        sportzino_task = asyncio.create_task(Sportzino(ctx, driver, channel))
    else:
        await ctx.send("Sportzino automation is already running.")


@tasks.loop(hours=12)
async def new_chanced_session():
    print("Starting new_chanced_session...")
    channel = bot.get_channel(DISCORD_CHANNEL)
    # Load credentials from environment variables
    chanced_credentials = os.getenv("CHANCED")
    
    if chanced_credentials:
        chanced_username, chanced_password = chanced_credentials.split(':')
        credentials = (chanced_username, chanced_password)
    else:
        credentials = (None, None)
    
    if credentials[0] and credentials[1]:
        await channel.send(f"Creating a new Chanced session with credentials.")
    else:
        await channel.send(f"Unable to create new chanced.com session. Are the credentials set?")
    
    try:
        await logout_and_login(None, driver, channel, credentials)
    except Exception as e:
        await channel.send(f"Error during session refresh: {str(e)}")

@tasks.loop(minutes=62)
async def chanced_casino_loop():
    print("Starting chanced_casino_loop...")

    # Get the channel object
    channel = bot.get_channel(DISCORD_CHANNEL)

    # Check if the channel is valid
    if channel is None:
        print(f"Error: Invalid channel ID '{DISCORD_CHANNEL}' or bot is not connected.")
        return  # Exit the task loop early if the channel is invalid

    try:
        # Run the chanced casino task
        await chanced_casino(None, driver, channel, None)
    except Exception as e:
        print(f"Error in loop: {str(e)}")
        await channel.send(f"Error in Chanced Casino loop: {str(e)}")



# @tasks.loop(hours=24)
# async def dingdingding_auth_task():
#     channel = bot.get_channel(DISCORD_CHANNEL)
#     await channel.send("Running scheduled DingDingDing authentication...")
#     auth_status["dingdingding"] = await authenticate_dingdingding(driver, bot, None, channel)
#     if auth_status["dingdingding"]:
#         await channel.send("DingDingDing authentication succeeded during the scheduled task.")
#     else:
#         await channel.send("DingDingDing authentication failed during the scheduled task.")


@tasks.loop(hours=2, )
async def casino_loop():
    print("Starting casino_loop...")

    channel = bot.get_channel(DISCORD_CHANNEL)
    if channel is None:
        print(f"Error: Invalid channel ID '{DISCORD_CHANNEL}' or bot is not connected.")
        return  # Exit the task loop early if the channel is invalid


    try:
        # Run the casino tasks sequentially with 2-hour gaps
        try:
            await asyncio.sleep(40)
            await zula_casino(None, driver, channel)
        except:
            print("Error in Zula")
            await asyncio.sleep(50)
        await asyncio.sleep(80)
        try:
            await Sportzino(None, driver, channel)
            await asyncio.sleep(50)
        except:
            print("Error in Sportzino")
            await asyncio.sleep(50)
        await asyncio.sleep(80)
        try:
            await crowncoins_casino(driver, bot, None, channel)
        except:
            print("Error in CrownCoinsCasino")
        await asyncio.sleep(30)
        try:
            bonus_claimed = await claim_modo_bonus(driver, bot, None, channel)
            if not bonus_claimed:
                print("Failed to claim Modo bonus. Checking countdown timer...")
                await check_modo_countdown(driver, bot, None, channel)
        except:
            print("Error in Modo")
        await asyncio.sleep(100)
        # try:
        #     bonus_claimed = await claim_dingdingding_bonus(driver, bot, None, channel)
        #     if not bonus_claimed:
        #         print("Failed to claim DingDingDing bonus. Checking countdown timer...")
        #         await check_dingdingding_countdown(driver, bot, None, channel)
        # except:
        #     print("Error in DingDingDing")
        # await asyncio.sleep(100)

        await asyncio.sleep(10)
        try:
            await global_poker(None, driver, channel)
            await asyncio.sleep(10)
        except:
            print("Error in GlobalPoker")
        await asyncio.sleep(10)
        try:
            bonus_claimed = await luckyBird_claim(driver, bot, None, channel)
            if not bonus_claimed:
                print("Failed to claim LuckyBird bonus. Checking countdown timer...")
                await extract_countdown_info(driver, bot, None, channel)
        except:
            print("Error in LuckyBird")
        await asyncio.sleep(10)
        try:
            await rolling_riches_casino(None, driver, channel)
        except:
            print("Error in RollingRiches")
        await asyncio.sleep(10)
        try:
            await jefebet_casino(None, driver, channel)
        except:
            print("Error in JefeBet")
        await asyncio.sleep(10)
        try:
            await spinpals_flow(None, driver, channel)
        except:
            print("Error in SpinPals")
        await asyncio.sleep(10)
        try:
            await nolimitcoins_flow(None, driver, channel)
        except:
            print("Error in NoLimitCoins")
        await asyncio.sleep(10)
        try:
            await chumba_casino(None, driver, bot)
        except:
            print("Error in Chumba")
        await asyncio.sleep(10)
        try:
            await stake_claim(driver, bot, None, channel)
        except:
            print("Error in Stake")


    except Exception as e:
        print(f"Error in loop: {str(e)}")


bot.run(DISCORD_TOKEN)