#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TDK Lambda Genesis series power supply tango device server"""
import sys
if '../TangoUtils' not in sys.path: sys.path.append('../TangoUtils')
if '../IT6900' not in sys.path: sys.path.append('../IT6900')

import logging
import time
from math import isnan

from tango import AttrQuality, AttrWriteType, DispLevel
from tango import DevState
from tango.server import attribute, command

from TDKLambda import TDKLambda, TDKLambda_SCPI
from TangoServerPrototype import TangoServerPrototype

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'TDK Lambda Genesis series PS Python Tango Server'
APPLICATION_NAME_SHORT = 'TDKLambda_Server'
APPLICATION_VERSION = '5.2'  # from ver 4.* Using Python Prototype Tango Server


class TDKLambda_Server(TangoServerPrototype):
    server_version_value = APPLICATION_VERSION
    server_name_value = APPLICATION_NAME_SHORT
    READING_VALID_TIME = 1.0

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
        super().init_device()
        self.pre = self.get_name()
        self.logger.debug(f'{self.pre} TDKLambda Initialization')
        self.set_state(DevState.INIT, f'{self.pre} TDKLambda Initialization')
        self.values = [float('NaN')] * 6
        self.time = time.time() - 100.0
        self.READING_VALID_TIME = self.config.get('reading_valid_time', self.READING_VALID_TIME)
        # get port and address from property
        kwargs = {}
        port = self.config.get('port', 'COM3')
        addr = self.config.get('addr', 6)
        baud = self.config.get('baudrate', 115200)
        kwargs['baudrate'] = baud
        kwargs['logger'] = self.logger
        kwargs['read_timeout'] = self.config.get('read_timeout', 1.0)
        kwargs['read_retries'] = self.config.get('read_retries', 2)
        protocol = self.config.get('protocol', 'GEN')
        # create TDKLambda device
        if protocol == 'GEN':
            self.tdk = TDKLambda(port, addr, **kwargs)
        else:
            self.tdk = TDKLambda_SCPI(port, addr, **kwargs)
        self.pre = f'{self.pre} {self.tdk.pre}'
        # add device to list
        # if self not in TDKLambda_Server.device_list:
        #     TDKLambda_Server.device_list[self.get_name()] = self
        # check if device OK
        if self.tdk.ready:
            if self.tdk.max_voltage < float('inf'):
                self.programmed_voltage.set_max_value(self.tdk.max_voltage)
            if self.tdk.max_current < float('inf'):
                self.programmed_current.set_max_value(self.tdk.max_current)
            self.programmed_voltage.set_write_value(self.read_programmed_voltage())
            self.programmed_current.set_write_value(self.read_programmed_current())
            self.output_state.set_write_value(self.read_output_state())
            # set state to running
            msg = f'{self.pre} created successfully'
            self.set_state(DevState.RUNNING, msg)
            self.logger.info(msg)
        else:
            msg = f'{self.pre} created with errors'
            self.set_state(DevState.FAULT, msg)
            self.logger.error(msg)

    def delete_device(self):
        self.tdk.__del__()
        msg = f'{self.pre} device has been deleted'
        self.logger.info(msg)
        super().delete_device()

    def read_port(self):
        if self.tdk.initialized():
            self.set_running()
        else:
            self.set_fault()
        return self.tdk.port

    def read_address(self):
        if self.tdk.ready:
            self.set_running()
        else:
            self.set_fault()
        return str(self.tdk.addr)

    def read_device_type(self):
        if self.tdk.ready:
            self.set_running()
            return self.tdk.id
        else:
            self.set_fault()
            return "Uninitialized"

    def read_output_state(self):
        value = self.tdk.read_output()
        if value is not None:
            qual = AttrQuality.ATTR_VALID
            self.set_running()
        else:
            qual = AttrQuality.ATTR_INVALID
            value = False
            msg = f'{self.pre} Output voltage read error'
            self.logger.debug(msg)
            self.set_fault(msg)
        self.output_state.set_quality(qual)
        return value

    def read_all(self):
        t0 = time.time()
        try:
            values = self.tdk.read_all()
            self.values = values
            self.time = time.time()
            # msg = '%s:%d read_all %s ms %s' % \
            #       (self.tdk.port, self.tdk.addr, int((self.time - t0) * 1000.0), values)
            # self.logger.debug(msg)
        except:
            msg = f'{self.pre}  read_all error'
            self.log_exception(msg)
            self.set_fault(msg)

    def read_voltage(self, attr):
        if time.time() - self.time > self.READING_VALID_TIME:
            self.read_all()
        val = self.values[0]
        attr.set_value(val)
        if isnan(val):
            attr.set_quality(AttrQuality.ATTR_INVALID)
            msg = f'{self.pre}  Output voltage read error'
            self.logger.debug(msg)
            self.set_fault(msg)
        else:
            attr.set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
        return val

    def read_current(self, attr):
        if time.time() - self.time > self.READING_VALID_TIME:
            self.read_all()
        val = self.values[2]
        attr.set_value(val)
        if isnan(val):
            attr.set_quality(AttrQuality.ATTR_INVALID)
            msg = f'{self.pre} Output current read error'
            self.logger.debug(msg)
            self.set_fault(msg)
        else:
            attr.set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
        return val

    def read_programmed_voltage(self):
        if time.time() - self.time > self.READING_VALID_TIME:
            self.read_all()
        val = self.values[1]
        attr = self.programmed_voltage
        attr.set_value(val)
        if isnan(val):
            attr.set_quality(AttrQuality.ATTR_INVALID)
            msg = f'{self.pre} Programmed voltage read error'
            self.logger.debug(msg)
            self.set_fault(msg)
        else:
            attr.set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
        return val

    def read_programmed_current(self):
        if time.time() - self.time > self.READING_VALID_TIME:
            self.read_all()
        val = self.values[3]
        attr = self.programmed_current
        attr.set_value(val)
        if isnan(val):
            attr.set_quality(AttrQuality.ATTR_INVALID)
            msg = f'{self.pre} Programmed current read error'
            self.logger.debug(msg)
            self.set_fault(msg)
        else:
            attr.set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
        return val

    def write_output_state(self, value):
        if self.tdk.write_output(value):
            self.output_state.set_quality(AttrQuality.ATTR_VALID)
            self.output_state.set_value(value)
            self.output_state.set_write_value(value)
            self.set_running()
            return True
        else:
            msg = f'{self.pre} Error switch output'
            self.logger.warning(msg)
            self.output_state.set_quality(AttrQuality.ATTR_INVALID)
            self.set_fault(msg)
            return False

    def write_programmed_voltage(self, value):
        result = self.tdk.write_voltage(value)
        if result:
            self.programmed_voltage.set_quality(AttrQuality.ATTR_VALID)
            self.programmed_voltage.set_value(value)
            self.programmed_voltage.set_write_value(value)
            self.set_running()
        else:
            self.programmed_voltage.set_quality(AttrQuality.ATTR_INVALID)
            msg = f'{self.pre} Error writing programmed voltage'
            self.logger.warning(msg)
            self.set_fault()
        return result

    def write_programmed_current(self, value):
        result = self.tdk.write_current(value)
        if result:
            self.programmed_current.set_quality(AttrQuality.ATTR_VALID)
            self.programmed_current.set_value(value)
            self.programmed_current.set_write_value(value)
            self.set_running()
        else:
            self.programmed_current.set_quality(AttrQuality.ATTR_INVALID)
            msg = f'{self.pre} Error writing programmed current'
            self.logger.warning(msg)
            self.set_fault()
        return result

    def set_fault(self, msg=None):
        if msg is None:
            if self.tdk.initialized():
                msg = f'{self.pre} R/W error!'
            else:
                msg = f'{self.pre} was not initialized'
        super().set_fault(msg)

    @command(doc_in='Reset power supply by sending RST command',
             dtype_out=str, doc_out='Response from TDKLambda PS without final <CR>')
    def reset_ps(self):
        msg = f'{self.pre} Resetting PS'
        self.logger.info(msg)
        rsp = self.send_command(b'RST')
        return rsp

    @command(dtype_in=str, doc_in='Directly send command to the TDKLambda PS',
             dtype_out=str, doc_out='Response from TDKLambda PS without final <CR>')
    def send_command(self, cmd):
        result = self.tdk.send_command(cmd)
        rsp = self.tdk.response.decode()
        if result:
            msg = f'{self.pre} Command {cmd} executed, result {rsp}'
            self.logger.debug(msg)
            self.set_state(DevState.RUNNING, msg)
        else:
            msg = f'{self.pre} Command {cmd} ERROR, result {rsp}'
            self.logger.warning(msg)
            self.set_state(DevState.FAULT, msg)
        return msg

    @command
    def turn_on(self):
        self.write_output_state(True)

    @command
    def turn_off(self):
        self.write_output_state(False)


if __name__ == "__main__":
    TDKLambda_Server.run_server()
