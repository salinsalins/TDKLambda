"""Demo Tango Device Server using asyncio green mode"""

import logging
import asyncio
import time
from asyncio import InvalidStateError
from asyncio import CancelledError

from tango import DevState, GreenMode
from tango.server import Device, command, attribute


class AsyncioDevice(Device):
    green_mode = GreenMode.Asyncio
    loop_task = None

    async def init_device(self):
        await super().init_device()
        self.value = 0.0
        self.set_state(DevState.RUNNING)
        if AsyncioDevice.loop_task is None:
            # AsyncioDevice.loop_task = asyncio.create_task(loop_tasks(0.0, False, 10, True, False))
            asyncio.get_event_loop().set_debug(True)
            logging.getLogger("asyncio").setLevel(logging.DEBUG)

    @command
    async def long_running_command(self):
        self.set_state(DevState.OPEN)
        await asyncio.sleep(2)
        self.set_state(DevState.CLOSE)

    @command
    async def background_task_command(self):
        loop = asyncio.get_event_loop()
        future = loop.create_task(self.coroutine_target())

    async def coroutine_target(self):
        self.set_state(DevState.INSERT)
        await asyncio.sleep(3)
        self.set_state(DevState.EXTRACT)

    @attribute
    async def test_attribute(self):
        logger.info('Read entry %s', self)
        await asyncio.sleep(0.25)
        logger.info('Read exit %s', self)
        return self.value

    @test_attribute.write
    async def write_test_attribute(self, value):
        t0 = time.time()
        logger.info('Write entry %s', self)
        self.value = value
        # time.sleep(0.5)
        await asyncio.sleep(0.5)
        dt = (time.time() - t0) * 1000.0
        logger.info('Write exit %s', self)
        if dt > 2500.0:
            logger.info('Long write!!!!!!!!!!!!!!!!!!! %s', self)
        return('Write of %s finished in %d ms' % (value, dt))


async def loop_tasks(delay=0.0, verbose=False, threshold=-1, delta=True, exc=False, stack=True, no_self=True):
    tasks = {}
    n0 = 0
    while True:
        last_tasks = tasks
        n1 = n0
        tasks = asyncio.all_tasks()
        if no_self:
            try:
                tasks.discard(AsyncioDevice.loop_task)
            except:
                pass
        n0 = len(tasks)
        delta_flag = False
        if delta:
            for task in last_tasks:
                if task not in tasks:
                    delta_flag = True
            for task in tasks:
                if task not in last_tasks:
                    delta_flag = True
        if n0 > threshold or delta_flag or verbose:
            logger.debug("********************  Tasks in loop: %s (%s)", n0, n1)
            if delta_flag:
                for task in last_tasks:
                    if task not in tasks:
                        logger.debug(' - %s %s', id(task), task)
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
                        logger.debug(' + %s %s', id(task), task)
                        if stack:
                            logger.debug(str(task.get_stack()))
                    elif verbose:
                        logger.debug("   %s %s", id(task), task)
                elif verbose:
                    logger.debug("   %s %s", id(task), task)
            logger.debug("********************\n")
        await asyncio.sleep(delay)


if __name__ == '__main__':
    # configure logger
    logger = logging.getLogger(__name__)
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    f_str = '%(asctime)s,%(msecs)3d %(levelname)-7s [%(process)d:%(thread)d] %(filename)s ' \
            '%(funcName)s(%(lineno)s) %(message)s'
    log_formatter = logging.Formatter(f_str, datefmt='%H:%M:%S')
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    logger.addHandler(console_handler)
    logging.getLogger("tango").addHandler(console_handler)
    logging.getLogger("tango").setLevel(logging.DEBUG)

    # run server
    AsyncioDevice.run_server()

