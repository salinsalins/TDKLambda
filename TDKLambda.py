#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import socket
import time
from threading import Lock, Thread
from collections import deque
import asyncio

import serial
from serial import *

from EmulatedLambda import FakeComPort
from Counter import Counter
from TDKLambdaExceptions import *
from Async.AsyncSerial import Timeout

CR = b'\r'


class Command:
    def __init__(self, cmd, device, callback=None):
        self.command = cmd
        self.device = device
        self.time_start = time.time()
        self.time_end = 0.0
        self.callback = callback
        self.state = 0          # 0 - created; 1 - queued; 2 - executing; 3 - completed
        self.task = None
        self.result = b''

    @property
    def completed(self):
        return self.state >= 3

    @property
    def queued(self):
        return self.state == 1

    @property
    def executing(self):
        return self.state == 2


class MoxaTCPComPort:
    def __init__(self, host, port=4001, **kwargs):
        if ':' in host:
            n = host.find(':')
            self.host = host[:n].strip()
            try:
                self.port = int(host[n + 1:].strip())
            except:
                self.port = port
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

    def isOpen(self):
        return True

    def reset_input_buffer(self):
        return True


class ComPort:
    _devices = {}

    class UninitializedDevice:
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
        if port in cls._devices:
            return cls._devices[port]
        return object.__new__(cls)

    def __init__(self, port, *args, **kwargs):
        # use existed device
        if port in ComPort._devices:
            self.logger.debug('Using existent port')
            return
        self.port = port
        self.args = args
        self.kwargs = kwargs
        self.current_addr = -1
        self.lock = Lock()
        self._ex = None
        self.time = 0.0

        logger = logging.getLogger(str(self))
        logger.propagate = False
        level = logging.DEBUG
        logger.setLevel(level)
        f_str = '%(asctime)s,%(msecs)3d %(levelname)-7s [%(process)d:%(thread)d] %(filename)s ' \
                '%(funcName)s(%(lineno)s) ' + '%s' % self.port + ' - %(message)s'
        log_formatter = logging.Formatter(f_str, datefmt='%H:%M:%S')
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_formatter)
        if not logger.hasHandlers():
            logger.addHandler(console_handler)
        self.logger = logger
        # default device
        self._device = ComPort.UninitializedDevice(port)
        self.init()

    def init(self):
        if self.lock.locked():
            self.logger.warning('Init on locked port')
            self.lock.release()
        # initialize real device
        if self.port.startswith('FAKE'):
            self._device = FakeComPort(self.port, *self.args, **self.kwargs)
            result = True
        else:
            if time.time() - self.time < 3.0:
                self.logger.warning('Frequent initialization declined')
                return False
            try:
                self._device = serial.Serial(self.port, *self.args, timeout=0.0, write_timeout=0.0, **self.kwargs)
                result = True
            except Exception as ex:
                self._ex = [ex]
                result = False
            if not (self.port.upper().startswith('COM')
                    or self.port.startswith('tty')
                    or self.port.startswith('/dev')
                    or self.port.startswith('cua')):
                try:
                    self._device = MoxaTCPComPort(self.port, *self.args, **self.kwargs)
                    result = True
                except Exception as ex:
                    self._ex.append(ex)
                    result = False
        ComPort._devices[self.port] = self
        self.time = time.time()
        self.logger.debug('Port %s has been initialized', self.port)
        return result

    def read(self, *args, **kwargs):
        if self.ready:
            return self._device.read(*args, **kwargs)
        else:
            return b''

    def write(self, *args, **kwargs):
        if self.ready:
            return self._device.write(*args, **kwargs)
        else:
            return 0

    def reset_input_buffer(self):
        if self.ready:
            try:
                self._device.reset_input_buffer()
                return True
            except:
                return False
        else:
            return True

    def close(self):
        if self.ready:
            return self._device.close()
        else:
            return True

    @property
    def ready(self):
        return self._device.isOpen()


def ms(t0):
    return (time.perf_counter() - t0) * 1000.0


class TDKLambda:
    LOG_LEVEL = logging.DEBUG
    max_timeout = 0.8  # sec
    min_timeout = 0.15  # sec
    SUSPEND_TIME = 5.0
    devices = []
    loop = None
    thread = None
    commands = deque()
    completed_commands = deque()

    def __init__(self, port, addr, checksum=False, baud_rate=9600, logger=None, **kwargs):
        # check device address
        if addr <= 0:
            raise wrongAddressException
        # parameters
        self.port = port.strip()
        self.addr = addr
        self.check = checksum
        self.baud = baud_rate
        self.logger = logger
        self.auto_addr = True
        # create variables
        self.command = b''
        self.response = b''
        self.error_count = Counter(3, self.suspend)
        self.time = time.time()
        self.suspend_to = time.time()
        self.suspend_flag = False
        # timeouts
        self.read_timeout = self.min_timeout
        # default com port, id, and serial number
        self.com = None
        self.id = 'Unknown Device'
        self.sn = 0
        self.max_voltage = float('inf')
        self.max_current = float('inf')
        # configure logger
        self.configure_logger()
        # check if port and address are in use
        for d in TDKLambda.devices:
            if d.port == self.port and d.addr == self.addr and d != self:
                raise addressInUseException
        # create COM port
        self.com = self.create_com_port()
        # add device to list
        self.add_to_list()
        # further initialization (for possible async use)
        self.init()

    def __del__(self):
        if self in TDKLambda.devices:
            TDKLambda.devices.remove(self)

    @staticmethod
    async def dispatcher():
        while True:
            for cmd in TDKLambda.commands:
                if cmd.queued():
                    # check if it is repeated command
                    flag = False
                    cmd1 = cmd.command[:4]
                    for cmd2 in TDKLambda.commands:
                        if cmd2.state != 2:
                            continue
                        if cmd2.command[:4] == cmd1:
                            flag = True
                            break
                    if flag:
                        TDKLambda.commands.remove(cmd)
                    else:
                        cmd.task = asyncio.create_task(cmd.device._send_command(cmd.command))
                        cmd.state = 2
                elif cmd.task.done():
                    cmd.state = 3
                    cmd.exception = cmd.task.exception()
                    if cmd.exception is None:
                        cmd.result = cmd.task.result()
                    else:
                        cmd.result = b''
                    TDKLambda.commands.remove(cmd)
                    TDKLambda.completed_commands.append(cmd)
            await asyncio.sleep(0)

    @staticmethod
    def start_loop(self):
        if TDKLambda.loop is not None:
            return
        TDKLambda.loop = asyncio.get_running_loop()
        asyncio.run(TDKLambda.dispatcher())

    @staticmethod
    def init_thread(self):
        if TDKLambda.thread is not None:
            return
        TDKLambda.thread = Thread(target=TDKLambda.start_loop, args=())
        TDKLambda.thread.start()

    def configure_logger(self, level=None):
        logger = logging.getLogger(str(self))
        logger.propagate = False
        if level is None:
            level = self.LOG_LEVEL
        logger.setLevel(level)
        f_str = '%(asctime)s,%(msecs)3d %(levelname)-7s [%(process)d:%(thread)d] %(filename)s ' \
                '%(funcName)s(%(lineno)s) ' + '%s::%d ' % (self.port, self.addr) + ' - %(message)s'
        log_formatter = logging.Formatter(f_str, datefmt='%H:%M:%S')
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_formatter)
        if not logger.hasHandlers():
            logger.addHandler(console_handler)
        if self.logger is None:
            self.logger = logger
        return logger

    def create_com_port(self):
        self.com = ComPort(self.port, baudrate=self.baud)
        if self.com.ready:
            self.logger.debug('Port %s has been created', self.port)
        else:
            self.logger.error('Port %s creation error', self.port)
        return self.com

    def init(self):
        self.unsuspend()
        if not self.com.ready:
            self.suspend()
            return
        # set device address
        response = self.set_addr()
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

    def add_to_list(self):
        if self not in TDKLambda.devices:
            TDKLambda.devices.append(self)

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
                try:
                    serial_number = int(self.response[:-1].decode())
                except:
                    serial_number = -1
                return serial_number
            else:
                return -1
        except:
            return -1

    def close_com_port(self):
        try:
            self.com.current_addr = -1
            self.com.close()
        except:
            pass
        # suspend all devices with same port
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
        else:  # suspension expires
            if self.suspend_flag:  # if it was suspended and expires
                self.suspend_flag = False
                self.reset()
                if self.suspend_flag:  # was suspended during resset()
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
                if time.perf_counter() - t0 > self.read_timeout:
                    self.logger.info('Reading timeout')
                    raise SerialTimeoutException('Reading timeout')
        return result

    def read(self, size=1):
        result = b''
        t0 = time.perf_counter()
        try:
            result = self._read(size, self.read_timeout)
            dt = time.perf_counter() - t0
            self.read_timeout = min(max(2.0 * dt, self.min_timeout), self.max_timeout)
        except SerialTimeoutException:
            self.read_timeout = min(1.5 * self.read_timeout, self.max_timeout)
            self.logger.debug('Timeout increased to %5.2f s', self.read_timeout)
        except:
            self.read_timeout = min(1.5 * self.read_timeout, self.max_timeout)
            self.logger.info('Unexpected exception %s', sys.exc_info()[0])
            self.logger.debug('Exception', exc_info=True)
        return result

    def read_until(self, terminator=b'\r', size=None):
        result = b''
        t0 = time.perf_counter()
        while terminator not in result and not self.is_suspended():
            r = self.read(1)
            if len(r) <= 0:
                self.suspend()
                return result
            result += r
            if size is not None and len(result) >= size:
                break
        self.logger.debug('%s %s bytes in %4.0f ms', result, len(result), ms(t0))
        return result

    def read_response(self):
        result = self.read_until(CR)
        self.response = result
        if CR not in result:
            self.logger.warning('Response %s without CR', self.response)
            self.error_count.inc()
            return False
        if not self.check:
            self.error_count.clear()
            return True
        # checksum calculation and check
        m = result.find(b'$')
        if m < 0:
            self.logger.error('No expected checksum in response')
            self.error_count.inc()
            return False
        else:
            cs = self.checksum(result[:m])
            if result[m + 1:] != cs:
                self.logger.error('Incorrect checksum')
                self.error_count.inc()
                return False
            self.error_count.clear()
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
        # write command
        if not self.write(cmd):
            self.logger.debug('Error during write')
            return False
        # read response (to CR by default)
        result = self.read_response()
        dt = (time.perf_counter() - t0) * 1000.0
        self.logger.debug('%s -> %s %s %4.0f ms', cmd, self.response, result, dt)
        return result

    def send_command(self, cmd):
        #self.logger.debug('Before the lock ---------------------------')
        with self.com.lock:
            #self.logger.debug('In the lock +++++++++++++++++++++++++++++++')
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
                # add checksum
                if self.check:
                    cs = self.checksum(cmd[:-1])
                    cmd = b'%s$%s\r' % (cmd[:-1], cs)
                if self.com.current_addr != self.addr:
                    result = self.set_addr()
                    if not result:
                        self.suspend()
                        self.response = b''
                        return False
                result = self._send_command(cmd)
                if result:
                    return True
                self.logger.warning('Error, repeat command %s' % cmd)
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

    def set_addr(self):
        a0 = self.com.current_addr
        result = self._send_command(b'ADR %d' % self.addr)
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
        cmd = cmd.upper().strip() + b' ' + str.encode(str(value))[:10] + b'\r'
        if self.send_command(cmd):
            return self.check_response(expect)
        else:
            return False

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
        self.logger.debug('Resetting')
        # if por was not initialized
        self.com.current_addr = -1
        if not self.com.ready:
            self.com.close()
            self.com.init()
            if self.com.ready:
                # init all devices on same port
                for d in TDKLambda.devices:
                    if d.port == self.port:
                        d.init()
            else:
                # suspend all devices on same port
                for d in TDKLambda.devices:
                    if d.port == self.port:
                        d.suspend()
            return
        # port is OK, find working devices on same port
        for d in TDKLambda.devices:
            if d != self and d.port == self.port and d.alive():
                self.init()
                return
        # no working devices on same port so try to recreate com port
        self.com.close()
        self.com.init()
        if self.com.ready:
            # init all devices on same port
            for d in TDKLambda.devices:
                if d.port == self.port:
                    d.init()
        else:
            # suspend all devices on same port
            for d in TDKLambda.devices:
                if d.port == self.port:
                    d.suspend()
        return

    def initialized(self):
        return self.com.ready and self.id.find('LAMBDA') > 0

    def alive(self):
        return self.read_serial_number() > 0

    async def _send_command_async(self, cmd):
        return b''


if __name__ == "__main__":
    pd1 = TDKLambda("FAKECOM7", 6)
    pd2 = TDKLambda("FAKECOM7", 7)
    for i in range(5):
        t_0 = time.time()
        v1 = pd1.read_float("PC?")
        dt1 = int((time.time() - t_0) * 1000.0)  # ms
        print(pd1.port, pd1.addr, 'PC? ->', v1, '%4d ms ' % dt1, 'to=', '%5.3f' % pd1.read_timeout)
        t_0 = time.time()
        v1 = pd1.read_float("MV?")
        dt1 = int((time.time() - t_0) * 1000.0)  # ms
        print(pd1.port, pd1.addr, 'MV? ->', v1, '%4d ms ' % dt1, 'to=', '%5.3f' % pd1.read_timeout)
        t_0 = time.time()
        v1 = pd1.send_command("PV 1.0")
        dt1 = int((time.time() - t_0) * 1000.0)  # ms
        print(pd1.port, pd1.addr, 'PV? ->', v1, '%4d ms ' % dt1, 'to=', '%5.3f' % pd1.read_timeout)
        t_0 = time.time()
        v1 = pd1.read_float("PV?")
        dt1 = int((time.time() - t_0) * 1000.0)  # ms
        print(pd1.port, pd1.addr, 'PV? ->', v1, '%4d ms ' % dt1, 'to=', '%5.3f' % pd1.read_timeout)
        t_0 = time.time()
        v1 = pd1.read_all()
        dt1 = int((time.time() - t_0) * 1000.0)  # ms
        print(pd1.port, pd1.addr, 'DVC? ->', v1, '%4d ms ' % dt1, 'to=', '%5.3f' % pd1.read_timeout)
        t_0 = time.time()
        v1 = pd2.read_float("PC?")
        dt1 = int((time.time() - t_0) * 1000.0)  # ms
        print(pd2.port, pd2.addr, 'PC? ->', v1, '%4d ms ' % dt1, 'to=', '%5.3f' % pd2.read_timeout)
        t_0 = time.time()
        v1 = pd2.read_all()
        dt1 = int((time.time() - t_0) * 1000.0)  # ms
        print(pd2.port, pd2.addr, 'DVC? ->', v1, '%4d ms ' % dt1, 'to=', '%5.3f' % pd2.read_timeout)
        # time.sleep(0.5)
        # pd1.reset()
        # pd2.reset()
