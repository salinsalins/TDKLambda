#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Demo power supply tango device server"""

import time
import numpy

import os
import serial
# chose an implementation, depending on os
if os.name == 'nt':  # sys.platform == 'win32':
    from serial.tools.list_ports_windows import comports
elif os.name == 'posix':
    from serial.tools.list_ports_posix import comports
else:
    raise ImportError("No implementation for platform ('{}') is available".format(os.name))

import tango
from tango import AttrQuality, AttrWriteType, DispLevel, DevState, DebugIt
from tango.server import Device, attribute, command

from TDKLambda import TDKLambda


class TDKLambda_Server(Device):
    ports = []
    devices = []

    devicetype = attribute(label="type", dtype=str,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ,
                        unit="", format="%s",
                        doc="TDKLambda device type")

    onoff = attribute(label="on/off", dtype=bool,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ_WRITE,
                        unit="", format="",
                        doc="Output state on/off")

    voltage = attribute(label="Voltage", dtype=float,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ,
                        unit="V", format="8.4f",
                        doc="Measured voltage")

    programmed_voltage = attribute(label="Voltage", dtype=float,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ_WRITE,
                        unit="V", format="8.4f",
                        doc="Programmed voltage")

    current = attribute(label="Current", dtype=float,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ,
                        unit="A", format="8.4f",
                        doc="Measured current")

    programmed_current = attribute(label="Current", dtype=float,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ_WRITE,
                        unit="A", format="8.4f",
                        doc="Programmed current")

    def get_device_property(self, prop: str, default=None):
        name = self.get_name()
        # device proxy
        dp = tango.DeviceProxy(name)
        # read property
        pr = dp.get_property(prop)[prop]
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
        except:
            return result

    def init_device(self):
        self.set_state(DevState.INIT)
        Device.init_device(self)
        # get port and address from property
        port = self.get_device_property('port')
        addr = self.get_device_property('addr')
        # create TDKLambda device
        self.tdk = TDKLambda(port, addr)
        # check if device OK
        if self.com is None:
            msg = 'TDKLambda device creation error for %s' % self
            print(msg)
            self.error_stream(msg)
            self.set_state(DevState.FAULT)
            return
        # add device to list
        TDKLambda.devices.append(self)
        if self.tdk.id != b'':
            # set state to running
            self.set_state(DevState.RUNNING)
            msg = 'TDKLambda device %s at %s : %d has been successfully created' % (self.tdk.id, self.tdk.port, self.tdk.addr)
            print(msg)
            self.info_stream(msg)
        else:
            # unknown device type
            self.set_state(DevState.FAULT)

    def read_voltage(self, attr: tango.Attribute):
        if self.tdk.com is None:
            return
        val = self.tdk.read_float('MV?')
        if val is float('nan'):
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)
            attr.set_value(float('nan'))
            self.error_stream("Output voltage read error ")
            return
        else:
            attr.set_value(val)
            attr.set_quality(tango.AttrQuality.ATTR_VALID)

    def read_programmed_voltage(self, attr: tango.Attribute):
        if self.tdk.com is None:
            return
        val = self.tdk.read_float('PV?')
        if val is float('nan'):
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)
            attr.set_value(float('nan'))
            self.error_stream("Programmed voltage read error ")
            return
        else:
            attr.set_value(val)
            attr.set_quality(tango.AttrQuality.ATTR_VALID)

    def write_programmed_voltage(self, attr: tango.WAttribute):
        if self.tdk.com is None:
            return
        value = attr.get_write_value()
        result = self.tdk.write_value('PV', value)
        if result:
            attr.set_quality(tango.AttrQuality.ATTR_VALID)
        else:
            self.error_stream("Error writing programmed voltage")
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)

    def write_programmed_current(self, attr: tango.WAttribute):
        if self.tdk.com is None:
            return
        value = attr.get_write_value()
        result = self.tdk.write_value('PC', value)
        if result:
            attr.set_quality(tango.AttrQuality.ATTR_VALID)
        else:
            self.error_stream("Error writing programmed current")
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)

    @command
    def Reconnect(self):
        self.info_stream(self, 'Reconnect')
        if self.et is None:
            self.init_device()
            if self.et is None:
                return
        self.remove_io()
        self.add_io()
        # if device type is recognized
        if self.et._name != 0:
            # set state to running
            self.set_state(DevState.RUNNING)
        else:
            # unknown device type
            self.set_state(DevState.FAULT)




    def read_current(self):
        return self.__current

    def read_programmed__voltage(self):
        # should set the power supply current
        self.__current = 0

    def read_programmed__current(self):
        # should set the power supply current
        self.__current = 0

    def write_programmed__voltage(self, v):
        # should set the power supply current
        self.__current = 0

    def write_programmed__current(self, c):
        # should set the power supply current
        self.__current = 0

    def read_info(self):
        return 'Information', dict(manufacturer='Tango',
                                   model='TDKLambda',
                                   version_number=123)

    @DebugIt()
    def read_devicetype(self):
        return 'TDKLambda'

    def send_command(self, cmd):
        if cmd[-1] != b'\r':
            cmd += b'\r'
        self.com.reset_input_buffer()
        self.com.write(cmd)
        return self.read_cr()

    def set_addr(self):
        result = self.send_command(b'ADR %d\r' % self.addr)
        if result != b'OK':
            self.io_error()
            return False
        return True

    def read_response(self):
        time0 = time.time()
        data = self.com.read(100)
        dt = time.time() - time0
        while len(data) <= 0:
            if dt > self.timeout:
                self.timeout = min(1.5*dt, MAX_TIMEOUT)
                return None
            data = self.com.read()
            dt = time.time() - time0
        self.timeout = max(2.0*dt, MIN_TIMEOUT)
        return data

    def read_cr(self):
        result = b''
        data = self.read_response()
        while data is not None:
            result += data
            if b'\r' in data:
                return result
            data = self.read_response()
        return result


    # process error reading or writing
    def io_error(self):
        return True

    @command
    def TurnOn(self):
        # turn on the actual power supply here
        self.set_state(DevState.ON)

    @command
    def TurnOff(self):
        # turn off the actual power supply here
        self.set_state(DevState.OFF)


if __name__ == "__main__":
    TDKLambda.run_server()
