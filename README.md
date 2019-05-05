# BitcoinTelegramBot
BitcoinTelegramBot is a announcer bot for the Bitcoin price into a Telegram channel

## Features

* Track Bitcoin price movement
* Announce the price in brackets e.g. every 100 USD 
* Announce the price in intervalls e.g. every 60 minutes
* Change settings via Telegram bot commands 
* Track your open Bitmex position

## Installation

*This guide was written on a Debian system.*

1. Clone BitcoinTelegramBot repository and enter the project directory:

```sh
git clone https://github.com/BuGGuru/BitcoinTelegramBot.git
cd BitcoinTelegramBot
```

2. Create configuration file:

```sh
cp config.cfg.template config.cfg
```

3. Edit configuration file

## Get your bot token and chat_id

1. Talk to the BotFather in Telegram and create a new bot.
2. You will get your bot token in this conversation.
3. Write a message to your new bot
4. Open this website in a browser, make sure to change the token to your own token.
```sh
https://api.telegram.org/bot<token>/getUpdates
```
5. Somewhere in the middle of this message you will find your chat_id.
   "chat":{"id": XXXXXXXXXX

## Usage

The Bot will understand these commands via chat:
/set_price_steps - Set the price steps 
/show_settings - Show the active settings
/show_position - Show open Bitmex position

You can talk to the BotFather and set these commands for easier access.

