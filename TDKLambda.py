#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import socket
import time
from threading import Lock

import serial
from serial import *
from EmulatedLambda import FakeComPort


class MoxaTCPComPort:
    def __init__(self, host: str, port: int = 4001):
        if ':' in host:
            n = host.find(':')
            self.host = host[:n].strip()
            self.port = int(host[n+1:].strip())
        else:
            self.host = host
            self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))

    def close(self):
        self.socket.close()
        return True

    def write(self, cmd):
        self.socket.send(cmd)

    def read(self, n):
        return self.socket.recv(n)


addressInUseException = Exception('Address is in use')
wrongAddressException = Exception('Wrong address')

CR = b'\r'


class Counter:
    def __init__(self, limit=0, action=None, *args, **kwargs):
        self.value = 0
        self.limit = limit
        self.action = action
        self.args = args
        self.kwargs = kwargs

    def clear(self):
        self.value = 0

    def inc(self):
        self.value += 1
        self.act()

    def check(self):
        return self.value > self.limit

    def act(self, action=None):
        if action is None:
            action = self.action
        if self.check():
            self.value = 0
            if action is not None:
                return action(*self.args, **self.kwargs)
            else:
                return True
        else:
            return False

    def __iadd__(self, other):
        self.value += other
        self.act()
        return self


class TDKLambda:
    LOG_LEVEL = logging.DEBUG
    EMULATE = False
    max_timeout = 0.8  # sec
    min_timeout = 0.15  # sec
    RETRIES = 3
    SUSPEND = 2.0
    sleep_small = 0.015
    devices = []
    ports = []

    def __init__(self, port: str, addr=6, checksum=False, baud_rate=9600, logger=None):
        # check device address
        if addr <= 0:
            raise wrongAddressException
        # input parameters
        self.port = port.upper().strip()
        self.addr = addr
        self.check = checksum
        self.baud = baud_rate
        self.logger = logger
        self.auto_addr = True
        # create variables
        self.last_command = b''
        self.last_response = b''
        self.error_count = Counter(3, self.suspend)
        self.time = time.time()
        self.suspend_to = time.time()
        self.suspend_flag = False
        self.retries = 0
        # timeouts
        self.read_timeout = self.min_timeout
        self.read_timeout_count = Counter(3, self.suspend)
        self.timeout_clear_input = 0.5
        # sleep timings
        self.sleep_after_write = 0.02
        self.sleep_clear_input = 0.0
        # default com port, id, and serial number
        self.com = None
        self._current_addr = -1
        self.id = 'Unknown Device'
        self.sn = 'Not initialized'
        self.max_voltage = float('inf')
        self.max_current = float('inf')
        # configure logger
        if self.logger is None:
            self.logger = logging.getLogger(str(self))
            self.logger.propagate = False
            self.logger.setLevel(self.LOG_LEVEL)
            f_str = '%(asctime)s,%(msecs)3d %(levelname)-7s [%(process)d:%(thread)d] %(filename)s ' \
                    '%(funcName)s(%(lineno)s) ' + '%s:%d ' % (self.port, self.addr) + '%(message)s'
            log_formatter = logging.Formatter(f_str, datefmt='%H:%M:%S')
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(log_formatter)
            if not self.logger.hasHandlers():
                self.logger.addHandler(console_handler)
        # check if port and address are in use
        for d in TDKLambda.devices:
            if d.port == self.port and d.addr == self.addr and d != self:
                raise addressInUseException
        # create COM port
        self.create_com_port()
        if self.com is None:
            self.suspend()
            msg = 'Uninitialized TDKLambda device has been added to list'
            self.logger.info(msg)
            TDKLambda.devices.append(self)
            return
        self.init()

    def __del__(self):
        if self in TDKLambda.devices:
            TDKLambda.devices.remove(self)

    def init(self):
        if self.com is None:
            return
        # set device address
        response = self.set_addr()
        if not response:
            msg = 'Uninitialized TDKLambda device has been added to list'
            self.logger.info(msg)
            TDKLambda.devices.append(self)
            return
        # read device type
        if self._send_command(b'IDN?'):
            self.id = self.last_response.decode()
            # determine max current and voltage from model name
            n1 = self.id.find('GEN')
            n2 = self.id.find('-')
            if n1 >= 0 and n2 >= 0:
                try:
                    self.max_voltage = float(self.id[n1+3:n2])
                    self.max_current = float(self.id[n2+1:])
                except:
                    pass
        # read device serial number
        if self._send_command(b'SN?'):
            self.serial_number = self.last_response.decode()
        # add device to list
        TDKLambda.devices.append(self)
        msg = 'TDKLambda: %s has been created' % self.id
        self.logger.info(msg)

    def close_com_port(self):
        try:
            self.com.close()
        except:
            pass
        self.com = None
        self.suspend()
        for d in TDKLambda.devices:
            if d.port == self.port:
                d.com = None
                d.suspend()

    def create_com_port(self):
        for d in TDKLambda.devices:
            # if com port already exists
            if d.port == self.port and d.com is not None:
                self.com = d.com
                return self.com
        try:
            if self.EMULATE:
                self.com = FakeComPort(self.port)
            else:
                if self.port.upper().startswith('COM'):
                    self.com = serial.Serial(self.port, baudrate=self.baud, timeout=0.0, write_timeout=0.0)
                else:
                    self.com = MoxaTCPComPort(self.port)
            self.com._current_addr = -1
            self.unsuspend()
            self.logger.debug('%s created' % self.port)
        except:
            self.logger.error('%s creation error' % self.port)
            self.logger.debug('', exc_info=True)
            self.com = None
        # update com for other devices with the same port
        for d in TDKLambda.devices:
            if d.port == self.port:
                d.com = self.com
        return self.com

    @staticmethod
    def checksum(cmd):
        s = 0
        for b in cmd:
            s += int(b)
        result = str.encode(hex(s)[-2:].upper())
        return result

    def suspend(self, duration=9.0):
        self.suspend_to = time.time() + duration
        self.suspend_flag = True
        msg = 'Suspended for %5.2f sec' % duration
        self.logger.info(msg)

    def unsuspend(self):
        self.suspend_to = 0.0
        self.suspend_flag = False
        self.logger.debug('Unsuspended')

    def is_suspended(self):
        if time.time() < self.suspend_to:   # if suspension does not expire
            self.logger.debug(' - Suspended')
            return True
        else:                               # suspension expires
            if self.suspend_flag:           # if it was suspended and expires
                self.reset()
                if self.com is None:        # if initialization was not successful
                    # suspend again
                    self.suspend(True)
                    return True
                else:                       # initialization was successful
                    self.unsuspend()
                    return False
            else:                           # it was not suspended
                return False

    def read(self, size=1, timeout=None):
        result = b''
        if self.is_suspended():
            return result
        if timeout is None:
            timeout = self.read_timeout
        to = Timeout(timeout)
        t0 = time.time()
        while len(result) < size:
            try:
                r = self.com.read(1)
                if len(r) > 0:
                    result += r
                    to.restart(timeout)
                    self.read_timeout_count.clear()
                    dt = time.time() - t0
                    self.read_timeout = max(2.0 * dt, self.min_timeout)
                else:
                    if to.expired():
                        raise SerialTimeoutException('Read timeout')
            except SerialTimeoutException:
                self.read_timeout = min(1.5 * self.read_timeout, self.max_timeout)
                timeout = self.read_timeout
                to.restart(timeout)
                self.logger.info('Reading timeout, corrected to %5.2f s' % self.read_timeout)
                self.read_timeout_count.inc()
            except:
                self.logger.info('Unexpected exception', exc_info=True)
                self.suspend()
            if self.is_suspended():
                raise SerialTimeoutException('Read timeout')
        #self.logger.debug('%s in %4.0f ms' % (result, (time.time() - t0) * 1000.0))
        return result

    def read_until(self, terminator=b'\r', size=None, timeout=None):
        result = b''
        if self.is_suspended():
            return result
        t0 = time.time()
        if timeout is None:
            timeout = self.read_timeout
        to = Timeout(timeout)
        try:
            while terminator not in result:
                r = self.read(1)
                if len(r) > 0:
                    result += r
                    to.restart(timeout)
                    if size is not None and len(result) >= size:
                        break
                else:
                    if to.expired():
                        raise SerialTimeoutException('Read_until timeout')
        except SerialTimeoutException:
            self.logger.info('Reading_until %s timeout' % terminator)
            # self.read_timeout = min(1.5 * self.read_timeout, self.max_timeout)
            # self.logger.info('Reading timeout, increased to %5.2f s' % self.read_timeout)
            # self.read_timeout_count.inc()
        except:
            self.logger.info('Unexpected exception', exc_info=True)
            self.suspend()
        else:
            self.read_timeout_count.clear()
            self.read_timeout = max(2.0 * (time.time() - t0), self.min_timeout)
        self.logger.debug('%s %s bytes in %4.0f ms' % (result, len(result)+1, (time.time() - t0) * 1000.0))
        return result

    def read_response(self):
        if self.is_suspended():
            self.last_response = b''
            return False
        result = self.read_until(terminator=CR)
        self.last_response = result[:-1]
        if CR not in result:
            self.logger.error('Response %s without CR' % self.last_response)
            self.error_count.inc()
            return False
        if self.check:
            m = result.find(b'$')
            if m < 0:
                self.logger.error('No expected checksum in response')
                self.error_count.inc()
                return False
            else:
                cs = self.checksum(result[:m])
                if result[m+1:] != cs:
                    self.logger.error('Incorrect checksum')
                    self.error_count.inc()
                    return False
                self.error_count.clear()
                self.last_response = result[:m]
                return True
        self.error_count.clear()
        return True

    def check_response(self, expected=b'OK', response=None):
        if response is None:
            response = self.last_response
        if not response.startswith(expected):
            msg = 'Unexpected response %s (not %s)' % (response, expected)
            self.logger.info(msg)
            return False
        return True

    def clear_input_buffer(self):
        self.com.reset_input_buffer()

    def write(self, cmd):
        if self.is_suspended():
            return False
        t0 = time.time()
        try:
            # clear input buffer
            self.clear_input_buffer()
            # write command
            #self.logger.debug('clear_input_buffer %4.0f ms' % ((time.time() - t0) * 1000.0))
            length = self.com.write(cmd)
            #time.sleep(self.sleep_after_write)
            if len(cmd) == length:
                result = True
            else:
                result = False
            self.logger.debug('%s %s bytes in %4.0f ms %s' % (cmd, length, (time.time() - t0) * 1000.0, result))
            return result
        except SerialTimeoutException:
            self.logger.error('Writing timeout')
            self.suspend()
            return False
        except:
            self.logger.error('Unexpected exception')
            self.logger.debug("", exc_info=True)
            self.logger.debug('%s %4.0f ms' % (cmd, (time.time() - t0) * 1000.0))
            self.suspend()
            return False

    def _send_command(self, cmd):
        self.last_command = cmd
        self.last_response = b''
        if self.is_suspended():
            return False
        if not cmd.endswith(b'\r'):
            cmd += b'\r'
        t0 = time.time()
        # write command
        if not self.write(cmd):
            return False
        # read response (to CR by default)
        result = self.read_response()
        self.logger.debug('%s -> %s %s %4.0f ms' % (cmd, self.last_response, result, (time.time()-t0)*1000.0))
        return result

    def send_command(self, cmd):
        if self.is_suspended():
            self.last_command = cmd
            self.last_response = b''
            return False
        try:
            # unify command
            cmd = cmd.upper().strip()
            # convert str to bytes
            if isinstance(cmd, str):
                cmd = str.encode(cmd)
            # add checksum
            if self.check:
                cs = self.checksum(cmd[:-1])
                cmd = b'%s$%s\r' % (cmd[:-1], cs)
            if self.auto_addr and self.com._current_addr != self.addr:
                result = self.set_addr()
                if not result:
                    self.suspend()
                    self.last_response = b''
                    return False
            result = self._send_command(cmd)
            if result:
                return True
            self.logger.warning('Repeat command %s' % cmd)
            result = self._send_command(cmd)
            if result:
                return True
            self.logger.error('Repeated command %s error' % cmd)
            self.suspend()
            self.last_response = b''
            return False
        except:
            self.logger.error('Unexpected exception')
            self.logger.debug("", exc_info=True)
            self.suspend()
            self.last_response = b''
            return b''

    def set_addr(self):
        if hasattr(self.com, '_current_addr'):
            a0 = self.com._current_addr
        else:
            a0 = -1
        result = self._send_command(b'ADR %d' % self.addr)
        if result and self.check_response(b'OK'):
            self.com._current_addr = self.addr
            self.logger.debug('Address %d -> %d' % (a0, self.addr))
            return True
        else:
            self.logger.error('Error set address %d -> %d' % (a0, self.addr))
            if self.com is not None:
                self.com._current_addr = -1
            return False

    def read_float(self, cmd):
        try:
            if not self.send_command(cmd):
                return float('Nan')
            v = float(self.last_response)
        except:
            self.logger.debug('%s is not a float' % self.last_response)
            v = float('Nan')
        return v

    def read_all(self):
        if not self.send_command(b'DVC?'):
            return [float('Nan')] * 6
        reply = self.last_response
        sv = reply.split(b',')
        vals = []
        for s in sv:
            try:
                v = float(s)
            except:
                self.logger.debug('%s is not a float' % reply)
                v = float('Nan')
            vals.append(v)
        if len(vals) <= 6:
            return vals
        else:
            return vals[:6]

    def read_value(self, cmd, v_type=type(str)):
        try:
            if self.send_command(cmd):
                v = v_type(self.last_response)
            else:
                v = None
        except:
            self.logger.info('Can not convert %s to %s' % (self.last_response, v_type))
            v = None
        return v

    def read_bool(self, cmd):
        if not self.send_command(cmd):
            return None
        response = self.last_response
        if response.upper() in (b'ON', b'1'):
            return True
        if response.upper() in (b'OFF', b'0'):
            return False
        self.check_response(response=b'Not boolean:' + response)
        return False

    def write_value(self, cmd: bytes, value, expect=b'OK'):
        cmd = cmd.upper().strip() + b' ' + str.encode(str(value))[:10] + b'\r'
        if self.send_command(cmd):
            return self.check_response(expect)
        else:
            return False

    def read_output(self):
        if not self.send_command(b'OUT?'):
            return None
        response = self.last_response.upper()
        if response.startswith((b'ON', b'1')):
            return True
        if response.startswith((b'OFF', b'0')):
            return False
        self.logger.info('Unexpected response %s' % response)
        return None

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

    def read_current(self):
        return self.read_value(b'MC?', v_type=float)

    def read_programmed_current(self):
        return self.read_value(b'PC?', v_type=float)

    def read_voltage(self):
        return self.read_value(b'MV?', v_type=float)

    def read_programmed_voltage(self):
        return self.read_value(b'PV?', v_type=float)

    def reset(self):
        self.__del__()
        self.__init__(self.port, self.addr, self.check, self.baud, self.logger)


if __name__ == "__main__":
    pd1 = TDKLambda("COM6", 6)
    ###pd1.init()
    pd2 = TDKLambda("COM6", 7)
    ####pd2.init()
    for i in range(5):
        t_0 = time.time()
        v1 = pd1.read_float("PC?")
        dt1 = int((time.time() - t_0) * 1000.0)    # ms
        print('1: ', '%4d ms ' % dt1,'PC?=', v1, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
        t_0 = time.time()
        v1 = pd1.read_float("MV?")
        dt1 = int((time.time() - t_0) * 1000.0)    # ms
        print('1: ', '%4d ms ' % dt1,'MV?=', v1, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
        t_0 = time.time()
        v1 = pd1.send_command("PV 1.0")
        dt1 = int((time.time() - t_0) * 1000.0)    # ms
        print('1: ', '%4d ms ' % dt1,'PV 1.0', v1, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
        t_0 = time.time()
        v1 = pd1.read_float("PV?")
        dt1 = int((time.time() - t_0) * 1000.0)    # ms
        print('1: ', '%4d ms ' % dt1,'PV?=', v1, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
        t_0 = time.time()
        v3 = pd1.read_all()
        dt1 = int((time.time() - t_0) * 1000.0)    # ms
        print('1: ', '%4d ms ' % dt1,'DVC?=', v3, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
        t_0 = time.time()
        v2 = pd2.read_float("PC?")
        dt2 = int((time.time() - t_0) * 1000.0)    # ms
        print('2: ', '%4d ms ' % dt2,'PC?=', v2, 'to=', '%5.3f' % pd2.read_timeout, pd2.port, pd2.addr)
        t_0 = time.time()
        v4 = pd2.read_all()
        dt1 = int((time.time() - t_0) * 1000.0)    # ms
        print('2: ', '%4d ms ' % dt1,'DVC?=', v4, 'to=', '%5.3f' % pd2.read_timeout, pd2.port, pd2.addr)
        time.sleep(0.1)
        pd1.reset()
        pd2.reset()
