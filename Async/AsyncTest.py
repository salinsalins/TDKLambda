# -*- coding: utf-8 -*-

import time
import logging
import asyncio

async def looper():
    loop = asyncio.get_running_loop()
    while True:
        print(time.time() - t0, loop.is_running(), len(asyncio.all_tasks()))
        await asyncio.sleep(0.5)

async def main():
    task1 = asyncio.create_task(looper())
    while True:
        await asyncio.sleep(0)
    #await asyncio.wait({task1})

if __name__ == "__main__":
    logging.getLogger("asyncio").setLevel(logging.DEBUG)
    t0 = time.time()
    asyncio.run(main(), debug=True)
