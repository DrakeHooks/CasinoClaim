# Drake Hooks
# Casino Claim
# Never Miss a Casino Bonus Again! A discord app for claiming social casino bonuses.

import os
import datetime
import time
import re
import asyncio
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from dotenv import load_dotenv
import discord
import undetected_chromedriver as uc
from discord import Intents, Client, Message
from discord.ext import commands, tasks
from seleniumbase import Driver
from selenium.webdriver.common.action_chains import ActionChains

#import custom API functions
from chancedAPI import *
from rollingrichesAPI import *
from globalpokerAPI import *
from dingdingdingAPI import *
from chumbaAPI import *
from crowncoinsAPI import *
from zulaAPI import *
from luckybirdAPI import *

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL = int(os.getenv("DISCORD_CHANNEL"))

intents = Intents.default()
intents.message_content = True

# Setup Chrome options
options = Options()
options.add_experimental_option("detach", True)
options.add_argument('--ignore-certificate-errors')
options.add_argument('--ignore-ssl-errors')
options.add_argument("disable-infobars")
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_argument('--no-sandbox')
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
# user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
options.add_argument(f"--user-agent={user_agent}")
user_data_dir = "/temp/google-chrome/"  # Change path for Linux environment
options.add_argument(f"--user-data-dir={user_data_dir}")
options.add_extension('/temp/CAPTCHA-Solver-auto-hCAPTCHA-reCAPTCHA-freely-Chrome-Web-Store.crx')
extension = "/root/.config/google-chrome/Default/Extensions"

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

bot = commands.Bot(command_prefix='!', intents=intents, case_insensitive=True)
bot.remove_command("help")
bot.two_fa_code = None  # Variable to store the 2FA code

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
sportzino_task = None
fortunecoins_task = None

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

    if not casino_loop.is_running():
        casino_loop.start()
    if not chanced_casino_loop.is_running():
        chanced_casino_loop.start()
    

@bot.command(name="ping")
async def ping(ctx):
    print("ponged")
    await ctx.send("Pong")


@bot.command(name="help")
async def help(ctx):
    await ctx.send("""Commands are not recommended. Available commands: 
    !chanced - Check Chanced.com for bonus
    !luckybird - Check LuckyBird.io for bonus
    !globalpoker - Check GlobalPoker for bonus
    !crowncoins - Check CrownCoinsCasino for bonus
    !chumba - Check Chumba for bonus
    !dingdingding - Check DingDingDing for bonus
    !stake - Check Stake for bonus
    !modo - Check Modo for bonus
    !sweepslots - Check SweepSlots for bonus
    !moonspin - Check MoonSpin for bonus
    !zula - Check Zula for bonus
    !rollingriches - Check RollingRiches for bonus
    !sportzino - Check Sportzino for bonus
    !fortunecoins - Check Fortunecoins for bonus
    !ping - Check if the bot is online
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


@bot.event
async def on_message(message):
    """Capture the 2FA code from the channel messages."""
    if message.channel.id == DISCORD_CHANNEL:
        content = message.content.strip()
        if len(content) == 6 and content.isdigit():
            bot.two_fa_code = content  # Store 2FA code in the variable
            print(f"2FA code {bot.two_fa_code} received.")

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
        bot.two_fa_code = None

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
    global luckybird_task
    if not luckybird_task or luckybird_task.done():
        await ctx.send("Checking LuckyBird for Bonus...")
        luckybird_task = asyncio.create_task(LuckyBird(ctx, driver, bot))
    else:
        await ctx.send("LuckyBird automation is already running.")

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
        CrownCoinsCasino_task = asyncio.create_task(crowncoins_casino(driver, bot, ctx))
    else:
        await ctx.send("CrownCoinsCasino automation is already running.")

@bot.command(name="dingdingding")
async def DingDingDing(ctx):
    global authenticated
    await ctx.send("Checking DingDingDing for bonus...")
    channel = bot.get_channel(DISCORD_CHANNEL)
    
    # Check if already authenticated
    if not authenticated:
        await ctx.send("Authenticating DingDingDing first...")
        authenticated = await authenticate_dingdingding(driver, channel)

    # Proceed if authentication was successful
    if authenticated:
        # Navigate to the lobby
        driver.get("https://www.dingdingding.com/lobby")

        # Attempt to claim the daily bonus (but proceed to check countdown regardless)
        await claim_dingdingding_bonus(driver, channel)

        # Always check for the countdown, even if the bonus claim was unsuccessful
        await check_dingdingding_countdown(driver, channel)
    else:
        await ctx.send("Authentication failed. Unable to proceed.")

     
@bot.command(name="Zula")
async def zula(ctx):
    global zula_task
    if not zula_task or zula_task.done():
        await ctx.send("Checking Zula Casino for Bonus...")
        zula_task = asyncio.create_task(zula_casino(driver, bot, ctx))
    else:
        await ctx.send("ZulaCasino automation is already running.")






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
            await crowncoins_casino(None, driver, channel)
        except:
            print("Error in CrownCoinsCasino")
        await asyncio.sleep(10)
        try:
            await dingdingding_casino(channel, driver, bot)  # Pass channel and bot directly
        except:
            print("Error in DingDingDing")
        await asyncio.sleep(10)
        try:
            await rolling_riches_casino(None, driver, channel)
        except:
            print("Error in RollingRiches")
        await asyncio.sleep(10)
        try:
            await global_poker(None, driver, channel)
        except:
            print("Error in GlobalPoker")
        await asyncio.sleep(10)
        try:
            await LuckyBird(None, driver, bot)
        except:
            print("Error in LuckyBird")
        try:
            await chumba_casino(None, driver, bot)
        except:
            print("Error in Chumba")
        await asyncio.sleep(10)


    except Exception as e:
        print(f"Error in loop: {str(e)}")


bot.run(DISCORD_TOKEN)
