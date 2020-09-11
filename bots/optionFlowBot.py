import websocket, requests, json
from datetime import datetime, timedelta
import pytz
import time

from config import *
algorithm = __import__('algorithms.{}'.format(ALGORITHM_FILENAME)).__dict__[ALGORITHM_FILENAME]

# parameters
RESERVED_CASH = 28000
DEBUG = True

# socket
DATA_SOCKET = 'wss://socket.polygon.io/stocks'
STREAM_SYMBOL = 'AM.' + LONG_SYMBOL

# api
HEADERS = {'APCA-API-KEY-ID': API_KEY, 'APCA-API-SECRET-KEY': SECRET_KEY}
CLOCK_URL = '{}/v2/clock'.format(BASE_URL)
ACCOUNT_URL = '{}/v2/account'.format(BASE_URL)
POSITIONS_URL = '{}/v2/positions'.format(BASE_URL)
ORDERS_URL = '{}/v2/orders'.format(BASE_URL)
MINUTE_BARS_URL = 'https://api.polygon.io/v2/aggs/ticker/{}/range/1/minute/'.format(LONG_SYMBOL)

# global variables
MarketOpen = None
MarketClose = None

# api calls
def set_market_hours():
    global MarketClose, MarketOpen
    r = requests.get(CLOCK_URL, headers=HEADERS)
    marketTimes = json.loads(r.content)
    curTime = datetime.now(pytz.timezone('America/New_York')).replace(tzinfo=None)
    MarketOpen = datetime.strptime(marketTimes['next_open'][:-9], '%Y-%m-%dT%H:%M')
    MarketClose = datetime.strptime(marketTimes['next_close'][:-9], '%Y-%m-%dT%H:%M')
    print('Next Open:{}, NextClose:{}'.format(marketTimes['next_open'], marketTimes['next_close']))
    if not marketTimes['is_open'] and curTime.day != MarketOpen.day:
        print('No Trading Today')
        return -1
    elif marketTimes['is_open'] and curTime.day != MarketOpen.day:
        openTime = curTime.strftime('%Y-%m-%dT') + '09:30'
        MarketOpen = datetime.strptime(openTime, '%Y-%m-%dT%H:%M')
        set_algorithm_price_data(curTime)
        print(openTime, 'starting from middle of day')

    if DEBUG: print('set market times (open/close):', MarketOpen, '/', MarketClose)
    return 0

def set_algorithm_price_data(curTime):
    global MarketOpen
    curDate = curTime.strftime('%Y-%m-%d')
    nytz = pytz.timezone('America/New_York')
    marketOpenTime = nytz.normalize(nytz.localize(MarketOpen, is_dst=True)).timestamp() * 1000
    url = '{}{}/{}?apiKey={}'.format(MINUTE_BARS_URL, curDate, curDate, API_KEY)
    r = requests.get(url)
    prices = json.loads(r.content)['results']
    prices = [p for p in prices if p['t'] > marketOpenTime]
    print('sec since epoch market open:', marketOpenTime)
    print(prices)
    for i,p in enumerate(prices):
        algorithm.on_minute(p, None, i + 1, 389 - i)

def check_account():
    r = requests.get(ACCOUNT_URL, headers=HEADERS)
    if DEBUG: print('checking account:', r.content)
    return json.loads(r.content)

def check_positions():
    r = requests.get(POSITIONS_URL, headers=HEADERS)
    if DEBUG: print('checking positions:', r.content)
    return json.loads(r.content)

def create_order(symbol, qty, side='buy', order_type='market', time_in_force='day', limit_price=None, stop_loss=None, stop_limit=None):
    data = {
        'symbol': symbol,
        'qty': qty,
        'side': side,
        'type': order_type,
        'time_in_force': time_in_force,
    }
    if limit_price:
        data['limit_price'] = limit_price,
        data['extended_hours'] = True
    if stop_loss:
        data['order_class'] = 'oto'
        data['stop_loss'] = dict()
        data['stop_loss']['stop_price'] = stop_loss
        if stop_limit:
            data['stop_loss']['limit_price'] = stop_limit
    r = requests.post(ORDERS_URL, json=data, headers=HEADERS)
    print('created order:', r.content)
    return json.loads(r.content)

def cancel_order():
    r = requests.delete(ORDERS_URL, headers=HEADERS)
    if DEBUG: print('deleting orders:', r.content)
    return json.loads(r.content)

def close_position(symbol=None, limit=None, qty=None, side=None):
    if not limit:
        if not symbol:
            r = requests.delete(POSITIONS_URL, headers=HEADERS)
        else:
            data = {'symbol': STREAM_SYMBOL}
            r = requests.delete('{}/{}'.format(POSITIONS_URL,symbol), json=data, headers=HEADERS)
    else:
        create_order(LONG_SYMBOL, qty, side, 'limit', limit_price=limit)
    print('closing positions:', r.content)
    return json.loads(r.content)

def on_open(ws):
    print('opening connection')
    auth_data = {
        'action': 'auth',
        'params': API_KEY
    }
    ws.send(json.dumps(auth_data))

def on_message(ws, message):
    message = json.loads(message)[0]
    print('received stream message:', message)
    if message['ev'] == 'AM':
        process_price_data(message)
        pass
    elif message['ev'] == 'status':
        print('status message:', message['message'])
        listen_message = {
            'action': 'subscribe',
            'params': STREAM_SYMBOL
        }
        ws.send(json.dumps(listen_message))
    else:
        print('unexpected message:', message)

def on_close(ws):
    print('connection closed, restarting connection')
    run_bot()

def on_error(ws, error):
    print('received error:', error)

def process_price_data(prices):
    position = check_positions()
    if position: position = position[0]['side']
    curTime = datetime.now(pytz.timezone('America/New_York')).replace(tzinfo=None)
    timeElapsed = curTime - MarketOpen
    timeLeft = MarketClose - curTime
    timeElapsed = timeElapsed / timedelta(minutes=1) - 1
    timeLeft = timeLeft / timedelta(minutes=1)
    action = algorithm.on_minute(prices, position, timeElapsed, timeLeft)
    
    if action['side'] == 'close':
        cancel_order()
        time.sleep(0.1)
        close_position()
        if timeLeft < 0 and position:
            cancel_order()
            time.sleep(0.1)
            close_position(limit= prices['c'], qty=abs(int(position[0]['qty'])), side='sell' if position == 'long' else 'buy')
            
    elif action['side'] != 'hold':
        side = 'buy' if action['side'] == 'long' else 'sell'
        orderType = 'limit' if 'limit' in action else 'market'
        limitPrice = action['limit'] if 'limit' in action else None
        stopLoss = action['stop_loss'] if 'stop_loss' in action else None
        stopLimit = action['stop_limit'] if 'stop_limit' in action else None
        if position and position != action['side']:
            account = check_account()
            available_cash = float(account['long_market_value']) - float(account['short_market_value'])
            qty = round(available_cash / prices['c'])
            cancel_order()
            time.sleep(0.1)
            create_order(LONG_SYMBOL, qty, side, orderType, limit_price=limitPrice)
            counter = 0
            while check_positions():
                if counter > 45:
                    print('{}: could not switch to {} position'.format(curTime.time(), action['side']))
                    return
                counter += 1
                time.sleep(1)
            create_order(LONG_SYMBOL, qty, side, orderType, limit_price=limitPrice, stop_loss = stopLoss, stop_limit = stopLimit)
        elif not position:
            available_cash = float(check_account()['cash']) - RESERVED_CASH
            qty = available_cash // prices['c']
            if qty <= 0:
                print('no cash left:', available_cash)
                return
            
            create_order(LONG_SYMBOL, qty, side, orderType, limit_price=limitPrice, stop_loss = stopLoss, stop_limit = stopLimit)
        else:
            print('holding {} position'.format(position))
    
    if DEBUG:
        print('{}: {}@{}'.format(curTime.time(), action['side'] if action['side'] != 'hold' or position else 'wait', prices['c']))
        return
    print('{}: {}@{}'.format(curTime.time(), action['side'], prices['c']))

def run_bot():
    if DEBUG: websocket.enableTrace(True)
    ws = websocket.WebSocketApp(
        DATA_SOCKET,
        on_open=on_open,
        on_message=on_message,
        on_close=on_close,
        on_error=on_error
    )
    if set_market_hours() != -1:
        ws.run_forever()

# tests
if __name__ == '__main__':
    # create_order('SPY', 2,'sell','market','day',None,325.012,326.535)
    # ws = websocket.WebSocketApp(
    #     DATA_SOCKET,
    #     on_open=on_open,
    #     on_message=on_message,
    #     on_close=on_close,
    #     on_error=on_error
    # )
    # ws.run_forever()
    set_market_hours()
    # print(check_account())
    pass
