#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import socket
import time
from threading import Lock

from AsyncSerial import *


class FakeComPort:
    SN = 123456
    RESPONSE = 0.035

    def __init__(self, port, *args, **kwargs):
        self.last_address = -1
        self.lock = Lock()
        self.online = False
        self.last_write = b''
        self.pv = {self.last_address: 0.0}
        self.pc = {self.last_address: 0.0}
        self.mv = {self.last_address: 0.0}
        self.mc = {self.last_address: 0.0}
        self.out = {self.last_address: False}
        self.sn = {self.last_address: str(FakeComPort.SN).encode()}
        FakeComPort.SN += 1
        self.id = {self.last_address: b'FAKELAMBDA GEN10-100'}
        self.t = {self.last_address: time.time()}

    def close(self):
        self.last_write = b''
        self.online = False
        return True

    def write(self, cmd):
        self.last_write = cmd
        try:
            if self.last_write.startswith(b'ADR '):
                self.last_address = int(self.last_write[4:])
                if self.last_address not in self.pv:
                    self.pv[self.last_address] = 0.0
                    self.pc[self.last_address] = 0.0
                    self.mv[self.last_address] = 0.0
                    self.mc[self.last_address] = 0.0
                    self.out[self.last_address] = False
                    self.sn[self.last_address] = str(FakeComPort.SN).encode()
                    FakeComPort.SN += 1
                    self.id[self.last_address] = self.id[-1]
                    self.t[self.last_address] = time.time()
            if self.last_write.startswith(b'PV '):
                self.pv[self.last_address] = float(cmd[3:])
                self.t[self.last_address] = time.time()
            if self.last_write.startswith(b'PC '):
                self.pc[self.last_address] = float(cmd[3:])
                self.t[self.last_address] = time.time()
            if self.last_write.startswith(b'OUT ON'):
                self.out[self.last_address] = True
                self.t[self.last_address] = time.time()
            if self.last_write.startswith(b'OUT OF'):
                self.out[self.last_address] = False
                self.t[self.last_address] = time.time()
        except:
            pass

    def read(self):
        if self.last_write == b'':
            return b''
        if time.time() - self.t[self.last_address] < self.RESPONSE:
            return b''
        self.t[self.last_address] = time.time()
        if self.last_write.startswith(b'ADR '):
            self.last_address = int(self.last_write[3:])
            self.last_write = b''
            return b'OK\r'
        if self.last_write.startswith(b'DVC?'):
            if self.out[self.last_address]:
                self.mv[self.last_address] = self.pv[self.last_address]
                self.mc[self.last_address] = self.pc[self.last_address]
            else:
                self.mv[self.last_address] += 0.5
                if self.mv[self.last_address] > 10.0:
                    self.mv[self.last_address] = 0.0
                self.mc[self.last_address] += 1.0
                if self.mc[self.last_address] > 100.0:
                    self.mc[self.last_address] = 0.0
            self.last_write = b''
            return b'%f, %f, %f, %f, 0.0, 0.0\r' % \
                   (self.mv[self.last_address], self.pv[self.last_address],
                    self.mc[self.last_address], self.pc[self.last_address])
        if self.last_write.startswith(b'PV?'):
            self.last_write = b''
            return str(self.pv[self.last_address]).encode() + b'\r'
        if self.last_write.startswith(b'MV?'):
            if self.out[self.last_address]:
                self.mv[self.last_address] = self.pv[self.last_address]
            else:
                self.mv[self.last_address] += 0.5
                if self.mv[self.last_address] > 10.0:
                    self.mv[self.last_address] = 0.0
            self.last_write = b''
            return str(self.mv[self.last_address]).encode() + b'\r'
        if self.last_write.startswith(b'PC?'):
            self.last_write = b''
            return str(self.pc[self.last_address]).encode() + b'\r'
        if self.last_write.startswith(b'MC?'):
            if self.out[self.last_address]:
                self.mc[self.last_address] = self.pc[self.last_address]
            else:
                self.mv[self.last_address] += 1.0
                if self.mv[self.last_address] > 100.0:
                    self.mv[self.last_address] = 0.0
            self.last_write = b''
            return str(self.mv[self.last_address]).encode() + b'\r'
        if self.last_write.startswith(b'IDN?'):
            self.last_write = b''
            return self.id[self.last_address] + b'\r'
        if self.last_write.startswith(b'SN?'):
            self.last_write = b''
            return self.sn[self.last_address] + b'\r'
        if self.last_write.startswith(b'OUT?'):
            self.last_write = b''
            if self.out[self.last_address]:
                return b'ON\r'
            else:
                return b'OFF\r'
        self.last_write = b''
        return b'OK\r'


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
wrongAddressException = Exception('Address is incorrect')

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

    def act(self):
        if self.value > self.limit:
            self.value = 0
            if self.action is not None:
                return self.action(*self.args, **self.kwargs)
            else:
                return True
        else:
            return False

    def __iadd__(self, other):
        self.value += other
        self.act()
        return self


class TDKLambda:
    LOG_LEVEL = logging.INFO
    EMULATE = False
    max_timeout = 0.5  # sec
    min_timeout = 0.1  # sec
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
        self.id = None
        self.sn = None
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
        # set device address
        response = self.set_addr()
        if not response:
            msg = 'Uninitialized TDKLambda device has been added to list'
            self.logger.info(msg)
            TDKLambda.devices.append(self)
            return
        # read device type
        self.id = self._send_command(b'IDN?').decode()
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
        self.serial_number = self._send_command(b'SN?').decode()
        # add device to list
        TDKLambda.devices.append(self)
        msg = 'TDKLambda: %s has been created' % self.id
        self.logger.info(msg)

    def __del__(self):
        if self in TDKLambda.devices:
            TDKLambda.devices.remove(self)

    def reinitialize(self):
        self.logger.debug('Initializing device')
        self.__del__()
        self.__init__(self.port, self.addr, self.check, self.baud, self.logger)

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
                    self.com = AsyncSerial(self.port, baudrate=self.baud)
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
                self.reinitialize()
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
        """
        read size byte from com port and correct timeout
        :return: byte
        """
        result = b''
        if self.is_suspended():
            return result
        if timeout is None:
            timeout = self.read_timeout
        t0 = time.time()
        try:
            result = await self.com.read(size, timeout=timeout)
        except SerialTimeoutException:
            self.read_timeout = min(1.5 * self.read_timeout, self.max_timeout)
            self.logger.info('Reading timeout, corrected to %5.2f s' % self.read_timeout)
            self.read_timeout_count.inc()
        except:
            self.logger.info('Unexpected exception', exc_info=True)
            self.suspend()
        else:
            self.read_timeout_count.clear()
            dt = time.time() - t0
            self.read_timeout = max(2.0 * dt, self.min_timeout)
        return result

    def read_until(self, terminator=b'\r', size=None, timeout=None):
        result = b''
        if self.is_suspended():
            return result
        t0 = time.time()
        if timeout is None:
            timeout = self.read_timeout
        try:
            result = await self.com.read_until(terminator, size, timeout)
        except SerialTimeoutException:
            self.read_timeout = min(1.5 * self.read_timeout, self.max_timeout)
            self.logger.info('Reading timeout, increased to %5.2f s' % self.read_timeout)
            self.read_timeout_count.inc()
        except:
            self.logger.info('Unexpected exception', exc_info=True)
            self.suspend()
        else:
            self.read_timeout_count.clear()
            dt = time.time() - t0
            self.read_timeout = max(2.0 * dt, self.min_timeout)
        return result

    def read_response(self):
        result = self.read_until()
        self.last_response = result
        if CR not in result:
            self.logger.error('Response without CR')
            self.error_count.inc()
            return result
        if self.check:
            m = result.find(b'$')
            if m < 0:
                self.logger.error('No expected checksum in response')
                self.error_count.inc()
                return result
            else:
                cs = self.checksum(result[:m])
                if result[m+1:] != cs:
                    self.logger.error('Incorrect checksum')
                    self.error_count.inc()
                    return result
                self.error_count.clear()
                return result[:m]
        self.error_count.clear()
        return result

    def check_response(self, expected=b'OK', response=None):
        if self.is_suspended():
            return False
        if response is None:
            response = self.last_response
        if not response.startswith(expected):
            msg = 'Unexpected response %s (not %s)' % (response, expected)
            self.logger.info(msg)
            return False
        return True

    def clear_input_buffer(self):
        await self.com.reset_input_buffer(self.read_timeout)

    def write(self, cmd):
        if self.is_suspended():
            return False
        t0 = time.time()
        try:
            # clear input buffer
            self.clear_input_buffer()
            # write command
            await self.com.write(cmd, timeout=self.read_timeout)
            await asyncio.sleep(self.sleep_after_write)
            self.logger.debug('%s %4.0f ms' % (cmd, (time.time() - t0) * 1000.0))
            return True
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
        try:
            cmd = cmd.upper().strip()
            # convert str to bytes
            if isinstance(cmd, str):
                cmd = str.encode(cmd)
            # add CR if missing
            if cmd[-1] != b'\r'[0]:
                cmd += b'\r'
            # add checksum
            if self.check:
                cs = self.checksum(cmd[:-1])
                cmd = b'%s$%s\r' % (cmd[:-1], cs)
            self.last_command = cmd
            t0 = time.time()
            # write command
            self.write(cmd)
            # read response (to CR by default)
            result = self.read_response()
            self.logger.debug('%s -> %s %4.0f ms' % (cmd, result, (time.time()-t0)*1000.0))
            if len(result) > 0:
                return result
            self.logger.warning('Writing error, repeat %s' % cmd)
            self.write(cmd)
            result = self.read_until()
            self.logger.debug('%s -> %s %4.0f ms' % (cmd, result, (time.time() - t0) * 1000.0))
            if result is not None:
                return result
            self.logger.error('Repeated writing error')
            self.suspend()
            self.last_response = b''
            return b''
        except:
            self.logger.error('Unexpected exception')
            self.logger.debug("", exc_info=True)
            self.suspend()
            self.last_response = b''
            return b''

    def send_command(self, cmd):
        if self.is_suspended():
            self.last_command = cmd
            self.last_response = b''
            return b''
        if self.auto_addr and self.com._current_addr != self.addr:
            result = self.set_addr()
            if not result:
                return b''
            return self._send_command(cmd)
        else:
            return self._send_command(cmd)

    def _set_addr(self):
        if hasattr(self.com, '_current_addr'):
            a0 = self.com._current_addr
        else:
            a0 = -1
        self._send_command(b'ADR %d' % abs(self.addr))
        if self.check_response():
            self.com._current_addr = self.addr
            self.logger.debug('Set address %d -> %d' % (a0, self.addr))
            return True
        else:
            self.logger.error('Error set address %d -> %d' % (a0, self.addr))
            if self.com is not None:
                self.com._current_addr = -1
            return False

    def set_addr(self):
        if self.com is None or self.suspend_flag:
            return False
        result = self._set_addr()
        if result:
            return True
        result = self._set_addr()
        if result:
            return True
        self.suspend()
        self.com._current_addr = -1
        return False

    def read_float(self, cmd):
        reply = self.send_command(cmd)
        try:
            v = float(reply)
        except:
            self.logger.debug('%s is not a float' % reply)
            v = float('Nan')
        return v

    def read_all(self):
        reply = self.send_command(b'DVC?')
        if reply == b'':
            return [float('Nan')] * 6
        sv = reply.split(b',')
        vals = []
        for s in sv:
            try:
                v = float(s)
            except:
                self.logger.debug('%s is not a float' % reply)
                v = float('Nan')
            vals.append(v)
        if len(vals) == 6:
            return vals
        elif len(vals) > 6:
            vals = [float('Nan')] * 6
            return vals
        else:
            vals += [float('Nan')] * (6 - len(vals))
            return vals

    def read_value(self, cmd, vtype=str):
        #t0 = time.time()
        reply = b''
        try:
            reply = self.send_command(cmd)
            v = vtype(reply)
        except:
            self.check_response(response=b'Wrong format:'+reply)
            v = None
        #dt = time.time() - t0
        #print('read_value', dt)
        return v

    def read_bool(self, cmd):
        response = self.send_command(cmd)
        if response.upper() in (b'ON', b'1'):
            return True
        if response.upper() in (b'OFF', b'0'):
            return False
        self.check_response(response=b'Not boolean:' + response)
        return False

    def write_value(self, cmd: bytes, value, expect=b'OK'):
        cmd = cmd.upper().strip() + b' ' + str.encode(str(value))[:10] + b'\r'
        self.send_command(cmd)
        return self.check_response(expect)

    def reset(self):
        self.__del__()
        self.__init__(self.port, self.addr, self.check, self.baud, self.logger)


if __name__ == "__main__":
    pd1 = TDKLambda("COM4", 6)
    pd2 = TDKLambda("COM4", 7)
    for i in range(5):
        t0 = time.time()
        v1 = pd1.read_float("PC?")
        dt1 = int((time.time()-t0)*1000.0)    #ms
        print('1: ', '%4d ms ' % dt1,'PC?=', v1, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
        t0 = time.time()
        v1 = pd1.read_float("MV?")
        dt1 = int((time.time()-t0)*1000.0)    #ms
        print('1: ', '%4d ms ' % dt1,'MV?=', v1, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
        t0 = time.time()
        v1 = pd1.send_command("PV 1.0")
        dt1 = int((time.time()-t0)*1000.0)    #ms
        print('1: ', '%4d ms ' % dt1,'PV 1.0', v1, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
        t0 = time.time()
        v1 = pd1.read_float("PV?")
        dt1 = int((time.time()-t0)*1000.0)    #ms
        print('1: ', '%4d ms ' % dt1,'PV?=', v1, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
        t0 = time.time()
        v3 = pd1.read_all()
        dt1 = int((time.time()-t0)*1000.0)    #ms
        print('1: ', '%4d ms ' % dt1,'DVC?=', v3, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
        t0 = time.time()
        v2 = pd2.read_float("PC?")
        dt2 = int((time.time()-t0)*1000.0)    #ms
        print('2: ', '%4d ms ' % dt2,'PC?=', v2, 'to=', '%5.3f' % pd2.read_timeout, pd2.port, pd2.addr)
        t0 = time.time()
        v4 = pd2.read_all()
        dt1 = int((time.time()-t0)*1000.0)    #ms
        print('2: ', '%4d ms ' % dt1,'DVC?=', v4, 'to=', '%5.3f' % pd2.read_timeout, pd2.port, pd2.addr)
        time.sleep(0.1)
