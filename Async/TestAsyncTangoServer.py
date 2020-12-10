"""Demo Tango Device Server using asyncio green mode"""

import logging
import asyncio
import time

from tango import DevState, GreenMode
from tango.server import Device, command, attribute


class AsyncioDevice(Device):
    green_mode = GreenMode.Asyncio

    async def init_device(self):
        await super().init_device()
        self.value = 0.0
        self.set_state(DevState.RUNNING)

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
        logger.info('Entry %s', self)
        await asyncio.sleep(0.5)
        logger.info('Exit %s', self)
        return self.value

    @test_attribute.write
    async def write_test_attribute(self, value):
        global n
        n1 = n
        n += 1
        logger.info('Entry %s', n1)
        self.value = value
        time.sleep(1.5)
        #await asyncio.sleep(0.5)
        logger.info('Exit %s', n1)

n = 0

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

    # run server
    AsyncioDevice.run_server()

