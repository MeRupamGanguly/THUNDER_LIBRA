import time
import tkinter
import requests
import urllib.parse
import webbrowser
import websockets
import asyncio
import ssl
import json
from threading import Thread
from google.protobuf.json_format import MessageToDict
import MarketDataFeed_pb2 as pb

# Common
jsonconfig=open('thunderlibra/config.json') 
configs=json.load(jsonconfig)

token_file_path=configs['token_file_path']

apiKey=configs['apiKey']
secrectKey=configs['secrectKey']
reUrl=configs['rurl']

sl_percentage_value=configs['sl_percentage_value']
target_percentage_value=configs['target_percentage_value']

trail_sl_percentage_value=configs['trail_sl_percentage_value']
trail_target_percentage_value=configs['trail_target_percentage_value']

debug_print="token file Path: "+str(token_file_path)+" sl percentage: "+str(sl_percentage_value)+" target percentage: "+str(target_percentage_value)
print(debug_print)

with open(token_file_path,"r") as tFile:
    access_token=tFile.read()

rurl=urllib.parse.quote(reUrl,safe="")
stop_all=False
# For SSL Local cert ERROR
ssl._create_default_https_context = ssl._create_unverified_context 

#------------------------------------------------------------------------
# API Call
# Open browser for Signin
def get_signin_url():
    uri=f'https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={apiKey}&redirect_uri={rurl}'
    webbrowser.open(uri)

# Gen access Bearer token
def gen_token():
    global access_token
    code=code_entry.get()
    tokenUrl='https://api.upstox.com/v2/login/authorization/token'
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {
        'code':code,
        'client_id':apiKey,
        'client_secret':secrectKey,
        'redirect_uri':reUrl,
        'grant_type':'authorization_code'
    }
    response = requests.post(tokenUrl, headers=headers,data=data)
    jsonResponse=response.json()

    access_token=jsonResponse['access_token']
    textFile=open(token_file_path,"w")
    textFile.write(access_token)
    textFile.close
    status_button_text.set("Done, Access token written to a File")

def decode_protobuf(buffer):
    feed_response = pb.FeedResponse()
    feed_response.ParseFromString(buffer)
    return feed_response

# Stream Socket
def getSocketMarketTickAuthorizedRedirectUri():
    url= 'https://api.upstox.com/v2/feed/market-data-feed/authorize'
    headers = {
    'accept': 'application/json',
    'Authorization':f'Bearer {access_token}'
    }
    payload={}
    response=requests.get(url, headers=headers,data=payload)
    jsonResponse=response.json()
    return jsonResponse['data']['authorized_redirect_uri']

async def socket_tick_streamer():
    global data_dict
    global is_position_closed
    global stop_all
    global entry_instrument

    authorized_redirect_uri=getSocketMarketTickAuthorizedRedirectUri()
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    async with websockets.connect(authorized_redirect_uri,ssl=ssl_context) as ws:
        print('Connection established')
        await asyncio.sleep(1)  # Wait for 1 second
        data = {
            "guid": "someguid",
            "method": "sub",
            "data": {
                "mode": "full",
                "instrumentKeys": [entry_instrument]
            }
        }
        binary_data = json.dumps(data).encode('utf-8')
        await ws.send(binary_data)
        while not is_position_closed: # Run Loop until is_position_closed event occur.
            try:
                raw= await ws.recv()
                decoded_data = decode_protobuf(raw)
                data_dict = MessageToDict(decoded_data)
                if stop_all: # if Stop_All event occur then Close the Websocket
                    data={
                        "guid": "someguid",
                        "method": "unsub",
                        "data": {
                            "mode": "full",
                            "instrumentKeys": [entry_instrument]
                        }
                    }
                    binary_data = json.dumps(data).encode('utf-8')
                    await ws.send(binary_data) # sending Unsubscribe payload
                    await asyncio.sleep(2)  # Wait for 2 second to digest the Unsubscribe Payload, then close the Connection
                    await ws.close()
                    print()
                    debug_print="stop all executed: conn close"
                    print(debug_print)
                    break
            except: # If any Error ocur from Socket then this block Send Unsubscribe Request to Socket
                data={
                    "guid": "someguid",
                    "method": "unsub",
                    "data": {
                        "mode": "full",
                        "instrumentKeys": [entry_instrument]
                    }
                }
                binary_data = json.dumps(data).encode('utf-8')
                await ws.send(binary_data)  # sending Unsubscribe payload
                await asyncio.sleep(2) # Wait for 2 second to digest the Unsubscribe Payload, then close the Connection
                await ws.close()
                print()
                debug_print="Exception: conn close"
                print(debug_print)
                break
        
        debug_print="Position closed executed: conn close"
        print()
        print(debug_print)

    print("socket_tick_streamer END")

def instruments_tick_stream():
    asyncio.run(socket_tick_streamer())

def order_book():
    url= 'https://api.upstox.com/v2/order/retrieve-all'
    headers = {
    'accept': 'application/json',
    'Content-Type': 'application/json',
    'Authorization':f'Bearer {access_token}'
    }
    payload={}
    response=requests.get(url, headers=headers,data=payload)
    jsonResponse=response.json()
    print(jsonResponse)
    
    
# Execute order api for close position
def execute_order():
    global entry_instrument
    global entry_qty
    url= 'https://api.upstox.com/v2/order/place'
    headers = {
    'accept': 'application/json',
    'Content-Type': 'application/json',
    'Authorization':f'Bearer {access_token}'
    }

    payload={
        "quantity":entry_qty,
        "product":"D",
        "validity":"DAY",
        "price":0,
        "tag":"auto",
        "instrument_token":entry_instrument,
        "order_type":"MARKET",
        "transaction_type":"SELL",
        "disclosed_quantity":0,
        "trigger_price":0,
        "is_amo":False
    }
    jsonPayload=json.dumps(payload)
    response = requests.post(url, headers=headers,data=jsonPayload)
    jsonResponse=response.json()
    print()
    debug_print="Execute Order Function Payload: "+str(jsonPayload)+ " --------->>>>>>>>> Response: "+str(jsonResponse)
    print(debug_print)
    print()

    status_str='Order Executed'
    status_button_text.set(status_str)

def health():
    global entry_instrument
    global data_dict
    global is_position_closed
    global stop_loss
    global target_price
    global stop_all
    while not is_position_closed:
        ltp=data_dict['feeds'][entry_instrument]['ff']['marketFF']['ltpc']['ltp']

        health_print="___ Health Checking ltp: "+str(ltp)+" SL: "+str(stop_loss)+" Target: "+str(target_price) +" ___"
        print(health_print)

        if stop_all:
            break
        time.sleep(10)

# Stoploss and Trail Stoploss Algorithm
def stoploss_algo():
    print("in stoploss_algo")
    global data_dict
    global stop_loss
    global target_price
    global is_position_closed
    global stop_all
    global entry_instrument

    trailHitCount=0

    while not is_position_closed:
        ltp=data_dict['feeds'][entry_instrument]['ff']['marketFF']['ltpc']['ltp']
       
        if ltp > target_price: # Trail when target price achived
            
            trailHitCount=trailHitCount+1
            
            if trailHitCount==1:
                target_price =round( ltp * (1 + 0.01),2) # move your trigger to (ltp + 1% of ltp) 
                stop_loss =round( ltp * (1- 0.00),2) # move your sl to ltp
                
            else:
                target_price =round( ltp * (1 + trail_target_percentage_value),2) 
                stop_loss =round( ltp * (1- trail_sl_percentage_value),2) 

        if ltp < stop_loss: # SL HIT
            
            is_position_closed=True
            stop_all=True
                
            execute_order()
            
            new_status_str='SL Hit'
            status_button_text.set(new_status_str)

            debug_print="Exit: SL Hit"
            print(debug_print)
                
            print()
            print("ORDER BOOK   ------->>>>>>>  ")
            order_book()
            print()    
            break

        if stop_all:
            break
        time.sleep(0.5) # Sleep for Consume less CPU - for not proccessing data too frequently.

    debug_print="stoploss_algo CLOSED"
    print(debug_print)

# Get position data for geting instrument-key and quantity
def get_positions():
    global stop_loss
    global target_price
    global is_position_closed
    global entry_instrument
    global entry_price
    global entry_qty
    url= 'https://api.upstox.com/v2/portfolio/short-term-positions'
    headers = {
    'accept': 'application/json',
    'Authorization':f'Bearer {access_token}'
    }
    params={}
    response=requests.get(url, headers=headers,params=params)
    jsonResponse=response.json()

    debug_print=jsonResponse
    print(debug_print)
    #order_book()
    for d in jsonResponse['data']:
        if d["day_sell_price"]==0.0 and d["day_sell_quantity"] ==0.0: # if position is not closed
            status_str="Tracking: "+ d['trading_symbol'] 
            status_button_text.set(status_str)
            entry_instrument=d['instrument_token']
            entry_price=d['day_buy_price'] 
            entry_qty=d['day_buy_quantity']

            debug_print="entry price: "+str(entry_price)+" entry qty: "+str(entry_qty)
            print(debug_print)

            is_position_closed=False
            stop_loss=round( entry_price * (1 - sl_percentage_value),2)
            target_price=round( entry_price * (1 + target_percentage_value),2)

            thread_one=Thread(target=instruments_tick_stream)
            thread_one.start()

            time.sleep(3)  # Wait for 3 second

            thread_two=Thread(target=stoploss_algo)
            thread_two.start()

            thread_health=Thread(target=health)
            thread_health.start()
        
def marketData(instruments):
    url= 'https://api.upstox.com/v2/market-quote/ltp'
    headers = {
    'accept': 'application/json',
    'Authorization':f'Bearer {access_token}'
    }
    params={
        'instrument_key':[instruments]
    }
    response=requests.get(url, headers=headers,params=params)
    jsonResponse=response.json()
    return jsonResponse

#------------------------------------------------------------------
# Fonts
app_font_big=('Courier New', '15')
app_font_normal=('Courier New', '12')
app_font_small=('Courier New', '9')
button_font_big=('Courier New', '16')

# Colors
white_color='#fff'
gray_color='#FF6090'
green_color='#006000'
red_color='#FF0000'
yellow_color='#F0CB07'
cean_color='#00B496'
fetch_color='#FF0099'

# Interactor --------------------------------------------
def exit_button_pressed():
    global is_position_closed
    global stop_all
    is_position_closed=True
    stop_all=True
    execute_order()
    order_book()
    status_button_text.set("Exit Button Pressed")

def close_tracking_button_pressed():
    global stop_all
    stop_all=True
    status_button_text.set("Close Tracking")

def sl_target_refresh_button_on_pressed():
    global sl_percentage_value
    global target_percentage_value
    global stop_loss
    global target_price
    global entry_price
    sl_v=sl_percentage.get()
    profit_v=target_percentage.get()
    sl_percentage_value=float(sl_v)
    target_percentage_value=float(profit_v)
    stop_loss=round( entry_price * (1 - sl_percentage_value),2)
    target_price=round( entry_price * (1 + target_percentage_value),2)
    status_str="Stoploss: "+str(stop_loss)+"Target: "+str(target_price)
    status_button_text.set(status_str)

#-----------------------------------------------------------------------------------------
# UI Layer

# Root
appWindow = tkinter.Tk()
appWindow.title("Thunder-Libra RupamGanguly")
root_frame=tkinter.Frame(appWindow)
root_frame.pack()

status_button_text=tkinter.StringVar()

# ROW 0
row0_frame=tkinter.Frame(root_frame)
row0_frame.grid(row=0,column=0,padx=5, pady=5,sticky="news")

# Get Code
gen_code=tkinter.Button(row0_frame, text="Gen C",font=app_font_normal,width=8,background=white_color,command=get_signin_url)
gen_code.grid(row=0,column=0,padx=5)

code_entry=tkinter.Entry(row0_frame,width=10,font=app_font_normal)
code_entry.grid(row=0,column=1,padx=2)

# Get Token
gen_access_token=tkinter.Button(row0_frame, text="Gen T",font=app_font_normal,width=10,background=white_color,command=gen_token)
gen_access_token.grid(row=0,column=2,padx=5)

# Exit Button
exit_button=tkinter.Button(row0_frame, text="EXIT",font=app_font_normal,width=20,background=cean_color,command=exit_button_pressed)
exit_button.grid(row=0,column=3,padx=(40,5))

# ROW 1
row1_frame=tkinter.Frame(root_frame)
row1_frame.grid(row=1,column=0,padx=5, pady=5,sticky="news")

# SL Percentage
percentag_sl_label=tkinter.Label(row1_frame,text="SL:",font=app_font_normal)
percentag_sl_label.grid(row=0,column=1,padx=5)

sl_percentage=tkinter.Entry(row1_frame,width=5,font=app_font_normal)
sl_percentage.insert(0,sl_percentage_value)
sl_percentage.grid(row=0,column=2,padx=5)

# Target Percentage
percentag_target_label=tkinter.Label(row1_frame,text="Target:",font=app_font_normal)
percentag_target_label.grid(row=0,column=3,padx=5)

target_percentage=tkinter.Entry(row1_frame,width=5,font=app_font_normal)
target_percentage.insert(0,target_percentage_value)
target_percentage.grid(row=0,column=4,padx=5)

target_percentage_button_text=tkinter.StringVar()
target_percentage_button=tkinter.Button(row1_frame, textvariable=target_percentage_button_text,font=app_font_normal,width=8,background=yellow_color,command=sl_target_refresh_button_on_pressed)
target_percentage_button_text.set("Refresh")
target_percentage_button.grid(row=0,column=5,padx=5,)

# Get Positions
exit_button=tkinter.Button(row1_frame, text="Ftch P",font=app_font_normal,width=10,background=fetch_color,command=get_positions)
exit_button.grid(row=0,column=6,padx=(30,0))

# ROW 2
row2_frame=tkinter.Frame(root_frame)
row2_frame.grid(row=2,column=0,padx=2, pady=2,sticky="news")

# Status
status_button=tkinter.Button(row2_frame, textvariable=status_button_text,font=app_font_small,width=67,borderwidth=0,)
status_button_text.set("Always Protect Your Capital")
status_button.grid(row=0,column=1,padx=5,)

close_button=tkinter.Button(row2_frame, text="X",font=app_font_normal,width=5,background=cean_color,command=close_tracking_button_pressed)
close_button.grid(row=0,column=0,padx=5)

#-------------------------------# UI Layer END #------------------------------------------

#Main
appWindow.mainloop()
