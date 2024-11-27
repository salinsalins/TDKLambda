#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Vtimer tango device server
import json
import os
import sys
import time

from CKD import CKD

util_path = os.path.realpath('../TangoUtils')
if util_path not in sys.path:
    sys.path.append(util_path)
del util_path

from tango import AttrQuality, AttrWriteType, DispLevel
from tango import DevState
from tango.server import attribute, command

from TangoServerPrototype import TangoServerPrototype
from Vtimer import Vtimer

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'CKD Python Tango Server'
APPLICATION_NAME_SHORT = os.path.basename(__file__).replace('.py', '')
APPLICATION_VERSION = '1.1'

DEFAULT_PORT = 'COM10'
DEFAULT_ADDRESS = 1
DEFAULT_READ_TIMEOUT = 1.0


class CKDServer(TangoServerPrototype):
    server_version_value = APPLICATION_VERSION
    server_name_value = APPLICATION_NAME

    # region ---------------- standard attributes --------------
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

    device_type = attribute(label="CKD Type", dtype=str,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ,
                            unit="", format="%s",
                            doc="CKD type")

    # endregion

    # region ---------------- custom attributes --------------
    set_voltage = attribute(label="Set Voltage", dtype=int,
                    display_level=DispLevel.OPERATOR,
                    access=AttrWriteType.READ_WRITE,
                    min_value=0,
                    max_value=3000,
                    unit="V",
                    doc="Set Voltage")

    set_current = attribute(label="Set Current", dtype=int,
                    display_level=DispLevel.OPERATOR,
                    access=AttrWriteType.READ_WRITE,
                    min_value=0,
                    max_value=1000,
                    unit="A",
                    doc="Set Current")

    out_voltage = attribute(label="Output Voltage", dtype=int,
                    display_level=DispLevel.OPERATOR,
                    access=AttrWriteType.READ,
                    min_value=0,
                    max_value=3000,
                    unit="V",
                    doc="Output Voltage")

    out_current = attribute(label="Output Current", dtype=int,
                    display_level=DispLevel.OPERATOR,
                    access=AttrWriteType.READ,
                    unit="A",
                    doc="Output Current")

    rectifier_current = attribute(label="Output Rectifier Current", dtype=int,
                    display_level=DispLevel.OPERATOR,
                    access=AttrWriteType.READ,
                    unit="A",
                    doc="Output Rectifier Current")

    error_state = attribute(label="Error State", dtype=bool,
                     display_level=DispLevel.OPERATOR,
                     access=AttrWriteType.READ_WRITE,
                     unit="",
                     doc="Error State")

    operation_state = attribute(label="Operation State", dtype=str,
                     display_level=DispLevel.OPERATOR,
                     access=AttrWriteType.READ,
                     unit="",
                     doc="Operation State")

    # password = attribute(label="Password", dtype=int,
    #                 display_level=DispLevel.EXPERT,
    #                 access=AttrWriteType.READ_WRITE,
    #                 unit="",
    #                 doc="Password to unlock CKD")

    k1_level = attribute(label="K1_Level", dtype=float,
                    display_level=DispLevel.OPERATOR,
                    access=AttrWriteType.READ_WRITE,
                    min_value=0.,
                    max_value=40.,
                    unit="%",
                    doc="Level for K1")

    k2_level = attribute(label="K2_Level", dtype=float,
                    display_level=DispLevel.OPERATOR,
                    access=AttrWriteType.READ_WRITE,
                    min_value=0.,
                    max_value=100.,
                    unit="%",
                    doc="Level for K2")

    # start = attribute(label="Start", dtype=bool,
    #                 display_level=DispLevel.OPERATOR,
    #                 access=AttrWriteType.READ_WRITE,
    #                 unit="",
    #                 doc="Switch output ON")
    #
    # stop = attribute(label="Stop", dtype=bool,
    #                 display_level=DispLevel.OPERATOR,
    #                 access=AttrWriteType.READ_WRITE,
    #                 unit="",
    #                 doc="Switch output OFF")

    # endregion

    def init_device(self):
        super().init_device()
        self.pre = f'{self.get_name()} CKD'
        msg = f'Initialization'
        self.log_debug(msg)
        self.set_state(DevState.INIT, msg)
        #
        # get port and address from property
        kwargs = {}
        port = self.config.get('port', DEFAULT_PORT)
        addr = self.config.get('addr', DEFAULT_ADDRESS)
        kwargs['logger'] = self.logger
        kwargs['read_timeout'] = self.config.get('read_timeout', DEFAULT_READ_TIMEOUT)
        # create CKD device
        self.ckd = CKD(port, **kwargs)
        # check if device OK
        if self.ckd.ready:
            self.set_current.set_write_value(self.read_set_current())
            self.set_voltage.set_write_value(self.read_set_voltage())
            self.k1_level.set_write_value(self.read_k1_level())
            self.k2_level.set_write_value(self.read_k2_level())
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

    # region ---------------- attributes read --------------
    def read_port(self):
        if self.ckd.ready:
            self.set_running()
        else:
            self.set_fault()
        return self.ckd.port

    def read_address(self):
        if self.ckd.ready:
            self.set_running()
        else:
            self.set_fault()
        return self.ckd.addr

    def read_device_type(self):
        if self.ckd.ready:
            self.set_running()
            return 'CKD Ready'
        else:
            self.set_fault()
            return "CKD Offline"

    # endregion

    # region ---------------- custom attributes read --------------
    def read_k1_level(self):
        v = self.ckd.modbus_read_ckd(192)
        if not v:
            self.set_fault()
            self.k1_level.set_quality(AttrQuality.ATTR_INVALID)
            return float('nan')
        self.set_running()
        self.k1_level.set_quality(AttrQuality.ATTR_VALID)
        return v / 64.

    def read_k2_level(self):
        v = self.ckd.modbus_read_ckd(193)
        if not v:
            self.set_fault()
            self.k2_level.set_quality(AttrQuality.ATTR_INVALID)
            return float('nan')
        self.set_running()
        self.k2_level.set_quality(AttrQuality.ATTR_VALID)
        return v / 64.

    def read_password(self):
        v = self.ckd.read_one(4102)
        if v is None:
            self.set_fault()
            self.password.set_quality(AttrQuality.ATTR_INVALID)
            return 0
        self.set_running()
        self.password.set_quality(AttrQuality.ATTR_VALID)
        return v

    def read_set_voltage(self):
        v = self.ckd.read_set_voltage()
        if v is None:
            self.set_fault()
            self.set_voltage.set_quality(AttrQuality.ATTR_INVALID)
            return 0
        self.set_running()
        self.set_voltage.set_quality(AttrQuality.ATTR_VALID)
        return v

    def read_set_current(self):
        v = self.ckd.read_set_current()
        if v is None:
            self.set_fault()
            self.set_current.set_quality(AttrQuality.ATTR_INVALID)
            return 0
        self.set_running()
        self.set_current.set_quality(AttrQuality.ATTR_VALID)
        return v

    def read_out_current(self):
        v = self.ckd.read_out_current()
        if v is None:
            self.set_fault()
            self.out_current.set_quality(AttrQuality.ATTR_INVALID)
            return -1
        self.set_running()
        self.out_current.set_quality(AttrQuality.ATTR_VALID)
        return v

    def read_out_voltage(self):
        v = self.ckd.read_out_voltage()
        if v is None:
            self.set_fault()
            self.out_voltage.set_quality(AttrQuality.ATTR_INVALID)
            return -1
        self.set_running()
        self.out_voltage.set_quality(AttrQuality.ATTR_VALID)
        return v

    def read_rectifier_current(self):
        v = self.ckd.read_rectifier_current_k()
        if v is None:
            self.set_fault()
            self.rectifier_current.set_quality(AttrQuality.ATTR_INVALID)
            return -1
        self.set_running()
        self.rectifier_current.set_quality(AttrQuality.ATTR_VALID)
        return v

    def read_error_state(self):
        if self.ckd.read_error():
            self.set_fault('ERROR State')
            return True
        self.set_running()
        return  False

    def read_operation_state(self):
        v = self.ckd.read_status()
        if v == 1:
            self.set_running()
            return "READY"
        if v == 4:
            self.set_running()
            return "WORKING"
        if v == 128:
            self.set_fault('ERROR State')
            return "ERROR"
        self.set_fault('Unknown state')
        return "UNKNOWN"

        # endregion

    # def read_start(self):
    #     v = self.ckd._read(4096, 1)
    #     if v is None:
    #         self.start.set_quality(AttrQuality.ATTR_INVALID)
    #         self.set_fault()
    #         return False
    #     self.start.set_quality(AttrQuality.ATTR_VALID)
    #     self.set_running()
    #     return v & 2
    #
    # def read_stop(self):
    #     v = self.ckd._read(4096, 1)
    #     if v is None:
    #         self.stop.set_quality(AttrQuality.ATTR_INVALID)
    #         self.set_fault()
    #         return False
    #     self.stop.set_quality(AttrQuality.ATTR_VALID)
    #     self.set_running()
    #     return v & 4

    # region ---------------- custom attributes write --------------

    # def write_start(self, v):
    #     self.ckd.modbus_write(4097, [2,])
    #     if self.ckd.modbus_write(4096, [2,]) == 1:
    #         self.set_running()
    #         return True
    #     else:
    #         self.set_fault('Start fault')
    #         return False
    #
    # def write_stop(self, v):
    #     self.ckd.modbus_write(4097, [4,])
    #     if self.ckd.modbus_write(4096, [4,]) == 1:
    #         self.set_running()
    #         return True
    #     else:
    #         self.set_fault('Stop fault')
    #         return False


    def write_k1_level(self, v):
        data = int(v * 64.)
        n = self.ckd.modbus_write_ckd(192, data)
        if n != 2:
            self.set_fault()
            self.k1_level.set_quality(AttrQuality.ATTR_INVALID)
            return False
        self.set_running()
        self.k1_level.set_quality(AttrQuality.ATTR_VALID)
        return True

    def write_k2_level(self, v):
        data = int(v * 64.)
        n = self.ckd.modbus_write_ckd(193, data)
        if n != 2:
            self.set_fault()
            self.k2_level.set_quality(AttrQuality.ATTR_INVALID)
            return False
        self.set_running()
        self.k2_level.set_quality(AttrQuality.ATTR_VALID)
        return True

    def write_password(self, v):
        if self.ckd.modbus_write(4102, [v,]) == 1:
            self.set_running()
            return True
        else:
            self.set_fault('Write voltage fault')
            return False

    def write_set_voltage(self, v):
        if self.ckd.write_set_voltage(v):
            self.set_running()
            return True
        else:
            self.set_fault('Write voltage fault')
            return False

    def write_set_current(self, v):
        if self.ckd.write_set_current(v):
            self.set_running()
            return True
        else:
            self.set_fault('Write current fault')
            return False

    def write_error_state(self, v):
        if self.ckd.write_error_state(v):
            self.set_running()
            return True
        else:
            self.set_fault('Reset Error Fault')
            return False

    # endregion

    # region ---------------- custom commands --------------

    @command(dtype_in=int, doc_in='Read Modbus Address',
             dtype_out=int, doc_out='Red Data')
    def read_modbus(self, addr):
        result = self.ckd.read_one(addr)
        if result is not None:
            self.set_running()
            return result
        msg = f'Pulse enable execution error {self.tmr.error}'
        self.set_fault(msg)
        return False

    # endregion


if __name__ == "__main__":
    CKDServer.run_server()
