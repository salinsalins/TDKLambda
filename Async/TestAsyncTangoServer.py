"""Demo Tango Device Server using asyncio green mode"""

import logging
import asyncio
import time
from asyncio import InvalidStateError

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
            AsyncioDevice.loop_task = asyncio.create_task(loop_tasks(0.0))

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
        await asyncio.sleep(0.5)
        logger.info('Read exit %s', self)
        return self.value

    @test_attribute.write
    async def write_test_attribute(self, value):
        global n
        n1 = n
        n += 1
        logger.info('Write entry %s', self)
        self.value = value
        # time.sleep(0.5)
        await asyncio.sleep(0.5)
        logger.info('Write exit %s', self)


n=0


async def loop_tasks(delay=0.5):
    loop = asyncio.get_running_loop()
    tasks = asyncio.all_tasks()
    logger.debug("********************\nTasks in loop: %s" % len(tasks))
    for task in tasks:
        logger.debug("%s" % task)
        # try:
        #     # print(task.exception())
        #     ex = task.exception()
        #     logger.debug("Exception %s" % ex)
        # except InvalidStateError:
        #     pass
        #     # logger.debug("InvalidStateError: Exception is not set.")
        # except:
        #     logger.debug("Exception", exc_info=True)
        # # print(task.get_name())
    # print(time.time() - t0, loop.is_running(), len(tasks))
    logger.debug("********************\n")
    # if len(tasks) <= 1:
    #     logger.debug("Closing loop")
    #     loop.stop()
    #     loop.close()
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

    # run server
    AsyncioDevice.run_server()

