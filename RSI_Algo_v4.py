# RSI_Algo_v4 Stochastic and RSI Strategy
# Created by: Horacio Oscar Fanelli - Pantersxx3 and NokerPlay
# This mod can be used only with:
# https://github.com/pantersxx3/Binance-Bot
#
# No future support offered, use this script at own risk - test before using real funds
# If you lose money using this MOD (and you will at some point) you've only got yourself to blame!

from tradingview_ta import TA_Handler, Interval, Exchange
from binance.client import Client, BinanceAPIException
import os
import sys
import glob
from datetime import date, datetime, timedelta
import time
import threading
import array
import statistics
import numpy as np
from math import exp, cos
from analysis_buffer import AnalysisBuffer
from helpers.os_utils import(rchop)
from helpers.parameters import parse_args, load_config
import pandas
import pandas as pd
import pandas_ta as ta
import pandas_ta as pta
import ccxt
import requests
import talib as ta 
import pandas_datareader.data as web
from talib import RSI, BBANDS
import matplotlib.pyplot as plt
import re
import json

args = parse_args()
DEFAULT_CONFIG_FILE = 'config.yml'

config_file = args.config if args.config else DEFAULT_CONFIG_FILE
parsed_config = load_config(config_file)

USE_MOST_VOLUME_COINS = parsed_config['trading_options']['USE_MOST_VOLUME_COINS']
PAIR_WITH = parsed_config['trading_options']['PAIR_WITH']
SELL_ON_SIGNAL_ONLY = parsed_config['trading_options']['SELL_ON_SIGNAL_ONLY']
TEST_MODE = parsed_config['script_options']['TEST_MODE']
LOG_FILE = parsed_config['script_options'].get('LOG_FILE')
COINS_BOUGHT = parsed_config['script_options'].get('COINS_BOUGHT')

INTERVAL1MIN = Interval.INTERVAL_1_MINUTE

RSI_MIN = 40
RSI_MAX = 70

STOCH_MIN = 20
STOCH_MAX = 60
STOCH_BUY = 5
#if after n seconds the coin was not sold exceeding RSI_MAX it will be sold at the same purchase value or a little more
TIME_MAX = 2700 # 45 minutes

class txcolors:
    BUY = '\033[92m'
    WARNING = '\033[93m'
    SELL_LOSS = '\033[91m'
    SELL_PROFIT = '\033[32m'
    DIM = '\033[2m\033[35m'
    Red = "\033[31m"
    DEFAULT = '\033[39m'
    
EXCHANGE = 'BINANCE'
SCREENER = 'CRYPTO'

global bought, timeHold

if USE_MOST_VOLUME_COINS == True:
    TICKERS = "volatile_volume_" + str(date.today()) + ".txt"
else:
    TICKERS = 'tickers.txt'

TIME_TO_WAIT = 1
FULL_LOG = False
DEBUG = True

SIGNAL_NAME = 'RSI_Algo'
SIGNAL_FILE_BUY = 'signals/' + SIGNAL_NAME + '.buy'
SIGNAL_FILE_SELL ='signals/' + SIGNAL_NAME + '.sell'
JSON_FILE_BOUGHT = SIGNAL_NAME + '.json'

def write_log(logline):
    try:
        timestamp = datetime.now().strftime("%y-%m-%d %H:%M:%S")
        if TEST_MODE:
            file_prefix = 'test_'
        else:
            file_prefix = 'live_'
            
        with open(file_prefix + LOG_FILE,'a') as f:
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            result = ansi_escape.sub('', logline)
            f.write(timestamp + ' ' + result + '\n')
        print(f'{logline}')
    except Exception as e:
        print(f'{"write_log"}: Exception in function: {e}')
        print("Error on line {}".format(sys.exc_info()[-1].tb_lineno))
        exit(1)
        
def crossunder(arr1, arr2):
    if arr1 != arr2:
        if arr1 > arr2 and arr2 < arr1:
            CrossUnder = True
        else:				
            CrossUnder = False
    else:
        CrossUnder = False
    return CrossUnder

def crossover(arr1, arr2):
    if arr1 != arr2:
        if arr1 < arr2 and arr2 > arr1:
            CrossOver = True
        else:				
            CrossOver = False
    else:
        CrossOver = False
    return CrossOver
    
def cross(arr1, arr2):
    if round(arr1,5) == round(arr2,5):
        Cross = True
    else:				
        Cross = False
    return Cross
    
def get_analysis(tf, p):
    exchange = ccxt.binance()
    data = exchange.fetch_ohlcv(p, timeframe=tf, limit=25)
    c = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    return c 

def load_json(p):
    try:
        bought_coin = {}
        value1 = 0
        value2 = 0
        if TEST_MODE:
            file_prefix = 'test_'
        else:
            file_prefix = 'live_'
        coins_bought_file_path = file_prefix + COINS_BOUGHT
        if os.path.exists(coins_bought_file_path) and os.path.getsize(coins_bought_file_path) > 2:
            with open(coins_bought_file_path,'r') as f:
                bought_coin = json.load(f)
            if p in bought_coin:
                value1 = round(float(bought_coin[p]['bought_at']),5)
                value2 = round(float(bought_coin[p]['timestamp']),5)
                bought_coin = {}
    except Exception as e:
        print(f'{SIGNAL_NAME}: {txcolors.Red} {"load_json"}: Exception in function: {e}')
        print("Error on line {}".format(sys.exc_info()[-1].tb_lineno))
   
    return value1, value2
    
def analyze(pairs):
    signal_coins = {}
    analysis1MIN = {}
    handler1MIN = {}
    last_price = 0
    
    if os.path.exists(SIGNAL_FILE_BUY ):
        os.remove(SIGNAL_FILE_BUY )

    for pair in pairs:
        handler1MIN[pair] = TA_Handler(
            symbol=pair,
            exchange=EXCHANGE,
            screener=SCREENER,
            interval=INTERVAL1MIN,
            timeout= 10)

    print(f'{SIGNAL_NAME}: {txcolors.BUY}Analyzing {len(pairs)} coins...{txcolors.DEFAULT}')   
    for pair in pairs:
        print(f'{SIGNAL_NAME}: {txcolors.BUY}Analyzing {pair} coin...{txcolors.DEFAULT}') 
        exchange = ccxt.binance()
        try:
            coins = get_analysis('1m', pair)
            analysis1MIN = handler1MIN[pair].get_analysis()

            RSI = coins.ta.rsi(length=10)
            SMA50_1MIN = round(analysis1MIN.indicators['SMA50'],4)
            SMA10_1MIN = round(analysis1MIN.indicators['SMA10'],4)
            SMA20_1MIN = round(analysis1MIN.indicators['SMA20'],4)
            STOCH_K = round(analysis1MIN.indicators['Stoch.K'],2)
            STOCH_D = round(analysis1MIN.indicators['Stoch.D'],2)
            STOCH_K1 = round(analysis1MIN.indicators['Stoch.K[1]'],2)
            STOCH_D1 = round(analysis1MIN.indicators['Stoch.D[1]'],2)
            STOCH_DIFF = round(STOCH_K - STOCH_D,2)
            
            RSI = RSI.iloc[-1]
            CLOSE = round(coins['close'].iloc[-1],5)
            
            print(f'{SIGNAL_NAME}: {txcolors.BUY}{pair} - RSI = {format(RSI,"6f")}{txcolors.DEFAULT} {txcolors.BUY} STOCH_DIFF = {format(STOCH_DIFF,"2f")}{txcolors.DEFAULT}')

            #buySignal = (crossunder(RSI2,RSI_MIN2) and (RSI2 <= RSI_MIN) and (SMA20_1MIN >= SMA50_1MIN))
            buySignal = (STOCH_DIFF >= STOCH_BUY) and (STOCH_K >= STOCH_MIN and STOCH_K <= STOCH_MAX) and (STOCH_D >= STOCH_MIN and STOCH_D <= STOCH_MAX) and crossunder(RSI,RSI_MIN)
            
            if buySignal:
                signal_coins[pair] = pair
                with open(SIGNAL_FILE_BUY,'a+') as f:
                    f.write(pair + '\n')
            
            if SELL_ON_SIGNAL_ONLY == True:
                last_price, timeHold = load_json(pair)
                if last_price != 0:
                    time_held = timedelta(seconds=datetime.now().timestamp()-int(timeHold))
                    if round(time_held.total_seconds(),0) >= TIME_MAX and TIME_MAX != 0:
                        timemax = True
                        sellSignal = CLOSE >= last_price
                    else:
                        timemax = False
                        sellSignal = crossunder(RSI2,RSI_MAX) and last_price !=0 and last_price < CLOSE
                    if sellSignal == True:
                        write_log(f'{SIGNAL_NAME}: {txcolors.BUY}{pair} - Sell Signal Detected RSI10={round(RSI2,5)} last_price={last_price} CLOSE={round(CLOSE,5)} timemax= {round(time_held.total_seconds(),0)}/{timemax} sellSignal= {sellSignal}{txcolors.DEFAULT}')
                        with open(SIGNAL_FILE_SELL,'a+') as f:
                            f.write(pair + '\n')
                
        except Exception as e:
            print(f'{SIGNAL_NAME}: {txcolors.Red} {pair} - Exception: {e}')
            print("Error on line {}".format(sys.exc_info()[-1].tb_lineno))
            pass
    return signal_coins

def do_work():
    signal_coins = {}
    pairs = {}
    pairs=[line.strip() for line in open(TICKERS)]
    for line in open(TICKERS):
        pairs=[line.strip() + PAIR_WITH for line in open(TICKERS)] 
    while True:
        try:
            if not threading.main_thread().is_alive(): exit()
            print(f'Signals {SIGNAL_NAME}: Analyzing {len(pairs)} coins{txcolors.DEFAULT}')
            signal_coins = analyze(pairs)
            if len(signal_coins) > 0:
                print(f'Signals {SIGNAL_NAME}: {len(signal_coins)} coins  of {len(pairs)} with Buy Signals. Waiting {TIME_TO_WAIT} minutes for next analysis.{txcolors.DEFAULT}')
                time.sleep(TIME_TO_WAIT*10)
            else:
                print(f'Signals {SIGNAL_NAME}: {len(signal_coins)} coins  of {len(pairs)} with Buy Signals. Waiting 1 second for next analysis.{txcolors.DEFAULT}')
                time.sleep(1)
        except Exception as e:
            print(f'{SIGNAL_NAME}: {txcolors.Red}: Exception do_work(): {e}{txcolors.DEFAULT}')
            pass
        except KeyboardInterrupt as ki:
            pass
