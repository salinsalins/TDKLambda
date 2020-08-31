# coding: utf-8
import time
import tango

dn = 'binp/nbi/TDKLambda1'
dp = tango.DeviceProxy(dn)
ping = dp.ping()
print(dn, 'ping', ping)
ran = ['programmed_voltage', 'voltage', 'current', 'programmed_current']
wan = ['programmed_voltage', 'programmed_current']
wv = 0.0
while True:
    for a in ran:
        t0 = time.time()
        v = dp.read_attribute(a)
        dt = (time.time()-t0)*1000.0
        print(a, v.value, int(dt), 'ms')
    for a in wan:
        t0 = time.time()
        dp.write_attribute(a, wv)
        dt = (time.time()-t0)*1000.0
        wv += 0.1
        if wv >= 1.0:
            wv = 0.0
        print(a, 'write', wv, int(dt), 'ms')

