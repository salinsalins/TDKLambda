# -*- coding: utf-8 -*-
"""TDK Lambda Genesis series power supply tango device server"""
from Async.AsyncTDKLambda import AsyncTDKLambda

import logging
import time
from math import isnan
import asyncio
from asyncio import InvalidStateError
import threading

import tango
from tango import AttrQuality, AttrWriteType, DispLevel, DevState, DebugIt, DeviceAttribute
from tango import GreenMode
from tango.server import Device, attribute, command

from Utils import *

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'Async_TDKLambda_Server'
APPLICATION_VERSION = '1_0'

# config logger
# logger = config_logger(level=logging.DEBUG)
# logger = logging.getLogger(__name__)
# logger.propagate = False
# logger.setLevel(logging.DEBUG)
# f_str = '%(asctime)s,%(msecs)3d %(levelname)-7s [%(process)d:%(thread)d] %(filename)s ' \
#         '%(funcName)s(%(lineno)s) %(message)s'
# log_formatter = logging.Formatter(f_str, datefmt='%H:%M:%S')
# console_handler = logging.StreamHandler()
# console_handler.setFormatter(log_formatter)
# logger.addHandler(console_handler)


class Async_TDKLambda_Server(Device):
    green_mode = GreenMode.Asyncio
    #reen_mode = GreenMode.Synchronous

    READING_VALID_TIME = 3.0
    devices = []

    device_type = attribute(label="PS Type", dtype=str,
                           display_level=DispLevel.OPERATOR,
                           access=AttrWriteType.READ,
                           unit="", format="%s",
                           doc="TDKLambda device type")

    port = attribute(label="Port", dtype=str,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ,
                            unit="", format="%s",
                            doc="TDKLambda port")

    address = attribute(label="Address", dtype=str,
                     display_level=DispLevel.OPERATOR,
                     access=AttrWriteType.READ,
                     unit="", format="%s",
                     doc="TDKLambda address")

    output_state = attribute(label="Output", dtype=bool,
                             display_level=DispLevel.OPERATOR,
                             access=AttrWriteType.READ_WRITE,
                             unit="", format="",
                             doc="Output on/off state")

    voltage = attribute(label="Voltage", dtype=float,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ,
                        unit="V", format="%6.2f",
                        min_value=0.0,
                        doc="Measured voltage")

    programmed_voltage = attribute(label="Programmed Voltage", dtype=float,
                                   display_level=DispLevel.OPERATOR,
                                   access=AttrWriteType.READ_WRITE,
                                   unit="V", format="%6.2f",
                                   min_value=0.0,
                                   doc="Programmed voltage")

    current = attribute(label="Current", dtype=float,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ,
                        unit="A", format="%6.2f",
                        min_value=0.0,
                        doc="Measured current")

    programmed_current = attribute(label="Programmed Current", dtype=float,
                                   display_level=DispLevel.OPERATOR,
                                   access=AttrWriteType.READ_WRITE,
                                   unit="A", format="%6.2f",
                                   min_value=0.0,
                                   doc="Programmed current")

    def get_device_property(self, prop: str, default=None):
        name = self.get_name()
        # create device proxy
        if not hasattr(self, 'dp'):
            self.dp = tango.DeviceProxy(name)
        # read property
        pr = self.dp.get_property(prop)[prop]
        result = None
        if len(pr) > 0:
            result = pr[0]
        if default is None:
            return result
        try:
            if result is None or result == '':
                result = default
            else:
                result = type(default)(result)
            return result
        except:
            return default

    async def init_device(self):
        self.lock = asyncio.Lock()
        self.task = None
        self.error_count = 0
        self.values = [float('NaN')] * 6
        self.time = time.time() - self.READING_VALID_TIME - 1.0
        self.timeval = tango.TimeVal.now()
        self.set_state(DevState.INIT)
        Device.init_device(self)
        self.last_level = logging.INFO
        # get device proxy
        self.dp = tango.DeviceProxy(self.get_name())
        # get all defined device properties
        self.proplist = self.dp.get_property_list('*')
        self.properties = self.dp.get_property(self.proplist)
        # read port and addr properties
        self.prt = self.get_device_property('port', 'COM1')
        self.addr = self.get_device_property('addr', 6)
        # config logger
        #self.logger = logging.getLogger(__name__)
        self.logger = logging.getLogger('%s:%s' %(self.prt, self.addr))
        self.logger.propagate = False
        self.logger.setLevel(logging.DEBUG)
        self.f_str = '%(asctime)s,%(msecs)3d %(levelname)-7s [%(process)d:%(thread)d] %(filename)s ' \
                '%(funcName)s(%(lineno)s) ' + ('%s:%s' %(self.prt, self.addr)) + ' - %(message)s'
        log_formatter = logging.Formatter(self.f_str, datefmt='%H:%M:%S')
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_formatter)
        if not self.logger.hasHandlers():
            self.logger.addHandler(console_handler)
        # create TDKLambda device
        self.tdk = AsyncTDKLambda(self.prt, self.addr, logger=self.logger)
        await self.tdk.init()
        # check if device OK
        if self.tdk.initialized():
            # add device to list
            Async_TDKLambda_Server.devices.append(self)
            # set state to running
            self.set_state(DevState.RUNNING)
            # set maximal values for set voltage and current
            self.programmed_current.set_max_value(self.tdk.max_current)
            self.programmed_voltage.set_max_value(self.tdk.max_voltage)
            await self.read_all()
            msg = '%s:%d TDKLambda %s created successfully' % (self.tdk.port, self.tdk.addr, self.tdk.id)
            self.logger.info(msg)
            self.info_stream(msg)
        else:
            self.set_state(DevState.FAULT)
            msg = '%s:%d TDKLambda device created with errors' % (self.tdk.port, self.tdk.addr)
            self.logger.error(msg)
            self.error_stream(msg)

    async def delete_device(self):
        if self in Async_TDKLambda_Server.devices:
            Async_TDKLambda_Server.devices.remove(self)
            self.tdk.__del__()
            msg = ' %s:%d TDKLambda device has been deleted' % (self.tdk.port, self.tdk.addr)
            self.logger.info(msg)
            self.info_stream(msg)

    async def read_device_type(self):
        self.logger.debug('------------Entry----------')
        if self.tdk.initialized():
            return self.tdk.id
        return "Uninitialized"

    async def read_port(self):
        self.logger.debug('------------Entry----------')
        if self.tdk.initialized():
            return self.tdk.port
        return "Unknown"

    async def read_address(self):
        self.logger.debug('------------Entry----------')
        if self.tdk.initialized():
            return str(self.tdk.addr)
        return "-1"

    async def attrib_r_wrapper(self, coro, valid_time=0):
        try:
            if not self.tdk.initialized():
                msg = "Reading offline device %s" % self
                self.logger.warning(msg)
                self.set_fault()
                return False
            if self.task is not None and not self.task.done():
                self.logger.debug('============Awaiting task 3 %s', self.task)
                await self.task
                self.logger.debug('============Awaited 3')
            self.task = asyncio.create_task(coro)
            if time.time() - self.time > valid_time:
                self.logger.debug('============Awaiting task 4 %s', self.task)
                await self.task
                self.logger.debug('============Awaited 4')
                # try to get result
                result = self.task.result()
            return True
        except:
            self.task.print_stack()
            self.logger.debug("\nTask %s Exception info:", self.task, exc_info=True)
            return False

    async def read_all(self):
        t0 = time.time()
        try:
            values = await self.tdk.read_all()
            self.time = time.time()
            self.timeval = tango.TimeVal.now()
            self.values = values
            msg = '%s:%d read_all %s ms %s' % \
                  (self.tdk.port, self.tdk.addr, int((self.time - t0) * 1000.0), values)
            self.logger.debug(msg)
            # self.debug_stream(msg)
            return values
        except:
            self.time = time.time()
            self.timeval = tango.TimeVal.now()
            self.set_fault()
            msg = '%s:%d read_all error' % (self.tdk.port, self.tdk.addr)
            self.logger.info(msg)
            self.logger.debug(' ', exc_info=True)
            self.info_stream(msg)

    async def read_one(self, attr: tango.Attribute, index: int, message: str):
        val = float('nan')
        if await self.attrib_r_wrapper(self.read_all(), valid_time=self.READING_VALID_TIME):
            val = self.values[index]
            attr.set_value(val)
            attr.set_date(self.timeval)
            if isnan(val):
                attr.set_quality(tango.AttrQuality.ATTR_INVALID)
                self.set_fault()
                msg = ('%s ' + message) % self
                # self.info_stream(msg)
                self.logger.warning(msg)
            else:
                attr.set_quality(tango.AttrQuality.ATTR_VALID)
                self.set_running()
        else:
            attr.set_value(val)
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)
            self.set_fault()
        return val

    async def read_voltage(self, attr: tango.Attribute):
        self.logger.debug('------------Entry----------')
        async with self.lock:
            self.logger.debug('++++++++++++In Lock+++++++++++')
            v = await self.read_one(attr, 0, "Output voltage read error")
            return v

    async def read_current(self, attr: tango.Attribute):
        self.logger.debug('------------Entry----------')
        async with self.lock:
            self.logger.debug('++++++++++++In Lock+++++++++++')
            return await self.read_one(attr, 2, "Output current read error")

    async def read_programmed_voltage(self, attr: tango.Attribute):
        self.logger.debug('------------Entry----------')
        async with self.lock:
            self.logger.debug('++++++++++++In Lock+++++++++++')
            return await self.read_one(attr, 1, "Programmed voltage read error")

    async def read_programmed_current(self, attr: tango.Attribute):
        self.logger.debug('------------Entry----------')
        async with self.lock:
            self.logger.debug('++++++++++++In Lock+++++++++++')
            return await self.read_one(attr, 3, "Programmed current read error")

    async def write_one(self, attrib, value, cmd, message):
        result = False
        try:
            if not self.tdk.initialized():
                attrib.set_quality(tango.AttrQuality.ATTR_INVALID)
                msg = "%s Writing to offline device" % self
                #self.info_stream(msg)
                self.logger.warning(msg)
                result = False
                self.set_fault()
            else:
                if self.task is not None and not self.task.done():
                    self.logger.debug('============Awaiting task 1 %s', self.task)
                    await self.task
                    self.logger.debug('============Awaited 1')
                self.task = asyncio.create_task(self.tdk.write_value(cmd, value))
                #done, pending = await asyncio.wait({self.task})
                self.logger.debug('============Awaiting task 2 %s', self.task)
                await self.task
                self.logger.debug('============Awaited 2')
                if self.task.cancelled():
                    self.logger.warning('Task %s was cancelled', self.task)
                ex = self.task.exception()
                if ex is not None:
                    self.logger.warning('Exception %s executing Task %s', ex, self.task)
                    raise ex
                result = self.task.result()
                #result = await self.tdk.write_value(cmd, value)
            if result:
                attrib.set_quality(tango.AttrQuality.ATTR_VALID)
                self.set_running()
            else:
                attrib.set_quality(tango.AttrQuality.ATTR_INVALID)
                msg = ('%s ' + message) % self
                self.logger.warning(msg)
                self.info_stream(msg)
                self.set_fault()
            return result
        except:
            self.logger.warning('Exception %s Task %s', ex, self.task)
            attrib.set_quality(tango.AttrQuality.ATTR_INVALID)
            msg = ('%s ' + message) % self
            self.logger.warning(msg)
            self.info_stream(msg)
            self.logger.debug("", exc_info=True)
            self.set_fault()
            return result

    async def write_programmed_voltage(self, value):
        self.logger.debug('------------Entry----------')
        async with self.lock:
            self.logger.debug('++++++++++++In Lock+++++++++++')
            result = await self.write_one(self.programmed_voltage, value, b'PV', 'Error writing programmed voltage')
            return result

    async def write_programmed_current(self, value):
        self.logger.debug('------------Entry----------')
        async with self.lock:
            self.logger.debug('++++++++++++In Lock+++++++++++')
            return await self.write_one(self.programmed_current, value, b'PC', 'Error writing programmed current')

    async def read_output_state(self, attr: tango.Attribute):
        self.logger.debug('------------Entry----------')
        async with self.lock:
            self.logger.debug('++++++++++++In Lock+++++++++++')
            response = None
            try:
                if not self.tdk.initialized():
                    self.set_fault()
                    attr.set_value(False)
                    attr.set_quality(tango.AttrQuality.ATTR_INVALID)
                    return False
                if self.task is not None and not self.task.done():
                    await self.task
                self.task = asyncio.create_task(self.tdk.read_output())
                await self.task
                response = self.task.result()
                #response = await self.tdk.read_output()
                if response is None:
                    msg = "%s Error reading output state" % self
                    self.info_stream(msg)
                    self.logger.warning(msg)
                    self.set_fault()
                    attr.set_value(False)
                    attr.set_quality(tango.AttrQuality.ATTR_INVALID)
                    return False
                attr.set_value(response)
                attr.set_quality(tango.AttrQuality.ATTR_VALID)
                return response
            except:
                self.logger.debug("Task %s error", self.task)
                self.logger.debug("Exception info:", exc_info=True)
                return response

    async def write_output_state(self, value):
        self.logger.debug('------------Entry----------')
        async with self.lock:
            self.logger.debug('++++++++++++In Lock+++++++++++')
            if not self.tdk.initialized():
                msg = '%s:%d Switch output for offline device' % (self.tdk.port, self.tdk.addr)
                self.debug_stream(msg)
                self.logger.debug(msg)
                self.output_state.set_quality(tango.AttrQuality.ATTR_INVALID)
                result = False
                self.set_fault()
                return result
            attr = self.output_state
            if self.task is not None and not self.task.done():
                await asyncio.wait({self.task})
            self.task = asyncio.create_task(self.tdk.write_output(value))
            await asyncio.wait({self.task})
            result = self.task.result()
            # result = await self.tdk.write_output(value)
            if result is None:
                msg = "%s Error writing output state" % self
                self.info_stream(msg)
                self.logger.warning(msg)
                self.set_fault()
                attr.set_value(False)
                attr.set_quality(tango.AttrQuality.ATTR_INVALID)
                return False
            #attr.set_value(value)
            attr.set_quality(tango.AttrQuality.ATTR_VALID)
            self.set_running()
            return result

    @command
    async def Reset(self):
        self.logger.debug('------------Entry----------')
        async with self.lock:
            msg = '%s:%d Reset TDKLambda PS' % (self.tdk.port, self.tdk.addr)
            self.logger.info(msg)
            self.info_stream(msg)
            await self.tdk.send_command(b'RST')

    @command
    async def Debug(self):
        self.logger.debug('------------Entry----------')
        async with self.lock:
            if self.logger.getEffectiveLevel() != logging.DEBUG:
                self.last_level = self.logger.getEffectiveLevel()
                self.logger.setLevel(logging.DEBUG)
                #self.tdk.logger.setLevel(logging.DEBUG)
                msg = '%s:%d switch logging to DEBUG' % (self.tdk.port, self.tdk.addr)
                self.logger.info(msg)
                self.info_stream(msg)
            else:
                self.logger.setLevel(self.last_level)
                msg = '%s:%d switch logging from DEBUG' % (self.tdk.port, self.tdk.addr)
                self.logger.info(msg)
                self.info_stream(msg)

    @command(dtype_in=int)
    async def SetLogLevel(self, level):
        self.logger.debug('------------Entry----------')
        async with self.lock:
            msg = '%s:%d set log level to %d' % (self.tdk.port, self.tdk.addr, level)
            self.logger.info(msg)
            self.info_stream(msg)
            self.logger.setLevel(level)
            # self.tdk.logger.setLevel(level)

    @command(dtype_in=str, doc_in='Directly send command to the device',
             dtype_out=str, doc_out='Response from device without final CR')
    async def SendCommand(self, cmd):
        self.logger.debug('------------Entry----------')
        async with self.lock:
            rsp = self.tdk.send_command(cmd).decode()
            msg = '%s:%d %s -> %s' % (self.tdk.port, self.tdk.addr, cmd, rsp)
            self.logger.debug(msg)
            self.debug_stream(msg)
            if self.tdk.com is None:
                msg = '%s COM port is None' % self
                self.logger.debug(msg)
                self.debug_stream(msg)
                self.set_state(DevState.FAULT)
                return
            return rsp

    @command
    async def TurnOn(self):
        self.logger.debug('------------Entry----------')
        async with self.lock:
            # turn on the power supply
            msg = '%s Turn On' % self
            self.logger.debug(msg)
            await self.write_output_state(True)

    @command
    async def TurnOff(self):
        self.logger.debug('------------Entry----------')
        async with self.lock:
            # turn off the power supply
            msg = '%s Turn Off' % self
            self.logger.debug(msg)
            await self.write_output_state(False)

    def set_running(self):
        self.error_count = 0
        self.set_state(DevState.RUNNING)

    def set_fault(self):
        self.error_count += 1
        if self.error_count > 5:
            self.set_state(DevState.FAULT)

# def looping():
#     time.sleep(0.3)


async def looper(delay=1.0):
    loop = asyncio.get_running_loop()
    while True:
        tasks = asyncio.all_tasks()
        #logger.debug("Running tasks: %s" % len(tasks))
        #print("Running tasks: %s" % len(tasks))
        for task in tasks:
            #logger.debug("%s" % task)
            #print("%s" % task)
            try:
                # print(task.exception())
                ex = task.exception()
                #logger.debug("%s" % ex)
                print("%s" % ex)
            except InvalidStateError:
                pass
                # logger.debug("InvalidStateError: Exception is not set.")
            except:
                print("Exception")
                #logger.debug("", exc_info=True)
            # print(task.get_name())
        print(len(tasks))
        #logger.debug("\n")
        await asyncio.sleep(delay)

def timertask():
    print(time.time())
    t = threading.Timer(0.5, timertask)
    t.start()


if __name__ == "__main__":
    #timer = threading.Timer(0.5, timertask)
    #timer.start()
    logging.getLogger('asyncio').setLevel(logging.DEBUG)
    Async_TDKLambda_Server.run_server()
