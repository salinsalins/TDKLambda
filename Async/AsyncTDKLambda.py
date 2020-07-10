#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import socket
from threading import Lock
import time

from Async.AsyncSerial import *
from EmulatedLambda import FakeComPort
from serial import SerialTimeoutException

from TDKLambda import *


class FakeAsyncComPort(FakeComPort):
    SN = 9876543
    RESPONSE_TIME = 0.035

    def __init__(self, port, *args, **kwargs):
        super().__init__(port, *args, **kwargs)
        self.async_lock = asyncio.Lock()

    async def reset_input_buffer(self, timeout=None):
        return True

    async def close(self):
        super().close()
        return True

    async def write(self, cmd, timeout=None):
        async with self.async_lock:
            return super().write(cmd, timeout)

    async def read(self, size=1, timeout=None):
        return super().read(size, timeout)

    async def read_until(self, terminator=b'\r', size=None, timeout=None):
        result = bytearray()
        to = serial.Timeout(timeout)
        async with self.async_lock:
            while True:
                c = await self.read(1)
                if c:
                    result += c
                    if terminator in result:
                        break
                    if size is not None and len(result) >= size:
                        break
                    to.restart(timeout)
                if to.expired():
                    raise SerialTimeoutException('Read timeout')
        return bytes(result)


class AsyncTDKLambda(TDKLambda):
    pass


async def main():
    pd1 = AsyncTDKLambda("COM6", 6)
    await pd1.init()
    pd2 = AsyncTDKLambda("COM6", 7)
    await pd2.init()
    task1 = asyncio.create_task(pd1.read_float("MC?"))
    task2 = asyncio.create_task(pd2.read_float("MC?"))
    task5 = asyncio.create_task(pd1.write_current(2.0))
    task3 = asyncio.create_task(pd1.read_float("PC?"))
    task6 = asyncio.create_task(pd2.write_current(3.0))
    task4 = asyncio.create_task(pd2.read_float("PC?"))
    t_0 = time.time()
    await asyncio.wait({task1})
    dt = int((time.time() - t_0) * 1000.0)    # ms
    v1 = task1.result()
    v2 = task2.result()
    v3 = task3.result()
    v4 = task4.result()
    print('1: ', '%4d ms ' % dt, 'MC?=', v1, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
    print('2: ', '%4d ms ' % dt, 'MC?=', v2, 'to=', '%5.3f' % pd2.read_timeout, pd2.port, pd2.addr)
    print('3: ', '%4d ms ' % dt, 'PC?=', v3, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
    print('3: ', '%4d ms ' % dt, 'PC?=', v4, 'to=', '%5.3f' % pd2.read_timeout, pd2.port, pd2.addr)
    print('Elapsed: %4d ms ' % dt)

if __name__ == "__main__":
    # pd1 = TDKLambda("COM4", 6)
    # pd2 = TDKLambda("COM4", 7)
    # for i in range(5):
    #     t_0 = time.time()
    #     v1 = pd1.read_float("PC?")
    #     dt1 = int((time.time() - t_0) * 1000.0)    # ms
    #     print('1: ', '%4d ms ' % dt1,'PC?=', v1, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
    #     t_0 = time.time()
    #     v1 = pd1.read_float("MV?")
    #     dt1 = int((time.time() - t_0) * 1000.0)    # ms
    #     print('1: ', '%4d ms ' % dt1,'MV?=', v1, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
    #     t_0 = time.time()
    #     v1 = pd1.send_command("PV 1.0")
    #     dt1 = int((time.time() - t_0) * 1000.0)    # ms
    #     print('1: ', '%4d ms ' % dt1,'PV 1.0', v1, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
    #     t_0 = time.time()
    #     v1 = pd1.read_float("PV?")
    #     dt1 = int((time.time() - t_0) * 1000.0)    # ms
    #     print('1: ', '%4d ms ' % dt1,'PV?=', v1, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
    #     t_0 = time.time()
    #     v3 = pd1.read_all()
    #     dt1 = int((time.time() - t_0) * 1000.0)    # ms
    #     print('1: ', '%4d ms ' % dt1,'DVC?=', v3, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
    #     t_0 = time.time()
    #     v2 = pd2.read_float("PC?")
    #     dt2 = int((time.time() - t_0) * 1000.0)    # ms
    #     print('2: ', '%4d ms ' % dt2,'PC?=', v2, 'to=', '%5.3f' % pd2.read_timeout, pd2.port, pd2.addr)
    #     t_0 = time.time()
    #     v4 = pd2.read_all()
    #     dt1 = int((time.time() - t_0) * 1000.0)    # ms
    #     print('2: ', '%4d ms ' % dt1,'DVC?=', v4, 'to=', '%5.3f' % pd2.read_timeout, pd2.port, pd2.addr)
    #     time.sleep(0.1)

    asyncio.run(main())
