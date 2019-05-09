######################
## BTC TELEGRAM BOT ##
######################
from time import sleep
import configparser
import requests
import bitmex
import urllib3
from datetime import datetime
import json

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
def get_messages(offset_func):
    offset_url = "https://api.telegram.org/bot" + str(bot_token) + "/getUpdates?offset=" + offset_func
    bot_messages = requests.get(offset_url)
    return bot_messages.json()

## Send message to a chat
def send_message(chat, message_func):
    requests.get("https://api.telegram.org/bot" + str(bot_token) + "/sendMessage?chat_id=" + str(chat) + "&text=" + str(message_func))

####################
## Bitmex methods ##
####################

## Get open position
def get_bitmex_position(bitmex_client_func, askedValue):
    try:
        ## Get data from Bitmex - filtered for XBT positions
        result = bitmex_client_func.Position.Position_get(filter=json.dumps({'symbol': 'XBTUSD'})).result()
        ## Parse first position found
        result_json = result[0][0]
        ## Unrealised PNL
        unrealisedPnl = result_json["unrealisedPnl"] / 100000000
        unrealisedPnl = round(unrealisedPnl, 6)
        ## Rebalanced PNL
        rebalancedPnl = result_json["rebalancedPnl"] / 10000000
        rebalancedPnl = round(rebalancedPnl, 6)
        ## Break even price
        breakEvenPrice = int(result_json["breakEvenPrice"])
        ## Last price
        lastPrice = int(result_json["lastPrice"])
        ## Calculate the difference to break even
        diff_break_even = abs(breakEvenPrice - lastPrice)
        ## Position size
        currentQty = result_json["currentQty"]

        ## Long or Short
        long_short = "No Position!"
        if currentQty > 0:
            long_short = "Long"
        if currentQty < 0:
            long_short = "Short"

        ## Return the open position and stats
        if askedValue == "openPosition":
            openPosition = long_short + " position: " + str(currentQty) + " | Open PNL: " + str(unrealisedPnl) + "\nFull PNL: " + str(rebalancedPnl) + " | Break even: " + str(breakEvenPrice) + " (" + str(diff_break_even) + ")"
            return openPosition
        ## Return the position size
        if askedValue == "currentQty":
            return currentQty
        ## return the unrealisedPnl
        if askedValue == "unrealisedPnl":
            return unrealisedPnl
    except IndexError or AttributeError:
        return "No open position!"

#############
## Configs ##
#############

## Import the configs from file
config = configparser.RawConfigParser()
config.read("./config.cfg")

## Get general configs
bot_token = config.get("General", "bot_token")

## Get user configs
userlist_import = config.get("General", "userlist")
userlist = userlist_import.split(',')

## Put every user in a 2-dim list
user_position = 0
for user in userlist:

    user_chat_id = user
    history_length = int(config.get(user, "history_length"))
    divider = int(config.get(user, "divider"))
    interval_check = config.getboolean(user, "interval_check")
    bitmex_active = config.getboolean(user, "bitmex_active")
    bitmex_key = config.get(user, "bitmex_api_key")
    bitmex_secret = config.get(user, "bitmex_secret")
    announced_price = int(config.get(user, "announced_price"))
    history = []
    ask_price_steps = False
    ask_bitmex_key = False
    ask_bitmex_secret = False
    bitmex_client = False
    bitmex_position_amount = 0
    if bitmex_active:
        bitmex_client = bitmex.bitmex(test=False, api_key=bitmex_key, api_secret=bitmex_secret)
        bitmex_position_amount = get_bitmex_position(bitmex_client, "currentQty")
    settings = [user_position, user_chat_id, history_length, divider, interval_check, bitmex_active, bitmex_key, bitmex_secret, history, announced_price, bitmex_client, bitmex_position_amount, ask_price_steps, ask_bitmex_key, ask_bitmex_secret]
    userlist[user_position] = settings
    user_position = user_position + 1

###################
## Bot variables ##
###################

offset = "-0"
messages = []
write_config = False
bot_restarted = True
previous_price = 0
interval_count = 0
devmode = False

##################
## Pre-warm Bot ##
##################

## Set the price level and fill the history for every user
for user in userlist:
    ## Last user announced price / user divider
    price_level = int(user[9]/user[3])
    ## Fill history as long as the user wants
    while len(user[8]) < user[2]:
        user[8].append(price_level)

## Send out restart message if not in dev mode
if bot_restarted and not devmode:
    message = "The Bot restarted"
    print(message)
    ## Send message to the admin user (first user)
    print("Reported to Admin: " + str(userlist[0][1]))
    send_message(userlist[0][1], message)

###############
## Main loop ##
###############

while True:
    ## Print the Time to the console
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    ## Get new price from api
    new_price = get_latest_bitcoin_price("usd")

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

    ## Check every user if an announcement is needed
    for user in userlist:

        ## Get user info in readable variables
        price_level = user[8][-1]
        divider = user[3]
        history = user[8]
        bitmex_active = user[5]
        interval_check = user[4]
        announced_price = user[9]

        ## Check if the user has an open Bitmex position
        bitmex_open_position = "None!"
        if bitmex_active:
            if user[10]:
                bitmex_open_position = get_bitmex_position(user[10], "openPosition")

        ## Get new price level for the user
        new_price_level = int(new_price / divider)
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
                    ## Update the users announced_price
                    user[9] = new_price
                    config.set(str(user[1]), "announced_price", new_price)
                    write_config = True

                    ## Announce open position if Bitmex is active
                    if bitmex_active:
                        message = bitmex_open_position
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

                    ## Announce open position if Bitmex is active
                    if bitmex_active:
                        message = bitmex_open_position
                        print(message)
                        messages.append(message)

        ##################
        ## Make history ##
        ##################

        history.append(new_price_level)
        del history[0]
        # print("Price level history: " + str(history))

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
                    message = bitmex_open_position
                    print(message)
                    messages.append(message)
            interval_count = 0
        interval_count = interval_count + 1

        #############################
        ## Bitmex position tracker ##
        #############################

        if bitmex_active:
            if user[10]:
                ## Get position size
                bitmex_position_amount_new = int(get_bitmex_position(user[10], "currentQty"))
                bitmex_position_amount = int(user[11])

                ## Calculate the difference
                bitmex_position_amount_change = abs(bitmex_position_amount_new - bitmex_position_amount)

                ## Increased and reduced is based on long or short

                ## If position is a long
                if bitmex_position_amount_new > 0:
                    ## Announce if position was reduced
                    if bitmex_position_amount_new < bitmex_position_amount:
                        message = "Reduced long position by " + str(bitmex_position_amount_change)
                        print(message)
                        messages.append(message)
                        ## Announce new position and PNL
                        message = bitmex_open_position
                        print(message)
                        messages.append(message)
                    ## Announce if position was increased
                    elif bitmex_position_amount_new > bitmex_position_amount:
                        message = "Increased long position by " + str(bitmex_position_amount_change)
                        print(message)
                        messages.append(message)
                        ## Announce new position and PNL
                        message = bitmex_open_position
                        print(message)
                        messages.append(message)

                ## Position is a short
                else:
                    ## Announce if position was reduced
                    if bitmex_position_amount_new > bitmex_position_amount:
                        message = "Reduced short position by " + str(bitmex_position_amount_change)
                        print(message)
                        messages.append(message)
                        ## Announce new position and PNL
                        message = bitmex_open_position
                        print(message)
                        messages.append(message)
                    ## Announce if position was increased
                    elif bitmex_position_amount_new < bitmex_position_amount:
                        message = "Increased short position by " + str(bitmex_position_amount_change)
                        print(message)
                        messages.append(message)
                        ## Announce new position and PNL
                        message = bitmex_open_position
                        print(message)
                        messages.append(message)
                ## Set new Bitmex position amount
                user[11] = bitmex_position_amount_new

                ## Suppress message if the bot restarted
                if bot_restarted:
                    messages = []

        ## Write config to file if necessary
        if write_config:
            with open('config.cfg', 'w') as configfile:
                config.write(configfile)
                configfile.close()

        ## If there are messages, sent them to the user
        if messages:
            print("Sending messages to the chat: " + str(user[1]))
            all_messages = ""
            for x in messages:
                all_messages = all_messages + "\n" + x
            send_message(user[1], all_messages)
            messages = []

    #####################
    ## Chat monitoring ##
    #####################

    ## Let the bot monitor for at least 65 Sec.
    ## To avoid api limitations
    mon_loop = 0
    while mon_loop < 13:
        ## Get updates from bot
        bot_messages_json = get_messages(offset)

        ## Check the amount of messages received
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
                        print("New Message: " + bot_messages_text_single)

                        ## Check who wrote the message
                        check_user = bot_messages_json["result"][message_counter]["message"]["from"]["id"]
                        print("From user: " + str(check_user))

                        ## Check if we know the user
                        counter = 0
                        find_user_index = "None"
                        for user in userlist:
                            if str(user[1]) == str(check_user):
                                find_user_index = userlist[counter][0]
                                break
                            counter = counter + 1

                        ## Introduce new user
                        if find_user_index == "None":
                            ## Message the user that he is new
                            message = "Hello there, you must be new!\n\nYou can type / or press the symbol on the right to get into my commands.\n\nThere are also Bitmex API related commands to set the API access:\n/set_bitmex_key\n/set_bitmex_secret\n\nBe sure to create a read-only API Key on Bitmex"
                            send_message(check_user, message)
                            ## Write the new user into the config file
                            userlist_write = config.get("General", "userlist") + "," + str(check_user)
                            config.set("General", 'userlist', userlist_write)
                            ## Write config to file
                            with open('config.cfg', 'w') as configfile:
                                config.write(configfile)
                                configfile.close()

                            ## Create new user section with basic settings
                            f = open("config.cfg", "a+")
                            f.write("[" + str(check_user) + "]\n")
                            f.write("history_length = 15\n")
                            f.write("divider = 25\n")
                            f.write("interval_check = False\n")
                            f.write("announced_price = 0\n")
                            f.write("bitmex_active = False\n")
                            f.write("bitmex_api_key = \n")
                            f.write("bitmex_secret = \n")
                            f.close()

                            ## Import the new config file
                            config = configparser.RawConfigParser()
                            config.read("./config.cfg")

                            ## Set the new user in running config
                            user_position = len(userlist)

                            ## Fill history as long as the user wants
                            history = []
                            while len(history) < 15:
                                history.append(int(new_price / 25))

                            settings = [user_position, check_user, 15, 25, False, False, False, False, history, 0, False, 0, False, False, False]
                            userlist.append(settings)

                            ## Get our of this message
                            break

                        ## Get settings into readable variables
                        divider = userlist[find_user_index][3]
                        history_length = userlist[find_user_index][2]
                        bitmex_key = userlist[find_user_index][6]
                        bitmex_secret = userlist[find_user_index][7]
                        bitmex_active = userlist[find_user_index][5]
                        ask_price_steps = userlist[find_user_index][12]
                        ask_bitmex_key = userlist[find_user_index][13]
                        ask_bitmex_secret = userlist[find_user_index][14]

                        ## Update the message counter
                        message_counter = message_counter + 1

                        ##############
                        ## Commands ##
                        ##############

                        ## Check for commands
                        ## Split message by " " to be able to parse it easier
                        splitted = bot_messages_text_single.split(' ')

                        ## Tell the user his settings
                        if splitted[0] == "/show_settings":
                            ## Tell the user how big the price brackets are and when the price is considered stable
                            message = "Price steps are " + str(divider) + " and the price is stable after " + str(history_length) + " minutes"
                            print(message)
                            messages.append(message)

                        ## Tell the user his open bitmex position
                        if splitted[0] == "/show_position":
                            if bitmex_key and bitmex_secret:
                                bitmex_client = bitmex.bitmex(test=False, api_key=bitmex_key, api_secret=bitmex_secret)
                                message = get_bitmex_position(bitmex_client, "openPosition")
                                print(message)
                                messages.append(message)
                            else:
                                message = "You need to set your API Key and Secret:\n/set_bitmex_key\n/set_bitmex_secret"
                                print(message)
                                messages.append(message)

                        ## The user wants to change the price steps
                        if splitted[0] == "/set_price_steps":
                            if len(splitted) > 1:
                                try:
                                    ## Look for a valid value for the new price steps
                                    divider = int(splitted[1])
                                    config.set(str(check_user), 'divider', divider)
                                    write_config = True
                                    userlist[find_user_index][3] = divider
                                    message = "The price stepping is set to " + str(splitted[1] + " now.")
                                    print(message)
                                    messages.append(message)
                                    mon_loop = 50
                                except ValueError:
                                    ## The user did not give a valid value for the price steps so ask him
                                    ask_price_steps = True
                                    userlist[find_user_index][12] = True
                            else:
                                ## The user did not give a valid value for the price steps so ask him
                                ask_price_steps = True
                                userlist[find_user_index][12] = True
                        ## If the user got asked for his desired price steps, look for the answer
                        if ask_price_steps:
                            try:
                                ## Look for a valid value for the new price steps
                                divider = int(splitted[0])
                                config.set(str(check_user), 'divider', divider)
                                write_config = True
                                userlist[find_user_index][3] = divider
                                message = "The price stepping is set to " + str(splitted[0]) + " now."
                                print(message)
                                messages.append(message)
                                mon_loop = 50
                                ask_price_steps = False
                                userlist[find_user_index][12] = False
                            ## The user did not give a valid value for the price steps so ask him
                            except ValueError:
                                ask_price_steps = True
                                userlist[find_user_index][12] = True
                                message = "Tell me your desired price steps in USD as integer"
                                messages.append(message)
                                print(message)

                        ## Listen for Bitmex toggle command
                        if splitted[0] == "/toggle_bitmex":
                            ## Check if the API settings are there
                            if bitmex_key and bitmex_secret:
                                ## Deactivate Bitmex if it is enabled
                                if bitmex_active:
                                    bitmex_active = False
                                    userlist[find_user_index][5] = False
                                    config.set(str(check_user), "bitmex_active", "False")
                                    write_config = True
                                    message = "Bitmex disabled"
                                    messages.append(message)
                                ## Enable Bitmex if it is disabled
                                else:
                                    userlist[find_user_index][10] = bitmex.bitmex(test=False, api_key=bitmex_key, api_secret=bitmex_secret)
                                    bitmex_active = True
                                    userlist[find_user_index][5] = True
                                    config.set(str(check_user), "bitmex_active", "True")
                                    write_config = True
                                    message = "Bitmex enabled"
                                    messages.append(message)
                            else:
                                message = "You need to set your API key and Secret:\n/set_bitmex_key\n/set_bitmex_secret"
                                print(message)
                                messages.append(message)

                        ## The user wants to change his Bitmex API Key
                        if splitted[0] == "/set_bitmex_key":
                            if len(splitted) > 1:
                                ## Look for a valid value for the new price steps
                                ## Only clue we have it has to be 24 chars long
                                if len(splitted[1]) == 24:
                                    bitmex_key = str(splitted[1])
                                    config.set(str(check_user), 'bitmex_api_key', bitmex_key)
                                    write_config = True
                                    userlist[find_user_index][6] = bitmex_key
                                    message = "Okay, i saved your Bitmex key. Make sure to set also the secret\n/set_bitmex_secret.\n\nIf you set both you can use:\n/toggle_bitmex\n/show_position"
                                    print(message)
                                    messages.append(message)
                                    mon_loop = 50
                                else:
                                    ## The user did not give a valid value for the Bitmex key so ask him
                                    ask_bitmex_key = True
                                    userlist[find_user_index][13] = True
                            else:
                                ## The user did not give a valid value for the Bitmex key so ask him
                                ask_bitmex_key = True
                                userlist[find_user_index][13] = True
                        ## If the user got asked for the Bitmex key, look for the answer
                        if ask_bitmex_key:
                            ## Look for a valid value for the Bitmex key
                            ## Only clue we have it has to be 24 chars long
                            if len(splitted[0]) == 24:
                                bitmex_key = str(splitted[0])
                                config.set(str(check_user), 'bitmex_api_key', bitmex_key)
                                write_config = True
                                ask_bitmex_key = False
                                userlist[find_user_index][13] = False
                                userlist[find_user_index][6] = bitmex_key
                                message = "Okay, i saved your Bitmex key. Make sure you also set the secret\n/set_bitmex_secret.\n\nIf you set both you can use:\n/toggle_bitmex\n/show_position"
                                print(message)
                                messages.append(message)
                                mon_loop = 50
                            else:
                                ## The user did not give a valid value for the Bitmex key so ask him
                                ask_bitmex_key = True
                                userlist[find_user_index][13] = True
                                message = "Tell me your Bitmex API key. Be sure you created a read-only API Key on Bitmex."
                                messages.append(message)
                                print(message)

                        ## The user wants to change his Bitmex API secret
                        if splitted[0] == "/set_bitmex_secret":
                            if len(splitted) > 1:
                                ## Look for a valid value for the Bitmex API secret
                                ## Only clue we have it has to be 48 chars long
                                if len(splitted[1]) == 48:
                                    bitmex_key = str(splitted[1])
                                    config.set(str(check_user), 'bitmex_secret', bitmex_secret)
                                    write_config = True
                                    userlist[find_user_index][7] = bitmex_secret
                                    message = "Okay, i saved your Bitmex secret. Make sure to set also the key\n/set_bitmex_key.\n\nIf you set both you can use:\n/toggle_bitmex\n/show_position"
                                    print(message)
                                    messages.append(message)
                                    mon_loop = 50
                                else:
                                    ## The user did not give a valid value for the Bitmex secret so ask him
                                    ask_bitmex_secret = True
                                    userlist[find_user_index][14] = True
                            else:
                                ## The user did not give a valid value for the Bitmex secret so ask him
                                ask_bitmex_secret = True
                                userlist[find_user_index][14] = True
                        ## If the user got asked for the Bitmex secret, look for the answer
                        if ask_bitmex_secret:
                            ## Look for a valid value for the Bitmex secret
                            ## Only clue we have it has to be 48 chars long
                            if len(splitted[0]) == 48:
                                bitmex_secret = str(splitted[0])
                                config.set(str(check_user), 'bitmex_secret', bitmex_secret)
                                write_config = True
                                ask_bitmex_secret = False
                                userlist[find_user_index][14] = False
                                userlist[find_user_index][7] = bitmex_secret
                                message = "Okay, i saved your Bitmex secret. Make sure you also set the key\n/set_bitmex_key\n\nIf you set both you can use:\n/toggle_bitmex\n/show_position"
                                print(message)
                                messages.append(message)
                                mon_loop = 50
                            else:
                                ## The user did not give a valid value for the Bitmex key so ask him
                                ask_bitmex_secret = True
                                userlist[find_user_index][14] = True
                                message = "Tell me your Bitmex API secret. Be sure you created a read-only API key on Bitmex."
                                messages.append(message)
                                print(message)

                        ## Tell the user the real price
                        if splitted[0] == "/show_real_price":
                            message = "The BTC price is: " + str(new_price) + " USD"
                            print(message)
                            messages.append(message)

                        #####################
                        ## End of commands ##
                        #####################

                        ## Write config to file if necessary
                        if write_config:
                            with open('config.cfg', 'w') as configfile:
                                config.write(configfile)
                                configfile.close()

                        ## Send collected messages
                        if messages:
                            print("Sending collected messages to the chat: " + str(check_user))
                            all_messages = ""
                            for x in messages:
                                all_messages = all_messages + "\n" + x
                            send_message(check_user, all_messages)
                            messages = []

                    ## Discard all other messages
                    except KeyError:
                        print("Another type of message received")

            ## Set new offset to acknowledge messages on the telegram api
            offset = str(bot_messages_json["result"][message_amount - 1]["update_id"] + 1)

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
