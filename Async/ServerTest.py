# coding: utf-8
import sys
import time
import tango
import asyncio

dn1 = 'binp/test/asyncdemo'
#dn1 = 'bint/taet/lambda1'
#dn1 = 'bip/nbi/AsyncLambda'
#dn2 = 'binp/nbi/TDKLambda2'
dp1 = tango.DeviceProxy(dn1)
#dp2 = tango.DeviceProxy(dn2)
ping1 = dp1.ping()
#ping2 = dp2.ping()
print(dn1, 'ping', ping1, 's')
#print(dn2, 'ping', ping2, 's')
an = 'test_attribute'
#ran = ['device_type', 'port', 'address', 'output_state', 'voltage', 'programmed_voltage', 'current', 'programmed_current']
#wan = ['programmed_voltage', 'programmed_current']
wan = ['programmed_voltage']
wv = 0.0
rid = [0,1]
print(' ')

# for i in range(2):
#     for a in ran:
#         t0 = time.time()
#         v1 = dp1.read_attribute(a)
#         dt = (time.time()-t0)*1000.0
#         print(' read', dn1, a, v1.value, int(dt), 'ms')
#         #v2 = dp2.read_attribute(a)
#         #dt = (time.time()-t0)*1000.0
#         #print(dn2, a, v2.value, int(dt), 'ms')
#
#     a = 'output_state'
#     for i in range(10):
#         t0 = time.time()
#         v1 = dp1.read_attribute(a)
#         dt = (time.time()-t0)*1000.0
#         print(' read', dn1, a, v1.value, int(dt), 'ms')
#
#     for i in range(10):
#         for a in wan:
#             try:
#                 t0 = time.time()
#                 dp1.write_attribute(a, wv)
#                 #dt = (time.time()-t0)*1000.0
#                 wv += 0.1
#                 if wv >= 3.0:
#                     wv = 0.0
#             except:
#                 print('exception', sys.exc_info())
#             dt = (time.time()-t0)*1000.0
#             print('write', dn1, a, wv, int(dt), 'ms')
#
#     print(' ')
#     rids = []
#     t0 = time.time()
#     for a in ran:
#         rid = dp1.read_attribute_asynch(a)
#         dt = (time.time()-t0)*1000.0
#         print('async read request', a, int(dt), 'ms', rid)
#         rids.append(rid)
#
#     print(' ')
#     rids = []
#     wids = []
#     t0 = time.time()
#     for i in range(10):
#         for a in wan:
#             wid = dp1.write_attribute_asynch(a, wv)
#             rid = dp1.read_attribute_asynch(a)
#             dt = (time.time()-t0)*1000.0
#             wv += 0.1
#             if wv >= 3.0:
#                 wv = 0.0
#             print('async WRITE request', a, int(dt), 'ms', wid, wv)
#             wids.append(wid)
#
#             for i in range(10):
#                 for a in wan:
#                     try:
#                         t0 = time.time()
#                         dp1.write_attribute(a, wv)
#                         #dt = (time.time()-t0)*1000.0
#                         wv += 0.1
#                         if wv >= 3.0:
#                             wv = 0.0
#                     except:
#                         print('exception', sys.exc_info())
#                     dt = (time.time()-t0)*1000.0
#                     print('write', dn1, a, wv, int(dt), 'ms')
#
#     print(' ')
#     wids = []
#     t0 = time.time()
#     for i in range(10):
#         for a in wan:
#             wid = dp1.write_attribute_asynch(a, wv)
#             dt = (time.time()-t0)*1000.0
#             wv += 0.1
#             if wv >= 3.0:
#                 wv = 0.0
#             print('async WRITE request', a, int(dt), 'ms', wid, wv)
#             wids.append(wid)
#
#     print(' ')
#     results = []
#     while len(rids) > 0:
#         for id in rids:
#             try:
#                 result = dp1.read_attribute_reply(id)
#                 results.append(result.value)
#                 rids.remove(id)
#             except tango.AsynReplyNotArrived:
#                 pass
#             except:
#                 print('Error', sys.exc_info(), result)
#     dt = (time.time()-t0)*1000.0
#     print(results)
#     print('async read time', int(dt), 'ms')
#
#     print(' ')
#     #results = []
#     while len(wids) > 0:
#         for id in wids:
#             try:
#                 result = dp1.write_attribute_reply(id)
#                 #results.append(result.value)
#                 wids.remove(id)
#             except tango.AsynReplyNotArrived:
#                 pass
#             except:
#                 print('Error', sys.exc_info())
#     dt = (time.time()-t0)*1000.0
#     #print(results)
#     print('async write time', int(dt), 'ms')
#     print('\n')
