# -*- coding: utf-8 -*-
"""
Created on Mon Jan 18 12:27:22 2021

@author: io
"""
import datetime as dt
import time
import pandas as pd
import numpy as np
import math
import os.path
import time
import os
import keys
import talib as ta
from datetime import timedelta, datetime
from dateutil import parser
from binance.client import Client


### API
client = Client(keys.APIkey,keys.APIsecret)

### CONSTANTS
binsizes = {"1m": 1, "5m": 5, "1h": 60, "1d": 1440}
batch_size = 750


### FUNCTIONS
def minutes_of_new_data(symbol, kline_size, data, source):
    if len(data) > 0:  old = parser.parse(data["timestamp"].iloc[-1])
    elif source == "binance": old = datetime.strptime('1 Jan 2017', '%d %b %Y')
    if source == "binance": new = pd.to_datetime(client.get_klines(symbol=symbol, interval=kline_size)[-1][0], unit='ms')
    return old, new

def get_all_binance(symbol, kline_size, save = False):
    filename = '%s-%s-data.csv' % (symbol, kline_size)
    if os.path.isfile(filename): data_df = pd.read_csv(filename)
    else: data_df = pd.DataFrame()
    oldest_point, newest_point = minutes_of_new_data(symbol, kline_size, data_df, source = "binance")
    delta_min = (newest_point - oldest_point).total_seconds()/60
    available_data = math.ceil(delta_min/binsizes[kline_size])
    if oldest_point == datetime.strptime('1 Jan 2017', '%d %b %Y'): print('Downloading all available %s data for %s. Be patient..!' % (kline_size, symbol))
    else: print('Downloading %d minutes of new data available for %s, i.e. %d instances of %s data.' % (delta_min, symbol, available_data, kline_size))
    klines = client.get_historical_klines(symbol, kline_size, oldest_point.strftime("%d %b %Y %H:%M:%S"), newest_point.strftime("%d %b %Y %H:%M:%S"))
    data = pd.DataFrame(klines, columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore' ])
    data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
    if len(data_df) > 0:
        temp_df = pd.DataFrame(data)
        data_df = data_df.append(temp_df)
    else: data_df = data
    data_df.set_index('timestamp', inplace=True)
    if save: data_df.to_csv(filename)
    print('All caught up..!')
    return data_df


binance_symbols = ["ETHUSDT"]
for symbol in binance_symbols:
    get_all_binance(symbol, '5m', save = True)
df = pd.read_csv(r"ETHUSDT-5m-data.csv", parse_dates=True)
df = df[["timestamp","open","high","low","close","volume","close_time","quote_av","trades","tb_base_av","tb_quote_av"]]
df = df[:-1]
#df.drop_duplicates(subset ="timestamp", keep='first', inplace = True)
df.to_csv(r"ETHUSDT-5m-data.csv")

#df.drop_duplicates(subset ="timestamp", keep='first', inplace = True)
df = df.tail(8640)
#Computing indicators SMA and ADX, and whether trend is bear or bull according to sma
df['sma_fast'] = ta.SMA(df['close'],95)
df['sma_slow'] = ta.SMA(df['close'],200)
df['upper_band'], df['middle_band'], df['lower_band'] = ta.BBANDS(df['close'], timeperiod =20)
df['rsi'] = ta.RSI(df['close'],15)
df['adx'] = ta.ADX(df.high, df.low, df.close, timeperiod=3)
df['bear0bull1'] = np.where((df["sma_fast"] < df["sma_slow"]), 0, 1)
# Computing if trend is real according to number of consecutive rows with equal values in bear0bull1 column        
df['uptrend'] = 0
from itertools import islice
for index, row in islice(df.iterrows(), 1, None):
    if ((row["bear0bull1"]) == 1):
        df.loc[index, 'uptrend'] = df.loc[index - 1, 'uptrend'] +1
    else:
        df.loc[index, 'uptrend'] = 0
# Computing RSI so that it is different according to the value in uptrend column
for index, row in df.iterrows():
    if ((row["uptrend"]) > 9):
        df['rsi'] = ta.RSI(df['close'],10)
# Computing general tresholds for RSI according to uptrend column 
df['rsi_high'] = np.where((df["uptrend"] < 10), 50, 75)
df['rsi_low'] = np.where((df["uptrend"] < 10), 30, 60)
# Adjusting RSI treshold according to extreme values of ADX 
df.loc[(df['adx'] > 70) & (df['uptrend'] < 10), 'rsi_high'] = df['rsi_high'] + 10 #+20
df.loc[(df['adx'] < 50) & (df['uptrend'] < 10), 'rsi_low'] = df['rsi_low'] -8
df.loc[(df['adx'] > 70) & (df['uptrend'] > 9), 'rsi_high'] = df['rsi_high'] + 7
df.loc[(df['adx'] < 50) & (df['uptrend'] > 9), 'rsi_low'] = df['rsi_low'] -8
# Computing action to be taken (1 = buy, -1 = sell, 0 = stay)
position = 0
df['position'] = 0
for index, row in df.iterrows():
    if ((row["rsi"]) < (row["rsi_low"])) & (position == 0):
        df.loc[index, 'position'] = 1
        position = 1
    elif ((row["rsi"]) > (row["rsi_high"])) & (position == 1):
        df.loc[index, 'position'] = -1
        position = 0
# Backtesting: Computing revenues
alloc = 100
df['net_position'] = df.position.cumsum().shift().fillna(0)
df['change'] = (df.close.pct_change() * df.net_position + 1).cumprod() * alloc
dfeth = df.tail(1)
#The same for NANO
binance_symbols = ["NANOUSDT"]
for symbol in binance_symbols:
    get_all_binance(symbol, '5m', save = True)
df = pd.read_csv(r"NANOUSDT-5m-data.csv", parse_dates=True)
df = df[["timestamp","open","high","low","close","volume","close_time","quote_av","trades","tb_base_av","tb_quote_av"]]
df = df[:-1]
df.to_csv(r"NANOUSDT-5m-data.csv")

#df.drop_duplicates(subset ="timestamp", keep='first', inplace = True)
df = df.tail(8640)
#Computing indicators SMA and ADX, and whether trend is bear or bull according to sma
df['sma_fast'] = ta.SMA(df['close'],95)
df['sma_slow'] = ta.SMA(df['close'],200)
df['upper_band'], df['middle_band'], df['lower_band'] = ta.BBANDS(df['close'], timeperiod =20)
df['rsi'] = ta.RSI(df['close'],15)
df['adx'] = ta.ADX(df.high, df.low, df.close, timeperiod=3)
df['bear0bull1'] = np.where((df["sma_fast"] < df["sma_slow"]), 0, 1)
# Computing if trend is real according to number of consecutive rows with equal values in bear0bull1 column        
df['uptrend'] = 0
for index, row in islice(df.iterrows(), 1, None):
    if ((row["bear0bull1"]) == 1):
        df.loc[index, 'uptrend'] = df.loc[index - 1, 'uptrend'] +1
    else:
        df.loc[index, 'uptrend'] = 0
# Computing RSI so that it is different according to the value in uptrend column
for index, row in df.iterrows():
    if ((row["uptrend"]) > 9):
        df['rsi'] = ta.RSI(df['close'],10)
# Computing general tresholds for RSI according to uptrend column 
df['rsi_high'] = np.where((df["uptrend"] < 10), 50, 75)
df['rsi_low'] = np.where((df["uptrend"] < 10), 30, 60)
# Adjusting RSI treshold according to extreme values of ADX 
df.loc[(df['adx'] > 70) & (df['uptrend'] < 10), 'rsi_high'] = df['rsi_high'] + 20 #+20
df.loc[(df['adx'] < 50) & (df['uptrend'] < 10), 'rsi_low'] = df['rsi_low'] -8
df.loc[(df['adx'] > 70) & (df['uptrend'] > 9), 'rsi_high'] = df['rsi_high'] + 7
df.loc[(df['adx'] < 50) & (df['uptrend'] > 9), 'rsi_low'] = df['rsi_low'] -8
# Computing action to be taken (1 = buy, -1 = sell, 0 = stay)
position = 0
df['position'] = 0
for index, row in df.iterrows():
    if ((row["rsi"]) < (row["rsi_low"])) & (position == 0):
        df.loc[index, 'position'] = 1
        position = 1
    elif ((row["rsi"]) > (row["rsi_high"])) & (position == 1):
        df.loc[index, 'position'] = -1
        position = 0
# Backtesting: Computing revenues
alloc = 100
df['net_position'] = df.position.cumsum().shift().fillna(0)
df['change'] = (df.close.pct_change() * df.net_position + 1).cumprod() * alloc
dfnano = df.tail(1)
# Taking actions
t = time.localtime()
current_time = time.strftime("%H:%M:%S", t)
balanceusdt = client.get_asset_balance(asset='USDT')
balanceusdt = float(balanceusdt['free'])
balancenano = client.get_asset_balance(asset='NANO')
balancenano = float(balancenano['free'])
balanceeth = client.get_asset_balance(asset='ETH')
balanceeth = float(balanceeth['free'])
action="I am going to wait"   
if (dfnano.iloc[0,23] == 1) & (balanceusdt > 10):
    print("I am going to buy NANO") 
    print(current_time)
    action="I am going to buy NANO"
    balance = client.get_asset_balance(asset='USDT')
    trades = client.get_recent_trades(symbol='NANOUSDT')
    quantity = (float(balance['free']))/float(trades[0]['price'])*0.9995
    quantity = round(quantity, 2)
    bought = quantity
    client.order_market_buy(symbol='NANOUSDT', quantity=quantity) 
if (dfeth.iloc[0,23] == 1) & (balanceusdt > 10):
    print("I am going to buy ETH") 
    print(current_time)
    action="I am going to buy ETH"
    balance = client.get_asset_balance(asset='USDT')
    trades = client.get_recent_trades(symbol='ETHUSDT')
    quantity = (float(balance['free']))/float(trades[0]['price'])*0.9995
    quantity = round(quantity, 2)
    bought = quantity
    client.order_market_buy(symbol='ETHUSDT', quantity=quantity)    
if (dfeth.iloc[0, 23] == -1) & (balanceeth > 0.1):
    print("I am going to sell ETH") 
    print(current_time)
    action="I am going to sell ETH"
    quantity=balanceeth
    quantity = round(quantity, 2)
    symbol = "ETHUSDT"
    client.order_market_sell(symbol=symbol,quantity=quantity) 
if (dfeth.iloc[0, 23] == -1) & (balancenano > 10):
    print("I am going to sell NANO") 
    print(current_time)
    action="I am going to sell NANO"
    quantity=balancenano
    quantity = round(quantity, 2)
    symbol = "NANOUSDT"
    client.order_market_sell(symbol=symbol,quantity=quantity) 

full_history = pd.read_csv(r"history.csv", parse_dates=True)
full_history=full_history.iloc[0:,np.r_[1:3]]
current_time=current_time
history = pd.DataFrame(
       {
           "timestamp": [current_time],
           "action": [action],
       },
   )

frames=[full_history,history]
history = pd.concat(frames)
history.to_csv(r"history.csv")

f=open("timeline.txt", "a+")
f.write("Executed at %s\r\n" % time.localtime( time.time()) )
f.close()
