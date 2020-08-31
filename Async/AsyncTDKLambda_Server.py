# -*- coding: utf-8 -*-
"""TDK Lambda Genesis series power supply tango device server"""
from Async.AsyncTDKLambda import AsyncTDKLambda

import logging
import time
from threading import Lock
from math import isnan
import asyncio
from asyncio import InvalidStateError

import tango
from tango import AttrQuality, AttrWriteType, DispLevel, DevState, DebugIt, DeviceAttribute
from tango import GreenMode
from tango.server import Device, attribute, command

from Utils import *

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'Async_TDKLambda_Server'
APPLICATION_VERSION = '1_0'

# init a thread lock
_lock = Lock()
# config logger
logger = config_logger(level=logging.INFO)


class Async_TDKLambda_Server(Device):
    green_mode = GreenMode.Asyncio
    #reen_mode = GreenMode.Synchronous

    READING_VALID_TIME = 0.7
    devices = []

    device_type = attribute(label="PS Type", dtype=str,
                           display_level=DispLevel.OPERATOR,
                           access=AttrWriteType.READ,
                           unit="", format="%s",
                           doc="TDKLambda device type")

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
        if not hasattr(self, 'dp'):
            # device proxy
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
        if not hasattr(Async_TDKLambda_Server, 'task1'):
            Async_TDKLambda_Server.task1 = asyncio.create_task(looper(0.5))
            print('looper created')
        self.tasks = []
        self.error_count = 0
        self.values = [float('NaN')] * 6
        self.time = time.time() - 100.0
        self.set_state(DevState.INIT)
        Device.init_device(self)
        self.last_level = logging.INFO
        # get port and address from property
        port = self.get_device_property('port', 'COM1')
        addr = self.get_device_property('addr', 6)
        # create TDKLambda device
        self.tdk = AsyncTDKLambda(port, addr)
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
            msg = '%s:%d TDKLambda %s created successfully' % (self.tdk.port, self.tdk.addr, self.tdk.id)
            logger.info(msg)
            self.info_stream(msg)
        else:
            msg = '%s:%d TDKLambda device created with errors' % (self.tdk.port, self.tdk.addr)
            logger.error(msg)
            self.error_stream(msg)
            self.set_state(DevState.FAULT)

    async def delete_device(self):
        #with _lock:
            if self in Async_TDKLambda_Server.devices:
                Async_TDKLambda_Server.devices.remove(self)
                self.tdk.__del__()
                msg = ' %s:%d TDKLambda device has been deleted' % (self.tdk.port, self.tdk.addr)
                logger.info(msg)
                self.info_stream(msg)

    async def read_device_type(self):
        #with _lock:
            if self.tdk.initialized():
                return self.tdk.id
            return "Uninitialized"

    async def read_all(self):
        t0 = time.time()
        try:
            values = await self.tdk.read_all()
            self.values = values
            self.time = time.time()
            msg = '%s:%d read_all %s ms %s' % \
                  (self.tdk.port, self.tdk.addr, int((self.time - t0) * 1000.0), values)
            logger.debug(msg)
            # self.debug_stream(msg)
            return values
        except:
            self.set_fault()
            msg = '%s:%d read_all error' % (self.tdk.port, self.tdk.addr)
            logger.info(msg)
            logger.debug('', exc_info=True)
            self.info_stream(msg)

    async def read_one(self, attr: tango.Attribute, index: int, message: str):
        val = float('nan')
        try:
            # if time.time() - self.time > self.READING_VALID_TIME:
            #     await self.read_all()
            #await self.read_all()
            task = asyncio.create_task(self.read_all())
            #await asyncio.sleep(0)
            #await asyncio.wait_for(task, 1.0)

            val = self.values[index]
            attr.set_value(val)
            if isnan(val):
                attr.set_quality(tango.AttrQuality.ATTR_INVALID)
                msg = ('%s ' + message) % self
                self.info_stream(msg)
                logger.warning(msg)
                self.set_fault()
            else:
                attr.set_quality(tango.AttrQuality.ATTR_VALID)
                self.set_running()
            return val
        except:
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)
            self.logger.debug("", exc_info=True)
            return val

    async def read_voltage(self, attr: tango.Attribute):
        #with _lock:
            v = await self.read_one(attr, 0, "Output voltage read error")
            return v

    async def read_current(self, attr: tango.Attribute):
        #with _lock:
            return await self.read_one(attr, 2, "Output current read error")

    async def read_programmed_voltage(self, attr: tango.Attribute):
        #with _lock:
            return await self.read_one(attr, 1, "Programmed voltage read error")

    async def read_programmed_current(self, attr: tango.Attribute):
        #with _lock:
            return await self.read_one(attr, 3, "Programmed current read error")

    async def write_one(self, attrib, value, cmd, message):
        result = False
        try:
            if not self.tdk.initialized():
                attrib.set_quality(tango.AttrQuality.ATTR_INVALID)
                msg = "%s Writing to offline device" % self
                #self.info_stream(msg)
                logger.warning(msg)
                result = False
                self.set_fault()
            else:
                result = await self.tdk.write_value(cmd, value)
            if result:
                pass
                attrib.set_quality(tango.AttrQuality.ATTR_VALID)
                self.set_running()
            else:
                attrib.set_quality(tango.AttrQuality.ATTR_INVALID)
                msg = ('%s ' + message) % self
                self.info_stream(msg)
                logger.warning(msg)
                self.set_fault()
            return result
        except:
            print(self.com.async_lock.locked())
            self.logger.debug("", exc_info=True)
            return result

    async def write_programmed_voltage(self, value):
        #with _lock:
            result = await self.write_one(self.programmed_voltage, value, b'PV', 'Error writing programmed voltage')
            return result

    async def write_programmed_current(self, value):
        #with _lock:
            return await self.write_one(self.programmed_current, value, b'PC', 'Error writing programmed current')

    async def read_output_state(self, attr: tango.Attribute):
        try:
        #with _lock:
            if not self.tdk.initialized():
                self.set_fault()
                attr.set_value(False)
                attr.set_quality(tango.AttrQuality.ATTR_INVALID)
                return False
            response = await self.tdk.read_output()
            if response is None:
                msg = "%s Error reading output state" % self
                self.info_stream(msg)
                logger.warning(msg)
                self.set_fault()
                attr.set_value(False)
                attr.set_quality(tango.AttrQuality.ATTR_INVALID)
                return False
            attr.set_value(response)
            attr.set_quality(tango.AttrQuality.ATTR_VALID)
            return response
        except:
            print(self.com.async_lock.locked())
            self.logger.debug("", exc_info=True)
            return response

    async def write_output_state(self, value):
        #with _lock:
            if not self.tdk.initialized():
                msg = '%s:%d Switch output for offline device' % (self.tdk.port, self.tdk.addr)
                self.debug_stream(msg)
                logger.debug(msg)
                self.output_state.set_quality(tango.AttrQuality.ATTR_INVALID)
                result = False
                self.set_fault()
                return result
            attr = self.output_state
            result = await self.tdk.write_output(value)
            if result is None:
                msg = "%s Error writing output state" % self
                self.info_stream(msg)
                logger.warning(msg)
                self.set_fault()
                attr.set_value(False)
                attr.set_quality(tango.AttrQuality.ATTR_INVALID)
                return False
            attr.set_value(value)
            attr.set_quality(tango.AttrQuality.ATTR_VALID)
            self.set_running()
            return result

    @command
    async def Reset(self):
        #with _lock:
            msg = '%s:%d Reset TDKLambda PS' % (self.tdk.port, self.tdk.addr)
            logger.info(msg)
            self.info_stream(msg)
            await self.tdk.send_command(b'RST')

    @command
    async def Debug(self):
        #with _lock:
            if self.tdk.logger.getEffectiveLevel() != logging.DEBUG:
                self.last_level = self.tdk.logger.getEffectiveLevel()
                logger.setLevel(logging.DEBUG)
                self.tdk.logger.setLevel(logging.DEBUG)
                msg = '%s:%d switch logging to DEBUG' % (self.tdk.port, self.tdk.addr)
                logger.info(msg)
                self.info_stream(msg)
            else:
                self.tdk.logger.setLevel(self.last_level)
                msg = '%s:%d switch logging from DEBUG' % (self.tdk.port, self.tdk.addr)
                logger.info(msg)
                self.info_stream(msg)

    @command(dtype_in=int)
    async def SetLogLevel(self, level):
        #with _lock:
            msg = '%s:%d set log level to %d' % (self.tdk.port, self.tdk.addr, level)
            logger.info(msg)
            self.info_stream(msg)
            logger.setLevel(level)
            self.tdk.logger.setLevel(level)

    @command(dtype_in=str, doc_in='Directly send command to the device',
             dtype_out=str, doc_out='Response from device without final CR')
    async def SendCommand(self, cmd):
        #with _lock:
            rsp = self.tdk.send_command(cmd).decode()
            msg = '%s:%d %s -> %s' % (self.tdk.port, self.tdk.addr, cmd, rsp)
            logger.debug(msg)
            self.debug_stream(msg)
            if self.tdk.com is None:
                msg = '%s COM port is None' % self
                logger.debug(msg)
                self.debug_stream(msg)
                self.set_state(DevState.FAULT)
                return
            return rsp

    @command
    async def TurnOn(self):
        #with _lock:
            # turn on the power supply
            msg = '%s Turn On' % self
            logger.debug(msg)
            await self.write_output_state(True)

    @command
    async def TurnOff(self):
        #with _lock:
            # turn off the power supply
            msg = '%s Turn Off' % self
            logger.debug(msg)
            await self.write_output_state(False)

    def set_running(self):
        self.set_state(DevState.RUNNING)

    def set_fault(self):
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

if __name__ == "__main__":
    Async_TDKLambda_Server.run_server()
