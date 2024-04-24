#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Vtimer tango device server
import json
import os
import sys
import time

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
APPLICATION_NAME = 'Vtimer Python Tango Server'
APPLICATION_NAME_SHORT = os.path.basename(__file__).replace('.py', '')
APPLICATION_VERSION = '1.3'

DEFAULT_PORT = 'COM17'
DEFAULT_ADDRESS = 1
DEFAULT_READ_TIMEOUT = 1.0


class VtimerServer(TangoServerPrototype):
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

    device_type = attribute(label="Vtimer Type", dtype=str,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ,
                            unit="", format="%s",
                            doc="Vtimer device type")

    # endregion

    # region ---------------- custom attributes --------------
    run = attribute(label="Run", dtype=int,
                    display_level=DispLevel.OPERATOR,
                    access=AttrWriteType.READ_WRITE,
                    min_value=0,
                    max_value=3,
                    unit="",
                    doc="Run register")

    mode = attribute(label="Mode", dtype=int,
                     display_level=DispLevel.OPERATOR,
                     access=AttrWriteType.READ_WRITE,
                     min_value=0,
                     max_value=2,
                     unit="",
                     doc="Mode register")

    last_duration = attribute(label="Last Run", dtype=int,
                              display_level=DispLevel.OPERATOR,
                              access=AttrWriteType.READ,
                              unit="ms",
                              format="%d",
                              doc="Last script duration [ms]")

    last_time = attribute(label="Last Shot Time", dtype=float,
                          display_level=DispLevel.OPERATOR,
                          access=AttrWriteType.READ,
                          unit="",
                          format="%f",
                          doc="Last shot time UTF")

    duration = attribute(label="Script duration", dtype=int,
                         display_level=DispLevel.OPERATOR,
                         access=AttrWriteType.READ_WRITE,
                         unit="ms", format="%d",
                         doc="Total script duration [ms]")

    output = attribute(label="Output", dtype=bool,
                       display_level=DispLevel.OPERATOR,
                       access=AttrWriteType.READ_WRITE,
                       unit="",
                       doc="Optical output control")

    pulse = attribute(label="Pulse state", dtype=bool,
                      display_level=DispLevel.OPERATOR,
                      access=AttrWriteType.READ,
                      unit="",
                      doc="Pulse ON/OFF state")

    faults = attribute(label="Faults register", dtype=int,
                       display_level=DispLevel.OPERATOR,
                       access=AttrWriteType.READ,
                       unit="",
                       doc="Faults register state")

    period = attribute(label="Period", dtype=float,
                       display_level=DispLevel.OPERATOR,
                       access=AttrWriteType.READ_WRITE,
                       unit="s",
                       doc="Automatic start period [s]")

    start_mode = attribute(label="Auto start mode", dtype=bool,
                           display_level=DispLevel.OPERATOR,
                           access=AttrWriteType.READ_WRITE,
                           unit="",
                           doc="Auto start mode")
    # endregion

    # region ---------------- channels --------------
    channel_enable0 = attribute(label="Channel 0", dtype=bool,
                                display_level=DispLevel.OPERATOR,
                                access=AttrWriteType.READ_WRITE,
                                unit="",
                                doc="Channel 0 ON/OFF state")

    pulse_start0 = attribute(label="Channel 0 start", dtype=int,
                             display_level=DispLevel.OPERATOR,
                             access=AttrWriteType.READ_WRITE,
                             unit="ms",
                             doc="Channel 0 start time [ms]")

    pulse_stop0 = attribute(label="Channel 0 stop", dtype=int,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ_WRITE,
                            unit="ms",
                            doc="Channel 1 stop time [ms]")

    channel_enable1 = attribute(label="Channel 1", dtype=bool,
                                display_level=DispLevel.OPERATOR,
                                access=AttrWriteType.READ_WRITE,
                                unit="",
                                doc="Channel 1 ON/OFF state")

    pulse_start1 = attribute(label="Channel 1 start", dtype=int,
                             display_level=DispLevel.OPERATOR,
                             access=AttrWriteType.READ_WRITE,
                             unit="ms",
                             doc="Channel 1 start time [ms]")

    pulse_stop1 = attribute(label="Channel 1 stop", dtype=int,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ_WRITE,
                            unit="ms",
                            doc="Channel 1 stop time [ms]")

    channel_enable2 = attribute(label="Channel 2", dtype=bool,
                                display_level=DispLevel.OPERATOR,
                                access=AttrWriteType.READ_WRITE,
                                unit="",
                                doc="Channel 2 ON/OFF state")

    pulse_start2 = attribute(label="Channel 2 start", dtype=int,
                             display_level=DispLevel.OPERATOR,
                             access=AttrWriteType.READ_WRITE,
                             unit="ms",
                             doc="Channel 2 start time [ms]")

    pulse_stop2 = attribute(label="Channel 2 stop", dtype=int,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ_WRITE,
                            unit="ms",
                            doc="Channel 2 stop time [ms]")

    channel_enable3 = attribute(label="Channel 3", dtype=bool,
                                display_level=DispLevel.OPERATOR,
                                access=AttrWriteType.READ_WRITE,
                                unit="",
                                doc="Channel 3 ON/OFF state")

    pulse_start3 = attribute(label="Channel 3 start", dtype=int,
                             display_level=DispLevel.OPERATOR,
                             access=AttrWriteType.READ_WRITE,
                             unit="ms",
                             doc="Channel 3 start time [ms]")

    pulse_stop3 = attribute(label="Channel 3 stop", dtype=int,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ_WRITE,
                            unit="ms",
                            doc="Channel 3 stop time [ms]")

    channel_enable4 = attribute(label="Channel 4", dtype=bool,
                                display_level=DispLevel.OPERATOR,
                                access=AttrWriteType.READ_WRITE,
                                unit="",
                                doc="Channel 4 ON/OFF state")

    pulse_start4 = attribute(label="Channel 4 start", dtype=int,
                             display_level=DispLevel.OPERATOR,
                             access=AttrWriteType.READ_WRITE,
                             unit="ms",
                             doc="Channel 4 start time [ms]")

    pulse_stop4 = attribute(label="Channel 4 stop", dtype=int,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ_WRITE,
                            unit="ms",
                            doc="Channel 4 stop time [ms]")

    channel_enable5 = attribute(label="Channel 5", dtype=bool,
                                display_level=DispLevel.OPERATOR,
                                access=AttrWriteType.READ_WRITE,
                                unit="",
                                doc="Channel 5 ON/OFF state")

    pulse_start5 = attribute(label="Channel 5 start", dtype=int,
                             display_level=DispLevel.OPERATOR,
                             access=AttrWriteType.READ_WRITE,
                             unit="ms",
                             doc="Channel 5 start time [ms]")

    pulse_stop5 = attribute(label="Channel 5 stop", dtype=int,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ_WRITE,
                            unit="ms",
                            doc="Channel 5 stop time [ms]")

    channel_enable6 = attribute(label="Channel 6", dtype=bool,
                                display_level=DispLevel.OPERATOR,
                                access=AttrWriteType.READ_WRITE,
                                unit="",
                                doc="Channel 6 ON/OFF state")

    pulse_start6 = attribute(label="Channel 6 start", dtype=int,
                             display_level=DispLevel.OPERATOR,
                             access=AttrWriteType.READ_WRITE,
                             unit="ms",
                             doc="Channel 6 start time [ms]")

    pulse_stop6 = attribute(label="Channel 6 stop", dtype=int,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ_WRITE,
                            unit="ms",
                            doc="Channel 6 stop time [ms]")

    channel_enable7 = attribute(label="Channel 7", dtype=bool,
                                display_level=DispLevel.OPERATOR,
                                access=AttrWriteType.READ_WRITE,
                                unit="",
                                doc="Channel 7 ON/OFF state")

    pulse_start7 = attribute(label="Channel 7 start", dtype=int,
                             display_level=DispLevel.OPERATOR,
                             access=AttrWriteType.READ_WRITE,
                             unit="ms",
                             doc="Channel 7 start time [ms]")

    pulse_stop7 = attribute(label="Channel 7 stop", dtype=int,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ_WRITE,
                            unit="ms",
                            doc="Channel 7 stop time [ms]")

    channel_enable8 = attribute(label="Channel 8", dtype=bool,
                                display_level=DispLevel.OPERATOR,
                                access=AttrWriteType.READ_WRITE,
                                unit="",
                                doc="Channel 8 ON/OFF state")

    pulse_start8 = attribute(label="Channel 8 start", dtype=int,
                             display_level=DispLevel.OPERATOR,
                             access=AttrWriteType.READ_WRITE,
                             unit="ms",
                             doc="Channel 8 start time [ms]")

    pulse_stop8 = attribute(label="Channel 8 stop", dtype=int,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ_WRITE,
                            unit="ms",
                            doc="Channel 8 stop time [ms]")

    channel_enable9 = attribute(label="Channel 9", dtype=bool,
                                display_level=DispLevel.OPERATOR,
                                access=AttrWriteType.READ_WRITE,
                                unit="",
                                doc="Channel 9 ON/OFF state")

    pulse_start9 = attribute(label="Channel 9 start", dtype=int,
                             display_level=DispLevel.OPERATOR,
                             access=AttrWriteType.READ_WRITE,
                             unit="ms",
                             doc="Channel 9 start time [ms]")

    pulse_stop9 = attribute(label="Channel 9 stop", dtype=int,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ_WRITE,
                            unit="ms",
                            doc="Channel 9 stop time [ms]")

    channel_enable10 = attribute(label="Channel 10", dtype=bool,
                                 display_level=DispLevel.OPERATOR,
                                 access=AttrWriteType.READ_WRITE,
                                 unit="",
                                 doc="Channel 10 ON/OFF state")

    pulse_start10 = attribute(label="Channel 10 start", dtype=int,
                              display_level=DispLevel.OPERATOR,
                              access=AttrWriteType.READ_WRITE,
                              unit="ms",
                              doc="Channel 10 start time [ms]")

    pulse_stop10 = attribute(label="Channel 10 stop", dtype=int,
                             display_level=DispLevel.OPERATOR,
                             access=AttrWriteType.READ_WRITE,
                             unit="ms",
                             doc="Channel 10 stop time [ms]")

    channel_enable11 = attribute(label="Channel 11", dtype=bool,
                                 display_level=DispLevel.OPERATOR,
                                 access=AttrWriteType.READ_WRITE,
                                 unit="",
                                 doc="Channel 11 ON/OFF state")

    pulse_start11 = attribute(label="Channel 11 start", dtype=int,
                              display_level=DispLevel.OPERATOR,
                              access=AttrWriteType.READ_WRITE,
                              unit="ms",
                              doc="Channel 5 start time [ms]")

    pulse_stop11 = attribute(label="Channel 11 stop", dtype=int,
                             display_level=DispLevel.OPERATOR,
                             access=AttrWriteType.READ_WRITE,
                             unit="ms",
                             doc="Channel 11 stop time [ms]")

    # endregion

    def init_device(self):
        super().init_device()
        self.pre = f'{self.get_name()} Vtimer'
        msg = f'Initialization'
        self.log_debug(msg)
        self.set_state(DevState.INIT, msg)
        #
        self.last_pulse_time = 0.0
        self.period_value = 0.0
        self.start_mode_value = False
        self.max_time = 0
        self.ready = False
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
            if 'mode' in self.config:
                self.write_mode(self.config.get('mode', 0))
            if 'output' in self.config:
                self.write_output(self.config.get('output', True))
            self.run.set_write_value(self.read_run())
            self.mode.set_write_value(self.read_mode())
            self.output.set_write_value(self.read_output())
            self.period.set_write_value(self.read_period())
            self.duration.set_write_value(self.read_duration())
            self.start_mode.set_write_value(self.read_start_mode())
            self.pulse_stop0.set_write_value(self.read_pulse_stop0())
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

    # endregion

    # region ---------------- custom attributes read --------------
    def read_start_mode(self):
        return self.start_mode_value

    def read_period(self):
        return self.period_value

    def read_run(self):
        value = self.tmr.read_run()
        if value >= 0:
            self.run.set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
            return value
        self.run.set_quality(AttrQuality.ATTR_INVALID)
        msg = 'Run state read error'
        self.set_fault(msg)
        return 0

    def read_mode(self):
        value = self.tmr.read_mode()
        if value >= 0:
            self.mode.set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
            return value
        self.mode.set_quality(AttrQuality.ATTR_INVALID)
        msg = 'Mode read error'
        self.set_fault(msg)
        return 0

    def read_duration(self):
        value = self.tmr.read_duration()
        if value >= 0:
            self.duration.set_quality(AttrQuality.ATTR_VALID)
            self.duration.set_write_value(value)
            self.set_running()
            return value
        self.duration.set_quality(AttrQuality.ATTR_INVALID)
        msg = 'Script duration read error'
        self.set_fault(msg)
        return 0

    def read_last_duration(self):
        value = self.tmr.read_last()
        if value >= 0:
            self.last_duration.set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
            return value
        self.last_duration.set_quality(AttrQuality.ATTR_INVALID)
        msg = 'Run Time read error'
        self.set_fault(msg)
        return 0

    def read_last_time(self):
        return self.last_pulse_time

    def read_output(self):
        value = self.tmr.read_output()
        if value >= 0:
            self.output.set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
            return bool(value)
        self.output.set_quality(AttrQuality.ATTR_INVALID)
        msg = 'Output state read error'
        self.set_fault(msg)
        return False

    def read_pulse(self):
        value = self.tmr.read_status()
        if value >= 0:
            self.pulse.set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
            return bool(value)
        self.pulse.set_quality(AttrQuality.ATTR_INVALID)
        msg = 'Pulse ON|OFF state read error'
        self.set_fault(msg)
        return False

    def read_faults(self):
        value = self.tmr.read_fault()
        if value >= 0:
            self.faults.set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
            return value
        self.faults.set_quality(AttrQuality.ATTR_INVALID)
        msg = 'Faults register read error'
        self.set_fault(msg)
        return False

    def read_channel_n(self, n):
        name = f'channel_enable{n}'
        value = self.tmr.read_channel_enable(n + 1)
        if value >= 0:
            getattr(self, name).set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
            return bool(value)
        getattr(self, name).set_quality(AttrQuality.ATTR_INVALID)
        msg = f'Channel {n} state read error'
        self.set_fault(msg)
        return False

    def read_pulse_start_n(self, n):
        name = f'pulse_start{n}'
        value = self.tmr.read_channel_start(n + 1)
        if value >= 0:
            getattr(self, name).set_quality(AttrQuality.ATTR_VALID)
            return value
        getattr(self, name).set_quality(AttrQuality.ATTR_INVALID)
        msg = f'Channel {n} start time read error'
        self.set_fault(msg)
        return False

    def read_pulse_stop_n(self, n):
        name = f'pulse_stop{n}'
        value = self.tmr.read_channel_stop(n + 1)
        if value >= 0:
            getattr(self, name).set_quality(AttrQuality.ATTR_VALID)
            # self.logger.debug('read %d %s', n, value)
            return value
        getattr(self, name).set_quality(AttrQuality.ATTR_INVALID)
        msg = f'Channel {n} stop time read error'
        self.set_fault(msg)
        return False

    def read_channel_enable0(self):
        return self.read_channel_n(0)

    def read_pulse_start0(self):
        return self.read_pulse_start_n(0)

    def read_pulse_stop0(self):
        return self.read_pulse_stop_n(0)

    def read_channel_enable1(self):
        return self.read_channel_n(1)

    def read_pulse_start1(self):
        return self.read_pulse_start_n(1)

    def read_pulse_stop1(self):
        return self.read_pulse_stop_n(1)

    def read_channel_enable2(self):
        return self.read_channel_n(2)

    def read_pulse_start2(self):
        return self.read_pulse_start_n(2)

    def read_pulse_stop2(self):
        return self.read_pulse_stop_n(2)

    def read_channel_enable3(self):
        return self.read_channel_n(3)

    def read_pulse_start3(self):
        return self.read_pulse_start_n(3)

    def read_pulse_stop3(self):
        return self.read_pulse_stop_n(3)

    def read_channel_enable4(self):
        return self.read_channel_n(4)

    def read_pulse_start4(self):
        return self.read_pulse_start_n(4)

    def read_pulse_stop4(self):
        return self.read_pulse_stop_n(4)

    def read_channel_enable5(self):
        return self.read_channel_n(5)

    def read_pulse_start5(self):
        return self.read_pulse_start_n(5)

    def read_pulse_stop5(self):
        return self.read_pulse_stop_n(5)

    def read_channel_enable6(self):
        return self.read_channel_n(6)

    def read_pulse_start6(self):
        return self.read_pulse_start_n(6)

    def read_pulse_stop6(self):
        return self.read_pulse_stop_n(6)

    def read_channel_enable7(self):
        return self.read_channel_n(7)

    def read_pulse_start7(self):
        return self.read_pulse_start_n(7)

    def read_pulse_stop7(self):
        return self.read_pulse_stop_n(7)

    def read_channel_enable8(self):
        return self.read_channel_n(8)

    def read_pulse_start8(self):
        return self.read_pulse_start_n(8)

    def read_pulse_stop8(self):
        return self.read_pulse_stop_n(8)

    def read_channel_enable9(self):
        return self.read_channel_n(9)

    def read_pulse_start9(self):
        return self.read_pulse_start_n(9)

    def read_pulse_stop9(self):
        return self.read_pulse_stop_n(9)

    def read_channel_enable10(self):
        return self.read_channel_n(10)

    def read_pulse_start10(self):
        return self.read_pulse_start_n(10)

    def read_pulse_stop10(self):
        return self.read_pulse_stop_n(10)

    def read_channel_enable11(self):
        return self.read_channel_n(11)

    def read_pulse_start11(self):
        return self.read_pulse_start_n(11)

    def read_pulse_stop11(self):
        return self.read_pulse_stop_n(11)

    # endregion

    # region ---------------- custom attributes write --------------

    def write_start_mode(self, v):
        self.start_mode_value = v

    def write_period(self, v):
        self.period_value = v

    def write_run(self, value):
        result = self.tmr.write_run(value)
        if result:
            self.run.set_value(value)
            self.run.set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
            return True
        self.run.set_quality(AttrQuality.ATTR_INVALID)
        msg = 'Run state write error'
        self.set_fault(msg)
        self.run.set_write_value(0)
        return False

    def write_mode(self, value):
        result = self.tmr.write_mode(value)
        if result:
            self.mode.set_value(value)
            self.mode.set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
            return True
        self.mode.set_quality(AttrQuality.ATTR_INVALID)
        msg = 'Mode write error'
        self.set_fault(msg)
        self.mode.set_write_value(0)
        return False

    def write_output(self, value):
        result = self.tmr.write_output(int(value))
        if result:
            self.output.set_value(bool(value))
            self.output.set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
            return True
        self.output.set_quality(AttrQuality.ATTR_INVALID)
        msg = 'Output write error'
        self.set_fault(msg)
        self.output.set_write_value(False)
        return False

    def write_duration(self, value):
        result = self.tmr.write_duration(int(value))
        if result:
            self.duration.set_value(int(value))
            self.duration.set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
            return True
        self.duration.set_quality(AttrQuality.ATTR_INVALID)
        msg = 'Total duration write error'
        self.set_fault(msg)
        self.duration.set_write_value(0)
        return False

    def write_channel_n(self, n, value):
        result = self.tmr.write_channel_enable(n + 1, int(value))
        name = f'channel_enable{n}'
        if result:
            getattr(self, name).set_value(bool(value))
            getattr(self, name).set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
            return True
        getattr(self, name).set_quality(AttrQuality.ATTR_INVALID)
        msg = f'Channel {n} state write error'
        self.set_fault(msg)
        getattr(self, name).set_write_value(False)
        return False

    def write_pulse_start_n(self, n, value):
        name = f'pulse_start{n}'
        result = self.tmr.write_channel_start(n + 1, int(value))
        if result:
            getattr(self, name).set_value(int(value))
            getattr(self, name).set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
            return True
        getattr(self, name).set_quality(AttrQuality.ATTR_INVALID)
        msg = f'Channel {n} start time write error'
        self.set_fault(msg)
        getattr(self, name).set_write_value(0)
        return False

    def write_pulse_stop_n(self, n, value):
        name = f'pulse_stop{n}'
        result = self.tmr.write_channel_stop(n + 1, int(value))
        if result:
            getattr(self, name).set_value(int(value))
            getattr(self, name).set_quality(AttrQuality.ATTR_VALID)
            self.set_running()
            return True
        getattr(self, name).set_quality(AttrQuality.ATTR_INVALID)
        msg = f'Channel {n} stop time write error'
        self.set_fault(msg)
        getattr(self, name).set_write_value(0)
        return False

    def write_channel_enable0(self, value):
        return self.write_channel_n(0, value)

    def write_pulse_start0(self, value):
        return self.write_pulse_start_n(0, value)

    def write_pulse_stop0(self, value):
        return self.write_pulse_stop_n(0, value)

    def write_channel_enable1(self, value):
        return self.write_channel_n(1, value)

    def write_pulse_start1(self, value):
        return self.write_pulse_start_n(1, value)

    def write_pulse_stop1(self, value):
        return self.write_pulse_stop_n(1, value)

    def write_channel_enable2(self, value):
        return self.write_channel_n(2, value)

    def write_pulse_start2(self, value):
        return self.write_pulse_start_n(2, value)

    def write_pulse_stop2(self, value):
        return self.write_pulse_stop_n(2, value)

    def write_channel_enable3(self, value):
        return self.write_channel_n(3, value)

    def write_pulse_start3(self, value):
        return self.write_pulse_start_n(3, value)

    def write_pulse_stop3(self, value):
        return self.write_pulse_stop_n(3, value)

    def write_channel_enable4(self, value):
        return self.write_channel_n(4, value)

    def write_pulse_start4(self, value):
        return self.write_pulse_start_n(4, value)

    def write_pulse_stop4(self, value):
        return self.write_pulse_stop_n(4, value)

    def write_channel_enable5(self, value):
        return self.write_channel_n(5, value)

    def write_pulse_start5(self, value):
        return self.write_pulse_start_n(5, value)

    def write_pulse_stop5(self, value):
        return self.write_pulse_stop_n(5, value)

    def write_channel_enable6(self, value):
        return self.write_channel_n(6, value)

    def write_pulse_start6(self, value):
        return self.write_pulse_start_n(6, value)

    def write_pulse_stop6(self, value):
        return self.write_pulse_stop_n(6, value)

    def write_channel_enable7(self, value):
        return self.write_channel_n(7, value)

    def write_pulse_start7(self, value):
        return self.write_pulse_start_n(7, value)

    def write_pulse_stop7(self, value):
        return self.write_pulse_stop_n(7, value)

    def write_channel_enable8(self, value):
        return self.write_channel_n(8, value)

    def write_pulse_start8(self, value):
        return self.write_pulse_start_n(8, value)

    def write_pulse_stop8(self, value):
        return self.write_pulse_stop_n(8, value)

    def write_channel_enable9(self, value):
        return self.write_channel_n(9, value)

    def write_pulse_start9(self, value):
        return self.write_pulse_start_n(9, value)

    def write_pulse_stop9(self, value):
        return self.write_pulse_stop_n(9, value)

    def write_channel_enable10(self, value):
        return self.write_channel_n(10, value)

    def write_pulse_start10(self, value):
        return self.write_pulse_start_n(10, value)

    def write_pulse_stop10(self, value):
        return self.write_pulse_stop_n(10, value)

    def write_channel_enable11(self, value):
        return self.write_channel_n(11, value)

    def write_pulse_start11(self, value):
        return self.write_pulse_start_n(11, value)

    def write_pulse_stop11(self, value):
        return self.write_pulse_stop_n(11, value)

    # endregion

    # region ---------------- custom commands --------------

    @command(dtype_in=None, doc_in='Initiate timer pulse',
             dtype_out=bool, doc_out='True if success')
    def start_pulse(self):
        result = self.tmr.write_run(3)
        if result == 1:
            result = self.tmr.write_run(0)
            result = self.tmr.write_run(1)
            if result == 1:
                self.last_pulse_time = time.time()
                self.log_info('Pulse has been started')
                self.set_running()
                return True
        msg = f'Start pulse execution error {self.tmr.error}'
        self.log_debug(msg)
        self.set_fault(msg)
        return False

    @command(dtype_in=None, doc_in='Initiate timer pulse',
             dtype_out=bool, doc_out='True if success')
    def get_ready(self):
        result = self.tmr.write_run(3)
        if result == 1:
            result = self.tmr.write_run(0)
            result = self.tmr.write_run(2)
            if result == 1:
                # self.last_pulse_time = time.time()
                self.ready = True
                self.log_info('Ready for Pulse')
                self.set_running()
                return True
        msg = f'Pulse enable execution error {self.tmr.error}'
        self.log_debug(msg)
        self.set_fault(msg)
        return False

    @command(dtype_in=int, doc_in='Fast read channel data',
             dtype_out=[int], doc_out='[Enable, Start, Stop]')
    def read_channel(self, n):
        result = self.tmr.read_channel(n + 1)
        if result:
            self.set_running()
            return result
        msg = f'Fast read channel error {self.tmr.error}'
        self.log_debug(msg)
        self.set_fault(msg)
        return False
    # endregion

    @command(dtype_in=None, doc_in='Save current timer state',
             dtype_out=None)
    def save_state(self):
        state = {}
        state['mode'] = self.mode
        state['output'] = self.output
        state['period'] = self.period
        state['duration'] = self.duration
        for i in range(12):
            name = f'channel_enable{i}'
            state[name] = getattr(self, name)
            name = f'pulse_start{i}'
            state[name] = getattr(self, name)
            name = f'pulse_stop{i}'
            state[name] = getattr(self, name)
        js = json.dumps(state)
        self.set_device_property('state', js)
        self.logger.debug('state %s', js)
        self.set_running()


def looping():
    for dn in TangoServerPrototype.devices:
        dev = TangoServerPrototype.devices[dn]
        # if dev.mode == 2:
        #     if not dev.pulse:
        #         dev.get_ready()
        #     else:
        #         dev.ready = False
        # if dev.start_mode_value and dev.period_value > 0.0:
            # if dev.last_pulse_time + dev.period_value < time.time():
                # dev.start_pulse()
                # dev.last_pulse_time = time.time()
                # print('Pulse')
    time.sleep(0.1)


if __name__ == "__main__":
    VtimerServer.run_server(event_loop=looping)
