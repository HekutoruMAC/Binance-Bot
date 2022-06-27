# Megatronmod Strategy - All in One
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
import operator
#from math import exp, cos
#from analysis_buffer import AnalysisBuffer
#from helpers.os_utils import(rchop)
from helpers.parameters import parse_args, load_config
#import pandas
import pandas as pd
import pandas_ta as pta
import ccxt
import requests
import talib as ta 
#import pandas_datareader.data as web
#from talib import RSI, BBANDS, MACD
#import matplotlib.pyplot as plt
import re
import json

# Load creds modules
from helpers.handle_creds import (
	load_correct_creds, load_discord_creds
)

# Settings
args = parse_args()
DEFAULT_CONFIG_FILE = 'config.yml'
DEFAULT_CREDS_FILE = 'creds.yml'

config_file = args.config if args.config else DEFAULT_CONFIG_FILE
creds_file = args.creds if args.creds else DEFAULT_CREDS_FILE
parsed_creds = load_config(creds_file)
parsed_config = load_config(config_file)

USE_MOST_VOLUME_COINS = parsed_config['trading_options']['USE_MOST_VOLUME_COINS']
PAIR_WITH = parsed_config['trading_options']['PAIR_WITH']
SELL_ON_SIGNAL_ONLY = parsed_config['trading_options']['SELL_ON_SIGNAL_ONLY']
TEST_MODE = parsed_config['script_options']['TEST_MODE']
LOG_FILE = parsed_config['script_options'].get('LOG_FILE')
COINS_BOUGHT = parsed_config['script_options'].get('COINS_BOUGHT')
STOP_LOSS = parsed_config['trading_options']['STOP_LOSS']
TAKE_PROFIT = parsed_config['trading_options']['TAKE_PROFIT']
TRADE_SLOTS = parsed_config['trading_options']['TRADE_SLOTS']

# Load creds for correct environment
access_key, secret_key = load_correct_creds(parsed_creds)
client = Client(access_key, secret_key)

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

global bought, timeHold, CREATE_BUY_SELL_FILES

if USE_MOST_VOLUME_COINS == True:
    TICKERS = "volatile_volume_" + str(date.today()) + ".txt"
else:
    TICKERS = 'tickers.txt'

TIME_TO_WAIT = 1
CREATE_BUY_SELL_FILES = True
DEBUG = True

SIGNAL_NAME = 'megatronmod'

MINUS = 25
MORE = 25

RSI_MAX_RSI5 = 80 - MINUS
RSI_MIN_RSI5 = 20 + MORE

RSI_MAX_RSI10 = 75 - MINUS
RSI_MIN_RSI10 = 25 + MORE

RSI_MAX_RSI15 = 70 - MINUS
RSI_MIN_RSI15 = 30 + MORE

RSI_MIN = 12 # Min RSI Level for Buy Signal - Under 25 considered oversold (12)
RSI_MAX = 55 # Max RSI Level for Buy Signal - Over 80 considered overbought (55)

RSI_BUY = 0.3 # Difference in RSI levels over last 2 timescales for a Buy Signal (-0.3)

RSI1_MIN = 10
RSI1_MAX = 90

RSI2_MIN = 40
RSI2_MAX = 70

STOCH_SELL = 80
STOCH_BUY = 5
STOCH_MIN = 30
STOCH_MAX = 60

cci_min = -200
cci_max = 200
            
SIGNAL_FILE_BUY = 'signals/' + SIGNAL_NAME + '.buy'
SIGNAL_FILE_SELL ='signals/' + SIGNAL_NAME + '.sell'
JSON_FILE_BOUGHT = SIGNAL_NAME + '.json'

def write_log(logline, LOGFILE = LOG_FILE, show = True):
    try:
        if TEST_MODE:
            file_prefix = 'test_'
        else:
            file_prefix = 'live_'
            
        with open(file_prefix + LOGFILE,'a') as f:
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            result = ansi_escape.sub('', logline)
            if show == False:
                timestamp = datetime.now().strftime("%y-%m-%d %H:%M:%S")
                f.write(timestamp + ',' + result + '\n')            
                #timestamp = str(datetime.timestamp(datetime.now()))
                #f.write("time:" + timestamp + ',' + result + '\n')
            else:
                timestamp = datetime.now().strftime("%y-%m-%d %H:%M:%S")
                f.write(timestamp + ' ' + result + '\n')
        if show:
            print(f'{logline}')
    except Exception as e:
        print(f'{"write_log"}: Exception in function: {e}')
        print("Error on line {}".format(sys.exc_info()[-1].tb_lineno))
        exit(1)
        
def get_analysis(tf, p):
    #exchange = ccxt.binance()
    #data = exchange.fetch_ohlcv(p, timeframe=tf, limit=100)
    data = client.get_historical_klines(symbol=p, interval=tf, start_str=str(100) + 'min ago UTC')
    c = pd.DataFrame(data, columns=['time',
                                    'Open',
                                    'High',
                                    'Low',
                                    'Close',
                                    'Volume',
                                    'Close time',
                                    'Quote asset volume',
                                    'Number of trades',
                                    'Taker buy base asset volume',
                                    'Taker buy quote asset volume',
                                    'Ignore'])
    c = c.drop(c.columns[[6, 7, 8, 9, 10, 11]], axis=1)
    c['time'] = pd.to_datetime(c['time'], unit='ms')
    c.set_index(pd.DatetimeIndex(c['time']), inplace=True)
    return c 
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

def load_json(p):
    try:
        bought_COIN1MIN = {}
        value1 = 0
        value2 = 0
        value3 = 0
        if TEST_MODE:
            file_prefix = 'test_'
        else:
            file_prefix = 'live_'
        coins_bought_file_path = file_prefix + COINS_BOUGHT
        if os.path.exists(coins_bought_file_path) and os.path.getsize(coins_bought_file_path) > 2:
            with open(coins_bought_file_path,'r') as f:
                bought_COIN1MIN = json.load(f)

            for COIN1MIN in bought_COIN1MIN.keys():
                value3 = value3 + 1
                
            if p in bought_COIN1MIN:
                value1 = round(float(bought_COIN1MIN[p]['bought_at']),5)
                value2 = round(float(bought_COIN1MIN[p]['timestamp']),5)
                bought_COIN1MIN = {}
    except Exception as e:
        print(f'{SIGNAL_NAME}: {txcolors.Red} {"load_json"}: Exception in function: {e}')
        print("Error on line {}".format(sys.exc_info()[-1].tb_lineno))
   
    return value1, value2, value3

# def crossunder(arr1, arr2):
    # if arr1 != arr2:
        # if arr1 > arr2 and arr2 < arr1:
            # CrossUnder = True
        # else:
            # CrossUnder = False
    # else:
        # CrossUnder = False
    # return CrossUnder

# def crossover(arr1, arr2):
    # if arr1 != arr2:
        # if arr1 < arr2 and arr2 > arr1:
            # CrossOver = True
        # else:
            # CrossOver = False
    # else:
        # CrossOver = False
    # return CrossOver
    
# def cross(arr1, arr2):
    # if round(arr1,5) == round(arr2,5):
        # Cross = True
    # else:
        # Cross = False
    # return Cross

def TA_HMA(close, period):
    hma = ta.WMA(2 * ta.WMA(close, int(period / 2)) - ta.WMA(close, period), int(np.sqrt(period)))
    return hma
    
def CCI(self, period: int, bars: list):
	self.check_bars_type(bars)
	cci = ta.CCI(bars['high'], bars['low'], bars['close'], timeperiod=period)
	return cci

def isfloat(num):
    try:
        float(num)
        return True
    except ValueError:
        return False
        
def print_dic(dic, with_key=False):
    try:
        str1 = ""
        for key, value in dic.items():
            if with_key == False:
                if isfloat(value):
                    str1 = str1 + str(round(float(value),5)) + ","
                else:
                    str1 = str1 + str(value) + ","
            else:
                if isfloat(value):    
                    str1 = str1 + str(key) + ":" + str(round(float(value),5)) + ","
                else:
                    str1 = str1 + str(key) + ":" + str(value) + ","
        if with_key == False: str1 = str1[:-1].replace("[","").replace("]","")
    except Exception as e:
        print(f'{SIGNAL_NAME}: {txcolors.Red} {"print_dic"}: Exception in function: {e}')
        print("Error on line {}".format(sys.exc_info()[-1].tb_lineno))
    return str1[:-1]
    
def list_indicators():
    try:
        list_variables = {}
        all_variables = dir()
        for name in all_variables:
            if name.endswith("_1MIN") or name.endswith("_5MIN"):
                myvalue = round(float(eval(name)), 5)
                list_variables = {name : myvalue}
    except Exception as e:
        print(f'{SIGNAL_NAME}: {txcolors.Red} {"list_indicators"}: Exception in function: {e}')
        print("Error on line {}".format(sys.exc_info()[-1].tb_lineno))             
    return list_variables
    
def analyze(pairs, ext_data="", buy= True):
    signal_coins = {}
    analysis5MIN = {}
    handler5MIN = {}
    analysis15MIN = {}
    handler15MIN = {}
    analysis1MIN = {}
    handler1MIN = {}
    buySignal = {}
    buySignalData = {}
    dataBuy = {}
    dataSell = {}
    sellSignal = {}

    if os.path.exists(SIGNAL_FILE_BUY ):
        os.remove(SIGNAL_FILE_BUY )
    
    for pair in pairs:
        handler15MIN[pair] = TA_Handler(
            symbol=pair,
            exchange=EXCHANGE,
            screener=SCREENER,
            interval="15m",
            timeout= 10)
            
        handler5MIN[pair] = TA_Handler(
            symbol=pair,
            exchange=EXCHANGE,
            screener=SCREENER,
            interval="5m",
            timeout= 10)
            
        handler1MIN[pair] = TA_Handler(
            symbol=pair,
            exchange=EXCHANGE,
            screener=SCREENER,
            interval="1m",
            timeout= 10)
    
    if os.path.exists(SIGNAL_FILE_BUY) and ext_data == False:
        os.remove(SIGNAL_FILE_BUY )
              
    print(f'{SIGNAL_NAME}: {txcolors.BUY}Analyzing {len(pairs)} coins...{txcolors.DEFAULT}')
    for pair in pairs:
        #print(f'{SIGNAL_NAME}: {txcolors.BUY}Analyzing {pair} ...{txcolors.DEFAULT}')
        try:
            COIN1MIN = get_analysis('1m', pair)
            analysis1MIN = handler1MIN[pair].get_analysis()
            analysis5MIN = handler5MIN[pair].get_analysis()
            analysis15MIN = handler15MIN[pair].get_analysis()
            CLOSE = round(float(COIN1MIN['Close'].iloc[-1]),5)
            
            RSI1_1MIN = round(analysis1MIN.indicators['RSI'],5)
            RSI_5MIN = round(analysis15MIN.indicators['RSI'],5)
            RSI1_15MIN = round(analysis15MIN.indicators['RSI[1]'],5)
            RSI2_1MIN = round(ta.RSI(COIN1MIN['Close'], 2).iloc[-1],5)
            RSI15_1MIN = round(ta.RSI(COIN1MIN['Close'], 15).iloc[-1],5)
            RSI10_1MIN = round(ta.RSI(COIN1MIN['Close'], 10).iloc[-1],5)
            RSI5_1MIN = round(ta.RSI(COIN1MIN['Close'], 5).iloc[-1],5)
            RSI14_5MIN = round(analysis5MIN.indicators['RSI'],5)
            STOCH_K_5MIN = round(analysis5MIN.indicators['Stoch.K'],5)
            STOCH_D_5MIN = round(analysis5MIN.indicators['Stoch.D'],5)
            STOCH_K_1MIN = round(analysis1MIN.indicators['Stoch.K'],5)
            STOCH_D_1MIN = round(analysis1MIN.indicators['Stoch.D'],5)            
            EMA2_1MIN = round(pta.ema(COIN1MIN['Close'], length=2).iloc[-1],5)
            EMA3_1MIN = round(pta.ema(COIN1MIN['Close'], length=3).iloc[-1],5)
            EMA9_1MIN = round(pta.ema(COIN1MIN['Close'], length=9).iloc[-1],5)
            EMA21_1MIN = round(pta.ema(COIN1MIN['Close'], length=21).iloc[-1],5)
            EMA23_1MIN = round(pta.ema(COIN1MIN['Close'], length=23).iloc[-1],5)
            EMA25_1MIN = round(pta.ema(COIN1MIN['Close'], length=25).iloc[-1],5)
            HMA90_1MIN = round(TA_HMA(COIN1MIN['Close'],90).iloc[-1],5)
            HMA70_1MIN = round(TA_HMA(COIN1MIN['Close'],70).iloc[-1],5)
            CCI20_1MIN =  round(COIN1MIN.ta.cci(length=20).iloc[-1],5)
            CCI14_1MIN =  round(COIN1MIN.ta.cci(length=14).iloc[-1],5)
            SMA7_1MIN = round(pta.sma(COIN1MIN['Close'],length=7).iloc[-1],5)
            SMA25_1MIN = round(pta.sma(COIN1MIN['Close'],length=25).iloc[-1],5)
            SMA55_1MIN = round(pta.sma(COIN1MIN['Close'],length=55).iloc[-1],5)
            SMA5_1MIN = round(analysis1MIN.indicators['SMA5'],5)
            SMA10_1MIN = round(analysis1MIN.indicators['SMA10'],5)            
            SMA20_1MIN = round(analysis1MIN.indicators['SMA20'],5)
            SMA100_1MIN = round(analysis1MIN.indicators['SMA100'],5)
            SMA200_1MIN = round(analysis1MIN.indicators['SMA200'],5)
            MACD_1MIN = round(analysis1MIN.indicators["MACD.macd"],5)
            SMA5_5MIN = round(analysis5MIN.indicators['SMA5'],5)
            SMA10_5MIN = round(analysis5MIN.indicators['SMA10'],5)                                                   
            SMA20_5MIN = round(analysis5MIN.indicators['SMA20'],5)
            SMA100_5MIN = round(analysis5MIN.indicators['SMA100'],5)
            SMA200_5MIN = round(analysis5MIN.indicators['SMA200'],5)
            MACD_5MIN = round(analysis1MIN.indicators["MACD.macd"],5)            
            STOCH_DIFF_1MIN = round(STOCH_K_1MIN - STOCH_D_1MIN,5)

            list_variables = {}
            all_variables = dir()
            for name in all_variables:
                if name.endswith("_1MIN") and not name.startswith("SMA") and not name.startswith("EMA"):
                    myvalue = eval(name)
                    list_variables.update({name : myvalue})
            list_variables_sort = {}
            list_variables_sort = dict(sorted(list_variables.items(), key=operator.itemgetter(1), reverse=True))
            #print_dic(list_variables_sort)
            
            bought_at, timeHold, coins_bought = load_json(pair)            
            if coins_bought < TRADE_SLOTS and bought_at == 0:
                buySignal0 = str(RSI14_5MIN <= 40 and STOCH_K_5MIN <= 20 and STOCH_D_5MIN <= 20)
                buySignal1 = str((EMA2_1MIN > EMA3_1MIN) and (RSI2_1MIN < 45) and (STOCH_K_5MIN > STOCH_D_5MIN) and (STOCH_K_5MIN < 70 and STOCH_D_5MIN < 70))
                buySignal2 = str(RSI10_1MIN < RSI_MIN_RSI10 and RSI5_1MIN < RSI_MIN_RSI5 and RSI15_1MIN < RSI_MIN_RSI15)
                buySignal3 = str(cross(EMA9_1MIN, EMA21_1MIN) and (CLOSE > HMA90_1MIN))
                buySignal4 = str((SMA10_1MIN > SMA20_1MIN) and (SMA20_1MIN > SMA200_1MIN) and (MACD_1MIN <= 30))
                buySignal5 = str((SMA5_1MIN > SMA10_1MIN > SMA20_1MIN) and (RSI_5MIN >= RSI_MIN and RSI_5MIN <= RSI_MAX))
                buySignal6 = str(RSI10_1MIN <= RSI1_1MIN)
                buySignal7 = str((MACD_1MIN < 0) and (RSI_5MIN < 50))
                buySignal8 = str(crossover(RSI2_1MIN, RSI1_1MIN))
                buySignal9 = str((STOCH_DIFF_1MIN >= STOCH_BUY) and (STOCH_K_1MIN >= STOCH_MIN and STOCH_K_1MIN <= STOCH_MAX) and (STOCH_D_1MIN >= STOCH_MIN and STOCH_D_1MIN <= STOCH_MAX) and (RSI10_1MIN >= RSI2_MIN))
                buySignal10 = str(RSI14_5MIN <= 40 and STOCH_K_5MIN <= 20 and STOCH_D_5MIN <= 20)
                buySignal11 = str(CLOSE > SMA200_1MIN and CLOSE < SMA5_1MIN and RSI2_1MIN < 10)
                buySignal12 = str((RSI2_1MIN < 30) and (STOCH_K_1MIN > STOCH_D_1MIN) and (STOCH_K_1MIN < 50 and STOCH_D_1MIN < 50))
                buySignal13 = crossover(CCI20_1MIN,cci_min)
                
                dataBuy = {'buySignal0': buySignal0, 'buySignal1': buySignal1, 'buySignal2': buySignal2, 'buySignal3': buySignal3, 'buySignal4': buySignal4, 'buySignal5': buySignal5, 'buySignal6': buySignal6, 'buySignal7': buySignal7, 'buySignal8': buySignal8, 'buySignal9': buySignal9, 'buySignal10': buySignal10, 'buySignal11': buySignal11, 'buySignal12': buySignal12, 'buySignal13': buySignal13}
                for buyM in dataBuy:
                    if dataBuy[buyM] == 'True':
                        #COIN1MIN = get_analysis('1m', "BTC" + PAIR_WITH)
                        #CLOSEBTC1MIN = float(COIN1MIN['Close'].iloc[-1])
                        buySignal = {'bought_at': CLOSE} #, 'BTC': CLOSEBTC1MIN }
                        signal_coins[pair] = pair
                        #write_log(json.dumps(buySignal, indent=4), SIGNAL_NAME + ".buy", False)
                        if ext_data != "" and buy == True:
                            #print("Guardando datos...")
                            write_log(f'OrderID:{ext_data},type:BUY,pair:{pair.replace(PAIR_WITH,"")},{print_dic(buySignal, True)},{print_dic(list_variables_sort, True)}', SIGNAL_NAME + ".buy", False)
                            break
                        else:
                            buySignal = {}
                            dataBuy = {}
                            with open(SIGNAL_FILE_BUY,'a+') as f:
                                f.write(pair + '\n') 
                            break
                
            #print(f'{SIGNAL_NAME}: {txcolors.BUY}{json.dumps(dataBuy, indent=4)}{txcolors.DEFAULT}')        
            #print(json.dumps(buySignal, indent=4))
            
            if SELL_ON_SIGNAL_ONLY == True:
                bought_at, timeHold, coins_bought = load_json(pair)
                if float(bought_at) != 0 and float(coins_bought) != 0 and float(CLOSE) != 0:
                    SL = float(bought_at) - ((float(bought_at) * float(STOP_LOSS)) / 100) 
                    TP = float(bought_at) + ((float(bought_at) * float(TAKE_PROFIT)) / 100)
                    
                    TP_sell = str(float(CLOSE) > float(TP) and float(TP) != 0 and float(CLOSE) > float(bought_at))
                    SL_sell = str(float(CLOSE) < float(SL) and float(SL) != 0)                    
                    sellSignal0 = str(RSI14_5MIN >= 70 and STOCH_K_5MIN >= 80 and STOCH_D_5MIN >= 80 and float(CLOSE) > float(bought_at))
                    sellSignal1 = str(RSI10_1MIN > RSI_MAX_RSI10 and RSI5_1MIN > RSI_MAX_RSI5 and RSI15_1MIN > RSI_MAX_RSI15 and float(CLOSE) > float(bought_at))
                    sellSignal2 = str(RSI2_1MIN > 80 and float(CLOSE) > float(bought_at))
                    sellSignal3 = str((CLOSE < HMA90_1MIN and float(CLOSE) > float(bought_at)))  
                    sellSignal4 = str(RSI10_1MIN >= RSI1_MAX and float(CLOSE) > float(bought_at))
                    sellSignal5 = str(crossunder(RSI2_1MIN, RSI1_MAX) and float(CLOSE) > float(bought_at))
                    sellSignal6 = str(crossunder(STOCH_D_1MIN, STOCH_SELL) and float(CLOSE) > float(bought_at))
                    sellSignal7 = str(RSI2_1MIN > 75 and float(CLOSE) > float(bought_at))
                    sellSignal8 = str(CCI20_1MIN > 100 and float(CLOSE) > float(bought_at))
                    
                    print("sellSignal2", sellSignal2)
                    
                    dataSell = {'TP': TP_sell, 'SL': SL_sell, 'sellSignal0': sellSignal0, 'sellSignal1': sellSignal1, 'sellSignal2': sellSignal2, 'sellSignal3': sellSignal3, 'sellSignal4': sellSignal4, 'sellSignal5': sellSignal5, 'sellSignal6': sellSignal6, 'sellSignal7': sellSignal8, 'sellSignal7': sellSignal8}
                    for sellM in dataSell:
                        if dataSell[sellM] == 'True' and float(bought_at) != 0:
                            #COIN1MIN = get_analysis('1m', "BTC" + PAIR_WITH)
                            #CLOSEBTC1MIN = float(COIN1MIN['Close'].iloc[-1])
                            sellSignal = {'sell_at': CLOSE , 'bought_at': bought_at , 'earned': round(CLOSE - bought_at, 4)} #,'BTC': CLOSEBTC1MIN}
                            if ext_data != "" and buy == False:
                                write_log(f'OrderID:{ext_data},type:SELL,pair:{pair.replace(PAIR_WITH,"")},{print_dic(sellSignal, True)},{print_dic(list_variables_sort, True)}', SIGNAL_NAME + ".sell", False)
                                sellSignal = {}
                                dataSell = {}
                            else:
                                with open(SIGNAL_FILE_SELL,'a+') as f:
                                    f.write(pair + '\n')
                                break
                    #print(json.dumps(sellSignal, indent=4))                    
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
    #print(pairs)
    while True:
        try:
            if not threading.main_thread().is_alive(): exit()
            print(f'Signals {SIGNAL_NAME}: Analyzing {len(pairs)} coins{txcolors.DEFAULT}')
            signal_coins = analyze(pairs)
            if len(signal_coins) > 0:
                print(f'Signals {SIGNAL_NAME}: {len(signal_coins)} coins of {len(pairs)} with Buy Signals. Waiting {TIME_TO_WAIT} minutes for next analysis.{txcolors.DEFAULT}')
                time.sleep(TIME_TO_WAIT*10)
            else:
                print(f'Signals {SIGNAL_NAME}: {len(signal_coins)} coins of {len(pairs)} with Buy Signals. Waiting for next analysis.{txcolors.DEFAULT}')
                time.sleep(TIME_TO_WAIT*5)
        except Exception as e:
            print(f'{SIGNAL_NAME}: {txcolors.Red}: Exception do_work(): {e}{txcolors.DEFAULT}')
            pass
        except KeyboardInterrupt as ki:
            pass