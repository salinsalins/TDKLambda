# coding: utf-8
import sys
import time
import tango
import asyncio

dn1 = 'sys/test/1'
dp1 = tango.DeviceProxy(dn1)
ping1 = dp1.ping()
print(dn1, 'ping', ping1, 's')
an = 'test_attribute'
for i in range(1000):
    t0 = time.time()
    v1 = dp1.read_attribute(an)
    dt = (time.time()-t0)*1000.0
    print(' read', dn1, an, v1.value, int(dt), 'ms')
for i in range(10):
    t0 = time.time()
    dp1.write_attribute(an, float(i))
    dt = (time.time()-t0)*1000.0
    print(' write', dn1, an, int(dt), 'ms')
