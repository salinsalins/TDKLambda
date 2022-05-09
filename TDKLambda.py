#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import socket
from collections import deque
from threading import Lock, RLock

import serial
from serial import *

from EmulatedLambda import FakeComPort
from Moxa import MoxaTCPComPort
from config_logger import config_logger

CR = b'\r'
LF = b'\n'


class ComPort:
    _devices = {}
    dev_lock = Lock()

    class UninitializedComPort:
        def __init__(self, port, *args, **kwargs):
            self.port = port

        def read(self, *args, **kwargs):
            return b''

        def write(self, *args, **kwargs):
            return 0

        def reset_input_buffer(self):
            return True

        def close(self):
            return True

        def isOpen(self):
            return False

    def __new__(cls, port, *args, **kwargs):
        with ComPort.dev_lock:
            if port in cls._devices:
                return cls._devices[port]
        return object.__new__(cls)

    def __init__(self, port: str, *args, **kwargs):
        port = port.strip()
        # use existed device
        with ComPort.dev_lock:
            if port in ComPort._devices:
                ComPort._devices[port].logger.debug('Using existent COM port')
                return
        self.lock = RLock()
        with self.lock:
            self.logger = kwargs.get('logger', config_logger())
            self.port = port
            self.args = args
            self.kwargs = kwargs
            # address for RS485 devices
            self.current_addr = -1
            # initialize real device
            if self.port.startswith('FAKE'):
                self._device = FakeComPort(self.port, *self.args, **self.kwargs)
            elif (self.port.upper().startswith('COM')
                  or self.port.startswith('tty')
                  or self.port.startswith('/dev')
                  or self.port.startswith('cua')):
                self.kwargs['timeout'] = 0.0
                self.kwargs['write_timeout'] = 0.0
                self._device = serial.Serial(self.port, *self.args, **self.kwargs)
            else:
                self._device = MoxaTCPComPort(self.port, *self.args, **self.kwargs)
            del self._devices
            with ComPort.dev_lock:
                ComPort._devices[self.port] = self
            self.logger.debug('Port %s has been initialized', self.port)

    def read(self, *args, **kwargs):
        with ComPort._devices[self.port].lock:
            if ComPort._devices[self.port].ready:
                return ComPort._devices[self.port]._device.read(*args, **kwargs)
            else:
                return b''

    def write(self, *args, **kwargs):
        with ComPort._devices[self.port].lock:
            if ComPort._devices[self.port].ready:
                return ComPort._devices[self.port]._device.write(*args, **kwargs)
            else:
                return 0

    def reset_input_buffer(self):
        with ComPort._devices[self.port].lock:
            if ComPort._devices[self.port].ready:
                try:
                        ComPort._devices[self.port]._device.reset_input_buffer()
                        return True
                except:
                    return False
            else:
                return True

    def close(self):
        with ComPort._devices[self.port].lock:
            if ComPort._devices[self.port].ready:
                return ComPort._devices[self.port]._device.close()
            else:
                return True

    @property
    def ready(self):
        return ComPort._devices[self.port]._device.isOpen()


class TDKLambdaException(Exception):
    pass


SUSPEND_TIME = 5.0


class TDKLambda:
    devices = []
    dev_lock = Lock()

    def __init__(self, port, addr, checksum=False, baudrate=9600, **kwargs):
        # parameters
        self.port = port.strip()
        self.addr = addr
        self.kwargs = kwargs
        self.check = checksum
        self.baud = baudrate
        self.logger = None
        self.auto_addr = True
        # create variables
        self.command = b''
        self.response = b''
        self.time = time.time()
        self.suspend_to = time.time()
        self.suspend_flag = False
        # timeouts
        self.read_timeout = 0.5
        self.min_read_time = self.read_timeout
        # default com port, id, and serial number
        self.com = None
        self.id = 'Unknown Device'
        self.sn = ''
        self.max_voltage = float('inf')
        self.max_current = float('inf')
        # configure logger
        self.logger = kwargs.get('logger', config_logger())
        # check device address
        if addr <= 0:
            raise TDKLambdaException('Wrong address')
        # check if port and address are in use
        with TDKLambda.dev_lock:
            for d in TDKLambda.devices:
                if d.port == self.port and d.addr == self.addr and d != self:
                    raise TDKLambdaException('Address is in use')
        # create COM port
        self.com = self.create_com_port()
        # add device to list
        with TDKLambda.dev_lock:
            if self not in TDKLambda.devices:
                TDKLambda.devices.append(self)
        # further initialization (for possible async use)
        self.init()

    def __del__(self):
        with TDKLambda.dev_lock:
            if self in TDKLambda.devices:
                TDKLambda.devices.remove(self)

    def create_com_port(self):
        self.com = ComPort(self.port, baudrate=self.baud)
        if self.com.ready:
            self.logger.debug('Port %s is ready', self.port)
        else:
            self.logger.error('Port %s creation error', self.port)
        return self.com

    def init(self):
        self.unsuspend()
        if not self.com.ready:
            self.suspend()
            return
        # set device address
        response = self._set_addr()
        if not response:
            self.suspend()
            msg = 'TDKLambda: device was not initialized properly'
            self.logger.info(msg)
            return
        # read device serial number
        self.sn = self.read_serial_number()
        # read device type
        self.id = self.read_device_id()
        if self.id.find('LAMBDA') >= 0:
            # determine max current and voltage from model name
            n1 = self.id.find('GEN')
            n2 = self.id.find('-')
            if 0 <= n1 < n2:
                try:
                    self.max_voltage = float(self.id[n1 + 3:n2])
                    self.max_current = float(self.id[n2 + 1:])
                except:
                    pass
        else:
            self.suspend()
            msg = 'TDKLambda: device was not initialized properly'
            self.logger.info(msg)
            return
        msg = 'TDKLambda: %s SN:%s has been initialized' % (self.id, self.sn)
        self.logger.debug(msg)

    def close_com_port(self):
        try:
            self.com.current_addr = -1
            self.com.close()
        except:
            pass
        # suspend all devices with same port
        with TDKLambda.dev_lock:
            for d in TDKLambda.devices:
                if d.port == self.port:
                    d.suspend()

    @staticmethod
    def checksum(cmd):
        s = 0
        for b in cmd:
            s += int(b)
        result = str.encode(hex(s)[-2:].upper())
        return result

    def suspend(self, duration=SUSPEND_TIME):
        self.suspend_to = time.time() + duration
        self.suspend_flag = True
        self.logger.info('Suspended for %5.2f sec', duration)

    def unsuspend(self):
        self.suspend_to = 0.0
        self.suspend_flag = False
        self.logger.debug('Unsuspended')

    # check if suspended and try to reset
    def is_suspended(self):
        if time.time() < self.suspend_to:  # if suspension does not expire
            return True
        # suspension expires
        if self.suspend_flag:  # if it was suspended and expires
            self.suspend_flag = False
            self.reset()
            if self.suspend_flag:  # was suspended during reset()
                return True
            else:
                return False
        else:  # it was not suspended
            return False

    def _read(self, size=1, timeout=None):
        result = b''
        t0 = time.perf_counter()
        while len(result) < size:
            r = self.com.read(1)
            if len(r) > 0:
                result += r
            else:
                if timeout is not None and time.perf_counter() - t0 > timeout:
                    self.logger.info('Reading timeout')
                    raise SerialTimeoutException('Reading timeout')
        return result

    def read(self, size=1):
        try:
            result = self._read(size, self.read_timeout)
            return result
        except SerialTimeoutException:
            self.logger.info('Reading timeout')
            return b''
        except:
            self.logger.info('Unexpected exception %s', sys.exc_info()[0])
            self.logger.debug('Exception', exc_info=True)
            return b''

    def read_until(self, terminator=b'\r', size=None):
        result = b''
        t0 = time.perf_counter()
        while terminator not in result:
            r = self.read(1)
            if len(r) <= 0:
                self.suspend()
                return result
            result += r
            if size is not None and len(result) >= size:
                break
            if time.perf_counter() - t0 > self.read_timeout:
                self.suspend()
                break
        self.logger.debug('%s %s bytes in %4.0f ms', result, len(result), (time.perf_counter() - t0) * 1000.0)
        return result

    def read_response(self):
        result = self.read_until(CR)
        self.response = result
        if CR not in result:
            self.logger.error('Response %s without CR', self.response)
            return False
        # if checksum used
        if not self.check:
            return True
        # checksum calculation
        m = result.find(b'$')
        if m < 0:
            self.logger.error('No expected checksum in response')
            return False
        else:
            cs = self.checksum(result[:m])
            if result[m + 1:] != cs:
                self.logger.error('Incorrect checksum')
                return False
            self.response = result[:m]
            return True

    def check_response(self, expected=b'OK', response=None):
        if response is None:
            response = self.response
        if not response.startswith(expected):
            msg = 'Unexpected response %s (not %s)' % (response, expected)
            self.logger.info(msg)
            return False
        return True

    def write(self, cmd):
        length = 0
        result = False
        t0 = time.perf_counter()
        try:
            # reset input buffer
            if not self.com.reset_input_buffer():
                return False
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

    def _send_command(self, cmd):
        self.command = cmd
        self.response = b''
        t0 = time.perf_counter()
        with self.com.lock:
            # write command
            if not self.write(cmd):
                self.logger.debug('Error during write')
                return False
            # read response (to CR by default)
            result = self.read_response()
        dt = time.perf_counter() - t0
        if result and dt < self.min_read_time:
            self.min_read_time = dt
        self.logger.debug('%s -> %s %s %4.0f ms', cmd, self.response, result, dt*1000.)
        return result

    def _set_addr(self):
        with self.com.lock:
            a0 = self.com.current_addr
            result = self._send_command(b'ADR %d\r' % self.addr)
            if result and self.check_response(b'OK'):
                self.com.current_addr = self.addr
                self.logger.debug('Address %d -> %d' % (a0, self.addr))
                return True
            else:
                self.logger.error('Error set address %d -> %d' % (a0, self.addr))
                self.com.current_addr = -1
                return False

    def read_float(self, cmd):
        try:
            if not self.send_command(cmd):
                return float('Nan')
            v = float(self.response)
        except:
            self.logger.debug('%s is not a float' % self.response)
            v = float('Nan')
        return v

    def read_value(self, cmd, v_type=type(str)):
        try:
            if self.send_command(cmd):
                v = v_type(self.response)
            else:
                v = None
        except:
            self.logger.info('Can not convert %s to %s', self.response, v_type)
            v = None
        return v

    def read_bool(self, cmd):
        if not self.send_command(cmd):
            return None
        response = self.response
        if response.upper() in (b'ON', b'1'):
            return True
        if response.upper() in (b'OFF', b'0'):
            return False
        self.check_response(response=b'Not boolean:' + response)
        return False

    def write_value(self, cmd, value, expect=b'OK'):
        cmd = cmd.upper().strip() + b' ' + str.encode(str(value))[:10] + CR
        if self.send_command(cmd):
            return self.check_response(expect)
        else:
            return False

    def reset(self):
        self.logger.debug('Resetting')
        self.com.close()
        self.com = self.create_com_port()
        self.init()
        return

    # high level general command  ***************************
    def send_command(self, cmd) -> bool:
        if self.is_suspended():
            self.command = cmd
            self.response = b''
            self.logger.debug('Command %s to suspended device ignored', cmd)
            return False
        try:
            # unify command
            cmd = cmd.upper().strip()
            # convert str to bytes
            if isinstance(cmd, str):
                cmd = str.encode(cmd)
            if not cmd.endswith(CR):
                cmd += CR
            # add checksum
            if self.check:
                cs = self.checksum(cmd[:-1])
                cmd = b'%s$%s\r' % (cmd[:-1], cs)
            with self.com.lock:
                if self.auto_addr and self.com.current_addr != self.addr:
                    result = self._set_addr()
                    if not result:
                        self.suspend()
                        self.response = b''
                        return False
                result = self._send_command(cmd)
                if result:
                    return True
                self.logger.warning('Command %s error, repeat' % cmd)
                result = self._send_command(cmd)
                if result:
                    return True
                self.logger.error('Repeated command %s error' % cmd)
                self.suspend()
                self.response = b''
                return False
        except:
            self.logger.error('Unexpected exception %s', sys.exc_info()[0])
            self.logger.debug("", exc_info=True)
            self.suspend()
            self.response = b''
            return False

    # high level read commands ***************************
    def read_device_id(self):
        try:
            if self.send_command(b'IDN?'):
                return self.response[:-1].decode()
            else:
                return 'Unknown Device'
        except:
            return 'Unknown Device'

    def read_serial_number(self):
        try:
            if self.send_command(b'SN?'):
                serial_number = self.response[:-1].decode()
                return serial_number
            else:
                return ''
        except:
            return ''

    def read_output(self):
        if not self.send_command(b'OUT?'):
            return None
        response = self.response.upper()
        if response.startswith((b'ON', b'1')):
            return True
        if response.startswith((b'OFF', b'0')):
            return False
        self.logger.info('Unexpected response %s' % response)
        return None

    def read_current(self):
        return self.read_value(b'MC?', v_type=float)

    def read_programmed_current(self):
        return self.read_value(b'PC?', v_type=float)

    def read_voltage(self):
        return self.read_value(b'MV?', v_type=float)

    def read_programmed_voltage(self):
        return self.read_value(b'PV?', v_type=float)

    def read_all(self):
        if not self.send_command(b'DVC?'):
            return [float('Nan')] * 6
        reply = self.response
        sv = reply.split(b',')
        vals = []
        for s in sv:
            try:
                v = float(s)
            except:
                self.logger.debug('%s is not a float', reply)
                v = float('Nan')
            vals.append(v)
        if len(vals) <= 6:
            vals = [*vals, *[float('Nan')] * 6]
        return vals[:6]

    # high level write commands ***************************
    def write_output(self, value):
        if value:
            t_value = 'ON'
        else:
            t_value = 'OFF'
        return self.write_value(b'OUT', t_value)

    def write_voltage(self, value):
        return self.write_value(b'PV', value)

    def write_current(self, value):
        return self.write_value(b'PC', value)

    # high level check state commands  ***************************
    def initialized(self):
        return self.com.ready and self.id.find('LAMBDA') >= 0

    def alive(self):
        return self.read_device_id().find('LAMBDA') >= 0


if __name__ == "__main__":
    pd1 = TDKLambda("COM6", 7)
    # pd2 = TDKLambda("FAKECOM7", 7)
    for i in range(5):
        t_0 = time.time()
        v1 = pd1.read_float("PC?")
        dt1 = int((time.time() - t_0) * 1000.0)  # ms
        print(pd1.port, pd1.addr, 'PC? ->', v1, '%4d ms ' % dt1, '%5.3f' % pd1.min_read_time)
        t_0 = time.time()
        v1 = pd1.read_float("MV?")
        dt1 = int((time.time() - t_0) * 1000.0)  # ms
        print(pd1.port, pd1.addr, 'MV? ->', v1, '%4d ms ' % dt1, '%5.3f' % pd1.min_read_time)
        t_0 = time.time()
        v1 = pd1.send_command("PV 1.0")
        dt1 = int((time.time() - t_0) * 1000.0)  # ms
        print(pd1.port, pd1.addr, 'PV? ->', v1, '%4d ms ' % dt1, '%5.3f' % pd1.min_read_time)
        t_0 = time.time()
        v1 = pd1.read_float("PV?")
        dt1 = int((time.time() - t_0) * 1000.0)  # ms
        print(pd1.port, pd1.addr, 'PV? ->', v1, '%4d ms ' % dt1, '%5.3f' % pd1.min_read_time)
        t_0 = time.time()
        v1 = pd1.read_all()
        dt1 = int((time.time() - t_0) * 1000.0)  # ms
        print(pd1.port, pd1.addr, 'DVC? ->', v1, '%4d ms ' % dt1, '%5.3f' % pd1.min_read_time)
        t_0 = time.time()
        # v1 = pd2.read_float("PC?")
        # dt1 = int((time.time() - t_0) * 1000.0)  # ms
        # print(pd2.port, pd2.addr, 'PC? ->', v1, '%4d ms ' % dt1, '%5.3f' % pd2.min_read_time)
        # t_0 = time.time()
        # v1 = pd2.read_all()
        # dt1 = int((time.time() - t_0) * 1000.0)  # ms
        # print(pd2.port, pd2.addr, 'DVC? ->', v1, '%4d ms ' % dt1, '%5.3f' % pd2.min_read_time)
        # time.sleep(0.5)
        # pd1.reset()
        # pd2.reset()
