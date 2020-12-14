# coding: utf-8
import sys
import time
import tango
import asyncio
import logging

dn = 'binp/test/asyncdemo'
dp = tango.DeviceProxy(dn)
ping = dp.ping()
print(dn, 'ping', ping, 's')
an = 'test_attribute'


def read(a):
    t0 = time.time()
    v = dp.read_attribute(a)
    dt = (time.time() - t0) * 1000.0
    print('read', dn, a, v.value, int(dt), 'ms')


def write(a, value):
    t0 = time.time()
    dp.write_attribute(a, value)
    dt = (time.time() - t0) * 1000.0
    print('write', dn, a, int(dt), 'ms')


async def loop_tasks(delay=0.0, verbose=False, threshold=0, delta=True, exc=False, stack=True, no_self=True):
    tasks = {}
    n0 = 0
    while True:
        last_tasks = tasks
        n1 = n0
        tasks = asyncio.all_tasks()
        # if no_self:
        #     try:
        #         tasks.discard(AsyncioDevice.loop_task)
        #     except:
        #         pass
        n0 = len(tasks)
        delta_flag = False
        if delta:
            for task in last_tasks:
                if task not in tasks:
                    delta_flag = True
            for task in tasks:
                if task not in last_tasks:
                    delta_flag = True
        if n0 > threshold or delta_flag:
            logger.debug("********************  Tasks in loop: %s (%s)", n0, n1)
            if delta_flag:
                for task in last_tasks:
                    if task not in tasks:
                        logger.debug(' - %s', task)
                    if exc:
                        try:
                            ex = task.exception()
                            if ex is not None:
                                raise ex
                        except InvalidStateError:
                            # task is not done yet
                            pass
                        except:
                            logger.debug("Exception in the task", exc_info=True)
            for task in tasks:
                if task not in last_tasks:
                    if delta_flag:
                        logger.debug(' + %s', task)
                        if stack:
                            logger.debug(str(task.get_stack()))
                    elif verbose:
                        logger.debug("   %s" % task)
                elif verbose:
                    logger.debug("   %s" % task)
            logger.debug("********************\n")
        await asyncio.sleep(delay)


def main():
    while True:
        read(an)


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    f_str = '%(asctime)s,%(msecs)3d %(levelname)-7s [%(process)d:%(thread)d] %(filename)s ' \
            '%(funcName)s(%(lineno)s) ' + '%(message)s'
    log_formatter = logging.Formatter(f_str, datefmt='%H:%M:%S')
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    logger.addHandler(console_handler)

    main()