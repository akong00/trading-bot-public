import numpy as np
import pandas as pd

'''
example algorithm: buy at close and sell at open.

A lot of the S&P500 movement occurs between close and open,
so holding during this time gives you the benefit of holding
S&P but also leaves your funds available to algo trade intraday
for more profit.
'''
def on_minute(prices, position, timeElapsed, timeLeft):
    action = dict()
    action['side'] = 'hold'
    if timeLeft <= 1:
        action['side'] = 'long'
        return action
    elif timeElapsed >= 0:
        action['side'] = 'close'
    return action

if __name__ == '__main__':
    print('testing')