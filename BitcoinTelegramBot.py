######################
## BTC TELEGRAM BOT ##
######################
from time import sleep
import configparser
import requests


#############
## Configs ##
#############

config = configparser.RawConfigParser()
config.read('config.cfg')

## Bot
bot_token = config.get('BOT', 'token')

## Chats
chat_id = config.get('CHAT', 'chat_id')

## Basics
history_length = 5
divider = 25

#####################
## Price variables ##
#####################
previous_eur = 0
previous_usd = 0
price_level = 0
interval_check = 0
announced_price = 0
history = []

###################
## Bot variables ##
###################

offset = ""

####################
## Price methods  ##
####################

## Get the prices from the api
def get_latest_bitcoin_price(currency):
    if currency == "usd":
        response = requests.get("https://api.coindesk.com/v1/bpi/currentprice/USD.json")
        response_json = response.json()
        return int(response_json["bpi"]["USD"]["rate_float"])
    else:
        response = requests.get("https://api.coindesk.com/v1/bpi/currentprice/EUR.json")
        response_json = response.json()
        return int(response_json["bpi"]["EUR"]["rate_float"])

##################
## Bot methods  ##
##################

## Send message to a chat
def send_message(chat, message):
    requests.get("https://api.telegram.org/bot" + str(bot_token) + "/sendMessage?chat_id=" + str(chat) + "&text=" + str(message))

##################
## Pre-warm Bot ##
##################

## Set the price level an fill the history
price_level = int(get_latest_bitcoin_price("usd")/divider)
while len(history) < history_length:
    history.append(price_level)

## discard old messages
##########
## todo ##
##########

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
        print("Price change: New price is",get_latest_bitcoin_price("eur"),"EUR and changed", change_eur, "EUR", "-- DOWN")
    elif new_eur > previous_eur:
        change_eur = new_eur - previous_eur
        previous_eur = new_eur
        print("Price change: New price is",get_latest_bitcoin_price("eur"),"EUR and changed", change_eur, "EUR", "-- UP")
    else:
        change_eur = 0

    #############
    #### USD ####
    #############

    if new_usd < previous_usd:
        change_usd = new_usd - previous_usd
        previous_usd = new_usd
        print("Price change: New price is",get_latest_bitcoin_price("usd"),"USD and changed", change_usd, "USD", "-- DOWN")
    elif new_usd > previous_usd:
        change_usd = new_usd - previous_usd
        previous_usd = new_usd
        print("Price change: New price is",get_latest_bitcoin_price("usd"), "USD and changed", change_usd, "USD", "-- UP" )
    else:
        change_usd = 0

    #############
    #### BOT ####
    #############
    ## Do nothing if no new price level
    if price_level != new_usd_level:
        ## Price has to move more then half the divider
        if (new_usd < (announced_price-(divider/2))) or (new_usd > (announced_price+(divider/2))):
            ## Check if new price level is in history
            if not new_usd_level in history:
                ## Check if price is higher or lower
                if price_level > new_usd_level:
                    priceIs = "lower"
                else:
                    priceIs = "higher"

                ## Announce since price not in history
                message = "New price level - " + str(new_usd_level*divider) + " - price is now " + priceIs + " at " + str(new_usd) + " USD"
                print(message)
                send_message(chat_id, message)
                price_level = new_usd_level
                announced_price = new_usd

            ## Check if price is stable
            elif (sum(history)/len(history)) == new_usd_level:

                ## Check if price is higher or lower
                if price_level > new_usd_level:
                    priceIs = "lower"
                else:
                    priceIs = "higher"

                ## Announce since price is stable
                message = "New price level - " + str(new_usd_level*divider) + " - stable price is now " + priceIs + " at " + str(new_usd) + " USD"
                print(message)
                send_message(chat_id, message)
                price_level = new_usd_level
                announced_price = new_usd

    ##################
    ## Make history ##
    ##################

    history.append(new_usd_level)
    del history[0]
    print("Price level history: " + str(history))

    #####################
    ## Interval check ##
    #####################

    interval_check = interval_check + 1
    if interval_check == 60:
        message = "Interval check - the price is " + str(new_usd) + " USD"
        print(message)
        #send_message(myself, message)
        interval_check = 0

    #####################
    ## Chat monitoring ##
    #####################

    ## Let the bot monitor for at least 60 Sec.
    mon_loop = 0
    while mon_loop < 6:
        ## Get updates from bot
        offset_url = "https://api.telegram.org/bot" + str(bot_token) + "/getUpdates?offset=" + offset
        bot_messages = requests.get(offset_url)
        bot_messages_json = bot_messages.json()

        ### Check the amount of messages received
        message_amount = len(bot_messages_json["result"])

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
                    splitted = bot_messages_text_single.split(';')
                    if splitted[0] == "show settings":
                        message = "Price steps are " + str(divider) + " and the price is stable after " + str(history_length) + " minutes"
                        print(message)
                        send_message(chat_id, message)
                    if splitted[0] == "set settings":
                        try:
                            divider = int(splitted[1])
                            message = "Set the price stepping to " + str(splitted[1])
                            print(message)
                            mon_loop = 50
                        except ValueError:
                            message = "Invalid value for price stepping - has to be integer"
                            print(message)
                        send_message(chat_id, message)
                except KeyError:
                    print("Maybe edited message received")

            ## Acknowledge messages
            offset = str(bot_messages_json["result"][message_amount - 1]["update_id"] + 1)

        mon_loop = mon_loop + 1
        sleep(10)
        #####################
        ## End of mon loop ##
        #####################
    ######################
    ## End of main loop ##
    ######################
