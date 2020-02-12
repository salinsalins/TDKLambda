#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TDK Lambda Genesis series power supply tango device server"""


from TDKLambda import TDKLambda

import logging
import time
from threading import Thread, Lock
from math import isnan

import tango
from tango import AttrQuality, AttrWriteType, DispLevel, DevState, DebugIt, DeviceAttribute
from tango.server import Device, attribute, command

from Utils import *

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'TDKLambda_Server'
APPLICATION_NAME_SHORT = 'TDKLambda_Server'
APPLICATION_VERSION = '2_1'
# CONFIG_FILE = APPLICATION_NAME_SHORT + '.json'
# UI_FILE = APPLICATION_NAME_SHORT + '.ui'

# init a thread lock
_lock = Lock()
logger = config_logger(level=logging.DEBUG)


class TDKLambda_Server(Device):
    READING_PERIOD = 0.5
    devices = []

    devicetype = attribute(label="type", dtype=str,
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

    def init_device(self):
        with _lock:
            self.values = [float('NaN')] * 6
            self.time = time.time() - 100.0
            self.set_state(DevState.INIT)
            Device.init_device(self)
            self.last_level = logging.INFO
            # get port and address from property
            port = self.get_device_property('port', 'COM1')
            addr = self.get_device_property('addr', 6)
            # create TDKLambda device
            self.tdk = TDKLambda(port, addr)
            # check if device OK
            if self.tdk.com is None:
                msg = '%s TDKLambda device creation error' % self
                logger.error(msg)
                self.error_stream(msg)
                self.set_state(DevState.FAULT)
                return
            # add device to list
            TDKLambda_Server.devices.append(self)
            if self.tdk.id is not None and self.tdk.id != b'':
                # set state to running
                self.set_state(DevState.RUNNING)
                msg = '%s:%d TDKLambda %s created successfully' % (self.tdk.port, self.tdk.addr, self.tdk.id)
                logger.info(msg)
                self.info_stream(msg)
            else:
                # unknown device id
                msg = '%s:%d TDKLambda device created with errors' % (self.tdk.port, self.tdk.addr)
                logger.error(msg)
                self.error_stream(msg)
                self.set_state(DevState.FAULT)

    def delete_device(self):
        with _lock:
            if self in TDKLambda_Server.devices:
                TDKLambda_Server.devices.remove(self)
                self.tdk.__del__()
                msg = ' %s:%d TDKLambda device has been deleted' % (self.tdk.port, self.tdk.addr)
                logger.info(msg)
                self.info_stream(msg)

    def read_devicetype(self):
        with _lock:
            if self.tdk.com is None:
                return "Uninitialized"
            return self.tdk.id

    def read_all(self):
        t0 = time.time()
        # msg = '%s:%d read_all' % (self.tdk.port, self.tdk.addr)
        # logger.debug(msg)
        # self.debug_stream(msg)
        try:
            values = self.tdk.read_all()
            self.values = values
            self.time = time.time()
            msg = '%s:%d read_all %s ms %s' % \
                  (self.tdk.port, self.tdk.addr, int((self.time - t0) * 1000.0), values)
            logger.debug(msg)
            #self.debug_stream(msg)
        except:
            msg = '%s:%d TDKLambda read error' % (self.tdk.port, self.tdk.addr)
            logger.info(msg)
            self.info_stream(msg)

    def read_voltage(self, attr: tango.Attribute):
        with _lock:
            if time.time() - self.time > self.READING_PERIOD:
                self.read_all()
            val = self.values[0]
            attr.set_value(val)
            if isnan(val):
                attr.set_quality(tango.AttrQuality.ATTR_INVALID)
                msg = "%s Output voltage read error" % self
                self.info_stream(msg)
                logger.warning(msg)
            else:
                attr.set_quality(tango.AttrQuality.ATTR_VALID)
            return val

    def read_current(self, attr: tango.Attribute):
        with _lock:
            if time.time() - self.time > self.READING_PERIOD:
                self.read_all()
            val = self.values[2]
            attr.set_value(val)
            if isnan(val):
                attr.set_quality(tango.AttrQuality.ATTR_INVALID)
                msg = "%s Output current read error" % self
                self.info_stream(msg)
                logger.warning(msg)
            else:
                attr.set_quality(tango.AttrQuality.ATTR_VALID)
            return val

    def read_programmed_voltage(self, attr: tango.Attribute):
        with _lock:
            if time.time() - self.time > self.READING_PERIOD:
                self.read_all()
            val = self.values[1]
            attr.set_value(val)
            if isnan(val):
                attr.set_quality(tango.AttrQuality.ATTR_INVALID)
                msg = "%s Programmed voltage read error" % self
                self.info_stream(msg)
                logger.warning(msg)
            else:
                attr.set_quality(tango.AttrQuality.ATTR_VALID)
            return val

    def read_programmed_current(self, attr: tango.Attribute):
        with _lock:
            if time.time() - self.time > self.READING_PERIOD:
                self.read_all()
            val = self.values[3]
            attr.set_value(val)
            if isnan(val):
                attr.set_quality(tango.AttrQuality.ATTR_INVALID)
                msg = "%s Programmed current  read error" % self
                self.info_stream(msg)
                logger.warning(msg)
            else:
                attr.set_quality(tango.AttrQuality.ATTR_VALID)
            return val

    def write_programmed_voltage(self, value):
        with _lock:
            if self.tdk.com is None:
                self.programmed_voltage.set_quality(tango.AttrQuality.ATTR_INVALID)
                msg = "%s Writing to offline device" % self
                self.info_stream(msg)
                logger.warning(msg)
                result = False
            else:
                result = self.tdk.write_value(b'PV', value)
            if result:
                self.programmed_voltage.set_quality(tango.AttrQuality.ATTR_VALID)
            else:
                self.programmed_voltage.set_quality(tango.AttrQuality.ATTR_INVALID)
                msg = "%s Error writing programmed voltage" % self
                self.info_stream(msg)
                logger.warning(msg)
            ##print(self.tdk.port, self.tdk.addr, 'write_programmed_voltage value: ', value, result)
            # msg = 'write_voltage: %s = %s' % (str(value), str(result))
            # logger.debug(msg)
            return result

    def write_programmed_current(self, value):
        with _lock:
            if self.tdk.com is None:
                self.programmed_current.set_quality(tango.AttrQuality.ATTR_INVALID)
                msg = "%s Writing to offline device" % self
                self.info_stream(msg)
                logger.warning(msg)
                result = False
            else:
                result = self.tdk.write_value(b'PC', value)
            if result:
                self.programmed_current.set_quality(tango.AttrQuality.ATTR_VALID)
            else:
                self.programmed_current.set_quality(tango.AttrQuality.ATTR_INVALID)
                msg = "%s Error writing programmed current" % self
                self.info_stream(msg)
                logger.warning(msg)
            return result

    def read_output_state(self, attr: tango.Attribute):
        with _lock:
            qual = tango.AttrQuality.ATTR_INVALID
            if self.tdk.com is None:
                value = False
                qual = tango.AttrQuality.ATTR_INVALID
            else:
                response = self.tdk.send_command(b'OUT?')
                if response.upper().startswith(b'ON'):
                    qual = tango.AttrQuality.ATTR_VALID
                    value = True
                elif response.upper().startswith(b'OFF'):
                    qual = tango.AttrQuality.ATTR_VALID
                    value = False
                else:
                    msg = "%s Error reading output state" % self
                    self.info_stream(msg)
                    logger.warning(msg)
                    qual = tango.AttrQuality.ATTR_INVALID
                    value = False
            attr.set_value(value)
            attr.set_quality(qual)
            return value

    def write_output_state(self, value):
        with _lock:
            if self.tdk.com is None:
                msg = '%s:%d Switch output for offlie device' % (self.tdk.port, self.tdk.addr)
                self.debug_stream(msg)
                logger.debug(msg)
                self.output_state.set_quality(tango.AttrQuality.ATTR_INVALID)
                result = False
            else:
                if value:
                    response = self.tdk.send_command(b'OUT ON')
                else:
                    response = self.tdk.send_command(b'OUT OFF')
                if response.startswith(b'OK'):
                    self.output_state.set_quality(tango.AttrQuality.ATTR_VALID)
                    result = True
                else:
                    msg = '%s:%d Error switch output %s' % (self.tdk.port, self.tdk.addr, response)
                    self.error_stream(msg)
                    logger.error(msg)
                    self.output_state.set_quality(tango.AttrQuality.ATTR_INVALID)
                    # v = self.read_output_state(self.output_state)
                    # self.output_state.set_value(v)
                    result = False
            return result

    # @command
    # def Reconnect(self):
    #     with _lock:
    #         msg = '%s:%d Reconnect' % (self.tdk.port, self.tdk.addr)
    #         self.info_stream(msg)
    #         self.set_state(DevState.INIT)
    #         # get port and address from property
    #         port = self.get_device_property('port', 'COM1')
    #         addr = self.get_device_property('addr', 6)
    #         self.tdk.port = port
    #         self.tdk.addr = addr
    #         self.tdk.init_com_port()
    #         # check if COM OK
    #         if self.tdk.com is None:
    #             msg = 'TDKLambda device creation error for %s' % self
    #             logger.debug(msg)
    #             self.error_stream(msg)
    #             self.set_state(DevState.FAULT)
    #             return
    #         if self.tdk.id is not None and self.tdk.id != b'':
    #             # set state to running
    #             self.set_state(DevState.RUNNING)
    #             msg = '%s:%d TDKLambda %s created successfully' % (self.tdk.port, self.tdk.addr, self.tdk.id)
    #             logger.debug(msg)
    #             self.info_stream(msg)
    #         else:
    #             # unknown device id
    #             msg = '%s:%d TDKLambda device created with errors' % (self.tdk.port, self.tdk.addr)
    #             logger.debug(msg)
    #             self.error_stream(msg)
    #             self.set_state(DevState.FAULT)

    @command
    def Reset(self):
        with _lock:
            msg = '%s:%d Reset TDKLambda PS' % (self.tdk.port, self.tdk.addr)
            logger.info(msg)
            self.info_stream(msg)
            self.tdk._send_command(b'RST')

    @command
    def Debug(self):
        with _lock:
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
    def SetLogLevel(self, level):
        with _lock:
            msg = '%s:%d set log level to %d' % (self.tdk.port, self.tdk.addr, level)
            logger.info(msg)
            self.info_stream(msg)
            logger.setLevel(level)
            self.tdk.logger.setLevel(level)

    """
    Declares a new tango command in a :class:`Device`.
    To be used like a decorator in the methods you want to declare as
    tango commands. The following example declares commands:

        * `void TurnOn(void)`
        * `void Ramp(DevDouble current)`
        * `DevBool Pressurize(DevDouble pressure)`

    ::

        class PowerSupply(Device):

            @command
            def TurnOn(self):
                self.info_stream('Turning on the power supply')

            @command(dtype_in=float)
            def Ramp(self, current):
                self.info_stream('Ramping on %f...' % current)

            @command(dtype_in=float, doc_in='the pressure to be set',
                     dtype_out=bool, doc_out='True if it worked, False otherwise')
            def Pressurize(self, pressure):
                self.info_stream('Pressurizing to %f...' % pressure)
                return True

    .. note::
        avoid using *dformat* parameter. If you need a SPECTRUM
        attribute of say, boolean type, use instead ``dtype=(bool,)``.

    :param dtype_in:
        a :ref:`data type <pytango-hlapi-datatypes>` describing the
        type of parameter. Default is None meaning no parameter.
    :param dformat_in: parameter data format. Default is None.
    :type dformat_in: AttrDataFormat
    :param doc_in: parameter documentation
    :type doc_in: str

    :param dtype_out:
        a :ref:`data type <pytango-hlapi-datatypes>` describing the
        type of return value. Default is None meaning no return value.
    :param dformat_out: return value data format. Default is None.
    :type dformat_out: AttrDataFormat
    :param doc_out: return value documentation
    :type doc_out: str
    :param display_level: display level for the command (optional)
    :type display_level: DispLevel
    :param polling_period: polling period in milliseconds (optional)
    :type polling_period: int
    :param green_mode:
        set green mode on this specific command. Default value is None meaning
        use the server green mode. Set it to GreenMode.Synchronous to force
        a non green command in a green server.

    .. versionadded:: 8.1.7
        added green_mode option

    .. versionadded:: 9.2.0
        added display_level and polling_period optional argument
    """

    @command(dtype_in=str, doc_in='directly send command to the device',
             dtype_out=str, doc_out='response from device without final CR')
    def SendCommand(self, cmd):
        with _lock:
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
    def TurnOn(self):
        with _lock:
            # turn on the actual power supply here
            msg = '%s Turn On' % self
            logger.debug(msg)
            self.output_state = True
            # self.set_state(DevState.ON)

    @command
    def TurnOff(self):
        with _lock:
            # turn off the actual power supply here
            msg = '%s Turn Off' % self
            logger.debug(msg)
            self.output_state = False
            # self.set_state(DevState.OFF)


if __name__ == "__main__":
    TDKLambda_Server.run_server()
