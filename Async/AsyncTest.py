# -*- coding: utf-8 -*-

import time
import logging
import asyncio


async def looper(delay=0.5):
    loop = asyncio.get_running_loop()
    while True:
        tasks = asyncio.all_tasks()
        for task in tasks:
            print(task)
            try:
                print(task.exception())
            except:
                print('Exception')
            # print(task.get_name())
        print(time.time() - t0, loop.is_running(), len(tasks))
        await asyncio.sleep(delay)


async def printer(delay=0.5):
    loop = asyncio.get_running_loop()
    while True:
        print(time.time() - t0, loop.is_running())
        await asyncio.sleep(delay)


async def interrupter(delay=0.5):
    await asyncio.sleep(delay)
    raise Exception('Test')


async def main():
    task1 = asyncio.create_task(looper())
    task2 = asyncio.create_task(printer(1))
    task3 = asyncio.create_task(interrupter(1.2))
    while True:
        await asyncio.sleep(0)
    # await asyncio.wait({task1})

if __name__ == "__main__":
    logging.getLogger("asyncio").setLevel(logging.DEBUG)
    t0 = time.time()
    asyncio.run(main(), debug=True)
