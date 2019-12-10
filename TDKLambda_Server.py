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

    output = attribute(label="Output", dtype=bool,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ_WRITE,
                        unit="", format="",
                        doc="Output on/off state")

    voltage = attribute(label="Voltage", dtype=float,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ,
                        unit="V", format="6.2f",
                        min_value=0.0,
                        doc="Measured voltage")

    programmed_voltage = attribute(label="Programmed Voltage", dtype=float,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ_WRITE,
                        unit="V", format="6.2f",
                        min_value=0.0,
                        doc="Programmed voltage")

    current = attribute(label="Current", dtype=float,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ,
                        unit="A", format="6.2f",
                        min_value=0.0,
                        doc="Measured current")

    programmed_current = attribute(label="Programmed Current", dtype=float,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ_WRITE,
                        unit="A", format="6.2f",
                        min_value=0.0,
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
        addr = int(self.get_device_property('addr'))
        # create TDKLambda device
        self.tdk = TDKLambda(port, addr)
        # check if device OK
        if self.tdk.com is None:
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
            msg = 'TDKLambda device %s at %s : %d has been created with errors' % (self.tdk.id, self.tdk.port, self.tdk.addr)
            print(msg)
            self.info_stream(msg)
            self.set_state(DevState.FAULT)

    def delete_device(self):
        if self in TDKLambda_Server.devices:
            TDKLambda_Server.devices.remove(self)
            self.tdk.__del__()
            msg = 'TDKLambda device %s at %s : %d has been deleted' % (self.tdk.id, self.tdk.port, self.tdk.addr)
            self.info_stream(msg)

    def read_voltage(self, attr: tango.Attribute):
        if self.tdk.com is None:
            val = float('nan')
        else:
            val = self.tdk.read_float('MV?')
        attr.set_value(val)
        if val is float('nan'):
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)
            self.error_stream("Output voltage read error ")
        else:
            attr.set_quality(tango.AttrQuality.ATTR_VALID)
        msg = 'read_voltage: ' + str(val)
        print(msg)
        return val

    def read_current(self, attr: tango.Attribute):
        if self.tdk.com is None:
            val = float('nan')
        else:
            val = self.tdk.read_float('MC?')
        attr.set_value(val)
        if val is float('nan'):
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)
            self.error_stream("Output current read error ")
        else:
            attr.set_quality(tango.AttrQuality.ATTR_VALID)
        #msg = 'read_current: ' + str(val)
        #print(msg)
        return val

    def read_programmed_voltage(self, attr: tango.Attribute):
        if self.tdk.com is None:
            val = float('nan')
        else:
            val = self.tdk.read_float('PV?')
        attr.set_value(val)
        if val is float('nan'):
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)
            self.error_stream("Programmed voltage read error")
        else:
            attr.set_quality(tango.AttrQuality.ATTR_VALID)
        #msg = 'read_programmed_voltage: ' + str(val)
        #print(msg)
        return val

    def read_programmed_current(self, attr: tango.Attribute):
        if self.tdk.com is None:
            val = float('nan')
        else:
            val = self.tdk.read_float('PV?')
        attr.set_value(val)
        if val is float('nan'):
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)
            self.error_stream("Programmed current read error")
        else:
            attr.set_quality(tango.AttrQuality.ATTR_VALID)
        #msg = 'read_programmed_current: ' + str(val)
        #print(msg)
        return val

    def write_programmed_voltage(self, value):
        if self.tdk.com is None:
            self.programmed_voltage.set_quality(tango.AttrQuality.ATTR_INVALID)
            result = False
        else:
            result = self.tdk.write_value(b'PV', value)
        if result:
            self.programmed_voltage.set_quality(tango.AttrQuality.ATTR_VALID)
        else:
            self.error_stream("Error writing programmed voltage")
            self.programmed_voltage.set_quality(tango.AttrQuality.ATTR_INVALID)
        #msg = 'write_voltage: %s = %s' % (str(value), str(result))
        #print(msg)
        return result

    def write_programmed_current(self, value):
        if self.tdk.com is None:
            self.programmed_current.set_quality(tango.AttrQuality.ATTR_INVALID)
            result = False
        else:
            result = self.tdk.write_value(b'PC', value)
        if result:
            self.programmed_current.set_quality(tango.AttrQuality.ATTR_VALID)
        else:
            self.error_stream("Error writing programmed current")
            self.programmed_current.set_quality(tango.AttrQuality.ATTR_INVALID)
        #msg = 'write_current: %s = %s' % (str(value), str(result))
        #print(msg)
        return result

    def read_output(self, attr: tango.Attribute):
        if self.tdk.com is None:
            value = False
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)
        else:
            response = self.tdk.send_command(b'OUT?')
            if response.upper().startswith(b'ON'):
                attr.set_quality(tango.AttrQuality.ATTR_VALID)
                value = False
            elif response.upper().startswith(b'OFF'):
                attr.set_quality(tango.AttrQuality.ATTR_VALID)
                value = False
            else:
                attr.set_quality(tango.AttrQuality.ATTR_INVALID)
                value = False
        #msg = 'read_output: ' + str(value)
        #print(msg)
        attr.set_value(value)
        return value

    def write_output(self, value):
        if self.tdk.com is None:
            self.output.set_quality(tango.AttrQuality.ATTR_INVALID)
            result = False
        else:
            if value:
                response = self.tdk.send_command(b'OUT ON')
            else:
                response = self.tdk.send_command(b'OUT OFF')
            if response.startswith(b'OK'):
                self.output.set_quality(tango.AttrQuality.ATTR_VALID)
                result = True
            else:
                self.error_stream("Error switch output")
                self.output.set_quality(tango.AttrQuality.ATTR_INVALID)
                v = self.read_output(self.output)
                self.output.set_value(v)
                result = False
        #msg = 'write_output: %s = %s' % (str(value), str(result))
        #print(msg)
        return result

    @command
    def Reconnect(self):
        msg = 'Reconnect %s at %s : %d' % (self, self.tdk.port, self.tdk.addr)
        #print(msg)
        self.info_stream(msg)
        self.delete_device()
        self.init_device()

    @command
    def Reset(self):
        msg = 'Reset device at %s : %d' % (self, self.tdk.port, self.tdk.addr)
        self.info_stream(msg)
        #print(msg)
        self.tdk._send_command(b'RST')

    def read_info(self):
        return 'Information', dict(manufacturer='Tango',
                                   model='TDKLambda',
                                   version_number=1)

    def read_devicetype(self):
        if self.tdk.com is None:
            return "Uninitialized"
        return self.tdk.id.decode()

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
