"""Demo Tango Device Server"""

import logging
import time

from tango import DevState
from tango.server import Device, attribute


class TestDevice(Device):

    def init_device(self):
        await super().init_device()
        self.value = 0.0
        self.set_state(DevState.RUNNING)

    @attribute
    def test_attribute(self):
        t0 = time.time()
        logger.info('Read entry %s', self)
        dt = (time.time() - t0) * 1000.0
        logger.info('Read exit %s', self, int(dt))
        return self.value

    @test_attribute.write
    async def write_test_attribute(self, value):
        t0 = time.time()
        logger.info('Write entry %s', self)
        self.value = value
        # time.sleep(0.5)
        dt = (time.time() - t0) * 1000.0
        logger.info('Write exit %s', self, int(dt))
        return ('Write of %s finished in %d ms' % (value, dt))


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
    TestDevice.run_server()

