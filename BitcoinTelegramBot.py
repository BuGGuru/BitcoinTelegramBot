######################
## BTC TELEGRAM BOT ##
######################
import time
from time import sleep
import configparser
import requests
import bitmex
import urllib3
from datetime import datetime
import json
import threading
from deribit_api import RestClient
import os

## Disable warnings
urllib3.disable_warnings()

####################
## Price methods  ##
####################

## Get the prices from an api
def get_latest_bitcoin_price(source):
    global price_bitmex
    global price_deribit
    while True:
        ## Price source Bitmex
        if source == "bitmex":
            try:
                response = requests.get("https://www.bitmex.com/api/v1/trade?symbol=XBT&count=1&reverse=true", verify=False)
                response_json = response.json()
                price_bitmex = int(response_json[0]["price"])
                if devmode:
                    print(bitmex_rate_limit)
                sleep(3)
            except:
                price_bitmex = None
                if devmode:
                    print("Bitmex went shit")
                sleep(3)

        ## Price source Deribit
        if source == "deribit":
            try:
                price_deribit_api = deribit_client_price.getlasttrades("BTC-PERPETUAL", 1)
                price_deribit = int(price_deribit_api[0]["price"])
                sleep(3)
            except:
                price_deribit = None
                if devmode:
                    print("Deribit went shit")
                sleep(3)

#######################
## Telegram methods  ##
#######################

## Get updates from bot
def get_messages(offset_func):
    try:
        offset_url = "https://api.telegram.org/bot" + str(bot_token) + "/getUpdates?offset=" + offset_func
        bot_messages = requests.get(offset_url)
        return bot_messages.json()
    except:
        log("Error: Telegram API failed!")
        return False

## Send message to a chat
def send_message(chat, message_func):
    try:
        requests.get("https://api.telegram.org/bot" + str(bot_token) + "/sendMessage?chat_id=" + str(chat) + "&text=" + str(message_func))
        return True
    except:
        log("Error: Could not set message!")
        return False

######################
## Exchange methods ##
######################

## Get user Bitmex client running
def get_bitmex_client(testnet, key, secret):
    # noinspection PyBroadException
    try:
        bitmex_client_func = bitmex.bitmex(test=testnet, api_key=key, api_secret=secret)
        ## Use this to validate the bitmex client
        get_bitmex_position(bitmex_client_func, "currentQty")
        ## If we got a valid bitmex client return it
        return bitmex_client_func
    except:
        return False

## Get user Deribit client running
def get_deribit_client(testnet, key, secret):
    # noinspection PyBroadException
    if testnet:
        url = "https://test.deribit.com"
    else:
        url = "https://deribit.com"
    try:
        deribit_client_func = RestClient(key, secret, url)
        ## Use this to validate the bitmex client
        get_deribit_position(deribit_client_func, "currentQty")
        ## If we got a valid bitmex client return it
        return deribit_client_func
    except:
        return False

## Get open bitmex position
def get_bitmex_position(bitmex_client_func, askedValue):
    try:
        ## Get data from Bitmex - filtered for XBT positions
        result = bitmex_client_func.Position.Position_get(filter=json.dumps({'symbol': 'XBTUSD'})).result()

        global bitmex_rate_limit
        bitmex_rate_limit = int(result[1].headers["X-RateLimit-Remaining"])

        ## Parse first position found
        result_json = result[0][0]
        ## Unrealised PNL
        unrealisedPnl = result_json["unrealisedPnl"] / 100000000
        unrealisedPnl = round(unrealisedPnl, 6)
        ## realised PNL
        realisedPnl = result_json["realisedPnl"] / 100000000
        realisedPnl = round(realisedPnl, 6)
        ## rebalanced PNL
        rebalancedPnl = result_json["rebalancedPnl"] / 100000000
        rebalancedPnl = round(rebalancedPnl, 6)
        ## Full PNL = unrealisedPnl + realised + rebalancedPnl
        fullPnl = unrealisedPnl + realisedPnl + rebalancedPnl
        ## Break even price
        breakEvenPrice = int(result_json["breakEvenPrice"])
        ## Last price
        lastPrice = int(result_json["lastPrice"])
        ## Calculate the difference to break even
        diff_break_even = abs(breakEvenPrice - lastPrice)
        ## Position size
        currentQty = result_json["currentQty"]
        ## Last closed position
        prevRealisedPnl = result_json["prevRealisedPnl"] / 100000000
        prevRealisedPnl = round(prevRealisedPnl, 6)

        ## Long or Short
        long_short = "No Position!"
        if currentQty > 0:
            long_short = "Long"
        if currentQty < 0:
            long_short = "Short"

        ## Return the open position and stats
        if askedValue == "openPosition" and currentQty != 0:
            openPosition = long_short + " position: " + str(currentQty) + " | Open PNL: " + str(unrealisedPnl)[:8] + "\nFull PNL: " + str(fullPnl)[:8] + " | Break even: " + str(breakEvenPrice) + " (" + str(diff_break_even) + ")"
            return openPosition
        elif askedValue == "openPosition":
            openPosition = "No open Bitmex position at the moment.\nLast position PNL: " + str(prevRealisedPnl)
            return openPosition

        ## Return the position size
        if askedValue == "currentQty":
            return currentQty
        ## Return the unrealisedPnl
        if askedValue == "unrealisedPnl":
            return unrealisedPnl
        ## Return the prevRealisedPnl
        if askedValue == "prevRealisedPnl":
            return prevRealisedPnl

    except:
        return "No open Bitmex position!"

## Get user balance
def get_bitmex_balance(bitmex_client_func, askedValue):
    try:
        ## Get User balance from Bitmex
        result = bitmex_client_func.User.User_getMargin().result()
        result_json = result[0]

        ## Wallet balance
        walletBalance = result_json["walletBalance"] / 100000000
        walletBalance = round(walletBalance, 6)

        ## Margin balance = Wallet balance after position close
        marginBalance = result_json["marginBalance"] / 100000000
        marginBalance = round(marginBalance, 6)

        ## Return the wallet balance
        if askedValue == "walletBalance":
            return walletBalance

        ## Return the margin balance
        if askedValue == "marginBalance":
            return marginBalance

    except IndexError or AttributeError:
        return "No data received!"

## Get open Deribit position
def get_deribit_position(deribit_client, askedValue):
    try:
        ## Get data from Deribit
        result = deribit_client.positions()
        try:
            ## Parse first position found
            result_json = result[0]
            ## Unrealised PNL
            unrealisedPnl = result_json["profitLoss"]
            unrealisedPnl = round(unrealisedPnl, 6)
            ## realised PNL
            realisedPnl = result_json["realizedPl"]
            realisedPnl = round(realisedPnl, 6)
            ## rebalanced PNL
            fullPnl = result_json["floatingPl"]
            fullPnl = round(fullPnl, 6)
            ## Break even price
            breakEvenPrice = int(result_json["averagePrice"])
            ## Last price
            lastPrice = int(result_json["markPrice"])
            ## Calculate the difference to break even
            diff_break_even = abs(breakEvenPrice - lastPrice)
            ## Position size
            currentQty = int(result_json["amount"])
            ## Last closed position
            prevRealisedPnl = "Work in progress for Deribit"
        except IndexError or AttributeError:
            currentQty = 0

        ## Long or Short
        long_short = "No Position!"
        if currentQty > 0:
            long_short = "Long"
        if currentQty < 0:
            long_short = "Short"
        ## Return the open position and stats
        if askedValue == "openPosition" and currentQty != 0:
            openPosition = long_short + " position: " + str(currentQty) + " | Open PNL: " + str(unrealisedPnl)[:8] + "\nFull PNL: " + str(fullPnl)[:8] + " | Entry: " + str(breakEvenPrice) + " (" + str(diff_break_even) + ")"
            return openPosition
        elif askedValue == "openPosition":
            openPosition = "No open Deribit position at the moment."
            return openPosition
        ## Return the position size
        if askedValue == "currentQty":
            return currentQty
        ## Return the unrealisedPnl
        if askedValue == "unrealisedPnl":
            return unrealisedPnl

    except IndexError or AttributeError:
        return "No open Deribit position!"


## Log to console
def log(output):

    global last_log

    if overview_mode:
        ## Put Logs in a List so we can display it later in the overview
        if time.time() - last_log > 5:
            output = "\n-------------------\n" + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "\n-------------------\n" + str(output)
            logs.append(output)
            last_log = time.time()
        else:
            logs.append(output)
            last_log = time.time()
    else:
        ## Print new Timestamp in log if last log is older than 5 seconds
        if time.time() - last_log > 5:
            print("\n-------------------\n" + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "\n-------------------\n" + str(output))
            last_log = time.time()
        else:
            print(str(output))
            last_log = time.time()

#########################
## Overview CLI Output ##
#########################

def cli_overview():
    # If not in dev mode we can output a overview to the cli
    while True:
        os.system('clear')
        print("\n")
        print("Time: {}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        print("Devmode: " + str(devmode))
        print("")
        print("Bitmex Price.: {}".format(price_bitmex))
        print("Deribit Price: {}".format(price_deribit))
        print("")
        print("Last Action: {}".format(datetime.fromtimestamp(int(last_log))))
        print("")
        print("Last five logs: ({})".format(len(logs)))
        print("--------------------")

        ## We only want the last 5 log segments
        log_count = 0
        log_position = len(logs)
        if len(logs) > 0:
            logrotate = []
            while log_count < 5 and log_position > 0:
                logitem = logs[log_position-1]
                logrotate.insert(0, logitem)
                log_position = log_position - 1
                if str.find(logitem, "-------------------") != -1:
                    log_count = log_count + 1
            for item in logrotate:
                print(item)
        sleep(1)

################
## TX Checker ##
################

def tx_checker(tx, source):
    if source == "blockcypher":
        try:
            response = requests.get(
                "https://api.blockcypher.com/v1/btc/main/txs/eaffea28e77a8ebd9134003d00583f8a87d0b2b0a1c6687e64d861bc670b634c" + tx, verify=False)
            response_json = response.json()
            response_json["confirmed"]
            return "confirmed"
        except:
            return "unconfirmed"

    if source == "blockchair":
        try:
            response = requests.get("http://api.blockchair.com/bitcoin/dashboards/transaction/" + tx + "/priority", verify=False)
            response_json = response.json()
            position = response_json["data"][tx]["priority"]["position"]
            out_of = response_json["data"][tx]["priority"]["out_of"]

            if not position:
                response = requests.get("http://api.blockchair.com/bitcoin/dashboards/transaction/" + tx, verify=False)
                response_json = response.json()
                block = response_json["data"][tx]["transaction"]["block_id"]

                if block != "-1":
                    return "confirmed", "Your TX is confirmed in block " + str(block)
            else:
                return "unconfirmed", "The position of your TX is " + str(position) + " out of " + str(out_of)
        except:
            log("Blockchair TX lookup went shit")

#############
## Configs ##
#############

## Import the configs from file
config = configparser.RawConfigParser()
config.read("./config.cfg")

## Get general configs
bot_token = config.get("General", "bot_token")
report_chan = config.get("General", "report_chan")
devmode = config.getboolean("General", "devmode")
overview_mode = config.getboolean("General", "overview_mode")

## Get user configs
userlist_import = config.get("General", "userlist")
userlist = userlist_import.split(',')

## Put every user in a 2-dim list
user_position = 0
for user in userlist:

    user_chat_id = user
    username = config.get(user, "username")
    history_length = int(config.get(user, "history_length"))
    divider = int(config.get(user, "divider"))
    interval_check = config.getboolean(user, "interval_check")
    report_active = config.getboolean(user, "report_active")
    bitmex_active = config.getboolean(user, "bitmex_active")
    bitmex_key = config.get(user, "bitmex_api_key")
    bitmex_secret = config.get(user, "bitmex_secret")
    bitmex_testnet = config.getboolean(user, "bitmex_testnet")
    announced_price = int(config.get(user, "announced_price"))
    deribit_active = config.getboolean(user, "deribit_active")
    deribit_key = config.get(user, "deribit_api_key")
    deribit_secret = config.get(user, "deribit_secret")
    deribit_testnet = config.getboolean(user, "deribit_testnet")
    pref_exchange = config.get(user, "pref_exchange")
    history = []
    ask_price_steps = False
    ask_bitmex_key = False
    ask_bitmex_secret = False
    ask_deribit_key = False
    ask_deribit_secret = False
    bitmex_client = False
    deribit_client = False
    bitmex_position_amount = 0
    deribit_position_amount = 0
    tx_to_check = config.get(user, "tx_to_check")

    if bitmex_active:
        ## Try to get a client
        bitmex_client = get_bitmex_client(bitmex_testnet, bitmex_key, bitmex_secret)
        ## Check if valid client received
        if bitmex_client:
            # noinspection PyTypeChecker
            ## Got valid client - check position amount
            bitmex_position_amount = get_bitmex_position(bitmex_client, "currentQty")
        else:
            ## Client is not valid - deactivate Bitmex
            bitmex_active = False

    if deribit_active:
        ## Try to get a client
        deribit_client = get_deribit_client(deribit_testnet, deribit_key, deribit_secret)
        ## Check if valid client received
        if deribit_client:
            # noinspection PyTypeChecker
            ## Got valid client - check position amount
            deribit_position_amount = get_deribit_position(deribit_client, "currentQty")
        else:
            ## Client is not valid - deactivate Bitmex
            deribit_active = False

    settings = {
                "user_position": user_position,
                "user_chat_id": user_chat_id,
                "history_length": history_length,
                "divider": divider,
                "interval_check": interval_check,
                "bitmex_active": bitmex_active,
                "bitmex_key": bitmex_key,
                "bitmex_secret": bitmex_secret,
                "deribit_active": deribit_active,
                "deribit_key": deribit_key,
                "deribit_secret": deribit_secret,
                "history": history,
                "announced_price": announced_price,
                "bitmex_client": bitmex_client,
                "bitmex_position_amount": bitmex_position_amount,
                "deribit_client": deribit_client,
                "deribit_position_amount": deribit_position_amount,
                "ask_price_steps": ask_price_steps,
                "ask_bitmex_key": ask_bitmex_key,
                "ask_bitmex_secret": ask_bitmex_secret,
                "ask_deribit_key": ask_deribit_key,
                "ask_deribit_secret": ask_deribit_secret,
                "bitmex_testnet": bitmex_testnet,
                "deribit_testnet": deribit_testnet,
                "username": username,
                "report_active": report_active,
                "pref_exchange": pref_exchange,
                "tx_to_check": tx_to_check
                }
    userlist[user_position] = settings
    user_position = user_position + 1

###################
## Bot variables ##
###################

offset = "-0"
messages = []
messages_report_chan = []
write_config = False
bot_restarted = True
previous_price = 0
interval_count = 0
price_source = "bitmex"
log_pricemoves = False
price_error_count = 0
bitmex_rate_limit = 300
last_log = 0
price_bitmex = None
price_deribit = None
logs = []

##################
## Pre-warm Bot ##
##################

## Set the price level and fill the history for every user
for user in userlist:
    ## Last user announced price / user divider
    price_level = int(user["announced_price"]/user["divider"])
    ## Fill history as long as the user wants
    while len(user["history"]) < user["history_length"]:
        user["history"].append(price_level)

## Send out restart message if not in dev mode
if bot_restarted and not devmode:
    message = "The Bot restarted"
    log(message)
    ## Send message to the admin user (first user)
    log("Reported to Admin: " + str(userlist[0]["user_chat_id"]))
    send_message(userlist[0]["user_chat_id"], message)

## Get Deribit Api connector running for price fetches
## This is testnet trade read only API set
deribit_client_price = RestClient("Ml5lhKLH", "JqJOj5tKMBFIxOYE838jeBQA2nln-P-pB2OUrQoqyqU")

#############
## Threads ##
#############
t1 = threading.Thread(target=get_latest_bitcoin_price, args=("bitmex",))
t1.start()

t2 = threading.Thread(target=get_latest_bitcoin_price, args=("deribit",))
t2.start()

if overview_mode:
    t3 = threading.Thread(target=cli_overview)
    t3.start()

###############
## Main loop ##
###############

while True:
    ## Check status of the threads
    ## Restart and inform admin if needed

    if t1.isAlive() == False:
        t1.start()
        message = "Thread 1 died, i restart it."
        send_message(userlist[0]["user_chat_id"], message)

    if t2.isAlive() == False:
        t2.start()
        message = "Thread 2 died, i restart it."
        send_message(userlist[0]["user_chat_id"], message)

    if overview_mode:
        if t3.isAlive() == False:
            t3.start()
            message = "Thread 3 died, i restart it."
            send_message(userlist[0]["user_chat_id"], message)

    #############
    #### BOT ####
    #############

    ## Check every user if an announcement is needed
    for user in userlist:

        ## Shorten variables
        price_level = user["history"][-1]
        divider = user["divider"]
        history = user["history"]
        bitmex_active = user["bitmex_active"]
        deribit_active = user["deribit_active"]
        interval_check = user["interval_check"]
        announced_price = user["announced_price"]
        username = user["username"]
        report_active = user["report_active"]
        pref_exchange = user["pref_exchange"]
        tx_to_check = user["tx_to_check"]

        if pref_exchange == "deribit":
            new_price = price_deribit
            if not new_price:
                continue
        else:
            new_price = price_bitmex
            if not new_price:
                continue

        ## Check if the user has an open Bitmex position
        if bitmex_active:
            ## Try to get Bitmex client
            if user["bitmex_client"]:
                bitmex_open_position = get_bitmex_position(user["bitmex_client"], "openPosition")
            else:
                bitmex_active = False
        ## Check if the user has an open Deribit position
        if deribit_active:
            ## Try to get Deribit client
            if user["deribit_client"]:
                deribit_open_position = get_deribit_position(user["deribit_client"], "openPosition")
            else:
                deribit_active = False
        ## Get new price level for the user
        new_price_level = int(new_price / divider)
        ## Do nothing if no new price level
        if price_level != new_price_level:
            ## Price has to move more then xx% of the divider to avoid spam
            if (new_price < (announced_price - (divider / 6))) or (new_price > (announced_price + (divider / 6))):
                ## Check if new price level is not in history
                if new_price_level not in history:
                    ## Check if price is higher or lower
                    if announced_price > new_price:
                        priceIs = "Lower"
                        message = priceIs + " price level: " + str(new_price_level * divider + divider) + " - " + str(new_price_level * divider)
                    else:
                        priceIs = "Higher"
                        message = priceIs + " price level: " + str(new_price_level * divider) + " - " + str(new_price_level * divider + divider)

                    ## Announce since price not in history
                    log(message)
                    messages.append(message)
                    ## Update the users announced_price
                    user["announced_price"] = new_price
                    config.set(str(user["user_chat_id"]), "announced_price", new_price)
                    write_config = True

                    ## Announce open position if Bitmex is active
                    if bitmex_active:
                        # noinspection PyUnboundLocalVariable
                        message = str(bitmex_open_position)
                        log(message)
                        messages.append(message)

                    ## Announce open position if Deribit is active
                    if deribit_active:
                        # noinspection PyUnboundLocalVariable
                        message = str(deribit_open_position)
                        log(message)
                        messages.append(message)

                ## Check if price is stable
                elif (sum(history) / len(history)) == new_price_level:

                    ## Check if price is higher or lower
                    if announced_price > new_price:
                        priceIs = "Lower"
                        message = priceIs + " price level: " + str(new_price_level * divider + divider) + " - " + str(new_price_level * divider)
                    else:
                        priceIs = "Higher"
                        message = priceIs + " price level: " + str(new_price_level * divider) + " - " + str(new_price_level * divider + divider)

                    ## Announce since price is stable
                    log(message)
                    messages.append(message)

                    message = str(get_deribit_position(deribit_client, "openPosition"))
                    log(message)
                    messages.append(message)

                    ## Announce open position if Bitmex is active
                    if bitmex_active:
                        message = str(bitmex_open_position)
                        log(message)
                        messages.append(message)

                    ## Announce open position if Deribit is active
                    if deribit_active:
                        message = str(deribit_open_position)
                        log(message)
                        messages.append(message)

        ##################
        ## Make history ##
        ##################

        history.append(new_price_level)
        del history[0]

        #####################
        ## Interval check ##
        #####################

        if interval_count == 1200:
            message = "Interval check - the price is " + str(new_price) + " USD"
            log(message)
            # Announce interval check if active
            if interval_check:
                messages.append(message)
                ## Announce open position if Bitmex is active
                if bitmex_active:
                    message = bitmex_open_position
                    log(message)
                    messages.append(message)
            interval_count = 0
        interval_count = interval_count + 1

        #############################
        ## Bitmex position tracker ##
        #############################

        if bitmex_active:
            if user["bitmex_client"]:

                bitmex_position_amount_new = get_bitmex_position(user["bitmex_client"], "currentQty")

                if bitmex_position_amount_new != "No open Bitmex position!":
                    ## Get position size
                    bitmex_position_amount_new = int(bitmex_position_amount_new)
                    bitmex_position_amount = int(user["bitmex_position_amount"])

                    ## Calculate the difference
                    bitmex_position_amount_change = abs(bitmex_position_amount_new - bitmex_position_amount)

                    ## Check if position was closed or just changed
                    if bitmex_position_amount_new == 0 and bitmex_position_amount != 0:
                        ## Position was closed - check if long or short
                        if bitmex_position_amount > 0:
                            ## Announce closure of long position
                            message = "Closed long position @ " + str(new_price) + "\nPNL: " + str(get_bitmex_position(user["bitmex_client"], "prevRealisedPnl"))
                            log(message)
                            messages.append(message)
                            messages_report_chan.append(message)
                        elif bitmex_position_amount < 0:
                            ## Announce closure of short position
                            message = "Closed short position @ " + str(new_price) + "\nPNL: " + str(get_bitmex_position(user["bitmex_client"], "prevRealisedPnl"))
                            log(message)
                            messages.append(message)
                            messages_report_chan.append(message)

                    ## Increased and reduced is based on long or short
                    ## If position is a long
                    elif bitmex_position_amount_new > 0:
                        ## Announce if position was reduced
                        if bitmex_position_amount_new < bitmex_position_amount:
                            message = "Reduced long position by " + str(bitmex_position_amount_change) + " @ " + str(new_price)
                            log(message)
                            messages.append(message)
                            messages_report_chan.append(message)
                            ## Announce new position and PNL
                            message = bitmex_open_position
                            log(message)
                            messages.append(message)
                            messages_report_chan.append(message)
                        ## Announce if position was increased
                        elif bitmex_position_amount_new > bitmex_position_amount:
                            message = "Increased long position by " + str(bitmex_position_amount_change) + " @ " + str(new_price)
                            log(message)
                            messages.append(message)
                            messages_report_chan.append(message)
                            ## Announce new position and PNL
                            message = bitmex_open_position
                            log(message)
                            messages.append(message)
                            messages_report_chan.append(message)

                    ## Position is a short
                    else:
                        ## Announce if position was reduced
                        if bitmex_position_amount_new > bitmex_position_amount:
                            message = "Reduced short position by " + str(bitmex_position_amount_change) + " @ " + str(new_price)
                            log(message)
                            messages.append(message)
                            messages_report_chan.append(message)
                            ## Announce new position and PNL
                            message = bitmex_open_position
                            log(message)
                            messages.append(message)
                            messages_report_chan.append(message)
                        ## Announce if position was increased
                        elif bitmex_position_amount_new < bitmex_position_amount:
                            message = "Increased short position by " + str(bitmex_position_amount_change) + " @ " + str(new_price)
                            log(message)
                            messages.append(message)
                            messages_report_chan.append(message)
                            ## Announce new position and PNL
                            message = bitmex_open_position
                            log(message)
                            messages.append(message)
                            messages_report_chan.append(message)

                    ## Set new Bitmex position amount
                    user["bitmex_position_amount"] = bitmex_position_amount_new

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
            log("Sending messages to the chat: " + str(user["username"]))
            all_messages = ""
            for x in messages:
                all_messages = all_messages + "\n" + x
            send_message(user["user_chat_id"], all_messages)
            messages = []

        ## If there are messages, sent them to the report channel
        if messages_report_chan and report_chan:
            if report_active:
                report_user = "User: " + str(username)
                messages_report_chan.insert(0, report_user)
                log("Sending messages to the report channel for user: " + str(user["username"]))
                all_messages = ""
                for x in messages_report_chan:
                    all_messages = all_messages + "\n" + x
                send_message(report_chan, all_messages)
                messages_report_chan = []

        ##############################
        ## Deribit position tracker ##
        ##############################
        if deribit_active:
            if user["deribit_client"]:
                deribit_position_amount_new = get_deribit_position(user["deribit_client"], "currentQty")
                if deribit_position_amount_new != "No open Deribit position!":
                    ## Get position size
                    deribit_position_amount_new = int(deribit_position_amount_new)
                    deribit_position_amount = int(user["deribit_position_amount"])
                    ## Calculate the difference
                    deribit_position_amount_change = abs(deribit_position_amount_new - deribit_position_amount)
                    ## Check if position was closed or just changed
                    if deribit_position_amount_new == 0 and deribit_position_amount != 0:
                        ## Position was closed - check if long or short
                        if deribit_position_amount > 0:
                            ## Announce closure of long position
                            message = "Closed long position @ " + str(new_price) + "\nPNL: " + str(get_deribit_position(user["deribit_client"], "prevRealisedPnl"))
                            log(message)
                            messages.append(message)
                            messages_report_chan.append(message)
                        elif deribit_position_amount < 0:
                            ## Announce closure of short position
                            message = "Closed short position @ " + str(new_price) + "\nPNL: " + str(get_deribit_position(user["deribit_client"], "prevRealisedPnl"))
                            log(message)
                            messages.append(message)
                            messages_report_chan.append(message)

                    ## Increased and reduced is based on long or short
                    ## If position is a long
                    elif deribit_position_amount_new > 0:
                        ## Announce if position was reduced
                        if deribit_position_amount_new < deribit_position_amount:
                            message = "Reduced long position by " + str(deribit_position_amount_change) + " @ " + str(new_price)
                            log(message)
                            messages.append(message)
                            messages_report_chan.append(message)
                            ## Announce new position and PNL
                            message = deribit_open_position
                            log(message)
                            messages.append(message)
                            messages_report_chan.append(message)
                        ## Announce if position was increased
                        elif deribit_position_amount_new > deribit_position_amount:
                            message = "Increased long position by " + str(deribit_position_amount_change) + " @ " + str(new_price)
                            log(message)
                            messages.append(message)
                            messages_report_chan.append(message)
                            ## Announce new position and PNL
                            message = deribit_open_position
                            log(message)
                            messages.append(message)
                            messages_report_chan.append(message)

                    ## Position is a short
                    else:
                        ## Announce if position was reduced
                        if deribit_position_amount_new > deribit_position_amount:
                            message = "Reduced short position by " + str(deribit_position_amount_change) + " @ " + str(new_price)
                            log(message)
                            messages.append(message)
                            messages_report_chan.append(message)
                            ## Announce new position and PNL
                            message = deribit_open_position
                            log(message)
                            messages.append(message)
                            messages_report_chan.append(message)
                        ## Announce if position was increased
                        elif deribit_position_amount_new < deribit_position_amount:
                            message = "Increased short position by " + str(deribit_position_amount_change) + " @ " + str(new_price)
                            log(message)
                            messages.append(message)
                            messages_report_chan.append(message)
                            ## Announce new position and PNL
                            message = deribit_open_position
                            log(message)
                            messages.append(message)
                            messages_report_chan.append(message)

                    ## Set new deribit position amount
                    user["deribit_position_amount"] = deribit_position_amount_new

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
            log("Sending messages to the chat: " + str(user["username"]))
            all_messages = ""
            for x in messages:
                all_messages = all_messages + "\n" + x
            send_message(user["user_chat_id"], all_messages)
            messages = []

        ## If there are messages, sent them to the report channel
        if messages_report_chan and report_chan:
            if report_active:
                report_user = "User: " + str(username)
                messages_report_chan.insert(0, report_user)
                log("Sending messages to the report channel for user: " + str(user["username"]))
                all_messages = ""
                for x in messages_report_chan:
                    all_messages = all_messages + "\n" + x
                send_message(report_chan, all_messages)
                messages_report_chan = []

        ################
        ## TX Tracker ##
        ################

        if tx_to_check != "confirmed" and interval_count % 10 == 0:

            ## If TX is confirmed disable tracking and send message to user
            tx_check = tx_checker(tx_to_check, "blockchair")
            if tx_check[0] == "confirmed":
                ## Write config
                config.set(str(user["user_chat_id"]), 'tx_to_check', 'confirmed')
                user["tx_to_check"] = "confirmed"
                with open('config.cfg', 'w') as configfile:
                    config.write(configfile)
                    configfile.close()
                ## Send message to user with block id
                message = tx_check[1]
                log(message)
                messages.append(message)

                ## Push messagess
                log("Sending messages to the chat: " + str(user["username"]))
                all_messages = ""
                for x in messages:
                    all_messages = all_messages + "\n" + x
                send_message(user["user_chat_id"], all_messages)
                messages = []

            ## If TX is unconfirmed send user the position of his TX
            ''' This Spams the chat - needs work
            if tx_check[0] == "unconfirmed":
                message = tx_check[1]
                log(message)
                messages.append(message)

            ## Push messagess
            log("Sending messages to the chat: " + str(user["username"]))
            all_messages = ""
            for x in messages:
                all_messages = all_messages + "\n" + x
            send_message(user["user_chat_id"], all_messages)
            messages = []
            '''

    #####################
    ## Chat monitoring ##
    #####################

    ## Monitor loop
    mon_loop = 0
    while mon_loop < 1:
        ## Get updates from bot
        bot_messages_json = get_messages(offset)
        ## Check the amount of messages received
        try:
            message_amount = len(bot_messages_json["result"])
        except KeyError and TypeError:
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
                        log("New Message: " + bot_messages_text_single)

                        ## Check who wrote the message
                        check_user = bot_messages_json["result"][message_counter]["message"]["from"]["id"]
                        log("From user: " + str(check_user))

                        ## Check if we know the user
                        counter = 0
                        find_user_index = "None"
                        for user in userlist:
                            if str(user["user_chat_id"]) == str(check_user):
                                find_user_index = userlist[counter]["user_position"]
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
                            f.write("username = Anonymous\n")
                            f.write("history_length = 60\n")
                            f.write("divider = 25\n")
                            f.write("interval_check = False\n")
                            f.write("report_active = False\n")
                            f.write("announced_price = 0\n")
                            f.write("bitmex_active = False\n")
                            f.write("bitmex_api_key = \n")
                            f.write("bitmex_secret = \n")
                            f.write("bitmex_testnet = False\n")
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

                        ## Shorten variables
                        divider = userlist[find_user_index]["divider"]
                        history_length = userlist[find_user_index]["history_length"]
                        interval_check = userlist[find_user_index]["interval_check"]
                        bitmex_key = userlist[find_user_index]["bitmex_key"]
                        bitmex_secret = userlist[find_user_index]["bitmex_secret"]
                        bitmex_active = userlist[find_user_index]["bitmex_active"]
                        bitmex_testnet = userlist[find_user_index]["bitmex_testnet"]
                        ask_bitmex_key = userlist[find_user_index]["ask_bitmex_key"]
                        ask_bitmex_secret = userlist[find_user_index]["ask_bitmex_secret"]
                        ask_price_steps = userlist[find_user_index]["ask_price_steps"]
                        username = userlist[find_user_index]["username"]
                        report_active = userlist[find_user_index]["report_active"]
                        deribit_key = userlist[find_user_index]["deribit_key"]
                        deribit_secret = userlist[find_user_index]["deribit_secret"]
                        deribit_active = userlist[find_user_index]["deribit_active"]
                        deribit_testnet = userlist[find_user_index]["deribit_testnet"]
                        ask_deribit_key = userlist[find_user_index]["ask_deribit_key"]
                        ask_deribit_secret = userlist[find_user_index]["ask_deribit_secret"]
                        tx_to_check = userlist[find_user_index]["tx_to_check"]

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
                            ## Tell the user how big the price brackets and if the interval check is enabled
                            message = "Price steps: " + str(divider) + " | Interval check: " + str(interval_check)
                            log(message)
                            messages.append(message)

                        ## Set Bitmex as prefered exchange
                        if splitted[0] == "/set_prefered_exchange_to_bitmex":
                            pref_exchange = "bitmex"
                            config.set(str(check_user), 'pref_exchange', pref_exchange)
                            write_config = True
                            userlist[find_user_index]["pref_exchange"] = pref_exchange
                            ## Tell the user that Bitmex is now the prefered exchange
                            message = "The prefered exchange is now Bitmex (price source)"
                            log(message)
                            messages.append(message)

                        ## Set Deribit as prefered exchange
                        if splitted[0] == "/set_prefered_exchange_to_deribit":
                            pref_exchange = "deribit"
                            config.set(str(check_user), 'pref_exchange', pref_exchange)
                            write_config = True
                            userlist[find_user_index]["pref_exchange"] = pref_exchange
                            ## Tell the user that Deribit is now the prefered exchange
                            message = "The prefered exchange is now Deribit (price source)"
                            log(message)
                            messages.append(message)

                        ## Tell the user his open Bitmex position
                        if splitted[0] == "/show_bitmex_position":
                            if bitmex_key and bitmex_secret:
                                bitmex_client = get_bitmex_client(bitmex_testnet, bitmex_key, bitmex_secret)
                                if bitmex_client:
                                    # noinspection PyTypeChecker
                                    message = get_bitmex_position(bitmex_client, "openPosition")
                                    log(message)
                                    messages.append(message)
                                else:
                                    message = "Something went wrong. Ask the Admin!"
                                    log(message)
                                    messages.append(message)
                            else:
                                message = "You need to set your API Key and Secret:\n/set_bitmex_key\n/set_bitmex_secret"
                                log(message)
                                messages.append(message)

                        ## Tell the user his open Deribit position
                        if splitted[0] == "/show_deribit_position":
                            if deribit_key and deribit_secret:
                                deribit_client = get_deribit_client(deribit_testnet, deribit_key, deribit_secret)
                                if deribit_client:
                                    # noinspection PyTypeChecker
                                    message = get_deribit_position(deribit_client, "openPosition")
                                    log(message)
                                    messages.append(message)
                                else:
                                    message = "Something went wrong. Ask the Admin!"
                                    log(message)
                                    messages.append(message)
                            else:
                                message = "You need to set your API Key and Secret:\n/set_deribit_key\n/set_deribit_secret"
                                log(message)
                                messages.append(message)

                        ## Tell the user his bitmex balance
                        if splitted[0] == "/show_bitmex_balance":
                            if bitmex_key and bitmex_secret:
                                bitmex_client = get_bitmex_client(bitmex_testnet, bitmex_key, bitmex_secret)
                                if bitmex_client:
                                    # noinspection PyTypeChecker
                                    wallet_balance = get_bitmex_balance(bitmex_client, "walletBalance")
                                    margin_balance = get_bitmex_balance(bitmex_client, "marginBalance")
                                    message = "Your wallet balance: " + str(wallet_balance)
                                    log(message)
                                    messages.append(message)
                                    ## Margin balance if open position
                                    if wallet_balance != margin_balance:
                                        message = "After position close.: " + str(margin_balance)
                                        log(message)
                                        messages.append(message)
                                else:
                                    message = "Something went wrong. Ask the Admin!"
                                    log(message)
                                    messages.append(message)
                            else:
                                message = "You need to set your API Key and Secret:\n/set_bitmex_key\n/set_bitmex_secret"
                                log(message)
                                messages.append(message)

                        ## The user wants to change the price steps
                        if splitted[0] == "/set_price_steps":
                            if len(splitted) > 1:
                                try:
                                    ## Look for a valid value for the new price steps
                                    divider = int(splitted[1])
                                    config.set(str(check_user), 'divider', divider)
                                    write_config = True
                                    userlist[find_user_index]["divider"] = divider
                                    message = "The price stepping is set to " + str(splitted[1] + " now.")
                                    log(message)
                                    messages.append(message)
                                    mon_loop = 50
                                except ValueError:
                                    ## The user did not give a valid value for the price steps so ask him
                                    ask_price_steps = True
                                    userlist[find_user_index]["ask_price_steps"] = True
                            else:
                                ## The user did not give a valid value for the price steps so ask him
                                ask_price_steps = True
                                userlist[find_user_index]["ask_price_steps"] = True
                        ## If the user got asked for his desired price steps, look for the answer
                        if ask_price_steps:
                            try:
                                ## Look for a valid value for the new price steps
                                divider = int(splitted[0])
                                config.set(str(check_user), 'divider', divider)
                                write_config = True
                                userlist[find_user_index]["divider"] = divider
                                message = "The price stepping is set to " + str(splitted[0]) + " now."
                                log(message)
                                messages.append(message)
                                mon_loop = 50
                                ask_price_steps = False
                                userlist[find_user_index]["ask_price_steps"] = False
                            ## The user did not give a valid value for the price steps so ask him
                            except ValueError:
                                ask_price_steps = True
                                userlist[find_user_index]["ask_price_steps"] = True
                                message = "Tell me your desired price steps in USD as integer"
                                messages.append(message)
                                log(message)

                        ## Listen for Bitmex toggle command
                        if splitted[0] == "/toggle_bitmex":
                            ## Check if the API settings are there
                            if bitmex_key and bitmex_secret:
                                ## Deactivate Bitmex if it is enabled
                                if bitmex_active:
                                    bitmex_active = False
                                    userlist[find_user_index]["bitmex_active"] = False
                                    config.set(str(check_user), "bitmex_active", "False")
                                    write_config = True
                                    message = "Bitmex disabled"
                                    messages.append(message)
                                ## Enable Bitmex if it is disabled
                                else:
                                    bitmex_client = get_bitmex_client(bitmex_testnet, bitmex_key, bitmex_secret)
                                    if bitmex_client:
                                        userlist[find_user_index]["bitmex_client"] = bitmex_client
                                        bitmex_active = True
                                        userlist[find_user_index]["bitmex_active"] = True
                                        config.set(str(check_user), "bitmex_active", "True")
                                        write_config = True
                                        message = "Bitmex enabled"
                                        messages.append(message)
                                    else:
                                        message = "You might need to set your API key and Secret:\n/set_bitmex_key\n/set_bitmex_secret\nAfter that, try again!"
                                        log(message)
                                        messages.append(message)
                            else:
                                message = "You need to set your API key and Secret:\n/set_bitmex_key\n/set_bitmex_secret"
                                log(message)
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
                                    userlist[find_user_index]["bitmex_key"] = bitmex_key
                                    message = "Okay, i saved your Bitmex key. Make sure to set also the secret\n/set_bitmex_secret.\n\nIf you set both you can use:\n/toggle_bitmex\n/show_bitmex_position"
                                    log(message)
                                    messages.append(message)
                                    mon_loop = 50
                                else:
                                    ## The user did not give a valid value for the Bitmex key so ask him
                                    ask_bitmex_key = True
                                    userlist[find_user_index]["ask_bitmex_key"] = True
                            else:
                                ## The user did not give a valid value for the Bitmex key so ask him
                                ask_bitmex_key = True
                                userlist[find_user_index]["ask_bitmex_key"] = True
                        ## If the user got asked for the Bitmex key, look for the answer
                        if ask_bitmex_key:
                            ## Look for a valid value for the Bitmex key
                            ## Only clue we have it has to be 24 chars long
                            if len(splitted[0]) == 24:
                                bitmex_key = str(splitted[0])
                                config.set(str(check_user), 'bitmex_api_key', bitmex_key)
                                write_config = True
                                ask_bitmex_key = False
                                userlist[find_user_index]["ask_bitmex_key"] = False
                                userlist[find_user_index]["bitmex_key"] = bitmex_key
                                message = "Okay, i saved your Bitmex key. Make sure you also set the secret\n/set_bitmex_secret.\n\nIf you set both you can use:\n/toggle_bitmex\n/show_bitmex_position"
                                log(message)
                                messages.append(message)
                                mon_loop = 50
                            else:
                                ## The user did not give a valid value for the Bitmex key so ask him
                                ask_bitmex_key = True
                                userlist[find_user_index]["ask_bitmex_key"] = True
                                message = "Tell me your Bitmex API key. Be sure you created a read-only API Key on Bitmex."
                                messages.append(message)
                                log(message)

                        ## The user wants to change his Bitmex API secret
                        if splitted[0] == "/set_bitmex_secret":
                            if len(splitted) > 1:
                                ## Look for a valid value for the Bitmex API secret
                                ## Only clue we have it has to be 48 chars long
                                if len(splitted[1]) == 48:
                                    bitmex_key = str(splitted[1])
                                    config.set(str(check_user), 'bitmex_secret', bitmex_secret)
                                    write_config = True
                                    userlist[find_user_index]["bitmex_secret"] = bitmex_secret
                                    message = "Okay, i saved your Bitmex secret. Make sure to set also the key\n/set_bitmex_key.\n\nIf you set both you can use:\n/toggle_bitmex\n/show_bitmex_position"
                                    log(message)
                                    messages.append(message)
                                    mon_loop = 50
                                else:
                                    ## The user did not give a valid value for the Bitmex secret so ask him
                                    ask_bitmex_secret = True
                                    userlist[find_user_index]["ask_bitmex_secret"] = True
                            else:
                                ## The user did not give a valid value for the Bitmex secret so ask him
                                ask_bitmex_secret = True
                                userlist[find_user_index]["ask_bitmex_secret"] = True
                        ## If the user got asked for the Bitmex secret, look for the answer
                        if ask_bitmex_secret:
                            ## Look for a valid value for the Bitmex secret
                            ## Only clue we have it has to be 48 chars long
                            if len(splitted[0]) == 48:
                                bitmex_secret = str(splitted[0])
                                config.set(str(check_user), 'bitmex_secret', bitmex_secret)
                                write_config = True
                                ask_bitmex_secret = False
                                userlist[find_user_index]["ask_bitmex_secret"] = False
                                userlist[find_user_index]["bitmex_secret"] = bitmex_secret
                                message = "Okay, i saved your Bitmex secret. Make sure you also set the key\n/set_bitmex_key\n\nIf you set both you can use:\n/toggle_bitmex\n/show_bitmex_position"
                                log(message)
                                messages.append(message)
                                mon_loop = 50
                            else:
                                ## The user did not give a valid value for the Bitmex key so ask him
                                ask_bitmex_secret = True
                                userlist[find_user_index]["ask_bitmex_secret"] = True
                                message = "Tell me your Bitmex API secret. Be sure you created a read-only API key on Bitmex."
                                messages.append(message)
                                log(message)

                        ## Listen for Deribit toggle command
                        if splitted[0] == "/toggle_deribit":
                            ## Check if the API settings are there
                            if deribit_key and deribit_secret:
                                ## Deactivate Deribit if it is enabled
                                if deribit_active:
                                    deribit_active = False
                                    userlist[find_user_index]["deribit_active"] = False
                                    config.set(str(check_user), "deribit_active", "False")
                                    write_config = True
                                    message = "Deribit disabled"
                                    messages.append(message)
                                ## Enable Deribit if it is disabled
                                else:
                                    deribit_client = get_deribit_client(deribit_testnet, deribit_key, deribit_secret)
                                    if deribit_client:
                                        userlist[find_user_index]["deribit_client"] = deribit_client
                                        deribit_active = True
                                        userlist[find_user_index]["deribit_active"] = True
                                        config.set(str(check_user), "deribit_active", "True")
                                        write_config = True
                                        message = "Deribit enabled"
                                        messages.append(message)
                                    else:
                                        message = "You might need to set your API key and Secret:\n/set_deribit_key\n/set_deribit_secret\nAfter that, try again!"
                                        log(message)
                                        messages.append(message)
                            else:
                                message = "You need to set your API key and Secret:\n/set_deribit_key\n/set_deribit_secret"
                                log(message)
                                messages.append(message)

                        ## The user wants to change his Deribit API Key
                        if splitted[0] == "/set_deribit_key":
                            if len(splitted) > 1:
                                ## Look for a valid value for the new price steps
                                ## Only clue we have it has to be 24 chars long
                                if len(splitted[1]) == 8:
                                    deribit_key = str(splitted[1])
                                    config.set(str(check_user), 'deribit_api_key', deribit_key)
                                    write_config = True
                                    userlist[find_user_index]["deribit_key"] = deribit_key
                                    message = "Okay, i saved your Deribit key. Make sure to set also the secret\n/set_deribit_secret.\n\nIf you set both you can use:\n/toggle_deribit\n/show_deribit_position"
                                    log(message)
                                    messages.append(message)
                                    mon_loop = 50
                                else:
                                    ## The user did not give a valid value for the Deribit key so ask him
                                    ask_deribit_key = True
                                    userlist[find_user_index]["ask_deribit_key"] = True
                            else:
                                ## The user did not give a valid value for the Deribit key so ask him
                                ask_deribit_key = True
                                userlist[find_user_index]["ask_deribit_key"] = True
                        ## If the user got asked for the Deribit key, look for the answer
                        if ask_deribit_key:
                            ## Look for a valid value for the Deribit key
                            ## Only clue we have it has to be 24 chars long
                            if len(splitted[0]) == 8:
                                deribit_key = str(splitted[0])
                                config.set(str(check_user), 'deribit_api_key', deribit_key)
                                write_config = True
                                ask_deribit_key = False
                                userlist[find_user_index]["ask_deribit_key"] = False
                                userlist[find_user_index]["deribit_key"] = deribit_key
                                message = "Okay, i saved your Deribit key. Make sure you also set the secret\n/set_deribit_secret.\n\nIf you set both you can use:\n/toggle_deribit\n/show_deribit_position"
                                log(message)
                                messages.append(message)
                                mon_loop = 50
                            else:
                                ## The user did not give a valid value for the Deribit key so ask him
                                ask_deribit_key = True
                                userlist[find_user_index]["ask_deribit_key"] = True
                                message = "Tell me your Deribit API key. Be sure you created a read-only API Key on Deribit."
                                messages.append(message)
                                log(message)

                        ## The user wants to change his Deribit API secret
                        if splitted[0] == "/set_deribit_secret":
                            if len(splitted) > 1:
                                ## Look for a valid value for the Deribit API secret
                                ## Only clue we have it has to be 48 chars long
                                if len(splitted[1]) == 43:
                                    deribit_key = str(splitted[1])
                                    config.set(str(check_user), 'deribit_secret', deribit_secret)
                                    write_config = True
                                    userlist[find_user_index]["deribit_secret"] = deribit_secret
                                    message = "Okay, i saved your Deribit secret. Make sure to set also the key\n/set_deribit_key.\n\nIf you set both you can use:\n/toggle_deribit\n/show_deribit_position"
                                    log(message)
                                    messages.append(message)
                                    mon_loop = 50
                                else:
                                    ## The user did not give a valid value for the Deribit secret so ask him
                                    ask_deribit_secret = True
                                    userlist[find_user_index]["ask_deribit_secret"] = True
                            else:
                                ## The user did not give a valid value for the Deribit secret so ask him
                                ask_deribit_secret = True
                                userlist[find_user_index]["ask_deribit_secret"] = True
                        ## If the user got asked for the Deribit secret, look for the answer
                        if ask_deribit_secret:
                            ## Look for a valid value for the Deribit secret
                            ## Only clue we have it has to be 48 chars long
                            if len(splitted[0]) == 43:
                                deribit_secret = str(splitted[0])
                                config.set(str(check_user), 'deribit_secret', deribit_secret)
                                write_config = True
                                ask_deribit_secret = False
                                userlist[find_user_index]["ask_deribit_secret"] = False
                                userlist[find_user_index]["deribit_secret"] = deribit_secret
                                message = "Okay, i saved your Deribit secret. Make sure you also set the key\n/set_deribit_key\n\nIf you set both you can use:\n/toggle_deribit\n/show_deribit_position"
                                log(message)
                                messages.append(message)
                                mon_loop = 50
                            else:
                                ## The user did not give a valid value for the Deribit key so ask him
                                ask_deribit_secret = True
                                userlist[find_user_index]["ask_deribit_secret"] = True
                                message = "Tell me your Deribit API secret. Be sure you created a read-only API key on Deribit."
                                messages.append(message)
                                log(message)

                        ## Tell the user the Bitmex price
                        if splitted[0] == "/show_bitmex_price":
                            message = "The BTC price is: " + str(price_bitmex) + " USD"
                            log(message)
                            messages.append(message)

                        ## Tell the user the Deribit price
                        if splitted[0] == "/show_deribit_price":
                            message = "The BTC price is: " + str(price_deribit) + " USD"
                            log(message)
                            messages.append(message)

                        ## Toggle Bitmex Testnet
                        if splitted[0] == "/toggle_bitmex_testnet":
                            if bitmex_testnet:
                                bitmex_testnet = False
                                userlist[find_user_index]["bitmex_testnet"] = False
                                config.set(str(check_user), 'bitmex_testnet', bitmex_testnet)
                                write_config = True
                                message = "Activated Mainnet  - make sure to set the right API Keys\nUse /toggle_bitmex afterwards!"
                                log(message)
                                messages.append(message)
                            else:
                                bitmex_testnet = True
                                userlist[find_user_index]["bitmex_testnet"] = True
                                config.set(str(check_user), 'bitmex_testnet', bitmex_testnet)
                                write_config = True
                                message = "Activated Testnet - make sure to set the right API Keys\nUse /toggle_bitmex afterwards!"
                                log(message)
                                messages.append(message)

                        ## Toggle Deribit Testnet
                        if splitted[0] == "/toggle_deribit_testnet":
                            if bitmex_testnet:
                                deribit_testnet = False
                                userlist[find_user_index]["deribit_testnet"] = False
                                config.set(str(check_user), 'deribit_testnet', deribit_testnet)
                                write_config = True
                                message = "Activated Mainnet  - make sure to set the right API Keys\nUse /toggle_deribit afterwards!"
                                log(message)
                                messages.append(message)
                            else:
                                deribit_testnet = True
                                userlist[find_user_index]["deribit_testnet"] = True
                                config.set(str(check_user), 'deribit_testnet', deribit_testnet)
                                write_config = True
                                message = "Activated Testnet - make sure to set the right API Keys\nUse /toggle_deribit afterwards!"
                                log(message)
                                messages.append(message)

                        ## Toggle reporting
                        if splitted[0] == "/toggle_report":
                            if report_active:
                                report_active = False
                                userlist[find_user_index]["report_active"] = False
                                config.set(str(check_user), 'report_active', report_active)
                                write_config = True
                                message = "Deactivated reporting!"
                                log(message)
                                messages.append(message)
                                ## Let the other user know that the user deactivated the reporting
                                message_report = str(username) + " deactivated reporting!"
                                log(message_report)
                                send_message(report_chan, message_report)
                            else:
                                report_active = True
                                userlist[find_user_index]["report_active"] = True
                                config.set(str(check_user), 'report_active', report_active)
                                write_config = True
                                message = "Activated reporting!"
                                log(message)
                                messages.append(message)
                                ## Let the other user know that the user activated the reporting
                                message_report = str(username) + " activated reporting!"
                                log(message_report)
                                send_message(report_chan, message_report)

                        ## Listen for tx IDs
                        if len(splitted[0]) == 64:
                            tx_to_check = splitted[0]
                            tx_status = tx_checker(tx_to_check, "blockchair")
                            if tx_status[0] == "confirmed":
                                message = tx_status[1]
                                log(message)
                                messages.append(message)
                            else:
                                message = "Your TX is not confirmed yet. I will let you know when it is."
                                log(message)
                                messages.append(message)
                                ## Look up position in queue
                                message = tx_status[1]
                                log(message)
                                messages.append(message)
                                ## Tell the user the /show_tx_position command
                                message = "You can use /show_tx_position to get the up-to-date position of our tx in mempool"
                                log(message)
                                messages.append(message)
                                ## Watch TX
                                config.set(str(check_user), 'tx_to_check', tx_to_check)
                                write_config = True
                                userlist[find_user_index]["tx_to_check"] = tx_to_check

                        if splitted[0] == "/show_tx_position":
                            if tx_to_check == "confirmed":
                                message = "No TX to check, please send me the TX hash."
                                log(message)
                                messages.append(message)
                            else:
                                tx_status = tx_checker(tx_to_check, "blockchair")
                                message = tx_status[1]
                                log(message)
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
                            log("Sending collected messages to the chat: " + str(check_user))
                            all_messages = ""
                            for x in messages:
                                all_messages = all_messages + "\n" + x
                            send_message(check_user, all_messages)
                            messages = []

                    ## Discard all other messages
                    except KeyError:
                        log("Another type of message received")

            ## Set new offset to acknowledge messages on the telegram api
            offset = str(bot_messages_json["result"][message_amount - 1]["update_id"] + 1)

        ## Loop things
        mon_loop = mon_loop + 1
        bot_restarted = False
        sleep(1)

        #####################
        ## End of mon loop ##
        #####################

        ## Check if we run out of Bitmex API calls. We can do (300 in x seconds)
        if bitmex_rate_limit < 50:
            ## Send message to the admin user (first user)
            message = "Bitmex API calls remaining = " + str(bitmex_rate_limit)
            send_message(userlist[0]["user_chat_id"], message)
            log(message)
            log("Reported to Admin: " + str(userlist[0]["user_chat_id"]))

    ######################
    ## End of main loop ##
    ######################
