# Casino Claim 🎰
Never miss a casino bonus again! A discord app for claiming social casino bonuses.

<p>
<img src="https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54"/>
<img src="https://img.shields.io/badge/-selenium-%43B02A?style=for-the-badge&logo=selenium&logoColor=white"/>
<img src="https://img.shields.io/badge/-discord.py-%232c2f33?style=for-the-badge&logo=discord&logoColor=white"/>
<img src="https://img.shields.io/badge/-docker-%232c2f33?style=for-the-badge&logo=docker&logoColor=white"/>
</p>

# About 🧾
Casino Claim is a selenium based python bot for claiming social casino bonuses. The bot will automatically claim your bonus, and provide a countdown for the next. If authentication is required, the bot will handle it. 

# DISCLAIMER ⚖️
I am not responsible for any financial loss or gain incurred with the use of this tool. I have no relationship with any business or website. This tool is for educational purposes only. 

# Acknowledgement 🏆
This program is heavily inspired by auto-rsa from Nelson Dane. Go check it out and give it a star here: https://github.com/NelsonDane/auto-rsa

# Installation 🛠️

1. Install `git` for your operating system. Then, install `docker` and `docker-compose` for your operating system. You can follow this guide to install docker and docker-compose: https://docs.docker.com/get-docker/ Note: If you are using Windows, I strongly recommend docker desktop for Windows.

2. Clone this repository and cd into it:
```bash
git clone https://github.com/DrakeHooks/CasinoClaim.git
cd CasinoClaim
```

1. Sign in to CrownCoins Casino, and Luckybird in a chrome browser. Then, take the "User Data" folder (usually located in "AppData/Local/Google/Chrome"), and place it in the "google-chrome" folder in the project.

2. Create a discord bot and invite it to your server. You can follow this guide to create a discord bot: [guide](discordBot.md)

3. Create the .env file in the root directory of the project by editing the .env.example file and add the following:
    1. Add `DISCORD_TOKEN` and `DISCORD_CHANNEL` to your `.env` file.
    2. Add your casino login credentials by editing the .env.example file. After editing, rename the file to .env and save. Note: some casino logins are currently only supported through the User Data directory.
4. run `docker compose up -d`







# Supported Casinos ✅
| Casino         | Auto Claim | Countdown Timer | Require User Data Directory | Notes            | Trusted? (payment proof) |
|----------------|------------|-----------------|-----------------------------|------------------|---------|
| Chanced        | ✓          | ✓               | No                          | Varies between $.3-$1 SC bonus/day    | Yes     |
| Global Poker   | ✓          | ✓               | No                          | $0.00-$2 SC bonus/day | Yes     |
| Rolling Riches | ✓          | ✓               | No                          | $.20 bonus every 6 hours | Yes     |
| Chumba         | ✓          | ✓               | No                          | $1 bonus/day     | Yes     |
| DingDingDing   | ✓          | ✓               | No                          | Varies between $0.50 SC and $1 SC | Yes     |
| Stake          | ✗          | ✓               | Yes                         | $1 bonus/day. Auto Claim in development | Yes     |
| Zula           | ✓          | ✓               | No                          | $1 bonus/day     | Yes     |
| Fortune Coins  | ✓          | ✗               | No                          | $0.50-$1.20 SC bonus every 24 hours | Yes     |
| Sportzino      | ✓          | ✓               | No                          | $1 bonus/day     | Yes     |
| Goldnluck      | ✗          | ✗               | No                          | $2 bonus/day     | No     |
| Luckybird      | ✓          | ✓               | No                          | $.25 bonus/day. Increases with VIP | Yes     |
| Crown Coins    | ✓          | ✓               | Yes                         | Varies between $0.00-$2 bonus/day. Requires Usr Data Dir for auth. Social Auth support in development | Yes     |
| Modo           | ✓          | ✓               | No                          | $.30-$1 SC bonus/day | Yes     |
| Pulsz          | IN DEVELOPMENT | IN DEVELOPMENT | IN DEVELOPMENT            | Varies between $.20-$3 SC bonus/day | Yes      |



# Support 🔮 
Browser automation breaks. It is just a matter of when. Casino Claim is the only free and open source social casino claim bot. If you would like to see this project grow, consider sponsoring or donating via ko-fi. I will do my best to push updates quickly for changes in website structure as well as overall efficiency of the bot. If you identify a fix, feel free to submit a pull request and I will review it.


# Problem Gambling 🎲
Gambling can become addicting, if you start feeling addicted, please get help before it affects your life negatively. Always remember, you are not alone!

<a href="https://www.ncpgambling.org/help-treatment/"><img src="https://www.ncpgambling.org/wp-content/themes/magneti/assets/build/images/800gamb-logo-header.svg"/></a>
