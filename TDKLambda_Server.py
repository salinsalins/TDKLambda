#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TDK Lambda Genesis series power supply tango device server"""
import sys; sys.path.append('../TangoUtils'); sys.path.append('../IT6900')

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
APPLICATION_VERSION = '5.1'  # from ver 4.* Using Python Prototype Tango Server


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
        # self.logger.info('TDKLambda Initialization start')
        super().init_device()
        self.logger.info('TDKLambda Initialization')
        # self.configure_tango_logging()
        self.error_count = 0
        self.values = [float('NaN')] * 6
        self.time = time.time() - 100.0
        self.set_state(DevState.INIT, 'TDKLambda Initialization')
        self.last_level = logging.INFO
        self.READING_VALID_TIME = self.config.get('reading_valid_time', self.READING_VALID_TIME)
        # get port and address from property
        kwargs = {}
        port = self.config.get('port', 'COM3')
        addr = self.config.get('addr', 6)
        baud = self.config.get('baudrate', 115200)
        kwargs['baudrate'] = baud
        kwargs['logger'] = self.logger
        protocol = self.config.pop('protocol', 'GEN')
        # create TDKLambda device
        if protocol == 'GEN':
            self.tdk = TDKLambda(port, addr, **kwargs)
        else:
            self.tdk = TDKLambda_SCPI(port, addr, **kwargs)
        # add device to list
        if self not in TDKLambda_Server.device_list:
            TDKLambda_Server.device_list.append(self)
        # self.write_config_to_properties()
        # check if device OK
        if self.tdk.initialized():
            if self.tdk.max_voltage < float('inf'):
                self.programmed_voltage.set_max_value(self.tdk.max_voltage)
            if self.tdk.max_current < float('inf'):
                self.programmed_current.set_max_value(self.tdk.max_current)
            self.programmed_voltage.set_write_value(self.read_programmed_voltage())
            self.programmed_current.set_write_value(self.read_programmed_current())
            self.output_state.set_write_value(self.read_output_state())
            # set state to running
            msg = 'TDKLambda %s created successfully at %s:%d' % (self.tdk.id, self.tdk.port, self.tdk.addr)
            self.set_state(DevState.RUNNING, msg)
            self.logger.info(msg)
        else:
            msg = 'TDKLambda %s at %s:%d created with errors' % (self.tdk.id, self.tdk.port, self.tdk.addr)
            self.set_state(DevState.FAULT, msg)
            self.logger.error(msg)

    def delete_device(self):
        if self in TDKLambda_Server.device_list:
            TDKLambda_Server.device_list.remove(self)
            self.tdk.__del__()
            msg = ' %s:%d TDKLambda device has been deleted' % (self.tdk.port, self.tdk.addr)
            self.logger.info(msg)
        super().delete_device()

    def read_port(self):
        if self.tdk.initialized():
            return self.tdk.port
        return "Unknown"

    def read_address(self):
        if self.tdk.initialized():
            return str(self.tdk.addr)
        return "-1"

    def read_device_type(self):
        if self.tdk.initialized():
            return self.tdk.id
        return "Uninitialized"

    def read_output_state(self):
        if self.tdk.initialized():
            value = self.tdk.read_output()
            if value is not None:
                qual = AttrQuality.ATTR_VALID
                self.set_running()
            else:
                qual = AttrQuality.ATTR_INVALID
                value = False
                self.set_fault('Output read error')
        else:
            value = False
            qual = AttrQuality.ATTR_INVALID
            self.set_fault()
        self.output_state.set_quality(qual)
        return value

    def write_output_state(self, value):
        if self.tdk.com is None:
            msg = '%s:%d Switch output for offline device' % (self.tdk.port, self.tdk.addr)
            self.logger.debug(msg)
            self.output_state.set_quality(AttrQuality.ATTR_INVALID)
            result = False
            self.set_fault(msg)
        else:
            if self.tdk.write_output(value):
                self.output_state.set_quality(AttrQuality.ATTR_VALID)
                result = True
                self.set_running()
            else:
                msg = '%s:%d Error switch output' % (self.tdk.port, self.tdk.addr)
                self.log_exception(self.logger, msg)
                result = False
                self.set_fault(msg)
        return result

    def read_all(self):
        t0 = time.time()
        try:
            values = self.tdk.read_all()
            self.values = values
            self.time = time.time()
            msg = '%s:%d read_all %s ms %s' % \
                  (self.tdk.port, self.tdk.addr, int((self.time - t0) * 1000.0), values)
            self.logger.debug(msg)
        except:
            self.set_fault()
            msg = '%s:%d read_all error' % (self.tdk.port, self.tdk.addr)
            self.log_exception(msg)

    def read_voltage(self, attr):
        if time.time() - self.time > self.READING_VALID_TIME:
            self.read_all()
        val = self.values[0]
        attr.set_value(val)
        if isnan(val):
            attr.set_quality(AttrQuality.ATTR_INVALID)
            self.logger.warning("Output voltage read error")
            self.set_fault()
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
            self.logger.warning("Output current read error")
            self.set_fault()
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
            self.logger.warning("Programmed voltage read error")
            self.set_fault()
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
            self.logger.warning("Programmed current  read error")
            self.set_fault()
        else:
            attr.set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
        return val

    def write_programmed_voltage(self, value):
        if self.tdk.com is None:
            self.programmed_voltage.set_quality(AttrQuality.ATTR_INVALID)
            msg = "%s Writing to offline device" % self
            self.logger.warning(msg)
            result = False
            self.set_fault()
        else:
            result = self.tdk.write_voltage(value)
        if result:
            self.programmed_voltage.set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
        else:
            self.programmed_voltage.set_quality(AttrQuality.ATTR_INVALID)
            msg = "%s Error writing programmed voltage" % self
            self.logger.warning(msg)
            self.set_fault()
        return result

    def write_programmed_current(self, value):
        if self.tdk.com is None:
            self.programmed_current.set_quality(AttrQuality.ATTR_INVALID)
            msg = "%s Writing to offline device" % self
            self.logger.warning(msg)
            result = False
            self.set_fault()
        else:
            result = self.tdk.write_current(value)
        if result:
            self.programmed_current.set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
        else:
            self.programmed_current.set_quality(AttrQuality.ATTR_INVALID)
            msg = "%s Error writing programmed current" % self
            self.logger.warning(msg)
            self.set_fault()
        return result

    # def set_running(self, msg=None):
    #     # self.error_count = 0
    #     super().set_running(msg)
    #
    def set_fault(self, msg=None):
        # self.error_count += 1
        # if self.error_count > 5:
        #     super().set_fault()
        if msg is None:
            if self.tdk.initialized():
                msg = 'R/W error!'
            else:
                msg = 'TDKLambda was not initialized'
        super().set_fault(msg)

    @command(doc_in='Reset power supply by sending RST command',
             dtype_out=str, doc_out='Response from TDKLambda PS without final <CR>')
    def reset_ps(self):
        msg = '%s:%d Resetting TDKLambda PS' % (self.tdk.port, self.tdk.addr)
        self.logger.info(msg)
        rsp = self.send_command(b'RST')
        return rsp

    @command(dtype_in=str, doc_in='Directly send command to the TDKLambda PS',
             dtype_out=str, doc_out='Response from TDKLambda PS without final <CR>')
    def send_command(self, cmd):
        result = self.tdk.send_command(cmd)
        rsp = self.tdk.response.decode()
        if result:
            msg = f'Command {cmd} OK, result {rsp}'
            self.logger.debug(msg)
            self.set_state(DevState.RUNNING, msg)
        else:
            msg = f'Command {cmd} ERROR, result {rsp}'
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
