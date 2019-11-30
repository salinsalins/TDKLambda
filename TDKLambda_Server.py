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


class TDKLamda(Device):
    ports = []
    devices = []

    devicetype = attribute(label="type", dtype=str,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ,
                        unit="", format="%s",
                        doc="device type")

    onoff = attribute(label="on/off", dtype=bool,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ_WRITE,
                        unit="", format="",
                        doc="on/off")

    voltage = attribute(label="Voltage", dtype=float,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ,
                        unit="V", format="8.4f",
                        doc="Measured voltage")

    prorgammed_voltage = attribute(label="Voltage", dtype=float,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ_WRITE,
                        unit="V", format="8.4f",
                        doc="Programmed voltage")

    current = attribute(label="Current", dtype=float,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ,
                        unit="A", format="8.4f",
                        doc="Measured current")

    prorgammed_current = attribute(label="Current", dtype=float,
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
        if hasattr(self, 'port') and self.port is not None:
            self.port.close()
            self.port = None
            self.addr = None
        self.set_state(DevState.INIT)
        Device.init_device(self)
        # get port and arrdess from property
        self.port = self.get_device_property('port')
        self.addr = self.get_device_property('addr')
        # if port or address is not defined
        if self.port is None or self.addr is None:
            msg = 'Address or port not defined for %s' % self
            print(msg)
            self.error_stream(msg)
            self.set_state(DevState.FAULT)
            return
        # check if port an addr are in use
        for d in TDKLamda.devices:
            if d.port == self.port and d.addr == self.addr:
                msg = 'Address %s is in use for port %s device %s' % (self.addr, self.port, self)
                print(msg)
                self.error_stream(msg)
                self.set_state(DevState.FAULT)
                return
        if len(TDKLamda.ports) == 0:
            TDKLamda.ports = comports()
        found = False
        for p in TDKLamda.ports:
            if p.name == self.port:
                found = True
        if not found:
            msg = 'COM port %s does not exist for %s' % (self.port, self)
            print(msg)
            self.error_stream(msg)
            self.set_state(DevState.FAULT)
            return
        # create TDKLamda device
        self.com = serial.Serial(self.port, baudrate=9600, timeout=0)
        # create variables
        self.time = time.time()
        self.reconnect_timeout = self.get_device_property('reconnect_timeout', 5000)
        self.error_retries = self.get_device_property('error_retries', 3)
        # add device to list
        TDKLamda.devices.append(self)
        msg = 'TDKLamda device at %s %d has been created' % (self.port, self.addr)
        print(msg)
        self.info_stream(msg)
        # initilize device type
        self.type = self.read_devicetype()
        if self.type is not None:
            # set state to running
            self.set_state(DevState.RUNNING)
        else:
            # unknown device type
            self.set_state(DevState.FAULT)

    def read_voltage(self):
        self.info_stream("read_voltage(%s, %d)", self.host, self.port)
        return 9.99, time.time(), AttrQuality.ATTR_WARNING

    def read_current(self):
        return self.__current

    def read_prorgammed__voltage(self):
        # should set the power supply current
        self.__current = 0

    def read_prorgammed__current(self):
        # should set the power supply current
        self.__current = 0

    def write_prorgammed__voltage(self, v):
        # should set the power supply current
        self.__current = 0

    def write_prorgammed__current(self, c):
        # should set the power supply current
        self.__current = 0

    def read_info(self):
        return 'Information', dict(manufacturer='Tango',
                                   model='PS2000',
                                   version_number=123)

    @DebugIt()
    def read_devicetype(self):
        return 'TDKLambda'

    def send_command(self, cmd):
        self.com.write(b'ADR %d\r' % self.addr)
        if self.read_response() != 'OK':
            self.io_error()
        self.com.write(cmd)
        return self.read_response()

    def read_response(self):
        data = self.com.read()
        print(time.time(), data)
        return True

    # process error reding or writing
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
    TDKLamda.run_server()
