#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TDK Lambda Genesis series power supply tango device server"""
import sys
from math import isnan

import tango
from tango import AttrQuality, AttrWriteType, DispLevel
from tango import DevState
from tango.server import Device, attribute, command

import IT6900
from config_logger import config_logger

sys.path.append('../TangoUtils')
from TangoServerPrototype import TangoServerPrototype

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'IT6900 family Power Supply Tango Device Server'
APPLICATION_NAME_SHORT = 'IT6900_Server'
APPLICATION_VERSION = '0.1'

logger = config_logger()


class IT6900_Server(TangoServerPrototype):
    server_version = '0.1'
    server_name = APPLICATION_NAME

    port = attribute(label="Port", dtype=str,
                     display_level=DispLevel.OPERATOR,
                     access=AttrWriteType.READ,
                     unit="", format="%s",
                     doc="TDKLambda port")

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

    def init_device(self):
        super().__init__()
        kwargs = {}
        args = ()
        port = self.config.get('port', 'COM3')
        baud = self.config.get('baudrate', 115200)
        kwargs['baudrate'] = baud
        kwargs['logger'] = self.logger
        self.it6900 = IT6900.IT6900(port, *args, **kwargs)
        if self.it6900.initialized():
            # add device to list
            IT6900_Server.devices.append(self)
            # set state to running
            self.set_state(DevState.RUNNING)
            self.set_status('Successfully initialized')
            msg = '%s %s created successfully' % (self.it6900.port, self.it6900.type)
            logger.info(msg)
        else:
            msg = '%s %s creation error' % (self.it6900.port, self.it6900.type)
            logger.error(msg)
            self.set_state(DevState.FAULT)
            self.set_status('Initialization error')

    def delete_device(self):
        if self in IT6900_Server.devices:
            IT6900_Server.devices.remove(self)
            self.it6900.close_com_port()
            msg = 'Device has been deleted'
            logger.info(msg)

    def read_port(self):
        if self.it6900.initialized():
            return self.it6900.port
        return "Uninitialized"

    def read_device_type(self):
        if self.it6900.initialized():
            return self.it6900.type
        return "Uninitialized"

    def read_output_state(self):
        if self.it6900.initialized():
            value = self.it6900.read_output()
            if value is not None:
                qual = AttrQuality.ATTR_VALID
                self.set_running()
            else:
                qual = AttrQuality.ATTR_INVALID
                value = False
                self.set_fault()
        else:
            value = False
            qual = AttrQuality.ATTR_INVALID
            self.set_fault()
        self.output_state.set_value(value)
        self.output_state.set_quality(qual)
        return value

    def write_output_state(self, value):
            if self.it6900.com is None:
                msg = '%s:%d Switch output for offline device' % (self.it6900.port, self.it6900.addr)
                self.debug_stream(msg)
                logger.debug(msg)
                self.output_state.set_quality(AttrQuality.ATTR_INVALID)
                result = False
                self.set_fault()
            else:
                if self.it6900.write_output(value):
                    self.output_state.set_quality(AttrQuality.ATTR_VALID)
                    result = True
                    self.set_running()
                else:
                    msg = '%s:%d Error switch output' % (self.it6900.port, self.it6900.addr)
                    logger.error(msg)
                    self.output_state.set_quality(AttrQuality.ATTR_INVALID)
                    result = False
                    self.set_fault()
            return result

    def read_voltage(self):
        if self.it6900.initialized():
            value = self.it6900.read_voltage()
            if value is not None:
                qual = AttrQuality.ATTR_VALID
                self.set_running()
            else:
                qual = AttrQuality.ATTR_INVALID
                value = float('nan')
                self.set_fault()
        else:
            value = float('nan')
            qual = AttrQuality.ATTR_INVALID
            self.set_fault()
        self.voltage.set_value(value)
        self.voltage.set_quality(qual)
        return value

    def read_current(self):
        if self.it6900.initialized():
            value = self.it6900.read_voltage()
            if value is not None:
                qual = AttrQuality.ATTR_VALID
                self.set_running()
            else:
                qual = AttrQuality.ATTR_INVALID
                value = float('nan')
                self.set_fault()
        else:
            value = float('nan')
            qual = AttrQuality.ATTR_INVALID
            self.set_fault()
        self.current.set_value(value)
        self.current.set_quality(qual)
        return value

    def read_programmed_voltage(self):
        if self.it6900.initialized():
            value = self.it6900.read_programmed_voltage()
            if value is not None:
                qual = AttrQuality.ATTR_VALID
                self.set_running()
            else:
                qual = AttrQuality.ATTR_INVALID
                value = float('nan')
                self.set_fault()
        else:
            value = float('nan')
            qual = AttrQuality.ATTR_INVALID
            self.set_fault()
        self.programmed_voltage.set_value(value)
        self.programmed_voltage.set_quality(qual)
        return value

    def read_programmed_current(self):
        if self.it6900.initialized():
            value = self.it6900.read_programmed_current()
            if value is not None:
                qual = AttrQuality.ATTR_VALID
                self.set_running()
            else:
                qual = AttrQuality.ATTR_INVALID
                value = float('nan')
                self.set_fault()
        else:
            value = float('nan')
            qual = AttrQuality.ATTR_INVALID
            self.set_fault()
        self.programmed_current.set_value(value)
        self.programmed_current.set_quality(qual)
        return value

    def write_programmed_voltage(self, value):
        if not self.it6900.initialized():
            self.programmed_voltage.set_quality(AttrQuality.ATTR_INVALID)
            msg = "%s Writing to offline device" % self
            self.logger.warning(msg)
            result = False
            self.set_fault()
        else:
            result = self.it6900.write_voltage(value)
        if result:
            self.programmed_voltage.set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
        else:
            self.programmed_voltage.set_quality(AttrQuality.ATTR_INVALID)
            self.set_fault()
        return result

    def write_programmed_current(self, value):
        if not self.it6900.initialized():
            self.programmed_voltage.set_quality(AttrQuality.ATTR_INVALID)
            msg = "%s Writing to offline device" % self
            self.logger.warning(msg)
            result = False
            self.set_fault()
        else:
            result = self.it6900.write_current(value)
        if result:
            self.programmed_voltage.set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
        else:
            self.programmed_voltage.set_quality(AttrQuality.ATTR_INVALID)
            self.set_fault()
        return result

    def set_running(self):
        self.set_state(DevState.RUNNING)
        self.set_status('R/W OK')

    def set_fault(self):
        self.set_state(DevState.FAULT)
        self.set_status('Error during R/W')

    @command
    def reconnect(self):
        kwargs = {}
        args = ()
        port = self.config.get('port', 'COM3')
        kwargs['baudrate'] = self.config.get('baudrate', 115200)
        kwargs['logger'] = self.logger
        self.it6900.reconnect(port, *args, **kwargs)

    @command(dtype_in=str, doc_in='Directly send command to the device',
             dtype_out=str, doc_out='Response from device without final LF')
    def send_command(self, cmd):
        self.it6900.send_command(cmd).decode()
        return self.it6900.response[:-1].decode()

if __name__ == "__main__":
    IT6900_Server.run_server()
