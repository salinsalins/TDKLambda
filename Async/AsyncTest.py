# -*- coding: utf-8 -*-

import time
import logging
import asyncio
from asyncio import InvalidStateError
from threading import Thread


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
        if len(tasks) <= 1:
            logger.debug("Closing loop")
            loop.stop()
            loop.close()
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


def benchmark(func):
    async def wrapper(*args, **kwargs):
        start = time.time()
        await func(*args, **kwargs)
        end = time.time()
        print('Время выполнения %s %s секунд' % (func, end-start))
    return wrapper


def enterexit(func):
    async def wrapper(*args, **kwargs):
        start = time.time()
        print('Enter ', func)
        await func(*args, **kwargs)
        print('Exit ', func)
        end = time.time()
        print('Время выполнения %s %s секунд' % (func, end-start))
    return wrapper


@enterexit
async def wait(task):
    await task


def start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


def more_work(x):
    print("More work %s" % x)
    time.sleep(x)
    print("Finished more work %s" % x)


async def do_some_work(x):
    print("Waiting " + str(x))
    await asyncio.sleep(x)
    print("Waiting " + str(x) + ' finished')


async def main():
    global task3
    task1 = asyncio.create_task(looper())
    task2 = asyncio.create_task(printer(1))
    task3 = asyncio.create_task(interrupter(1.2))
    task4 = asyncio.create_task(asyncio.sleep(3))
    task5 = asyncio.create_task(wait(task4))
    task6 = asyncio.create_task(wait(task4))
    # while True:
    #     await asyncio.sleep(0)
    at = await task5
    logger.debug("at1 %s", at)
    at = await task6
    logger.debug("at2 %s", at)
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

    # asyncio.run(main(), debug=True)

    #new_loop = asyncio.new_event_loop()
    new_loop = asyncio.get_event_loop()
    t = Thread(target=start_loop, args=(new_loop,))
    t.start()
    #new_loop.call_soon_threadsafe(more_work, 6)
    #new_loop.call_soon_threadsafe(more_work, 3)

    asyncio.run_coroutine_threadsafe(do_some_work(5), new_loop)
    asyncio.run_coroutine_threadsafe(do_some_work(3), new_loop)
    asyncio.run_coroutine_threadsafe(looper(), new_loop)




