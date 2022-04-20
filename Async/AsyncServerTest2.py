# coding: utf-8
import sys
import time
import tango
import asyncio
import logging

dn = 'binp/test/asyncdemo'
dp = tango.DeviceProxy(dn)
an = 'test_attribute'

ping = dp.ping()
print(dn, 'ping', ping, 's')


def read(a):
    t0 = time.time()
    v = dp.read_attribute(a)
    dt = (time.time() - t0) * 1000.0
    print('read', dn, a, v.value, int(dt), 'ms')


def write(a, v):
    t0 = time.time()
    dp.write_attribute(a, v)
    dt = (time.time() - t0) * 1000.0
    print('write', dn, a, int(dt), 'ms')


async def read_async(a):
    t0 = time.time()
    id = dp.read_attribute_asynch(a)
    while True:
        try:
            v = dp.read_attribute_reply(id)
            break
        except:
            await asyncio.sleep(0)
    dt = (time.time() - t0) * 1000.0
    print('read_async', dn, a, v.value, int(dt), 'ms')


async def write_async(a, v):
    t0 = time.time()
    id = dp.write_attribute_asynch(a, v)
    while True:
        try:
            dp.write_attribute_reply(id)
            break
        except:
            await asyncio.sleep(0)
    dt = (time.time() - t0) * 1000.0
    print('write_async', dn, a, v, int(dt), 'ms')


def main():
    while True:
        #read('test_attribute')
        read('state')
        #write('test_attribute', 1.0)
        #read('status')


async def main_async():
    task1 = asyncio.create_task(write_async(an, 1.0))
    task2 = asyncio.create_task(read_async(an))
    task3 = asyncio.create_task(read_async('state'))
    while True:
        if task1.done():
            task1 = asyncio.create_task(write_async(an, 1.0))
        if task2.done():
            task2 = asyncio.create_task(read_async(an))
        if task3.done():
            task3 = asyncio.create_task(read_async('state'))
        await asyncio.sleep(0)


if __name__ == "__main__":
    #main()
    asyncio.run(main_async())
