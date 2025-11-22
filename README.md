# Casino Claim 🎰
Never miss a casino bonus again! A discord app for claiming social casino bonuses.

<p>
<img src="https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54"/>
<img src="https://img.shields.io/badge/-selenium-%43B02A?style=for-the-badge&logo=selenium&logoColor=white"/>
<img src="https://img.shields.io/badge/-opencv-%235C3EE8?style=for-the-badge&logo=opencv&logoColor=white"/>
<img src="https://img.shields.io/badge/-pyautogui-%23FF6F00?style=for-the-badge&logo=python&logoColor=white"/>
<img src="https://img.shields.io/badge/-seleniumbase-%23323330?style=for-the-badge&logo=selenium&logoColor=white"/>
<img src="https://img.shields.io/badge/-requests-%232c2f33?style=for-the-badge&logo=&logoColor=white"/>
<img src="https://img.shields.io/badge/-discord.py-%232c2f33?style=for-the-badge&logo=discord&logoColor=white"/>
<img src="https://img.shields.io/badge/-docker-%232c2f33?style=for-the-badge&logo=docker&logoColor=white"/>

</p>

# About 
Casino Claim is a discord bot for claiming social casino bonuses. The bot will automatically claim your bonus, provide a countdown for the next, and authenticate if needed.

# DISCLAIMER 
I am not responsible for any financial loss or gain incurred with the use of this tool. I have no relationship with any business or website. This tool is for educational purposes only and is provided as is with no warranty.

# Having an Issue? 
For direct support, feature/casino requests, and community access, please sponsor me below and I will help you on Discord (exclusive to Sponsors and Contributors only).

[![Sponsor](https://img.shields.io/badge/sponsor-30363D?style=for-the-badge&logo=GitHub-Sponsors&logoColor=white)](https://github.com/sponsors/DrakeHooks)
[![ko-fi](https://img.shields.io/badge/Ko--fi-F16061?style=for-the-badge&logo=ko-fi&logoColor=white)](https://ko-fi.com/drakehooks)

# Acknowledgement 
This program is heavily inspired by auto-rsa from Nelson Dane. Go check it out and give it a star here: https://github.com/NelsonDane/auto-rsa


# Installation 
1. Install `git` for your operating system. Then, install `docker` and `docker-compose` for your operating system. You can follow this guide to install docker and docker-compose: https://docs.docker.com/get-docker/ Note: If you are using Windows, I strongly recommend docker desktop for Windows.

2. Clone this repository and cd into it:
```bash
git clone https://github.com/DrakeHooks/CasinoClaim.git
cd CasinoClaim
```
3. Create a discord bot and invite it to your server. You can follow this guide to create a discord bot: [guide](discordBot.md)

4. Create the .env file in the root directory of the project by editing the .env.example file and add the following:
    1. Add `DISCORD_TOKEN` and `DISCORD_CHANNEL` to your `.env` file.
    2. Add your casino login credentials by editing the .env.example file. After editing, rename the file to .env and save. 
5. run `docker compose up -d`
6. The Bot should now appear in Discord and start the 24 hour loop.


# Usage 🎰🤖
The bot is designed to check most casinos automatically in 2-hour intervals, with commands to check status of bonus. Some casinos only check once every 24 hours, but this can be changed with `!config` command.`!start` and `!stop` will start and stop the main loop. Running `!help` at any time provides the available commands. `!cleardatadir` command is useful for sites giving location issues, as well as sites you need to re-authenticate with.
 


# Supported Casinos ✅
| Casino          | Auto Claim | Countdown Timer | Backend API | Bonus (SC)            | Trusted? (payment proof) |
|-----------------|------------|-----------------|-----------------------------|------------------|---------|
| LuckyBird       | ✓          | ✓              | No                          | $0.25 Daily - Increases with VIP | Yes     |
| Global Poker    | ✓          | ✓              | No                          | $0.00-$4.00 Daily                | Yes     |
| JefeBet         | ✓          | ✓              | No                          | $0.20 every 6 hours              | Yes     |
| SpinQuest       | ✓          | ✓              | No                          | $1.00 Daily                      | Yes     |
| FortuneWheelz   | ✓          | ✗              | No                          | $0.20 Average Daily              | Yes     |
| NoLimitCoins    | ✗          | ✗              | No                          | $0.20 Average Daily              | Yes     |
| Modo            | ✗          | ✗              | No                          | $0.30-$1.00 Daily                | Yes     |
| Stake           | ✗          | ✗              | Yes                         | $1.00 Daily                      | Yes     |
| Funrize         | ✓          | ✗              | No                          | $0.20 Average Daily              | Yes     |
| Rolling Riches  | ✓          | ✗              | No                          | $0.20 Daily                      | Yes     |
| American Luck   | ✓          | ✗              | No                          | $0.60 Average Daily              | Yes     |
| Fortune Coins   | ✓          | ✗              | No                          | $0.46 Average Daily              | Yes     |
| Zula            | ✓          | ✓              | No                          | $1.00 Daily                      | Yes     |
| Sportzino       | ✓          | ✓              | No                          | $0.76 Average Daily              | Yes     |
| Smiles Casino   | ✗          | ✗              | No                          | $0.07 Average Daily              | Yes     |
| Yay Casino      | ✓          | ✗              | No                          | $0.50 Average Daily              | Yes     |
| RealPrize       | IN DEVELOPMENT | ✗          | No                          | $0.30 Daily                      | Yes     |
| LoneStar Casino | IN DEVELOPMENT | ✗          | No                          | $0.30 Daily                      | Yes     |
| Luckyland Slots | IN DEVELOPMENT | ✗          | No                          | $0.30-$1.00  Daily               | Yes     |
| Crown Coins     | IN DEVELOPMENT | ✓          | Yes                         | $0.00-$2.00 Varies Daily         | Yes     |
| Goldnluck       | IN DEVELOPMENT | ✓          | No                          | $2.00 Daily                      | No      |
| Chumba          | IN DEVELOPMENT | ✗          | No                          | $0.25-$3.00 Daily                | Yes     |
| Chanced         | IN DEVELOPMENT | ✗          | No                          | $0.30-$1.00 Varies Daily         | Yes     |
| iCasino         | IN DEVELOPMENT | ✗          | No                          | $1.70 Daily                      | Yes     |
| Spin Pals       | IN DEVELOPMENT | ✓          | No                          | $1.00  Daily                     | Yes     |
| Dara Casino     | IN DEVELOPMENT | ✗          | No                          | $1.00  Daily                     | Yes     |
| Pulsz           | IN DEVELOPMENT | ✗          | No                          | $0.20-$3.00 Varies Daily         | Yes     |


# Support 🔮 
Casino Claim is the only free and open source social casino claim bot.  
If you get value from this project and want to see it grow, consider sponsoring or donating via Ko-fi.  
A free way to support the project is by using these [**referrals**](https://drakehooks.github.io/referrals/).  

I will do my best to push updates quickly for changes in website structure as well as overall efficiency of the bot.  
If you identify a fix, feel free to submit a pull request and I will review it.


# Stars

  <a href="https://star-history.com/#DrakeHooks/CasinoClaim&Date">
    <img src="https://api.star-history.com/svg?repos=DrakeHooks/CasinoClaim&type=Date&theme=dark" alt="Star History Chart">
  </a>


# Problem Gambling 🎲
Gambling can become addictive. If you start feeling addicted, please seek help before it affects your life negatively. Always remember—you are not alone!

<a href="https://www.ncpgambling.org/help-treatment/"><img src="https://www.ncpgambling.org/wp-content/themes/magneti/assets/build/images/800gamb-logo-header.svg"/></a>
