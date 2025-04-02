#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LAUDA tango device server
"""
import os
import sys

from LaudaSmall import LaudaSmall

if os.path.realpath('../TangoUtils') not in sys.path: sys.path.append(os.path.realpath('../TangoUtils'))

from tango import Attribute, AttrQuality, AttrWriteType, DispLevel
from tango import DevState
from tango.server import attribute, command

from TangoServerPrototype import TangoServerPrototype
from Lauda import Lauda

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'LUDA Integral XT Python Tango Server'
APPLICATION_NAME_SHORT = os.path.basename(__file__).replace('.py', '')
APPLICATION_VERSION = '1.0'

LAUDA_DEFAULT_PORT = 'COM4'
LAUDA_DEFAULT_ADDRESS =  None
LAUDA_DEFAULT_BAUD =  9600
LAUDA_DEFAULT_READ_TIMEOUT = 1.0
LAUDA_DEFAULT_READ_RETRIES =  2


class LaudaSmallServer(TangoServerPrototype):
    server_version_value = APPLICATION_VERSION
    server_name_value = APPLICATION_NAME

    port = attribute(label="Port", dtype=str,
                     display_level=DispLevel.OPERATOR,
                     access=AttrWriteType.READ,
                     unit="", format="%s",
                     doc="LAUDA COM port")

    address = attribute(label="Address", dtype=str,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ,
                        unit="", format="%s",
                        doc="LAUDA address (Default None for COM port)")

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
                          doc="Local SetPoint")

    run = attribute(label="Run", dtype=bool,
                    display_level=DispLevel.OPERATOR,
                    access=AttrWriteType.READ_WRITE,
                    unit="",
                    doc="Run/Stop Button")

    pump = attribute(label="Pump Level", dtype=int,
                     display_level=DispLevel.OPERATOR,
                     access=AttrWriteType.READ_WRITE,
                     min_value=0,
                     max_value=8,
                     unit="",
                     doc="Pump Power Level")

    external_temp = attribute(label="External Probe Temperature", dtype=float,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ,
                            unit="C", format="%6.2f",
                            doc="External Probe Temperature")

    output_temp = attribute(label="Output Temperature", dtype=float,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ,
                            unit="C", format="%6.2f",
                            doc="Output Fluid Temperature")

    level = attribute(label="Expansion Tank Fluid Level", dtype=int,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ,
                            unit="", format="%1d",
                            doc="Fluid Level in the Expansion Tank (0-9)")

    cooling_mode = attribute(label="Cooling operating mode", dtype=int,
                            display_level=DispLevel.OPERATOR,
                            min_value=0,
                            max_value=2,
                            access=AttrWriteType.READ_WRITE,
                            unit="", format="%1d",
                            doc="Cooling operating mode (0 = OFF / 1 = ON / 2 = AUTOMATIC)")

    pressure = attribute(label="Output Pressure", dtype=float,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ,
                            unit="bar", format="%6.2f",
                            doc="Output Pressure (bar)")

    last_error = attribute(label="Last Error", dtype=str,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ,
                            unit="", format="%s",
                            doc="Last Error")

    error_diagnosis = attribute(label="Error diagnosis response", dtype=str,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ,
                            unit="", format="%s",
                            doc="Error diagnosis response")

    def init_device(self):
        self.lda = None
        super().init_device()
        self.pre = f'{self.get_name()} LAUDA'
        msg = f'Initialization'
        self.log_debug(msg)
        self.set_state(DevState.INIT, msg)
        # get port and address from property
        kwargs = {}
        port = self.config.get('port', LAUDA_DEFAULT_PORT)
        addr = self.config.get('addr', LAUDA_DEFAULT_ADDRESS)
        baud = self.config.get('baudrate', LAUDA_DEFAULT_BAUD)
        kwargs['baudrate'] = baud
        kwargs['logger'] = self.logger
        kwargs['read_timeout'] = self.config.get('read_timeout', LAUDA_DEFAULT_READ_TIMEOUT)
        kwargs['read_retries'] = self.config.get('read_retries', LAUDA_DEFAULT_READ_RETRIES)
        # create LAUDA device
        self.lda = LaudaSmall(port, addr, **kwargs)
        self.pre = f'{self.get_name()} {self.lda.pre}'
        # check if device OK
        if self.lda.ready:
            self.set_point.set_write_value(self.read_set_point())
            self.pump.set_write_value(self.read_pump())
            self.run.set_write_value(self.read_run())
            self.cooling_mode.set_write_value(self.read_cooling_mode())
            # set state to running
            msg = 'Created successfully'
            self.set_state(DevState.RUNNING, msg)
            self.log_info(msg)
        else:
            msg = 'Created with errors'
            self.set_state(DevState.FAULT, msg)
            self.log_error(msg)

    def delete_device(self):
        self.lda.__del__()
        super().delete_device()
        msg = 'Device has been deleted'
        self.log_info(msg)

    def read_port(self):
        if hasattr(self, 'lda') and hasattr(self.lda, 'ready') and self.lda.ready\
                and hasattr(self.lda, 'port'):
            self.port.set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
            return self.lda.port
        else:
            self.set_fault()
            self.port.set_quality(AttrQuality.ATTR_INVALID)
        return 'Undefined'

    def read_address(self):
        if self.lda.ready:
            self.set_running()
            self.address.set_quality(AttrQuality.ATTR_VALID)
        else:
            self.address.set_quality(AttrQuality.ATTR_INVALID)
            self.set_fault()
        return str(self.lda.addr)

    def read_device_type(self):
        if self.lda.ready:
            self.set_running()
            return self.lda.id
        else:
            self.set_fault()
            return "Uninitialized"

    #   ---------------- custom attributes read --------------
    def read_set_point(self):
        value = self.lda.read_value('IN_SP_00')
        if value is not None:
            self.set_point.set_quality(AttrQuality.ATTR_VALID)
            return value
        self.set_point.set_quality(AttrQuality.ATTR_INVALID)
        msg = 'Set point read error'
        self.set_fault(msg)
        return float('Nan')

    def read_run(self):
        value = int(self.lda.read_value('IN_MODE_02'))
        if value is not None:
            self.run.set_quality(AttrQuality.ATTR_VALID)
            if value == 0:
                self.set_state(DevState.RUNNING)
            else:
                # self.log_info('standby %s', value)
                self.set_state(DevState.STANDBY)
            return value == 0
        self.run.set_quality(AttrQuality.ATTR_INVALID)
        self.set_fault('Running state read error')
        return False

    def read_last_error(self):
        return self.lda.error

    def read_error_diagnosis(self):
        if self.lda.send_command('STAT'):
            self.error_diagnosis.set_quality(AttrQuality.ATTR_VALID)
        else:
            self.error_diagnosis.set_quality(AttrQuality.ATTR_INVALID)
        return self.lda.resp

    def read_pump(self):
        value = self.lda.read_value('IN_SP_01')
        if value is not None:
            self.pump.set_quality(AttrQuality.ATTR_VALID)
            return int(value)
        self.pump.set_quality(AttrQuality.ATTR_INVALID)
        self.set_fault('Pump Level read error')
        return -1

    def read_cooling_mode(self):
        value = self.lda.read_value('IN_SP_02')
        if value is not None:
            self.cooling_mode.set_quality(AttrQuality.ATTR_VALID)
            return int(value)
        self.cooling_mode.set_quality(AttrQuality.ATTR_INVALID)
        self.set_fault('Cooling operating mode read error')
        return -1

    def read_output_temp(self):
        value = self.lda.read_value('IN_PV_00')
        if value is not None:
            self.output_temp.set_quality(AttrQuality.ATTR_VALID)
            return value
        self.output_temp.set_quality(AttrQuality.ATTR_INVALID)
        msg = f'Output temperature read error'
        self.set_fault(msg)
        return float('Nan')

    def read_external_temp(self):
        value = self.lda.read_value('IN_PV_01')
        if value is not None:
            self.external_temp.set_quality(AttrQuality.ATTR_VALID)
            return value
        self.external_temp.set_quality(AttrQuality.ATTR_INVALID)
        msg = f'External temperature read error'
        self.set_fault(msg)
        return float('Nan')

    def read_level(self):
        value = self.lda.read_value('IN_PV_05')
        if value is not None:
            self.level.set_quality(AttrQuality.ATTR_VALID)
            return int(value)
        self.level.set_quality(AttrQuality.ATTR_INVALID)
        self.set_fault(f'Pump Level read error')
        return -1

    def read_pressure(self):
        value = self.lda.read_value('IN_PV_02')
        if value is not None:
            self.pressure.set_quality(AttrQuality.ATTR_VALID)
            return value
        self.pressure.set_quality(AttrQuality.ATTR_INVALID)
        self.set_fault(f'Pressure read error')
        return float('Nan')

    #   ---------------- custom attributes write --------------
    def write_set_point(self, value):
        result = self.lda.write_value('OUT_SP_00', value)
        if result:
            self.set_point.set_quality(AttrQuality.ATTR_VALID)
            self.set_point.set_write_value(value)
            return value
        self.set_point.set_quality(AttrQuality.ATTR_INVALID)
        self.set_point.set_write_value(float('Nan'))
        msg = 'Set point write error'
        self.set_fault(msg)
        return float('Nan')

    def write_run(self, value):
        if value:
            cmd = 'START'
        else:
            cmd = 'STOP'
        result = self.lda.send_command(cmd)
        if result:
            self.run.set_quality(AttrQuality.ATTR_VALID)
            self.run.set_write_value(value)
            if value:
                self.set_state(DevState.RUNNING)
            else:
                self.set_state(DevState.STANDBY)
            return value
        self.run.set_quality(AttrQuality.ATTR_INVALID)
        self.run.set_write_value(float('Nan'))
        msg = 'Can not Run'
        self.set_fault(msg)
        return False

    def write_pump(self, value):
        result = self.lda.write_value('OUT_SP_01', value)
        if result:
            self.pump.set_quality(AttrQuality.ATTR_VALID)
            self.pump.set_write_value(value)
            # self.log_debug('write %s', value)
            return value
        self.pump.set_quality(AttrQuality.ATTR_INVALID)
        self.pump.set_write_value(float('Nan'))
        msg = 'Pump Level write error'
        self.set_fault(msg)
        return False

    def write_cooling_mode(self, value):
        result = self.lda.write_value('OUT_SP_02', value)
        if result:
            self.cooling_mode.set_quality(AttrQuality.ATTR_VALID)
            self.cooling_mode.set_write_value(value)
            return value
        self.cooling_mode.set_quality(AttrQuality.ATTR_INVALID)
        self.cooling_mode.set_write_value(float('Nan'))
        msg = 'Cooling operating mode write error'
        self.set_fault(msg)
        return False

    #   ---------------- end custom attributes --------------
    def set_fault(self, msg=None):
        if msg is None:
            if self.lda.initialized():
                msg = 'R/W error'
            else:
                msg = 'Not initialized'
        super().set_fault(msg)

    @command(dtype_in=str, doc_in='Directly send command to the LAUDA',
             dtype_out=str, doc_out='Response from LAUDA without final <CR>')
    def send_command(self, cmd):
        result = self.lda.send_command(cmd)
        rsp = self.lda.resp
        if result:
            msg = f'Command {cmd} executed, result {rsp}'
            self.log_debug(msg)
            self.set_state(DevState.RUNNING, msg)
        else:
            msg = f'Command {cmd} ERROR, result {rsp}'
            self.log_warning(msg)
            self.set_state(DevState.FAULT, msg)
        return msg


if __name__ == "__main__":
    LaudaSmallServer.run_server()
