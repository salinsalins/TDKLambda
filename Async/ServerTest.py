# coding: utf-8
import sys
import time
import tango

dn1 = 'binp/nbi/TDKLambda1'
dn2 = 'binp/nbi/TDKLambda2'
dp1 = tango.DeviceProxy(dn1)
dp2 = tango.DeviceProxy(dn2)
ping1 = dp1.ping()
ping2 = dp2.ping()
print(dn1, 'ping', ping1)
print(dn2, 'ping', ping2)
ran = ['programmed_voltage', 'voltage', 'current', 'programmed_current']
wan = ['programmed_voltage', 'programmed_current']
wv = 0.0
rid = [0,1]

while True:
    for a in ran:
        t0 = time.time()
        v1 = dp1.read_attribute(a)
        dt = (time.time()-t0)*1000.0
        print(a, v1.value, int(dt), 'ms')
        v2 = dp2.read_attribute(a)
        dt = (time.time()-t0)*1000.0
        print(a, v1.value, v2.value, int(dt), 'ms')
    for a in wan:
        t0 = time.time()
        dp1.write_attribute(a, wv)
        dt = (time.time()-t0)*1000.0
        wv += 0.1
        if wv >= 1.0:
            wv = 0.0
        print(a, 'write', wv, int(dt), 'ms')

    t0 = time.time()
    rid[0] = dp1.read_attribute_asynch(ran[0])
    rid[1] = dp2.read_attribute_asynch(ran[0])
    dt = (time.time()-t0)*1000.0
    print('\nasync read request', int(dt), 'ms', rid[0], rid[1])
    read_result1 = None
    read_result2 = None
    flag = True
    while flag:
        try:
            if read_result1 is None:
                read_result1 = dp1.read_attribute_reply(rid[0])
            read_result2 = dp2.read_attribute_reply(rid[1])
            flag = False
        except tango.AsynReplyNotArrived:
            pass
        except:
            print('Error', sys.exc_info(), read_result1, read_result2)
            #flag = False
    dt = (time.time()-t0)*1000.0
    print('async read time', int(dt), 'ms')
    print('\n')
