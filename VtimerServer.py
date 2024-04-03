#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Vtimer tango device server

import os
import sys

util_path = os.path.realpath('../TangoUtils')
if util_path not in sys.path:
    sys.path.append(util_path)
del util_path

from tango import Attribute, AttrQuality, AttrWriteType, DispLevel
from tango import DevState
from tango.server import attribute, command

from TangoServerPrototype import TangoServerPrototype
from Vtimer import Vtimer

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'Vtimer Python Tango Server'
APPLICATION_NAME_SHORT = os.path.basename(__file__).replace('.py', '')
APPLICATION_VERSION = '2.0'

DEFAULT_PORT = 'COM17'
DEFAULT_ADDRESS = 1
DEFAULT_READ_TIMEOUT = 1.0


class VtimerServer(TangoServerPrototype):
    server_version_value = APPLICATION_VERSION
    server_name_value = APPLICATION_NAME

    port = attribute(label="Port", dtype=str,
                     display_level=DispLevel.OPERATOR,
                     access=AttrWriteType.READ,
                     unit="", format="%s",
                     doc="COM port (Default COM17)")

    address = attribute(label="Address", dtype=int,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ,
                        unit="", format="%d",
                        doc="Address (Default 1)")

    device_type = attribute(label="Vtimer Type", dtype=str,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ,
                            unit="", format="%s",
                            doc="Vtimer device type")

    run = attribute(label="Run", dtype=int,
                    display_level=DispLevel.OPERATOR,
                    access=AttrWriteType.READ_WRITE,
                    unit="",
                    doc="Run register")

    mode = attribute(label="Mode", dtype=int,
                     display_level=DispLevel.OPERATOR,
                     access=AttrWriteType.READ_WRITE,
                     unit="",
                     doc="Mode register")

    run_time = attribute(label="Run Time", dtype=float,
                         display_level=DispLevel.OPERATOR,
                         access=AttrWriteType.READ,
                         unit="ms", format="%d",
                         doc="Total script duration [ms]")

    def init_device(self):
        super().init_device()
        self.pre = f'{self.get_name()} Vtimer'
        msg = f'Initialization'
        self.log_debug(msg)
        self.set_state(DevState.INIT, msg)
        # get port and address from property
        kwargs = {}
        port = self.config.get('port', DEFAULT_PORT)
        addr = self.config.get('addr', DEFAULT_ADDRESS)
        kwargs['logger'] = self.logger
        kwargs['read_timeout'] = self.config.get('read_timeout', DEFAULT_READ_TIMEOUT)
        # create Vtimer device
        self.tmr = Vtimer(port, addr, **kwargs)
        self.pre = f'{self.get_name()} {self.tmr.pre}'
        # check if device OK
        if self.tmr.ready:
            self.run.set_write_value(self.read_run())
            # set state to running
            msg = 'Created successfully'
            self.set_state(DevState.RUNNING, msg)
            self.log_info(msg)
        else:
            msg = 'Created with errors'
            self.set_state(DevState.FAULT, msg)
            self.log_error(msg)

    def delete_device(self):
        self.tmr.__del__()
        super().delete_device()
        msg = 'Device has been deleted'
        self.log_info(msg)

    def read_port(self):
        if self.tmr.ready:
            self.set_running()
        else:
            self.set_fault()
        return self.tmr.port

    def read_address(self):
        if self.tmr.ready:
            self.set_running()
        else:
            self.set_fault()
        return self.tmr.addr

    def read_device_type(self):
        if self.tmr.ready:
            self.set_running()
            return self.tmr.id
        else:
            self.set_fault()
            return "Uninitialized"

    #   ---------------- custom attributes read --------------
    def read_run(self):
        value = self.tmr.read_run()
        if value >= 0:
            self.run.set_quality(AttrQuality.ATTR_VALID)
            return value
        self.run.set_quality(AttrQuality.ATTR_INVALID)
        msg = f'run state read error'
        self.set_fault(msg)
        return -1

    def read_mode(self):
        value = self.tmr.read_mode()
        if value >= 0:
            self.run.set_quality(AttrQuality.ATTR_VALID)
            return value
        self.run.set_quality(AttrQuality.ATTR_INVALID)
        msg = f'mode read error'
        self.set_fault(msg)
        return -1

    def read_run_time(self):
        value = self.tmr.read_last()
        if value >= 0:
            self.run.set_quality(AttrQuality.ATTR_VALID)
            return value
        self.run.set_quality(AttrQuality.ATTR_INVALID)
        msg = f'Run Time read error'
        self.set_fault(msg)
        return -1

    #   ---------------- custom attributes write --------------
    def write_value(self, param: str, value):
        resp = self.tmr.send_command(f'{param}={value}')
        if resp:
            return True
        msg = f'{param} write error'
        self.log_debug(msg)
        return False

    def write_bit(self, param: str, bit, value):
        v0 = self.read_value(param, int)
        if v0 is None:
            msg = f'{param}_{bit} write error'
            self.log_debug(msg)
            return False
        if value:
            v1 = v0 | 2 ** bit
        else:
            v1 = v0 & ~(2 ** bit)
        return self.write_value(param, v1)

    def write_set_point(self, value):
        result = self.write_value('1100', f'{value:.2f}')
        if result:
            self.set_point.set_quality(AttrQuality.ATTR_VALID)
            self.set_point.set_write_value(value)
            return value
        self.set_point.set_quality(AttrQuality.ATTR_INVALID)
        self.set_point.set_write_value(float('Nan'))
        msg = 'Set point write error'
        self.set_fault(msg)
        return float('Nan')

    def write_set_point_remote(self, value):
        result = self.write_value('6200', f'{value:.2f}')
        if result:
            self.set_point_remote.set_quality(AttrQuality.ATTR_VALID)
            self.set_point_remote.set_write_value(value)
            return value
        self.set_point_remote.set_quality(AttrQuality.ATTR_INVALID)
        self.set_point_remote.set_write_value(float('Nan'))
        msg = 'Remote set point write error'
        self.set_fault(msg)
        return float('Nan')

    def write_run(self, value):
        result = self.write_bit('6210', 1, value)
        if result:
            self.run.set_quality(AttrQuality.ATTR_VALID)
            self.run.set_write_value(value)
            return value
        self.run.set_quality(AttrQuality.ATTR_INVALID)
        self.run.set_write_value(float('Nan'))
        msg = 'Run switch write error'
        self.set_fault(msg)
        return False

    def write_reset(self, value):
        result = self.write_bit('6210', 2, value)
        if result:
            self.reset.set_quality(AttrQuality.ATTR_VALID)
            self.reset.set_write_value(value)
            return value
        self.reset.set_quality(AttrQuality.ATTR_INVALID)
        self.reset.set_write_value(float('Nan'))
        msg = 'Reset switch write error'
        self.set_fault(msg)
        return False

    def write_valve(self, value):
        result = self.write_bit('6210', 3, value)
        if result:
            self.valve.set_quality(AttrQuality.ATTR_VALID)
            self.valve.set_write_value(value)
            return value
        self.valve.set_quality(AttrQuality.ATTR_INVALID)
        self.valve.set_write_value(float('Nan'))
        msg = 'Valve switch write error'
        self.set_fault(msg)
        return False

    def write_enable(self, value):
        result = self.write_bit('6210', 0, value)
        if result:
            self.enable.set_quality(AttrQuality.ATTR_VALID)
            self.enable.set_write_value(value)
            return value
        self.enable.set_quality(AttrQuality.ATTR_INVALID)
        self.enable.set_write_value(float('Nan'))
        msg = f'enable switch write error'
        self.set_fault(msg)
        return False

    #   ---------------- end custom attributes --------------
    def set_fault(self, msg=None):
        if msg is None:
            if self.tmr.ready:
                msg = f'R/W error!'
            else:
                msg = f'was not initialized'
        super().set_fault(msg)

    # @command(dtype_in=str, doc_in='Directly send command to the Vtimer',
    #          dtype_out=str, doc_out='Response from Vtimer PS without final <CR>')
    # def send_command(self, cmd):
    #     result = self.tmr.send_command(cmd)
    #     rsp = self.tmr.get_response()
    #     if result:
    #         msg = f'Command {cmd} executed, result {rsp}'
    #         self.log_debug(msg)
    #         self.set_state(DevState.RUNNING, msg)
    #     else:
    #         msg = f'Command {cmd} ERROR, result {rsp}'
    #         self.log_warning(msg)
    #         self.set_state(DevState.FAULT, msg)
    #     return msg


if __name__ == "__main__":
    VtimerServer.run_server()
