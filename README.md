# BitcoinTelegramBot
BitcoinTelegramBot is a announcer bot for the Bitcoin price into a Telegram channel

## Features

* Track Bitcoin price movement
* Announce the price in brackets e.g. every 100 USD 
* Announce the price in intervalls e.g. every 60 minutes
* Change settings via Telegram bot commands 

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

4. Run the application:
```sh
python3 BitcoinTelegramBot.py
```
