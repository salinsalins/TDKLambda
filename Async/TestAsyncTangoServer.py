"""Demo Tango Device Server using asyncio green mode"""

import asyncio
from tango import DevState, GreenMode
from tango.server import Device, command, attribute


class AsyncioDevice(Device):
    green_mode = GreenMode.Asyncio

    async def init_device(self):
        await super().init_device()
        self.value = 0.0
        self.set_state(DevState.ON)

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
        await asyncio.sleep(1)
        return self.value

    @test_attribute.write
    async def write_test_attribute(self, value):
        self.value = value
        await asyncio.sleep(0.1)


if __name__ == '__main__':
    AsyncioDevice.run_server()

