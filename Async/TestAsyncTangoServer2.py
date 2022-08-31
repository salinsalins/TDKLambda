"""Demo Tango Device Server using asyncio green mode"""

import logging
import asyncio
import time
from asyncio import InvalidStateError
from asyncio import CancelledError

from tango import DevState, GreenMode
from tango.server import Device, command, attribute

from config_logger import config_logger


class AsyncioDevice(Device):
    green_mode = GreenMode.Asyncio

    async def init_device(self):
        await super().init_device()
        self.value = time.time()
        self.set_state(DevState.RUNNING)

    @attribute
    async def test_attribute(self):
        t0 = time.time()
        logger.info('Read entry %s', self)
        # time.sleep(0.25)
        await asyncio.sleep(0.25)
        dt = (time.time() - t0) * 1000.0
        logger.info('Read exit %s %d', self, dt)
        # self.value = time.time()
        return self.value

    @test_attribute.write
    async def write_test_attribute(self, value):
        t0 = time.time()
        logger.info('Write entry %s', self)
        self.value = value
        # time.sleep(0.5)
        await asyncio.sleep(0.5)
        dt = (time.time() - t0) * 1000.0
        logger.info('Write exit %s %d', self, dt)
        # if dt > 2500.0:
        #     logger.info('Long write!!!!!!!!!!!!!!!!!!! %s', self)
        return('Write of %s finished in %d ms' % (value, dt))


if __name__ == '__main__':
    logger = config_logger()
    # run server
    AsyncioDevice.run_server()

