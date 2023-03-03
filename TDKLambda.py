#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import sys; sys.path.append('../TangoUtils'); sys.path.append('../IT6900')
import time
from threading import Lock

from serial import SerialTimeoutException

from ComPort import ComPort
from EmultedTDKLambdaAtComPort import EmultedTDKLambdaAtComPort
from IT6900 import IT6900
from config_logger import config_logger
from log_exception import log_exception

CR = b'\r'
LF = b'\n'

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'TDK Lambda Genesis series PS Python API'
APPLICATION_NAME_SHORT = 'TDKLambda'
APPLICATION_VERSION = '3.0'


class TDKLambdaException(Exception):
    pass


SUSPEND_TIME = 5.0
STATE = {
    0: 'Pre init state',
    1: 'Initialized',
    -1: 'Wrong address',
    -2: 'Address is in use',
    -3: 'Address set error',
    -4: 'LAMBDA device is not recognized'}


class TDKLambda:
    devices = []
    dev_lock = Lock()

    def __init__(self, port, addr, checksum=False, auto_addr=True, **kwargs):
        # parameters
        self.port = port.strip()
        self.addr = addr
        self.check = checksum
        self.auto_addr = auto_addr
        self.protocol = kwargs.get('protocol', 'GEN')  # 'GEN' or 'SCPI'
        # configure logger
        self.logger = kwargs.get('logger', config_logger())
        # timeouts
        self.read_timeout = kwargs.pop('read_timeout', 0.5)
        self.read_reties = kwargs.pop('read_reties', 1)
        self.min_read_time = self.read_timeout
        # rest arguments for COM port creation
        self.kwargs = kwargs
        # create variables
        self.command = b''
        self.response = b''
        self.time = time.time()
        self.suspend_to = time.time()
        self.suspend_flag = False
        self.state = 0
        # default com port, id, serial number, and ...
        self.com = None
        self.id = 'Unknown Device'
        self.sn = ''
        self.max_voltage = float('inf')
        self.max_current = float('inf')
        # create COM port
        self.create_com_port()
        # check device address
        if addr <= 0:
            self.logger.error('Wrong address')
            self.state = -1
            # raise TDKLambdaException('Wrong address')
        # check if port:address is in use
        with TDKLambda.dev_lock:
            for d in TDKLambda.devices:
                if d != self and d.port == self.port and d.addr == self.addr and d.state > 0:
                    self.logger.error('Address is in use')
                    self.state = -2
                    # raise TDKLambdaException('Address is in use')
        # add device to list
        with TDKLambda.dev_lock:
            if self not in TDKLambda.devices:
                TDKLambda.devices.append(self)
        if self.state < 0:
            return
        # further initialization (for possible async use)
        self.init()

    def init(self):
        self.suspend_to = 0.0
        self.suspend_flag = False
        if not self.com.ready:
            self.suspend()
            return
        # set device address
        response = self._set_addr()
        if not response:
            self.suspend()
            msg = 'TDKLambda: device was not initialized properly'
            self.logger.info(msg)
            self.state = -3
            return
        # read device serial number
        self.sn = self.read_serial_number()
        # read device type
        self.id = self.read_device_id()
        if 'LAMBDA' in self.id:
            self.state = 1
            # determine max current and voltage from model name
            try:
                ids = self.id.split('-')
                mv = ids[-2].split('G')
                self.max_current = float(ids[-1])
                self.max_voltage = float(mv[-1][2:])
            except:
                self.logger.warning('Can not set max values')
        else:
            msg = 'LAMBDA device is not recognized'
            self.logger.error(msg)
            self.state = -4
            return
        # msg = 'TDKLambda: %s SN:%s has been initialized' % (self.id, self.sn)
        self.logger.debug(f'TDKLambda at {self.port}:{self.addr} has been initialized')

    def __del__(self):
        with TDKLambda.dev_lock:
            if self in TDKLambda.devices:
                self.close_com_port()
                TDKLambda.devices.remove(self)
                self.logger.debug(f'Device at {self.port}:{self.addr} has been deleted')

    def create_com_port(self):
        self.com = ComPort(self.port, emulated=EmultedTDKLambdaAtComPort, **self.kwargs)
        if self.com.ready:
            self.logger.debug('Port %s is ready', self.port)
        else:
            self.logger.error('Port %s creation error', self.port)
        return self.com

    def close_com_port(self):
        try:
            # self.com.current_addr = -1
            self.com.close()
        except:
            log_exception(self, 'COM port close exception')
        # # suspend all devices with same port
        # with TDKLambda.dev_lock:
        #     for d in TDKLambda.devices:
        #         if d.port == self.port:
        #             d.suspend()

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
        if self.state < 0 or time.time() < self.suspend_to:  # if suspension does not expire
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

    def _read(self, size=1, timeout=1.0):
        result = b''
        t0 = time.perf_counter()
        while len(result) < size:
            r = self.com.read(1)
            if len(r) > 0:
                result += r
            else:
                if timeout is not None and time.perf_counter() - t0 > timeout:
                    raise SerialTimeoutException('Reading timeout %s' % result)
        return result

    def read(self, size=1):
        try:
            result = self._read(size, self.read_timeout)
            return result
        except KeyboardInterrupt:
            raise
        except:
            log_exception(self)
            return b''

    def read_until(self, terminator=CR, size=None):
        result = b''
        t0 = time.perf_counter()
        while terminator not in result:
            r = self.read(1)
            if not r:
                self.suspend()
                break
            result += r
            if size is not None and len(result) >= size:
                break
            # if time.perf_counter() - t0 > self.read_timeout:
            #     self.suspend()
            #     break
        dt = (time.perf_counter() - t0) * 1000.0
        self.logger.debug('%s %s bytes in %4.0f ms', result, len(result), dt)
        return result

    def read_response(self, terminator=CR):
        result = self.read_until(terminator)
        self.response = result
        if terminator not in result:
            self.logger.error('Response %s without %s', result, terminator)
            return False
        # if checksum used
        if not self.check:
            return True
        # checksum calculation
        return self.verify_checksum(result)

    def verify_checksum(self, result):
        m = result.find(b'$')
        if m < 0:
            self.logger.error('No expected checksum in response')
            return False
        else:
            cs = self.checksum(result[:m])
            if result[m + 1:] != cs:
                self.logger.error('Incorrect checksum in response')
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
        except KeyboardInterrupt:
            raise
        except SerialTimeoutException:
            self.logger.error('Writing timeout')
            dt = (time.perf_counter() - t0) * 1000.0
            self.logger.debug('%s %s bytes in %4.0f ms %s', cmd, length, dt, result)
            return False
        except:
            log_exception(self)
            return False

    def _send_command(self, cmd, terminator=CR):
        self.command = cmd
        self.response = b''
        if self.state < 0:
            return False
        t0 = time.perf_counter()
        with self.com.lock:
            # write command
            if not self.write(cmd):
                self.logger.debug('Error during write to %s', self.com.port)
                return False
            # read response (to CR by default)
            result = self.read_response(terminator)
        dt = time.perf_counter() - t0
        if result and dt < self.min_read_time:
            self.min_read_time = dt
        self.logger.debug('%s -> %s %s %4.0f ms', cmd, self.response, result, dt * 1000.)
        return result

    def _set_addr(self):
        if not hasattr(self.com, 'current_addr'):
            self.com.current_addr = -1
        with self.com.lock:
            result = self._send_command(b'ADR %d\r' % self.addr)
            if result and self.check_response(b'OK'):
                self.logger.debug('Address %d -> %d' % (self.com.current_addr, self.addr))
                self.com.current_addr = self.addr
                return True
            else:
                self.logger.error('Error set address %d -> %d' % (self.com.current_addr, self.addr))
                self.com.current_addr = -1
                return False

    def read_float(self, cmd):
        try:
            if not self.send_command(cmd):
                return float('Nan')
            v = float(self.response[:-1])
        except KeyboardInterrupt:
            raise
        except:
            self.logger.debug('%s is not a float' % self.response)
            v = float('Nan')
        return v

    def read_value(self, cmd, v_type):
        try:
            if self.send_command(cmd):
                v = v_type(self.response[:-1].decode())
            else:
                v = None
        except KeyboardInterrupt:
            raise
        except:
            self.logger.info('Can not convert %s to %s', self.response, v_type)
            v = None
        return v

    def read_bool(self, cmd):
        if not self.send_command(cmd):
            return None
        response = self.response[:-1]
        if response.upper() in (b'ON', b'1'):
            return True
        if response.upper() in (b'OFF', b'0'):
            return False
        self.logger.info('Not boolean response %s ', response)
        return False

    def write_value(self, cmd, value, expect=b'OK'):
        cmd = cmd.upper().strip() + b' ' + str(value)[:10].encode() + CR
        if self.send_command(cmd):
            return self.check_response(expect)
        else:
            return False

    def reset(self):
        if self.state < 0:
            return
        self.logger.debug('Resetting')
        self.com.device.close()
        self.com.device.open()
        # self.com = self.create_com_port()
        self.init()
        return

    # high level general command  ***************************
    def send_command(self, cmd) -> bool:
        if self.is_suspended():
            self.command = cmd
            self.response = b''
            self.logger.debug('Ignored command %s to suspended device', cmd)
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
            cmd = self.add_checksum(cmd)
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
                self.logger.warning('Send command %s error' % cmd)
                n = self.read_reties
                while n > 1:
                    n -= 1
                    result = self._send_command(cmd)
                    if result:
                        return True
                    self.logger.warning('Repeated send command %s error' % cmd)
                self.suspend()
                self.response = b''
                self.logger.error('Can not send command %s' % cmd)
                return False
        except KeyboardInterrupt:
            raise
        except:
            log_exception(self)
            self.suspend()
            self.response = b''
            return False

    # high level read commands ***************************
    def add_checksum(self, cmd):
        if self.check:
            cs = self.checksum(cmd[:-1])
            cmd = b'%s$%s\r' % (cmd[:-1], cs)
        return cmd

    def read_device_id(self):
        try:
            if self.send_command(b'IDN?'):
                return self.response[:-1].decode()
            else:
                return 'Unknown Device'
        except KeyboardInterrupt:
            raise
        except:
            return 'Unknown Device'

    def read_serial_number(self):
        try:
            if self.send_command(b'SN?'):
                serial_number = self.response[:-1].decode()
                return serial_number
            else:
                return ''
        except KeyboardInterrupt:
            raise
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
        return self.state > 0 and self.com.ready and self.id.find('LAMBDA') >= 0

    def alive(self):
        return self.read_device_id().find('LAMBDA') >= 0


class TDKLambda_SCPI(IT6900):
    ID_OK = 'TDK-LAMBDA'
    DEVICE_NAME = 'TDK-LAMBDA Genesys+'
    DEVICE_FAMILY = 'TDK-LAMBDA Genesys+ family Power Supply'

    def __init__(self, port, addr, **kwargs):
        super().__init__(port, addr, **kwargs)
        self.addr = addr
        self.check = kwargs.pop('checksum', False)
        self.auto_addr = kwargs.pop('auto_addr', True)
        self.protocol = kwargs.pop('protocol', 'SCPI')  # 'GEN' or 'SCPI'
        # timeouts
        self.read_timeout = kwargs.pop('read_timeout', 0.5)
        self.min_read_time = self.read_timeout
        self.time = time.time()
        self.suspend_to = time.time()
        self.suspend_flag = False

    def read_all(self):
        v1 = self.read_voltage()
        v2 = self.read_programmed_voltage()
        v3 = self.read_current()
        v4 = self.read_programmed_current()
        return [v1, v2, v3, v4, self.max_voltage, self.max_current]

    def alive(self):
        return self.ID_OK in self.read_device_id()


if __name__ == "__main__":
    pd1 = TDKLambda("FAKECOM7", 6)
    pd2 = TDKLambda_SCPI("192.168.1.202:8003", 7)
    logger = pd2.logger
    t_0 = time.time()

    v1 = pd1.read_current()
    dt1 = int((time.time() - t_0) * 1000.0)  # ms
    print(pd1.port, pd1.addr, 'read_current ->', v1, '%4d ms ' % dt1, '%5.3f' % pd1.min_read_time)
    t_0 = time.time()
    v1 = pd1.read_voltage()
    dt1 = int((time.time() - t_0) * 1000.0)  # ms
    print(pd1.port, pd1.addr, 'read_voltage ->', v1, '%4d ms ' % dt1, '%5.3f' % pd1.min_read_time)
    t_0 = time.time()
    v1 = pd1.read_all()
    dt1 = int((time.time() - t_0) * 1000.0)  # ms
    print(pd1.port, pd1.addr, 'DVC? ->', v1, '%4d ms ' % dt1, '%5.3f' % pd1.min_read_time)

    t_0 = time.time()
    v1 = pd2.read_programmed_voltage()
    dt1 = int((time.time() - t_0) * 1000.0)  # ms
    print(pd2.port, pd2.addr, '2 read_programmed_voltage ->', v1, '%4d ms ' % dt1, '%5.3f' % pd2.min_read_time)
    t_0 = time.time()
    # v1 = pd2.send_command("PV 1.0")
    # dt1 = int((time.time() - t_0) * 1000.0)  # ms
    # print(pd2.port, pd2.addr, '2 PV 1.0 ->', v1, '%4d ms ' % dt1, '%5.3f' % pd2.min_read_time)
    # t_0 = time.time()
    # v1 = pd2.read_float("PV?")
    # dt1 = int((time.time() - t_0) * 1000.0)  # ms
    # print(pd2.port, pd2.addr, '2 PV? ->', v1, '%4d ms ' % dt1, '%5.3f' % pd2.min_read_time)

    del pd1
    del pd2
    print('Finished')
