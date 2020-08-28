# -*- coding: utf-8 -*-

import time
import logging
import asyncio
from asyncio import InvalidStateError


async def looper(delay=0.5):
    loop = asyncio.get_running_loop()
    while True:
        tasks = asyncio.all_tasks()
        logger.debug("Running tasks: %s" % len(tasks))
        for task in tasks:
            logger.debug("%s" % task)
            try:
                # print(task.exception())
                ex = task.exception()
                logger.debug("%s" % ex)
            except InvalidStateError:
                pass
                # logger.debug("InvalidStateError: Exception is not set.")
            except:
                logger.debug("", exc_info=True)
            # print(task.get_name())
        # print(time.time() - t0, loop.is_running(), len(tasks))
        logger.debug("\n")
        await asyncio.sleep(delay)


async def printer(delay=0.5):
    global task3
    loop = asyncio.get_running_loop()
    while True:
        #print(time.time() - t0, loop.is_running())
        #logger.debug("Loop_is_Running = %s\n" % loop.is_running())
        try:
            pass
            ex = task3.exception()
            logger.debug("Exception %s" % ex)
        except InvalidStateError:
            pass
            # logger.debug("InvalidStateError: Exception is not set.")
        except:
            logger.debug("", exc_info=True)
        await asyncio.sleep(delay)


async def interrupter(delay=0.7):
    await asyncio.sleep(delay)
    raise Exception('Test')


async def main():
    global task3
    task1 = asyncio.create_task(looper())
    task2 = asyncio.create_task(printer(1))
    task3 = asyncio.create_task(interrupter(1.2))
    while True:
        await asyncio.sleep(0)
    # await asyncio.wait({task1})

task3 = None

if __name__ == "__main__":
    logger = logging.getLogger("asyncio")
    #logger = logging.getLogger(str(self))
    #logger.propagate = False
    logger.setLevel(logging.DEBUG)
    f_str = '%(asctime)s,%(msecs)3d %(levelname)-7s [%(process)d:%(thread)d] %(filename)s ' \
            '%(funcName)s(%(lineno)s) ' + '%(message)s'
    log_formatter = logging.Formatter(f_str, datefmt='%H:%M:%S')
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    logger.addHandler(console_handler)

    t0 = time.time()

    asyncio.run(main(), debug=True)
