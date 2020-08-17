#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import socket
from threading import Lock
import time

from Async.AsyncSerial import *
from EmulatedLambda import FakeComPort
from serial import Timeout

from TDKLambda import *


class FakeAsyncComPort(FakeComPort):
    SN = 9876543
    RESPONSE_TIME = 0.035

    def __init__(self, port, *args, **kwargs):
        super().__init__(port, *args, **kwargs)
        self.async_lock = asyncio.Lock()

    async def reset_input_buffer(self, timeout=None):
        return True

    async def close(self):
        super().close()
        return True

    async def write(self, cmd, timeout=None):
        async with self.async_lock:
            return super().write(cmd, timeout)

    async def read(self, size=1, timeout=None):
        return super().read(size, timeout)

    async def read_until(self, terminator=b'\r', size=None, timeout=None):
        result = bytearray()
        to = Timeout(timeout)
        async with self.async_lock:
            while True:
                c = await self.read(1)
                if c:
                    result += c
                    if terminator in result:
                        break
                    if size is not None and len(result) >= size:
                        break
                    to.restart(timeout)
                if to.expired():
                    raise SerialTimeoutException('Read timeout')
        return bytes(result)


class AsyncTDKLambda(TDKLambda):

    def suspend(self, duration=9.0):
        self.suspend_to = time.time() + duration
        self.suspend_flag = True
        msg = '%s is suspended for %5.2f sec' % (self, duration)
        self.logger.debug(msg)

    def unsuspend(self):
        self.suspend_to = 0.0
        self.suspend_flag = False
        self.logger.debug('%s is unsuspended' % self)

    def is_suspended(self):
        if time.time() < self.suspend_to:   # if suspension does not expire
            self.logger.debug('%s suspended' % self)
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
                self.logger.debug('%s not suspended' % self)
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
        self.logger.debug('Resetting %s' % self)
        self.__del__()
        self.__init__(self.port, self.addr, self.check, self.baud, self.logger, self.auto_addr)



async def main():
    pd1 = AsyncTDKLambda("COM6", 6)
    await pd1.init()
    pd2 = AsyncTDKLambda("COM6", 7)
    await pd2.init()
    task1 = asyncio.create_task(pd1.read_float("MC?"))
    task2 = asyncio.create_task(pd2.read_float("MC?"))
    task5 = asyncio.create_task(pd1.write_current(2.0))
    task3 = asyncio.create_task(pd1.read_float("PC?"))
    task6 = asyncio.create_task(pd2.write_current(3.0))
    task4 = asyncio.create_task(pd2.read_float("PC?"))
    t_0 = time.time()
    await asyncio.wait({task1})
    dt = int((time.time() - t_0) * 1000.0)    # ms
    v1 = task1.result()
    v2 = task2.result()
    v3 = task3.result()
    v4 = task4.result()
    print('1: ', '%4d ms ' % dt, 'MC?=', v1, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
    print('2: ', '%4d ms ' % dt, 'MC?=', v2, 'to=', '%5.3f' % pd2.read_timeout, pd2.port, pd2.addr)
    print('3: ', '%4d ms ' % dt, 'PC?=', v3, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
    print('3: ', '%4d ms ' % dt, 'PC?=', v4, 'to=', '%5.3f' % pd2.read_timeout, pd2.port, pd2.addr)
    print('Elapsed: %4d ms ' % dt)

if __name__ == "__main__":
    # pd1 = TDKLambda("COM4", 6)
    # pd2 = TDKLambda("COM4", 7)
    # for i in range(5):
    #     t_0 = time.time()
    #     v1 = pd1.read_float("PC?")
    #     dt1 = int((time.time() - t_0) * 1000.0)    # ms
    #     print('1: ', '%4d ms ' % dt1,'PC?=', v1, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
    #     t_0 = time.time()
    #     v1 = pd1.read_float("MV?")
    #     dt1 = int((time.time() - t_0) * 1000.0)    # ms
    #     print('1: ', '%4d ms ' % dt1,'MV?=', v1, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
    #     t_0 = time.time()
    #     v1 = pd1.send_command("PV 1.0")
    #     dt1 = int((time.time() - t_0) * 1000.0)    # ms
    #     print('1: ', '%4d ms ' % dt1,'PV 1.0', v1, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
    #     t_0 = time.time()
    #     v1 = pd1.read_float("PV?")
    #     dt1 = int((time.time() - t_0) * 1000.0)    # ms
    #     print('1: ', '%4d ms ' % dt1,'PV?=', v1, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
    #     t_0 = time.time()
    #     v3 = pd1.read_all()
    #     dt1 = int((time.time() - t_0) * 1000.0)    # ms
    #     print('1: ', '%4d ms ' % dt1,'DVC?=', v3, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
    #     t_0 = time.time()
    #     v2 = pd2.read_float("PC?")
    #     dt2 = int((time.time() - t_0) * 1000.0)    # ms
    #     print('2: ', '%4d ms ' % dt2,'PC?=', v2, 'to=', '%5.3f' % pd2.read_timeout, pd2.port, pd2.addr)
    #     t_0 = time.time()
    #     v4 = pd2.read_all()
    #     dt1 = int((time.time() - t_0) * 1000.0)    # ms
    #     print('2: ', '%4d ms ' % dt1,'DVC?=', v4, 'to=', '%5.3f' % pd2.read_timeout, pd2.port, pd2.addr)
    #     time.sleep(0.1)

    asyncio.run(main())
