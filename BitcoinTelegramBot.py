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

####################
## Price methods  ##
####################

## Get the prices from an api
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
def get_bitmex_position(askedValue):
    result = bitmex_client.Position.Position_get().result()
    try:
        result_json = result[0][0]
        unrealisedPnl = result_json["unrealisedPnl"] / 100000000
        currentQty = result_json["currentQty"]
        if askedValue == "openPosition":
            openPosition = "Your Position of " + str(currentQty) + " has a PNL of " + str(unrealisedPnl)
            return openPosition
        if askedValue == "currentQty":
            return currentQty
        if askedValue == "unrealisedPnl":
            return unrealisedPnl
    except IndexError:
        return "No open position!"

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
interval_check = config.getboolean("BOT", "interval_check")

#####################
## Price variables ##
#####################

previous_eur = 0
previous_price = 0
interval_count = 0
announced_price = 0
history = []

###################
## Bot variables ##
###################

offset = "-0"
ask_price_steps = False
messages = []
write_config = False
bot_restarted = True

######################
## Bitmex variables ##
######################

## Import configs from file
bitmex_active = config.getboolean("BITMEX", "bitmex_active")
bitmex_key = config.get("BITMEX", "bitmex_api_key")
bitmex_secret = config.get("BITMEX", "bitmex_secret")

## Initiate Bitmex api
bitmex_client = bitmex.bitmex(test=False, api_key=bitmex_key, api_secret=bitmex_secret)

## Look if the user has an open position
bitmex_position_amount = get_bitmex_position("currentQty")

##################
## Pre-warm Bot ##
##################

## Set the price level and fill the history
price_level = int(get_latest_bitcoin_price("usd")/divider)
while len(history) < history_length:
    history.append(price_level)

## Send out restart message
if bot_restarted:
    message = "The Bot restarted"
    print(message)
    send_message(chat_id, message)

###############
## Main loop ##
###############

while True:
    ## Get new price from api
    new_price = get_latest_bitcoin_price("usd")
    new_price_level = int(new_price / divider)

    ## Print price changes to console
    if new_price < previous_price:
        price_change_amount = new_price - previous_price
        previous_price = new_price
        print("Price change: New price is", get_latest_bitcoin_price("usd"), "USD and changed", price_change_amount, "USD", "-- DOWN")
    elif new_price > previous_price:
        price_change_amount = new_price - previous_price
        previous_price = new_price
        print("Price change: New price is", get_latest_bitcoin_price("usd"), "USD and changed", price_change_amount, "USD", "-- UP")
    else:
        price_change_amount = 0

    #############
    #### BOT ####
    #############
    ## Do nothing if no new price level
    if price_level != new_price_level:
        ## Price has to move more then 25% of the divider to avoid spam
        if (new_price < (announced_price - (divider / 4))) or (new_price > (announced_price + (divider / 4))):
            ## Check if new price level is not in history
            if new_price_level not in history:
                ## Check if price is higher or lower
                if announced_price > new_price:
                    priceIs = "Lower"
                else:
                    priceIs = "Higher"

                ## Announce since price not in history
                message = priceIs + " price level: " + str(new_price_level * divider) + " - " + str(new_price_level * divider + divider)
                print(message)
                messages.append(message)
                price_level = new_price_level
                announced_price = new_price

                ## Announce open position if Bitmex is active
                if bitmex_active:
                    message = get_bitmex_position("openPosition")
                    print(message)
                    messages.append(message)

            ## Check if price is stable
            elif (sum(history)/len(history)) == new_price_level:

                ## Check if price is higher or lower
                if announced_price > new_price:
                    priceIs = "Lower"
                else:
                    priceIs = "Higher"

                ## Announce since price is stable
                message = priceIs + " price level: " + str(new_price_level * divider) + " - " + str(new_price_level * divider + divider)
                print(message)
                messages.append(message)
                price_level = new_price_level
                announced_price = new_price

                ## Announce open position if Bitmex is active
                if bitmex_active:
                    message = get_bitmex_position("openPosition")
                    print(message)
                    messages.append(message)

    ##################
    ## Make history ##
    ##################

    history.append(new_price_level)
    del history[0]
    print("Price level history: " + str(history))

    #####################
    ## Interval check ##
    #####################

    if interval_count == 60:
        message = "Interval check - the price is " + str(new_price) + " USD"
        print(message)
        # Announce interval check if active
        if interval_check:
            messages.append(message)
            ## Announce open position if Bitmex is active
            if bitmex_active:
                message = get_bitmex_position("openPosition")
                print(message)
                messages.append(message)
        interval_count = 0
    interval_count = interval_count + 1

    #############################
    ## Bitmex position tracker ##
    #############################

    if bitmex_active:
        ## Get position size
        bitmex_position_amount_new = get_bitmex_position("currentQty")
        ## Calculate the difference
        bitmex_position_amount_change = abs(bitmex_position_amount_new - bitmex_position_amount)
        ## Announce if position was reduced
        if bitmex_position_amount_new < bitmex_position_amount:
            message = "Reduced Bitmex position by " + str(bitmex_position_amount_change)
            print(message)
            messages.append(message)
            ## Announce new position and PNL
            message = get_bitmex_position("openPosition")
            print(message)
            messages.append(message)
        ## Announce if position was increased
        elif bitmex_position_amount_new > bitmex_position_amount:
            message = "Increased Bitmex position by " + str(bitmex_position_amount_change)
            print(message)
            messages.append(message)
            ## Announce new position and PNL
            message = get_bitmex_position("openPosition")
            print(message)
            messages.append(message)
        ## Set new Bitmex position amount
        bitmex_position_amount = bitmex_position_amount_new
        ## Suppress message if the bot restarted
        if bot_restarted:
            messages = []

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

            ## Suppress old actions if bot restarted
            if bot_restarted:
                bot_restarted = False
            else:
                ## Go through all new messages
                message_counter = 0
                for i in bot_messages_json["result"]:
                    ## Catch key error due to other updates than message
                    try:
                        bot_messages_text_single = str(bot_messages_json["result"][message_counter]["message"]["text"])
                        message_counter = message_counter + 1
                        print("New Message: " + bot_messages_text_single)

                        ## Check for commands
                        ## Split message by " " - space - to be able to parse it easier
                        splitted = bot_messages_text_single.split(' ')

                        ## Tells the user his settings
                        if splitted[0] == "/show_settings":
                            ## Tell the user how big the price brackets are and when the price is considered stable
                            message = "Price steps are " + str(divider) + " and the price is stable after " + str(history_length) + " minutes"
                            print(message)
                            messages.append(message)

                        ## Tell the user his open bitmex position
                        if splitted[0] == "/show_position":
                            bitmex_client = bitmex.bitmex(test=False, api_key=bitmex_key, api_secret=bitmex_secret)
                            message = get_bitmex_position("openPosition")
                            print(message)
                            messages.append(message)

                        ## The user wants to change the price steps
                        if splitted[0] == "/set_price_steps":
                            if len(splitted) > 1:
                                try:
                                    ## Look for a valid value for the new price steps
                                    divider = int(splitted[1])
                                    config.set('BOT', 'divider', divider)
                                    write_config = True
                                    message = "The price stepping is set to " + str(splitted[1])
                                    print(message)
                                    messages.append(message)
                                    mon_loop = 50
                                except ValueError:
                                    ## The user did not give a valid value for the price steps so ask him
                                    ask_price_steps = True
                            else:
                                ## The user did not give a valid value for the price steps so ask him
                                ask_price_steps = True
                        ## If the user got asked for his desired price steps, look for the answer
                        if ask_price_steps:
                            try:
                                ## Look for a valid value for the new price steps
                                divider = int(splitted[0])
                                config.set('BOT', 'divider', divider)
                                write_config = True
                                message = "The price stepping is set to " + str(splitted[0])
                                print(message)
                                messages.append(message)
                                mon_loop = 50
                                ask_price_steps = False
                            ## The user did not give a valid value for the price steps so ask him
                            except ValueError:
                                ask_price_steps = True
                                message = "Tell me your desired price steps in USD as integer"
                                messages.append(message)
                                print(message)

                        ## Listen for Bitmex toggle command
                        if splitted[0] == "/toggle_bitmex":
                            ## Deactivate Bitmex if it is enabled
                            if bitmex_active:
                                bitmex_active = False
                                config.set("BITMEX", "bitmex_active", "False")
                                write_config = True
                                message = "Bitmex disabled"
                                messages.append(message)
                            ## Enable Bitmex if it is disabled
                            else:
                                bitmex_active = True
                                config.set("BITMEX", "bitmex_active", "True")
                                write_config = True
                                bitmex_client = bitmex.bitmex(test=False, api_key=bitmex_key, api_secret=bitmex_secret)
                                message = "Bitmex enabled"
                                messages.append(message)
                    except KeyError:
                        print("Another type of message received")

            ## Set new offset to acknowledge messages on the telegram api
            offset = str(bot_messages_json["result"][message_amount - 1]["update_id"] + 1)

        ## Write config to file if necessary
        if write_config:
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
        bot_restarted = False
        sleep(5)

        #####################
        ## End of mon loop ##
        #####################

    ######################
    ## End of main loop ##
    ######################
