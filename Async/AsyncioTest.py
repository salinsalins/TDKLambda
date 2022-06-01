# -*- coding: utf-8 -*-

import time
import logging
import asyncio
from asyncio import InvalidStateError
from threading import Thread


async def loop_tasks(delay=0.5):
    while True:
        tasks = asyncio.all_tasks()
        logger.debug("*****************  Tasks in loop: %s" % len(tasks))
        for task in tasks:
            logger.debug("%s" % task)
            # try:
            #     # print(task.exception())
            #     ex = task.exception()
            #     logger.debug("%s" % ex)
            # except InvalidStateError:
            #     pass
            #     # logger.debug("InvalidStateError: Exception is not set.")
            # except:
            #     logger.debug("", exc_info=True)
            # # print(task.get_name())
        logger.debug("*****************\n")
        await asyncio.sleep(delay)


async def loop_stopper(n=1, m=999999):
    loop = asyncio.get_running_loop()
    while True:
        tasks = asyncio.all_tasks()
        m -= 1
        if len(tasks) <= n or m <= 0:
            logger.debug("Closing loop")
            loop.stop()
            loop.close()
        await asyncio.sleep(0)


async def raise_exception(delay=0.7):
    await asyncio.sleep(delay)
    raise Exception('Test')

# to use as decorator
def benchmark(func):
    async def wrapper(*args, **kwargs):
        start = time.time()
        await func(*args, **kwargs)
        end = time.time()
        print('Время выполнения %s %s секунд' % (func, end-start))
    return wrapper

# to use as decorator
def enter_exit(func):
    async def wrapper(*args, **kwargs):
        start = time.time()
        print('Enter ', func)
        await func(*args, **kwargs)
        end = time.time()
        print('Exit ', func)
        print('Время выполнения %s %s секунд' % (func, end-start))
    return wrapper

N = 0
#@enter_exit
async def wait(task):
    await task

async def context_test(m):
    global N
    n = N
    N += 1
    while True:
        logger.debug('Before sleep %s %s', m, n)
        await asyncio.sleep(0)
        logger.debug('After Sleep %s %s', m, n)


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
    task1 = asyncio.create_task(loop_tasks(0))
    task2 = asyncio.create_task(asyncio.sleep(.1))
    task3 = asyncio.create_task(asyncio.sleep(.2))
    task4 = asyncio.create_task(asyncio.sleep(.3))
    task5 = asyncio.create_task(context_test(1))
    task6 = asyncio.create_task(context_test(2))
    task7 = asyncio.create_task(loop_stopper(5))
    while True:
        await asyncio.sleep(0)


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

    # #new_loop = asyncio.new_event_loop()
    # new_loop = asyncio.get_event_loop()
    # t = Thread(target=start_loop, args=(new_loop,))
    # t.start()
    # #new_loop.call_soon_threadsafe(more_work, 6)
    # #new_loop.call_soon_threadsafe(more_work, 3)
    #
    # asyncio.run_coroutine_threadsafe(do_some_work(5), new_loop)
    # asyncio.run_coroutine_threadsafe(do_some_work(3), new_loop)
    # asyncio.run_coroutine_threadsafe(looper(), new_loop)




