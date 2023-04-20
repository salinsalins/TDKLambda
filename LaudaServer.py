#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TDK Lambda Genesis series power supply tango device server"""
import sys

from Lauda import Lauda

if '../TangoUtils' not in sys.path: sys.path.append('../TangoUtils')
if '../IT6900' not in sys.path: sys.path.append('../IT6900')

import logging
import time
from math import isnan

from tango import AttrQuality, AttrWriteType, DispLevel
from tango import DevState
from tango.server import attribute, command

from TangoServerPrototype import TangoServerPrototype

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'LUDA Python Tango Server'
APPLICATION_NAME_SHORT = 'LaudaServer'
APPLICATION_VERSION = '1.0'


class LaudaServer(TangoServerPrototype):
    server_version_value = APPLICATION_VERSION
    server_name_value = APPLICATION_NAME_SHORT

    port = attribute(label="Port", dtype=str,
                     display_level=DispLevel.OPERATOR,
                     access=AttrWriteType.READ,
                     unit="", format="%s",
                     doc="LAUDA COM port")

    address = attribute(label="Address", dtype=int,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ,
                        unit="", format="%d",
                        doc="LAUDA address (Default 5)")

    device_type = attribute(label="LAUDA Type", dtype=str,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ,
                            unit="", format="%s",
                            doc="LAUDA device type")

    p6230 = attribute(label="Parameter 6230", dtype=float,
                      display_level=DispLevel.OPERATOR,
                      access=AttrWriteType.READ,
                      unit="", format="%6.2f",
                      min_value=0.0,
                      doc="Parameter 6230")

    p1100 = attribute(label="Parameter 1100", dtype=float,
                      display_level=DispLevel.OPERATOR,
                      access=AttrWriteType.READ_WRITED,
                      unit="", format="%6.2f",
                      min_value=0.0,
                      doc="Main SetPoint")

    def init_device(self):
        super().init_device()
        self.pre = self.get_name()
        self.logger.debug(f'{self.pre}LAUDA Initialization')
        self.set_state(DevState.INIT, f'{self.pre} LAUDA Initialization')
        # get port and address from property
        kwargs = {}
        port = self.config.get('port', 'COM4')
        addr = self.config.get('addr', 5)
        baud = self.config.get('baudrate', 38400)
        kwargs['baudrate'] = baud
        kwargs['logger'] = self.logger
        # create LAUDA device
        self.lda = Lauda(port, addr, **kwargs)
        self.pre = f'{self.pre} {self.lda.pre}'
        # add device to list
        # if self not in Lauda_Server.device_list:
        #     Lauda_Server.device_list[self.get_name()] = self
        # check if device OK
        if self.lda.ready:
            # if self.lda.max_voltage < float('inf'):
            #     self.programmed_voltage.set_max_value(self.lda.max_voltage)
            # if self.lda.max_current < float('inf'):
            #     self.programmed_current.set_max_value(self.lda.max_current)
            # self.programmed_voltage.set_write_value(self.read_programmed_voltage())
            # self.programmed_current.set_write_value(self.read_programmed_current())
            # self.output_state.set_write_value(self.read_output_state())
            # set state to running
            msg = f'{self.pre} created successfully'
            self.set_state(DevState.RUNNING, msg)
            self.logger.info(msg)
        else:
            msg = f'{self.pre} created with errors'
            self.set_state(DevState.FAULT, msg)
            self.logger.error(msg)

    def delete_device(self):
        self.lda.__del__()
        msg = f'{self.pre} device has been deleted'
        self.logger.info(msg)
        super().delete_device()

    def read_port(self):
        if self.lda.initialized():
            self.set_running()
        else:
            self.set_fault()
        return self.lda.port

    def read_address(self):
        if self.lda.ready:
            self.set_running()
        else:
            self.set_fault()
        return self.lda.addr

    def read_device_type(self):
        if self.lda.ready:
            self.set_running()
            return self.lda.id
        else:
            self.set_fault()
            return "Uninitialized"

    def read_p1100(self):
        resp = self.lda.send_command('1100')
        if resp:
            try:
                v = self.lda.get_response()
                v1 = v.split('=')
                value = float(v1[-1])
                self.set_running()
                self.p1100.set_quality(AttrQuality.ATTR_VALID)
                return value
            except:
                pass
        msg = f'{self.pre} p1100 read error'
        self.logger.debug(msg)
        self.p1100.set_quality(AttrQuality.ATTR_INVALID)
        self.set_fault(msg)
        return float('Nan')

    def read_p6230(self):
        resp = self.lda.send_command('6230')
        if resp:
            try:
                v = self.lda.get_response()
                v1 = v.split('=')
                value = float(v1[-1])
                self.set_running()
                self.p1100.set_quality(AttrQuality.ATTR_VALID)
                return value
            except:
                pass
        msg = f'{self.pre} p6230 read error'
        self.logger.debug(msg)
        self.p1100.set_quality(AttrQuality.ATTR_INVALID)
        self.set_fault(msg)
        return float('Nan')

    def read_param(self, param: str, type=float):
        resp = self.lda.send_command(param)
        if resp:
            try:
                v = self.lda.get_response()
                v1 = v.split('=')
                value = type(v1[-1])
                return value
            except:
                pass
        msg = f'{self.pre} p{param} read error'
        self.logger.debug(msg)
        return None

    def write_param(self, param: str, value):
        resp = self.lda.send_command(f'{param}={value}')
        if resp:
            return True
        msg = f'{self.pre} p{param} write error'
        self.logger.debug(msg)
        return False

    def write_p1100(self, value):
        if self.write_param('1100', value):
            self.p1100.set_quality(AttrQuality.ATTR_VALID)
            self.p1100.set_value(value)
            self.p1100.set_write_value(value)
            self.set_running()
            return True
        else:
            msg = f'{self.pre} Error write p1100'
            self.logger.warning(msg)
            self.p1100.set_quality(AttrQuality.ATTR_INVALID)
            self.set_fault(msg)
            return False

    def set_fault(self, msg=None):
        if msg is None:
            if self.lda.initialized():
                msg = f'{self.pre} R/W error!'
            else:
                msg = f'{self.pre} was not initialized'
        super().set_fault(msg)

    @command(dtype_in=str, doc_in='Directly send command to the LAUDA PS',
             dtype_out=str, doc_out='Response from LAUDA PS without final <CR>')
    def send_command(self, cmd):
        result = self.lda.send_command(cmd)
        rsp = self.lda.get_response()
        if result:
            msg = f'{self.pre} Command {cmd} executed, result {rsp}'
            self.logger.debug(msg)
            self.set_state(DevState.RUNNING, msg)
        else:
            msg = f'{self.pre} Command {cmd} ERROR, result {rsp}'
            self.logger.warning(msg)
            self.set_state(DevState.FAULT, msg)
        return msg


if __name__ == "__main__":
    LaudaServer.run_server()
