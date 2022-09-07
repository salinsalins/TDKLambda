"""Demo Tango Device Server using asyncio green mode"""

import logging
import asyncio
import sys
import time
import traceback
from asyncio import InvalidStateError
from asyncio import CancelledError

import tango
from tango import DevState, GreenMode
from tango.server import Device, command, attribute

from config_logger import config_logger

old_tasks = []
n = 0


async def loop_task():
    global old_tasks, n
    while True:
        d = 0
        tasks = asyncio.all_tasks()
        # logger.debug("*******  Tasks in loop: %s" % len(tasks))
        for task in tasks:
            if task not in old_tasks:
                logger.debug("%d %d New       %s", len(tasks), n, task)
                d = 1
        for task in old_tasks:
            if task not in tasks:
                logger.debug("%d %d Completed %s", len(tasks), n, task)
                d = 1
                if task.exception():
                    print('Exception', task.exception(), file=sys.stderr)
                    traceback.print_tb(task.exception().__traceback__)
        old_tasks = tasks
        n += d
        await asyncio.sleep(0)


class AsyncioDevice(Device):
    green_mode = GreenMode.Asyncio

    async def init_device(self):
        await super().init_device()
        self.value = time.time()
        self.set_state(DevState.RUNNING)
        self.task = asyncio.create_task(loop_task(), name='asyncio.all_tasks')

    async def dev_state(self):
        return DevState.RUNNING

    async def dev_status(self):
        return 'Device is at RUNNING! state'

    # @attribute
    # async def test_attribute2(self):
    #     t0 = time.time()
    #     logger.info('Read entry %s', self)
    #     # time.sleep(0.25)
    #     await asyncio.sleep(0)
    #     dt = (time.time() - t0) * 1000.0
    #     logger.info('Read mark1 %s %d', self, dt)
    #     await asyncio.sleep(0)
    #     dt = (time.time() - t0) * 1000.0
    #     logger.info('Read mark2 %s %d', self, dt)
    #     await asyncio.sleep(0)
    #     dt = (time.time() - t0) * 1000.0
    #     logger.info('Read mark3 %s %d', self, dt)
    #     await asyncio.sleep(0.5)
    #     dt = (time.time() - t0) * 1000.0
    #     logger.info('Read exit %s %d', self, dt)
    #     # self.value = time.time()
    #     return self.value

    @attribute(access=tango.AttrWriteType.READ_WRITE)
    async def test_attribute(self):
        t0 = time.time()
        logger.info('Read entry %s', self)
        # await asyncio.sleep(0)
        # dt = (time.time() - t0) * 1000.0
        # logger.info('Read mark1 %s %d', self, dt)
        # await asyncio.sleep(0)
        # dt = (time.time() - t0) * 1000.0
        # logger.info('Read mark2 %s %d', self, dt)
        # await asyncio.sleep(0)
        # dt = (time.time() - t0) * 1000.0
        # logger.info('Read mark3 %s %d', self, dt)
        await asyncio.sleep(0.25)
        # time.sleep(0.25)
        dt = (time.time() - t0) * 1000.0
        logger.info('Read exit %s %d', self, dt)
        # self.value = time.time()
        return self.value

    # def is_test_attribute_allowed(self):
    #     t0 = time.time()
    #     logger.info('is_allowed entry %s', self)
    #     return True

    @test_attribute.write
    async def write_test_attribute(self, value):
        t0 = time.time()
        logger.info('Write entry %s', self)
        self.value = value
        # await asyncio.sleep(0.1)
        # dt = (time.time() - t0) * 1000.0
        # logger.info('Write mark1 %s %d', self, dt)
        # await asyncio.sleep(0.2)
        # dt = (time.time() - t0) * 1000.0
        # logger.info('Write mark2 %s %d', self, dt)
        # await asyncio.sleep(0.3)
        # dt = (time.time() - t0) * 1000.0
        # logger.info('Write mark3 %s %d', self, dt)
        # await asyncio.sleep(0)
        # time.sleep(0.5)
        await asyncio.sleep(0.5)
        dt = (time.time() - t0) * 1000.0
        logger.info('Write exit %s %d', self, dt)
        return True


if __name__ == '__main__':
    logger = config_logger()
    # run server
    AsyncioDevice.run_server()
