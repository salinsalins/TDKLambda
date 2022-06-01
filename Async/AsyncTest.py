# -*- coding: utf-8 -*-

import time
import logging

from config_logger import config_logger

l = config_logger()

def f(x):
    if x == 0:
        return x
    yield x+1
    yield x+2
    # return x+1

for i in range(0, 3):
    print(i, f(i))
    for j in f(i):
        print(j)
