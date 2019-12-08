#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""TDK Lambda Genesis series power supply tango device server"""

import tango
from tango import AttrQuality, AttrWriteType, DispLevel, DevState, DebugIt
from tango.server import Device, attribute, command

from TDKLambda import TDKLambda


class TDKLambda_Server(Device):
    devices = []

    devicetype = attribute(label="type", dtype=str,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ,
                        unit="", format="%s",
                        doc="TDKLambda device type")

    out = attribute(label="on/off", dtype=bool,
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
        TDKLambda_Server.devices.append(self)
        if self.tdk.id != b'':
            # set state to running
            self.set_state(DevState.RUNNING)
            msg = 'TDKLambda device %s at %s : %d has been successfully created' % (self.tdk.id, self.tdk.port, self.tdk.addr)
            print(msg)
            self.info_stream(msg)
        else:
            # unknown device type
            self.set_state(DevState.FAULT)

    def delete_device(self):
        if self in TDKLambda_Server.devices:
            TDKLambda_Server.devices.remove(self)
            self.tdk.__del__()
            msg = 'TDKLambda device %s at %s : %d has been deleetd' % (self.tdk.id, self.tdk.port, self.tdk.addr)
            self.info_stream(msg)

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

    def read_current(self, attr: tango.Attribute):
        if self.tdk.com is None:
            return
        val = self.tdk.read_float('MC?')
        if val is float('nan'):
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)
            attr.set_value(float('nan'))
            self.error_stream("Output current read error ")
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
            self.error_stream("Programmed voltage read error")
            return
        else:
            attr.set_value(val)
            attr.set_quality(tango.AttrQuality.ATTR_VALID)

    def read_programmed_current(self, attr: tango.Attribute):
        if self.tdk.com is None:
            return
        val = self.tdk.read_float('PC?')
        if val is float('nan'):
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)
            attr.set_value(float('nan'))
            self.error_stream("Programmed current read error")
            return
        else:
            attr.set_value(val)
            attr.set_quality(tango.AttrQuality.ATTR_VALID)

    def write_programmed_voltage(self, attr: tango.WAttribute):
        if self.tdk.com is None:
            return
        value = attr.get_write_value()
        result = self.tdk.write_value(b'PV', value)
        if result:
            attr.set_quality(tango.AttrQuality.ATTR_VALID)
        else:
            self.error_stream("Error writing programmed voltage")
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)

    def write_programmed_current(self, attr: tango.WAttribute):
        if self.tdk.com is None:
            return
        value = attr.get_write_value()
        result = self.tdk.write_value(b'PC', value)
        if result:
            attr.set_quality(tango.AttrQuality.ATTR_VALID)
        else:
            self.error_stream("Error writing programmed current")
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)

    def read_out(self, attr: tango.Attribute):
        if self.tdk.com is None:
            return
        response = self.send_command(b'OUT?\r')
        if response.upper() == b'ON':
            attr.set_value(True)
            attr.set_quality(tango.AttrQuality.ATTR_VALID)
            return True
        elif response.upper() == b'OFF':
            attr.set_value(False)
            attr.set_quality(tango.AttrQuality.ATTR_VALID)
            return False
        else:
            attr.set_value(False)
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)

    def write_out(self, attr: tango.WAttribute):
        if self.tdk.com is None:
            return
        value = attr.get_write_value()
        if value:
            response = self.send_command(b'OUT ON\r')
        else:
            response = self.send_command(b'OUT OFF\r')
        if response == b'OK':
            attr.set_quality(tango.AttrQuality.ATTR_VALID)
        else:
            self.error_stream("Error switch output")
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)

    @command
    def Reconnect(self):
        msg = 'Reconnect %s at %s : %d' % (self.tdk.id, self.tdk.port, self.tdk.addr)
        self.info_stream(msg)
        self.delete_device()
        self.init_device()

    def read_info(self):
        return 'Information', dict(manufacturer='Tango',
                                   model='TDKLambda',
                                   version_number=1)

    def read_devicetype(self):
        if self.tdk.com is None:
            return "Uninitialized"
        return self.tdk.id

    @command
    def TurnOn(self):
        # turn on the actual power supply here
        self.out = True
        #self.set_state(DevState.ON)

    @command
    def TurnOff(self):
        # turn off the actual power supply here
        self.out = False
        #self.set_state(DevState.OFF)


if __name__ == "__main__":
    TDKLambda_Server.run_server()
