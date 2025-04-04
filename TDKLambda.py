#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
if '../TangoUtils' not in sys.path: sys.path.append('../TangoUtils')
if '../IT6900' not in sys.path: sys.path.append('../IT6900')

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
APPLICATION_VERSION = '4.0' # reconnect corrected


class TDKLambdaException(Exception):
    pass


class TDKLambda:
    _devices = []
    _lock = Lock()
    SUSPEND_DELAY = 5.0
    STATES = {
        1: 'Initialized',
        0: 'Pre init state',
        -1: 'Wrong address',
        -2: 'Address is in use',
        -3: 'Address set error',
        -4: 'Device is not recognized',
        -5: 'COM port not ready'}

    def __init__(self, port, addr, checksum=False, auto_addr=True, **kwargs):
        # parameters
        self.port = port.strip()
        self.addr = addr
        self.check = checksum
        self.auto_addr = auto_addr
        self.protocol = kwargs.pop('protocol', 'GEN')  # 'GEN' or 'SCPI'
        self.read_timeout = kwargs.pop('read_timeout', 1.0)
        self.read_retries = kwargs.pop('read_retries', 2)
        self.suspend_delay = kwargs.pop('suspend_delay', TDKLambda.SUSPEND_DELAY)
        # configure logger
        self.logger = kwargs.get('logger', config_logger())
        # arguments for COM port creation
        self.kwargs = kwargs
        # create variables
        self.command = b''
        self.response = b''
        self.suspend_to = 0.0
        self.suspend_flag = False
        self.state = 0
        self.status = ''
        # default com port, id, serial number, and ...
        self.com = None
        self.id = 'Unknown Device'
        self.sn = ''
        self.max_voltage = float('inf')
        self.max_current = float('inf')
        self.pre = f'{self.id} at {self.port}: {self.addr} '
        # create COM port
        self.create_com_port()
        # add device to list
        with TDKLambda._lock:
            if self not in TDKLambda._devices:
                TDKLambda._devices.append(self)
        # further initialization (for possible async use)
        self.init()

    def init(self):
        self.state = 0
        self.suspend_to = 0.0
        # check device address
        if self.addr <= 0:
            self.state = -1
            self.logger.warning(f'{self.pre} ' + self.STATES[self.state])
            self.suspend()
            return False
        # check if port:address is in use
        with TDKLambda._lock:
            for d in TDKLambda._devices:
                if d != self and d.port == self.port and d.addr == self.addr and d.state > 0:
                    self.state = -2
                    self.logger.warning(f'{self.pre} ' + self.STATES[self.state])
                    self.suspend()
                    return False
        if not self.com.ready:
            self.state = -5
            self.logger.warning(f'{self.pre} ' + self.STATES[self.state])
            self.suspend()
            return False
        # set device address
        with self.com.lock:
            response = self._set_addr()
        if not response:
            self.state = -3
            self.logger.warning(f'{self.pre} ' + self.STATES[self.state])
            self.suspend()
            return False
        # read device serial number
        self.sn = self.read_serial_number()
        # read device type
        self.id = self.read_device_id()
        self.pre = f'{self.id} {self.port}: {self.addr} '
        if 'LAMBDA' in self.id:
            self.state = 1
            # determine max current and voltage from model name
            try:
                ids = self.id.split('-')
                mv = ids[-2].split('G')
                self.max_current = float(ids[-1])
                self.max_voltage = float(mv[-1][2:])
            except:
                msg = f'{self.pre} Can not set max values'
                self.logger.debug(msg)
        else:
            self.state = -4
            self.logger.warning(f'{self.pre} ' + self.STATES[self.state])
            self.suspend()
            return False
        msg = f'{self.pre} has been initialized'
        self.logger.info(msg)
        return True

    def __del__(self):
        with TDKLambda._lock:
            if self in TDKLambda._devices:
                self.close_com_port()
                TDKLambda._devices.remove(self)
                self.logger.debug(f'{self.pre} has been deleted')

    def create_com_port(self):
        self.com = ComPort(self.port, emulated=EmultedTDKLambdaAtComPort, **self.kwargs)
        return self.com

    def close_com_port(self):
        try:
            self.com.close()
        except KeyboardInterrupt:
            raise
        except:
            log_exception(self, f'{self.pre} COM port close exception')

    @staticmethod
    def checksum(cmd):
        s = 0
        for b in cmd:
            s += int(b)
        result = str.encode(hex(s)[-2:].upper())
        return result

    def suspend(self, duration=None):
        if time.time() < self.suspend_to:
            return
        if duration is None:
            duration = self.suspend_delay
        self.suspend_to = time.time() + duration
        self.logger.debug(f'{self.pre} suspended for %5.2f sec', duration)

    @property
    def ready(self):
        if time.time() < self.suspend_to:
            # self.logger.debug(f'{self.pre} Suspended')
            return False
        if self.suspend_to <= 0.0:
            return True
        # was suspended and expires
        # self.close_com_port()
        # self.create_com_port()
        val = self.init()
        return val

    def _read(self, size=1, timeout=1.0):
        result = b''
        t0 = time.perf_counter()
        while len(result) < size:
            r = self.com.read(1)
            if r:
                result += r
            else:
                if timeout is not None and time.perf_counter() - t0 > timeout:
                    raise SerialTimeoutException(f'{self.pre} Reading timeout {result}')
        return result

    def read(self, size=1):
        result = b''
        try:
            result = self._read(size, self.read_timeout)
            return result
        except KeyboardInterrupt:
            raise
        except SerialTimeoutException:
            self.logger.info(f'{self.pre} Reading timeout')
            return result
        except:
            log_exception(self.logger, f'{self.pre} Reading exception')
            return b''

    def read_until(self, terminator=CR, size=None):
        result = b''
        # t0 = time.perf_counter()
        while not any([i in result for i in terminator]):
            r = self.read(1)
            if not r:
                break
            result += r
            if size is not None and len(result) >= size:
                break
            # if time.perf_counter() - t0 > self.read_timeout:
            #     self.suspend()
            #     break
        # dt = (time.perf_counter() - t0) * 1000.0
        # self.logger.debug('%s %s bytes in %4.0f ms', result, len(result), dt)
        return result

    def read_response(self, terminator=CR):
        result = self.read_until(terminator)
        self.response = result
        if not any([i in result for i in terminator]):
            self.logger.debug(f'{self.pre} Response %s without %s', result, terminator)
            return False
        # checksum calculation
        return self.verify_checksum(result)

    def verify_checksum(self, result):
        if not self.check:
            return True
        m = result.find(b'$')
        if m < 0:
            self.logger.debug(f'{self.pre} No expected checksum in response')
            return False
        else:
            cs = self.checksum(result[:m])
            if result[m + 1:] != cs:
                self.logger.debug(f'{self.pre} Incorrect checksum in response')
                return False
            self.response = result[:m]
            return True

    def check_response(self, expected=b'OK', response=None):
        if response is None:
            response = self.response
        if response.startswith(expected):
            return True
        msg = f'{self.pre} Unexpected response %s (not %s)' % (response, expected)
        self.logger.debug(msg)
        return False

    def write(self, cmd):
        # t0 = time.perf_counter()
        try:
            # reset input buffer
            if not self.com.reset_input_buffer():
                return False
            # write command
            length = self.com.write(cmd)
            if len(cmd) == length:
                return True
            return False
        except KeyboardInterrupt:
            raise
        except SerialTimeoutException:
            self.logger.debug(f'{self.pre} Writing timeout')
            return False
        except:
            log_exception(self.logger, f'{self.pre} Writing exception')
            return False

    def _send_command(self, cmd, terminator=CR):
        if not cmd.endswith(terminator):
            if isinstance(terminator, bytes):
                cmd += terminator
            else:
                cmd += terminator[0]
        self.command = cmd
        self.response = b''
        t0 = time.perf_counter()
        # write command
        if not self.write(cmd):
            self.logger.debug(f'{self.pre} Error during write')
            return False
        # read response (to CR by default)
        result = self.read_response(terminator)
        dt = time.perf_counter() - t0
        self.logger.debug(f'{self.pre} %s -> %s %s %4.0f ms', cmd, self.response, result, dt * 1000.)
        return result

    def _set_addr(self):
        if not hasattr(self.com, 'current_addr'):
            self.com.current_addr = -1
        result = self._send_command(b'ADR %d\r' % self.addr)
        if result and self.check_response(b'OK'):
            self.logger.debug(f'{self.pre} Address %d -> %d' % (self.com.current_addr, self.addr))
            self.com.current_addr = self.addr
            return True
        else:
            self.logger.debug(f'{self.pre} Error address {self.com.current_addr} -> {self.addr} {self.response}')
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
            # self.logger.debug('%s is not a float' % self.response)
            return float('Nan')
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
            # self.logger.info('Can not convert %s to %s', self.response, v_type)
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
        # self.logger.info(f'{self.pre} Not boolean response %s ', response)
        return None

    def write_value(self, cmd, value, expect=b'OK'):
        cmd = cmd.upper().strip() + b' ' + str(value)[:10].encode() + CR
        if self.send_command(cmd):
            return self.check_response(expect)
        else:
            return False

    # high level general command  ***************************
    def send_command(self, cmd) -> bool:
        if not self.ready:
            self.command = cmd
            self.response = b''
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
                    n = self.read_retries
                    while n > 0:
                        n -= 1
                        result = self._set_addr()
                        if result:
                            break
                    if not result:
                        self.suspend()
                        self.response = b''
                        return False
                result = self._send_command(cmd)
                if result:
                    return True
                self.logger.debug(f'{self.pre} Send command %s error' % cmd)
                n = self.read_retries
                while n > 1:
                    n -= 1
                    result = self._send_command(cmd)
                    if result:
                        return True
                    # self.logger.debug(f'{self.pre} Repeated send command %s error' % cmd)
                self.suspend()
                self.response = b''
                self.logger.info(f'{self.pre} Can not send command %s' % cmd)
                return False
        except KeyboardInterrupt:
            raise
        except:
            log_exception(self.logger, f'{self.pre} Can not send command {cmd}')
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
        # if not self.send_command(b'OUT?'):
        #     return None
        # response = self.response.upper()
        # if response.startswith((b'ON', b'1')):
        #     return True
        # if response.startswith((b'OFF', b'0')):
        #     return False
        # self.logger.debug(f'{self.pre} Unexpected response %s' % response)
        return self.read_bool(b'OUT?')

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
                # self.logger.debug('%s is not a float', reply)
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
        return self.ready

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
        self.min_read_time = self.read_timeout

    def __del__(self):
        self.close_com_port()
        # with TDKLambda._lock:
        #     if self in TDKLambda._devices:
        #         self.close_com_port()
        #         TDKLambda_SCPI._devices.remove(self)
        self.logger.debug(f'Device at {self.port}:{self.addr} has been deleted')

    def read_all(self):
        v1 = self.read_voltage()
        v2 = self.read_programmed_voltage()
        v3 = self.read_current()
        v4 = self.read_programmed_current()
        return [v1, v2, v3, v4, self.max_voltage, self.max_current]

    def alive(self):
        return self.ID_OK in self.read_device_id()


if __name__ == "__main__":
    # pd1 = TDKLambda("FAKECOM7", 6)
    pd2 = TDKLambda_SCPI("192.168.1.202:8003", 7)
    logger = pd2.logger
    t_0 = time.time()

    # v1 = pd1.read_current()
    # dt1 = int((time.time() - t_0) * 1000.0)  # ms
    # print(pd1.port, pd1.addr, 'read_current ->', v1, '%4d ms ' % dt1)
    # t_0 = time.time()
    # v1 = pd1.read_voltage()
    # dt1 = int((time.time() - t_0) * 1000.0)  # ms
    # print(pd1.port, pd1.addr, 'read_voltage ->', v1, '%4d ms ' % dt1)
    # t_0 = time.time()
    # v1 = pd1.read_all()
    # dt1 = int((time.time() - t_0) * 1000.0)  # ms
    # print(pd1.port, pd1.addr, 'DVC? ->', v1, '%4d ms ' % dt1)
    while True:
        t_0 = time.time()
        v1 = pd2.read_programmed_voltage()
        dt1 = int((time.time() - t_0) * 1000.0)  # ms
        print(pd2.port, pd2.addr, '2 read_programmed_voltage ->', v1, '%4d ms ' % dt1)
    # t_0 = time.time()
    # v1 = pd2.send_command("PV 1.0")
    # dt1 = int((time.time() - t_0) * 1000.0)  # ms
    # print(pd2.port, pd2.addr, '2 PV 1.0 ->', v1, '%4d ms ' % dt1, '%5.3f' % pd2.min_read_time)
    # t_0 = time.time()
    # v1 = pd2.read_float("PV?")
    # dt1 = int((time.time() - t_0) * 1000.0)  # ms
    # print(pd2.port, pd2.addr, '2 PV? ->', v1, '%4d ms ' % dt1, '%5.3f' % pd2.min_read_time)

    # del pd1
    del pd2
    print('Finished')
