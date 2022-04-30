#!/usr/bin/env python
# -*- coding: utf-8 -*-

import serial
from serial import *

from TDKLambda import MoxaTCPComPort

sys.path.append('../TangoUtils')
from config_logger import config_logger
from log_exception import log_exception

LF = b'\n'
DEVICE_NAME = 'IT6900'
DEVICE_FAMILY = 'IT6900 family Power Supply'
SUSPEND_TIME = 3.0
READ_TIMEOUT = 0.5
ID_OK = 'ITECH Ltd., IT69'


class IT6900Exception(Exception):
    pass


class IT6900:

    def __init__(self, port: str, *args, **kwargs):
        # configure logger
        if 'logger' not in kwargs or kwargs['logger'] is None:
            self.logger = config_logger()
        else:
            self.logger = kwargs.pop('logger')
        # parameters
        self.read_count = 0
        self.avg_read_time = 0.0
        self.max_read_time = 0.0
        self.min_read_time = READ_TIMEOUT
        self.port = port.strip()
        self.args = args
        self.kwargs = kwargs
        # create variables
        self.command = b''
        self.response = b''
        # timeouts
        self.read_timeout = READ_TIMEOUT
        # default com port, id, and serial number
        self.com = None
        self.id = 'Unknown Device'
        self.type = 'Unknown Device'
        self.sn = 0
        self.max_voltage = float('inf')
        self.max_current = float('inf')
        self.ready = False
        # create and open COM port
        self.com = self.create_com_port()
        if self.com is None:
            self.logger.error('Can not open serial port')
            self.ready = False
            return
        # further initialization (for possible async use)
        self.init()

    def create_com_port(self):
        try:
            if (self.port.upper().startswith('COM')
                    or self.port.startswith('tty')
                    or self.port.startswith('/dev')
                    or self.port.startswith('cua')):
                if 'timeout' not in self.kwargs:
                    self.kwargs['timeout'] = READ_TIMEOUT
                # COM port will be openet automatically after creation
                self.com = serial.Serial(self.port, **self.kwargs)
            else:
                self.com = MoxaTCPComPort(self.port, *self.args, **self.kwargs)
            if self.com.isOpen():
                self.logger.debug('Port %s is ready', self.port)
            else:
                self.logger.error('Port %s creation error', self.port)
        except:
            self.logger.error('Port %s creation error', self.port)
            self.com = None
        return self.com

    def init(self):
        # device id, sn and type
        self.id = self.read_device_id()
        if not self.id.startswith(ID_OK):
            self.ready = False
            self.logger.error('%s initialization error', DEVICE_NAME)
            return
        self.ready = True
        self.sn = self.read_serial_number()
        self.type = self.read_device_type()
        # switch to remote mode
        self.switch_remote()
        self.clear_status()
        # read maximal voltage and current
        if self.send_command('VOLT? MAX'):
            self.max_voltage = float(self.response[:-1])
        if self.send_command('CURR? MAX'):
            self.max_current = float(self.response[:-1])
        msg = 'Device has been initialized %s' % self.id
        self.logger.debug(msg)

    def send_command(self, cmd, check_response=True):
        try:
            # unify command
            cmd = cmd.upper().strip()
            # convert str to bytes
            if isinstance(cmd, str):
                cmd = str.encode(cmd)
            if not cmd.endswith(LF):
                cmd += LF
            self.response = b''
            t0 = time.time()
            # write command
            if not self.write(cmd):
                return False
            if not check_response:
                return True
            # read response (to LF by default)
            result = self.read_response()
            # reding time stats
            dt = time.time() - t0
            if result and dt < self.min_read_time:
                self.min_read_time = dt
            if result and dt > self.max_read_time:
                self.max_read_time = dt
            self.read_count += 1
            self.avg_read_time = (self.avg_read_time * (self.read_count - 1) + dt) / self.read_count
            self.logger.debug('%s -> %s %s %4.0f ms', cmd, self.response, result, dt * 1000)
            return result
        except:
            log_exception(self, 'Unexpected exception')
            self.response = b''
            return False

    def read(self, size=1, timeout=None):
        result = b''
        t0 = time.perf_counter()
        while len(result) < size:
            r = self.com.read(1)
            if len(r) > 0:
                result += r
            else:
                if timeout is not None and time.perf_counter() - t0 > timeout:
                    raise SerialTimeoutException('Reading timeout')
        return result

    def read_until(self, terminator=LF, size=None):
        result = b''
        t0 = time.perf_counter()
        while terminator not in result:
            try:
                r = self.read(1, timeout=READ_TIMEOUT)
                if len(r) <= 0:
                    break
                result += r
                if size is not None and len(result) >= size:
                    break
                if time.perf_counter() - t0 > self.read_timeout:
                    break
            except:
                log_exception(self)
                return result
        return result

    def read_response(self):
        result = self.read_until(LF)
        self.response = result
        if LF not in result:
            self.logger.error('Response without LF %s ', self.response)
            return False
        return True

    def write(self, cmd):
        length = 0
        result = False
        t0 = time.perf_counter()
        try:
            # reset input buffer
            self.com.reset_input_buffer()
            # write command
            length = self.com.write(cmd)
            if len(cmd) == length:
                result = True
            else:
                result = False
            dt = (time.perf_counter() - t0) * 1000.0
            self.logger.debug('%s %s bytes in %4.0f ms %s', cmd, length, dt, result)
            return result
        except SerialTimeoutException:
            self.logger.error('Writing timeout')
            dt = (time.perf_counter() - t0) * 1000.0
            self.logger.debug('%s %s bytes in %4.0f ms %s', cmd, length, dt, result)
            return False
        except:
            self.logger.error('Unexpected exception %s', sys.exc_info()[0])
            dt = (time.perf_counter() - t0) * 1000.0
            self.logger.debug('%s %s bytes in %4.0f ms %s', cmd, length, dt, result)
            self.logger.debug("", exc_info=True)
            return False

    def read_value(self, cmd, v_type=float):
        try:
            if self.send_command(cmd):
                v = v_type(self.response)
            else:
                v = None
        except:
            v = None
            self.logger.debug('Can not convert %s to %s', self.response, v_type)
        return v

    def write_value(self, cmd, value):
        if isinstance(cmd, str):
            cmd = cmd.encode()
        cmd1 = cmd.upper().strip()
        cmd2 = cmd1 + b' ' + str(value).encode() + b';' + cmd1 + b'?'
        v = self.read_value(cmd2, type(value))
        return value == v

    def read_output(self):
        if not self.send_command(b'OUTP?'):
            return None
        response = self.response.upper()
        if response.startswith((b'ON', b'1')):
            return True
        if response.startswith((b'OFF', b'0')):
            return False
        self.logger.info('Unexpected response %s' % response)
        return None

    def write_output(self, value: bool):
        if value:
            t_value = 'ON'
        else:
            t_value = 'OFF'
        self.write_value(b'OUTP', t_value)
        return bool(self.response[:-1]) == value

    def write_voltage(self, value: float):
        return self.write_value(b'VOLT', value)

    def write_current(self, value: float):
        return self.write_value(b'CURR', value)

    def read_current(self):
        return self.read_value(b'MEAS:CURR?')

    def read_programmed_current(self):
        return self.read_value(b'CURR?')

    def read_voltage(self):
        return self.read_value(b'MEAS:VOLT?')

    def read_programmed_voltage(self):
        return self.read_value(b'VOLT?')

    def read_device_id(self):
        try:
            if self.send_command(b'*IDN?'):
                return self.response[:-1].decode()
            else:
                return 'Unknown Device'
        except:
            return 'Unknown Device'

    def read_serial_number(self):
        try:
            if self.send_command(b'*IDN?'):
                serial_number = int(self.response[:-1].decode().split(',')[2])
                return serial_number
            else:
                return "-1"
        except:
            return "-1"

    def read_device_type(self):
        try:
            if self.send_command(b'*IDN?'):
                return self.response[:-1].decode().split(',')[1]
            else:
                return "Unknown Device"
        except:
            return "Unknown Device"

    def close_com_port(self):
        self.ready = False
        try:
            self.com.close()
        except:
            pass

    def switch_remote(self):
        return self.send_command(b'SYST:REM', False)

    def read_errors(self):
        if self.send_command(b'SYST:ERR?'):
            return self.response[:-1].decode()
        else:
            return None

    def switch_local(self):
        return self.send_command(b'SYST:LOC', False)

    def clear_status(self):
        return self.send_command(b'*CLS', False)

    def reconnect(self, port=None, *args, **kwargs):
        if port is not None:
            self.port = port.strip()
        if len(args) > 0:
            self.args = args
        if len(kwargs) > 0:
            self.kwargs = kwargs
        self.ready = False
        self.close_com_port()
        self.com = self.create_com_port()
        self.init()

    def initialized(self):
        return self.ready


if __name__ == "__main__":
    pd1 = IT6900("COM3")
    for i in range(5):
        t_0 = time.time()
        v1 = pd1.send_command("*IDN?")
        dt1 = int((time.time() - t_0) * 1000.0)  # ms
        print(pd1.port, 'PC? ->', v1, '%4d ms ' % dt1, '%5.3f' % pd1.min_read_time)
