#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LAUDA tango device server
"""
import os
import sys

if '../TangoUtils' not in sys.path: sys.path.append('../TangoUtils')

from tango import Attribute, AttrQuality, AttrWriteType, DispLevel
from tango import DevState
from tango.server import attribute, command

from TangoServerPrototype import TangoServerPrototype
from Lauda import Lauda

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'LUDA Python Tango Server'
APPLICATION_NAME_SHORT = os.path.basename(__file__).replace('.py', '')
APPLICATION_VERSION = '2.0'


class LaudaServer(TangoServerPrototype):
    server_version_value = APPLICATION_VERSION
    server_name_value = APPLICATION_NAME

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

    set_point = attribute(label="Local Set Point", dtype=float,
                          display_level=DispLevel.OPERATOR,
                          access=AttrWriteType.READ_WRITE,
                          unit="", format="%6.2f",
                          min_value=0.0,
                          doc="Local Main SetPoint")

    set_point_remote = attribute(label="Remote Set Point", dtype=float,
                                 display_level=DispLevel.OPERATOR,
                                 access=AttrWriteType.READ_WRITE,
                                 unit="", format="%6.2f",
                                 min_value=0.0,
                                 doc="Remote SetPoint")

    run = attribute(label="Run", dtype=bool,
                    display_level=DispLevel.OPERATOR,
                    access=AttrWriteType.READ_WRITE,
                    unit="",
                    doc="Run/Stop button")

    reset = attribute(label="Reset", dtype=bool,
                      display_level=DispLevel.OPERATOR,
                      access=AttrWriteType.READ_WRITE,
                      unit="",
                      doc="Reset button")

    valve = attribute(label="Valve write", dtype=bool,
                      display_level=DispLevel.OPERATOR,
                      access=AttrWriteType.READ_WRITE,
                      unit="",
                      doc="Valve ON/OFF button")

    enable = attribute(label="Enable", dtype=bool,
                       display_level=DispLevel.OPERATOR,
                       access=AttrWriteType.READ_WRITE,
                       unit="",
                       doc="Enable ON/OFF button")

    pump = attribute(label="Pump State", dtype=bool,
                     display_level=DispLevel.OPERATOR,
                     access=AttrWriteType.READ,
                     unit="",
                     doc="Pump State")

    valve_state = attribute(label="Valve State", dtype=bool,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ,
                            unit="",
                            doc="Valve State")

    return_temp = attribute(label="Return Temperature", dtype=float,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ,
                            unit="", format="%6.2f",
                            doc="Return Fluid Temperature")

    output_temp = attribute(label="Output Temperature", dtype=float,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ,
                            unit="", format="%6.2f",
                            doc="Output Fluid Temperature")

    def init_device(self):
        super().init_device()
        self.pre = f'{self.get_name()} LAUDA'
        msg = f'{self.pre} Initialization'
        self.logger.debug(msg)
        self.set_state(DevState.INIT, msg)
        # get port and address from property
        kwargs = {}
        port = self.config.get('port', 'COM4')
        addr = self.config.get('addr', 5)
        baud = self.config.get('baudrate', 38400)
        kwargs['baudrate'] = baud
        kwargs['logger'] = self.logger
        kwargs['read_timeout'] = self.config.get('read_timeout', 1.0)
        kwargs['read_retries'] = self.config.get('read_retries', 2)
        # create LAUDA device
        self.lda = Lauda(port, addr, **kwargs)
        self.pre = f'{self.get_name()} {self.lda.pre}'
        # add device to list
        # if self not in Lauda_Server.device_list:
        #     Lauda_Server.device_list[self.get_name()] = self
        # check if device OK
        if self.lda.ready:
            self.set_point.set_write_value(self.read_set_point())
            self.set_point_remote.set_write_value(self.read_set_point_remote())
            self.run.set_write_value(self.read_run())
            self.reset.set_write_value(self.read_reset())
            self.valve.set_write_value(self.read_valve())
            self.enable.set_write_value(self.read_enable())
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
        if self.lda.ready:
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

    #   ---------------- custom attributes read --------------
    def read_general(self, attr: Attribute):
        attr_name = attr.get_name()
        # self.LOGGER.debug('entry %s %s', self.get_name(), attr_name)
        if self.is_connected():
            val = self._read_io(attr)
        else:
            val = None
            msg = '%s %s Waiting for reconnect' % (self.get_name(), attr.get_name())
            self.logger.debug(msg)
        return self.set_attribute_value(attr, val)

    def read_value(self, param: str, type=float):
        resp = self.lda.send_command(param)
        if resp:
            try:
                v = self.lda.get_response()
                v1 = v.split('=')
                value = type(v1[-1])
                return value
            except KeyboardInterrupt:
                raise
            except:
                pass
        msg = f'{self.pre} {param} read error'
        self.logger.debug(msg)
        return None

    def read_bit(self, param: str, n):
        resp = self.lda.send_command(param)
        if resp:
            try:
                v = self.lda.get_response()
                v1 = v.split('=')
                value = bool(int(v1[-1]) & 2 ** n)
                return value
            except KeyboardInterrupt:
                raise
            except:
                pass
        msg = f'{self.pre} p{param} read error'
        self.logger.debug(msg)
        return None

    def read_set_point(self):
        value = self.read_value('1100')
        if value is not None:
            self.set_point.set_quality(AttrQuality.ATTR_VALID)
            return value
        self.set_point.set_quality(AttrQuality.ATTR_INVALID)
        msg = f'{self.pre} set point read error'
        self.set_fault(msg)
        return float('Nan')

    def read_set_point_remote(self):
        value = self.read_value('6200')
        if value is not None:
            self.set_point_remote.set_quality(AttrQuality.ATTR_VALID)
            return value
        self.set_point_remote.set_quality(AttrQuality.ATTR_INVALID)
        msg = f'{self.pre} remote set point read error'
        self.set_fault(msg)
        return float('Nan')

    def read_run(self):
        value = self.read_bit('6210', 1)
        if value is not None:
            self.run.set_quality(AttrQuality.ATTR_VALID)
            return value
        self.run.set_quality(AttrQuality.ATTR_INVALID)
        msg = f'{self.pre} run state read error'
        self.set_fault(msg)
        return False

    def read_reset(self):
        value = self.read_bit('6210', 2)
        # self.logger.error(f'{value}')
        if value is not None:
            self.reset.set_quality(AttrQuality.ATTR_VALID)
            return value
        self.reset.set_quality(AttrQuality.ATTR_INVALID)
        msg = f'{self.pre} reset state read error'
        self.set_fault(msg)
        return False

    def read_enable(self):
        value = self.read_bit('6210', 0)
        if value is not None:
            self.enable.set_quality(AttrQuality.ATTR_VALID)
            return value
        self.enable.set_quality(AttrQuality.ATTR_INVALID)
        msg = f'{self.pre} enable state read error'
        self.set_fault(msg)
        return False

    def read_valve(self):
        value = self.read_bit('6210', 3)
        if value is not None:
            self.valve.set_quality(AttrQuality.ATTR_VALID)
            return value
        self.valve.set_quality(AttrQuality.ATTR_INVALID)
        msg = f'{self.pre} valve write state read error'
        self.set_fault(msg)
        return False

    def read_pump(self):
        value = self.read_bit('6230', 0)
        if value is not None:
            self.pump.set_quality(AttrQuality.ATTR_VALID)
            return value
        self.pump.set_quality(AttrQuality.ATTR_INVALID)
        msg = f'{self.pre} enable state read error'
        self.set_fault(msg)
        return False

    def read_valve_state(self):
        value = self.read_bit('6230', 7)
        if value is not None:
            self.valve_state.set_quality(AttrQuality.ATTR_VALID)
            return value
        self.valve_state.set_quality(AttrQuality.ATTR_INVALID)
        msg = f'{self.pre} valve state read error'
        self.set_fault(msg)
        return False

    def read_return_temp(self):
        value = self.read_value('1012')
        if value is not None:
            self.return_temp.set_quality(AttrQuality.ATTR_VALID)
            return value
        self.return_temp.set_quality(AttrQuality.ATTR_INVALID)
        msg = f'{self.pre} return temperature read error'
        self.set_fault(msg)
        return float('Nan')

    def read_output_temp(self):
        value = self.read_value('1011')
        if value is not None:
            self.output_temp.set_quality(AttrQuality.ATTR_VALID)
            return value
        self.output_temp.set_quality(AttrQuality.ATTR_INVALID)
        msg = f'{self.pre} output temperature read error'
        self.set_fault(msg)
        return float('Nan')

    #   ---------------- custom attributes write --------------
    def write_value(self, param: str, value):
        resp = self.lda.send_command(f'{param}={value}')
        if resp:
            return True
        msg = f'{self.pre} {param} write error'
        self.logger.debug(msg)
        return False

    def write_bit(self, param: str, bit, value):
        v0 = self.read_value(param, int)
        if v0 is None:
            msg = f'{self.pre} {param}_{bit} write error'
            self.logger.debug(msg)
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
        msg = f'{self.pre} set point write error'
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
        msg = f'{self.pre} remote set point write error'
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
        msg = f'{self.pre} run switch write error'
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
        msg = f'{self.pre} reset switch write error'
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
        msg = f'{self.pre} valve switch write error'
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
        msg = f'{self.pre} enable switch write error'
        self.set_fault(msg)
        return False

    #   ---------------- end custom attributes --------------
    def set_fault(self, msg=None):
        if msg is None:
            if self.lda.initialized():
                msg = f'{self.pre} R/W error!'
            else:
                msg = f'{self.pre} was not initialized'
        super().set_fault(msg)

    @command(dtype_in=str, doc_in='Directly send command to the LAUDA',
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
