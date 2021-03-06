import logging
import os
import pandas as pd
from common import indicators
import sys
from datetime import datetime, timedelta
from common.get_api_data import *

logging.basicConfig(level=logging.INFO)
import common.application as ap
import pytz
#from simulator import place_order as simulator
from common.SlackUtil import sendMessage

app_properties = ap.app_properties
token_mappings = ap.token_mappings
csv_mapping = ap.csv_mapping

api_key = app_properties['api_key']
api_secret = app_properties['api_secret']
token ="1510401"
os.makedirs(token, exist_ok=True)
file_name = "trades.csv"
tz = pytz.timezone('Asia/Kolkata')
logger = logging.getLogger('algo_tester')
# global define
profit = 0.019
stop_loss = 0.0095
historical_data = ""
rsi = 0.00
rsi_slope = 0.00
last_close = 0.00
last_high = 0.00
last_low = 0.00
last_price = get_price(token, 0.00)
current_price = 0.00
holding = ""
order_id = ""
swing = False
flag = ''
interval=10
rsi_count=0
sma_triggered=False
extrema_triggered=False
activation=''
def getDateTime():
    datetime_obj_hour_fwd = datetime.now(tz)+timedelta(seconds=74)
    return datetime_obj_hour_fwd


datetime_obj_hour_fwd = getDateTime() + timedelta(hours=1)
from_date = str(datetime_obj_hour_fwd - timedelta(days=14)).split(" ")[0]


def create_log(action):
    log = str(order_id) +',' + str(rsi) + ',' + str(rsi_slope) + ',' + str(last_close) + ',' + str(
        current_price) + ',' + str(action) + ',' + str(holding)+','+str(last_price)+","+str(sma_triggered)+","+str(activation)+","+str(rsi_count)+","+str(extrema_triggered)+","+str(getDateTime())+"\n"
    return log


def write_log(action, name=file_name):
    global last_close, last_price, order_id, holding,current_price
    log = ''
    current_price = get_price(token, last_price)
    if action == 'BUY' or action == 'SELL':
        #simulator.place_order(action, token_mappings[token], 1000)
        slack_msg = action + " : "+str(token_mappings[token]) + " @ "+str(current_price)  +" : Bollinger bands"
        if order_id == '':
            datetime_obj = getDateTime()
            order_id = str(datetime_obj.hour) + str(datetime_obj.minute) + str(datetime_obj.second)
            holding = 'up' if action == 'BUY' else 'down'
            last_price = current_price
            log = create_log(action)
        else:
            holding = ''
            slack_msg = slack_msg + ' for Order Id : '+str(order_id) + ' in : '+str(flag) +" : Bollinger bands"
            log = create_log(action)
            order_id = ''
        sendMessage(slack_msg)
    name = token + "/" + name
    f = open(name, 'a')
    if log == '':
        log = create_log(action)
    f.write(log)
    f.close()


def place_order(signal):
    if supertrend == 'up' and 60 <= rsi <= 80 and rsi_slope > 0.5 and wma5 >= wma20 and holding == '' and order_id == '' and signal == '':
        write_log('BUY')
    elif supertrend == 'down' and 20 <= rsi <= 40 and rsi_slope < -0.5 and wma5 <= wma20 and holding == '' and order_id == '' and signal == '':
        write_log('SELL')
    elif holding != '' and order_id != '' and signal == '':
        write_log('HOLD')
    elif holding != '' and order_id != '' and signal != '':
        write_log(signal)
    else:
        write_log('NONE')
    if holding != '' and order_id != '' and signal == '' and swing:
        action = 'SELL' if holding == 'up' else 'BUY'
        slack_msg = action + " : " + str(token_mappings[token]) + " @ " + str(current_price) + " for Order : "+str(order_id)+" : Swing"
        sendMessage(slack_msg)


def stopper():
    global last_price,flag
    flag = ''
    current_price = get_price(token, last_price)
    datetime_obj = getDateTime()
    if holding == 'up':
        temp_profit = (current_price - last_price) / last_price
        temp_loss = (last_price - current_price) / last_price
#         if temp_profit >= profit:
#             flag = 'Profit'
#             place_order('SELL')
        if temp_loss > stop_loss:
            flag = 'Loss'
            write_log('SELL')
        if datetime_obj.hour == 15 and datetime_obj.minute > 20:
            flag = 'Market Close : Profit/Loss'
            write_log('SELL')
    elif holding == 'down':
        temp_profit = (last_price - current_price) / last_price
        temp_loss = (current_price - last_price) / last_price
#         if temp_profit >= profit:
#             flag = 'Profit'
#             place_order('BUY')
        if temp_loss > stop_loss:
            flag = 'Loss'
            write_log('BUY')
        if datetime_obj.hour == 15 and datetime_obj.minute > 20:
            flag = 'Market Close : Profit/Loss'
            write_log('BUY')


def get_history_data():
    global historical_data, rsi, rsi_slope, last_close, swing,last_high,last_low,sma,ub,mb,lb,band_diff_trend,current_price
    swing = False
    to_date = str(getDateTime() - timedelta(minutes=2)).split(".")[0]
    current_price = get_price(token, last_close)
    historical_data = get_data(token, from_date, to_date, "10minute", historical_data)
    df = pd.DataFrame(historical_data)
    df = indicators.RSI(df,period=14)
    df=indicators.SMA(df, "close", "sma_7", 7)
    df['RSI_Trend'] = df['RSI_14'].diff()
    window = 20
    no_of_std = 2
    rolling_mean = df['close'].rolling(window).mean()
    rolling_std = df['close'].rolling(window).std()
    df['ub'] = rolling_mean + (rolling_std * no_of_std)
    df['mb'] = rolling_mean
    df['lb'] = rolling_mean - (rolling_std * no_of_std)
    df['band_diff']=(df['ub']-df['lb']).round(2)
    df['band_diff_trend'] = df['band_diff'].diff().round(0)
    df['3_ub_point']=df.ub.shift(2)+","+    df.ub.shift(1)+","+    df.ub
    df['3_lb_point']=df.lb.shift(2)+","+    df.lb.shift(1)+","+    df.lb
    df['divergence_angle']=df['3_ub_point'].apply(compute_angle)+df['3_lb_point'].apply(compute_angle)
    
    tail_dict = df.tail(1).to_dict('list')
    
    sma = tail_dict['sma_7'][0]
    rsi = tail_dict['RSI_14'][0]
    rsi_slope = tail_dict['RSI_Trend'][0]
    last_close = tail_dict['close'][0]
    last_low = tail_dict['low'][0]
    last_high = tail_dict['high'][0]
    ub=tail_dict['ub'][0]
    mb=tail_dict['mb'][0]
    lb=tail_dict['lb'][0]
    band_diff_trend=tail_dict['band_diff_trend'][0]
    swing = is_swing(df)

    name = token + "/" + "pandasdf"
    df.to_csv(name)

    


def is_swing(df):
    temp_df = df.iloc[-3:]
    if holding == 'up':
        high_values = list(temp_df['high'])
        if high_values[2] < high_values[0] < high_values[1]:
            return True
    else:
        low_values = list(temp_df['low'])
        if low_values[1] < low_values[0] < low_values[2]:
            return True


def trade():
    signal = ''
    last_min = -1
    
    while True:
        datetime_obj = getDateTime()
        if((datetime_obj.hour == 9 and datetime_obj.minute >= 15 )or (datetime_obj.hour > 9)):
            break
        
    while True:
        datetime_obj = getDateTime()
        if (datetime_obj.hour >= 15 and datetime_obj.minute > 28) or (
                datetime_obj.hour <= 9 and datetime_obj.minute <= 10):
            print('Market Not Tradable at this moment')
            break
        minutes = int(str(datetime_obj).split(".")[0].split(":")[1])
        if minutes % 10 == 5 and (last_min == -1 or (minutes != last_min and last_min != -1)):
            get_history_data()
            if (datetime_obj.hour < 15):
                enter_in_market()
            exit_from_market()
            last_min = minutes
        else:
            stopper()
        time.sleep(1)


def init():
    global order_id, holding,last_price,sma_triggered,activation,rsi_count,extrema_triggered
    name = token + "/trades.csv"
    try:
        with open(name, 'r') as f:
            lines = f.read().splitlines()
            last_line = lines[-1]
            order_id = last_line.split(",")[0]
            holding = last_line.split(",")[6]
            last_price = float(last_line.split(",")[7])
            sma_triggered=convert_to_bool(last_line.split(",")[8])
            activation=last_line.split(",")[9]
            rsi_count=int(last_line.split(",")[10])
            extrema_triggered=convert_to_bool(last_line.split(",")[11])
            trade()
    except:
        trade()

def convert_to_bool(bool_value):
    if(bool_value=='True'):
        bool_value=True
    else:
        bool_value=False
    return bool_value

def activate_signal():
    global activation,rsi_count
    if(rsi>70 and current_price > ub  ):
        rsi_count=rsi_count+1
        activation='high'
    elif(rsi<30 and current_price < lb ):
        activation='low'
        rsi_count=rsi_count+1
    elif(rsi_count==1):
        reset()

def enter_in_market():
    if(holding==''):
        activate_signal()
        if activation == 'high' and rsi<=70 and last_low <= ub and rsi_count >1: # we need to check the price also with the upper bolinger band.
            write_log("SELL")
        elif activation == 'low' and rsi>=30 and last_high >= lb and rsi_count >1:  # we need to check the price also with the lower bolinger band.
            write_log("BUY")
        else:
            write_log("NONE")
    elif holding != '' and order_id != '':
            write_log("HOLD")   

def is_sma_triggered():
    global sma_triggered
    if((activation=='high' and last_low<mb)or (activation=='low' and last_high>mb)):
        sma_triggered=True

def is_extrema_triggered():
    global extrema_triggered
    if(sma_triggered and (activation=='high' and last_low<lb)or (activation=='low' and last_high>ub)):
        extrema_triggered=True
        
def exit_from_market():
    global flag
    if(holding!=''):
        is_sma_triggered()
        if(activation=='high' and ((sma_triggered and last_close >= mb) or (extrema_triggered and last_close>=lb))):
            flag = 'Profit[Autotrigered]' if last_price > current_price  else 'LOSS[Autotrigered]'
            write_log('BUY')
            reset()
        elif(activation=='low' and ((sma_triggered and last_close <= mb) or (extrema_triggered and  last_close<=ub))):  # this condition needs to 
            flag = 'Profit[Autotrigered]' if last_price < current_price  else 'LOSS[Autotrigered]'
            write_log('SELL')
            reset()
         
def reset():
    global sma_triggered,activation,rsi_count,extrema_triggered
    sma_triggered=False
    extrema_triggered=False
    activation=""
    rsi_count=0


def magnitude(v):
    return (v[0]**2+v[1]**2)**(1/2)

def compute_angle(arr):
    arr=arr.split(",")
    p0=(0,float(arr[0]))
    p1=(10,float(arr[1]))
    p2=(20,float(arr[2]))
    v1=[p0[0]-p1[0],p0[1]-p1[1]]
    v2=[p2[0]-p1[0],p2[1]-p1[1]]
    m1=magnitude(v1)
    m2=magnitude(v2)
    return 180-np.arccos(np.dot(v1,v2)/(magnitude(v1)*magnitude(v2)))*180/3.14
    
    
    
    
    
    
    

if __name__ == "__main__":
    init()
