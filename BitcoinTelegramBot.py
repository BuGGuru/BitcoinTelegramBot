######################
## BTC TELEGRAM BOT ##
######################
from time import sleep
import configparser
import requests
import bitmex
import urllib3

## Disable warnings
urllib3.disable_warnings()

#############
## Configs ##
#############

## Import the configs from file
config = configparser.RawConfigParser()
config.read("./config.cfg")

## Get configs
bot_token = config.get("BOT", "token")
chat_id = config.get("CHAT", "chat_id")
history_length = int(config.get("BOT", "history_length"))
divider = int(config.get("BOT", "divider"))
interval_check = config.get("BOT", "interval_check")

## Convert String to bool for interval check
if interval_check == "True":
    interval_check = True
else:
    interval_check = False

#####################
## Price variables ##
#####################

previous_eur = 0
previous_usd = 0
interval_count = 0
announced_price = 0
history = []

###################
## Bot variables ##
###################

offset = "-0"
ask_price_steps = False
messages = []

######################
## Bitmex variables ##
######################

bitmex_key = config.get("BITMEX", "bitmex_api_key")
bitmex_secret = config.get("BITMEX", "bitmex_secret")

client = bitmex.bitmex(test=False, api_key=bitmex_key, api_secret=bitmex_secret)

####################
## Price methods  ##
####################

## Get the prices from the api
def get_latest_bitcoin_price(currency):
    if currency == "usd":
        response = requests.get("https://api.coindesk.com/v1/bpi/currentprice/USD.json", verify=False)
        response_json = response.json()
        return int(response_json["bpi"]["USD"]["rate_float"])
    else:
        response = requests.get("https://api.coindesk.com/v1/bpi/currentprice/EUR.json", verify=False)
        response_json = response.json()
        return int(response_json["bpi"]["EUR"]["rate_float"])

##################
## Bot methods  ##
##################

## Get updates from bot
def get_messages(offset):
    offset_url = "https://api.telegram.org/bot" + str(bot_token) + "/getUpdates?offset=" + offset
    bot_messages = requests.get(offset_url)
    return bot_messages.json()

## Send message to a chat
def send_message(chat, message):
    requests.get("https://api.telegram.org/bot" + str(bot_token) + "/sendMessage?chat_id=" + str(chat) + "&text=" + str(message))

####################
## Bitmex methods ##
####################

## Get open position
def get_bitmex_position():
    result = client.Position.Position_get().result()
    result_json = result[0][0]
    unrealisedPnl = result_json["unrealisedPnl"] / 100000000
    currentQty = result_json["currentQty"]
    openPosition = "Your Position of " + str(currentQty) + " has an PNL of " + str(unrealisedPnl)
    return openPosition

##################
## Pre-warm Bot ##
##################

## Set the price level and fill the history
price_level = int(get_latest_bitcoin_price("usd")/divider)
while len(history) < history_length:
    history.append(price_level)

## discard old messages
discard_messages = get_messages(offset)

## send out restart message
message = "The Bot restarted"
print(message)
send_message(chat_id, message)

###############
## Main loop ##
###############

while True:
    new_eur = get_latest_bitcoin_price("eur")
    new_usd = get_latest_bitcoin_price("usd")
    new_usd_level = int(new_usd / divider)
    new_eur_level = int(new_eur / divider)

    #############
    #### EUR ####
    #############

    if new_eur < previous_eur:
        change_eur = new_eur - previous_eur
        previous_eur = new_eur
        print("Price change: New price is", get_latest_bitcoin_price("eur"), "EUR and changed", change_eur, "EUR", "-- DOWN")
    elif new_eur > previous_eur:
        change_eur = new_eur - previous_eur
        previous_eur = new_eur
        print("Price change: New price is", get_latest_bitcoin_price("eur"), "EUR and changed", change_eur, "EUR", "-- UP")
    else:
        change_eur = 0

    #############
    #### USD ####
    #############

    if new_usd < previous_usd:
        change_usd = new_usd - previous_usd
        previous_usd = new_usd
        print("Price change: New price is", get_latest_bitcoin_price("usd"), "USD and changed", change_usd, "USD", "-- DOWN")
    elif new_usd > previous_usd:
        change_usd = new_usd - previous_usd
        previous_usd = new_usd
        print("Price change: New price is", get_latest_bitcoin_price("usd"), "USD and changed", change_usd, "USD", "-- UP" )
    else:
        change_usd = 0

    #############
    #### BOT ####
    #############
    ## Do nothing if no new price level
    if price_level != new_usd_level:
        ## Price has to move more then half the divider
        if (new_usd < (announced_price-(divider/4))) or (new_usd > (announced_price+(divider/4))):
            ## Check if new price level is in history
            if not new_usd_level in history:
                ## Check if price is higher or lower
                if announced_price > new_usd:
                    priceIs = "Lower"
                else:
                    priceIs = "Higher"

                ## Announce since price not in history
                message = priceIs + " price level: " + str(new_usd_level * divider) + " - " + str(new_usd_level * divider + divider)
                print(message)
                messages.append(message)
                price_level = new_usd_level
                announced_price = new_usd
                ## Announce open position
                message = get_bitmex_position()
                print(message)
                messages.append(message)

            ## Check if price is stable
            elif (sum(history)/len(history)) == new_usd_level:

                ## Check if price is higher or lower
                if announced_price > new_usd:
                    priceIs = "Lower"
                else:
                    priceIs = "Higher"

                ## Announce since price is stable
                message = priceIs + " price level: " + str(new_usd_level * divider) + " - " + str(new_usd_level * divider + divider)
                print(message)
                messages.append(message)
                price_level = new_usd_level
                announced_price = new_usd
                ## Announce open position
                message = get_bitmex_position()
                print(message)
                messages.append(message)

    ##################
    ## Make history ##
    ##################

    history.append(new_usd_level)
    del history[0]
    print("Price level history: " + str(history))

    #####################
    ## Interval check ##
    #####################

    if interval_count == 60:
        message = "Interval check - the price is " + str(new_usd) + " USD"
        print(message)
        if interval_check:
            messages.append(message)
            ## Announce open position
            message = get_bitmex_position()
            print(message)
            messages.append(message)
        interval_count = 0
    interval_count = interval_count + 1

    #####################
    ## Chat monitoring ##
    #####################

    ## Let the bot monitor for at least 60 Sec.
    mon_loop = 0
    while mon_loop < 12:
        ## Get updates from bot
        bot_messages_json = get_messages(offset)

        ### Check the amount of messages received
        try:
            message_amount = len(bot_messages_json["result"])
        except KeyError:
            message_amount = 0

        ## Check messages if exists
        if message_amount != 0:

            ## Go through all new messages
            message_counter = 0
            for i in bot_messages_json["result"]:
                ## Catch key error due to other updates than message
                try:
                    bot_messages_text_single = str(bot_messages_json["result"][message_counter]["message"]["text"])
                    message_counter = message_counter + 1
                    print("New Message: " + bot_messages_text_single)

                    ## Check for commands
                    splitted = bot_messages_text_single.split(' ')
                    if splitted[0] == "/show_settings":
                        message = "Price steps are " + str(divider) + " and the price is stable after " + str(history_length) + " minutes"
                        print(message)
                        messages.append(message)
                    if splitted[0] == "/show_position":
                        message = get_bitmex_position()
                        print(message)
                        messages.append(message)
                    if splitted[0] == "/set_price_steps":
                        if len(splitted) > 1:
                            try:
                                divider = int(splitted[1])
                                config.set('BOT', 'divider', divider)
                                message = "Set the price stepping to " + str(splitted[1])
                                print(message)
                                messages.append(message)
                                mon_loop = 50
                            except ValueError:
                                ask_price_steps = True
                        else:
                            ask_price_steps = True
                    if ask_price_steps:
                        try:
                            divider = int(splitted[0])
                            config.set('BOT', 'divider', divider)
                            message = "Set the price stepping to " + str(splitted[0])
                            print(message)
                            messages.append(message)
                            mon_loop = 50
                            ask_price_steps = False
                        except ValueError:
                            ask_price_steps = True
                            message = "Tell me your desired price steps in USD as integer"
                            messages.append(message)
                            print(message)
                except KeyError:
                    print("Maybe edited message received")

            ## Set new offset to acknowledge messages
            offset = str(bot_messages_json["result"][message_amount - 1]["update_id"] + 1)

        ## Write new configs to file
        with open('config.cfg', 'w') as configfile:
            config.write(configfile)

        ## Send collected messages
        if messages:
            print("Sending messages to the chat")
            all_messages = ""
            for x in messages:
                all_messages = all_messages + "\n" + x
            send_message(chat_id, all_messages)
            messages = []

        ## Loop things
        mon_loop = mon_loop + 1
        sleep(5)

        #####################
        ## End of mon loop ##
        #####################

    ######################
    ## End of main loop ##
    ######################
