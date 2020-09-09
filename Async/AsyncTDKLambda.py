#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import socket
from threading import Lock
import time
import types
from datetime import datetime

from Async.AsyncSerial import *
from EmulatedLambda import FakeComPort
from serial import Timeout

from TDKLambda import *


@types.coroutine
def async_yield():
    """Skip one event loop run cycle.
    """
    yield

class FakeAsyncComPort(FakeComPort):
    SN = 9876543
    RESPONSE_DELAY = 0.055

    def __init__(self, port, *args, **kwargs):
        FakeComPort.SN = FakeAsyncComPort.SN
        FakeComPort.RESPONSE_DELAY = FakeAsyncComPort.RESPONSE_DELAY
        super().__init__(port, *args, **kwargs)
        self.async_lock = asyncio.Lock()

    async def reset_input_buffer(self, timeout=None):
        return True

    async def close(self):
        super().close()
        return True

    async def write(self, cmd, timeout=None):
        return super().write(cmd, timeout)

    async def read(self, size=1, timeout=None):
        v = super().read(size, timeout)
        #await asyncio.sleep(0)
        return v

    async def read_until(self, terminator=b'\r', size=None, timeout=None):
        result = bytearray()
        to = Timeout(timeout)
        while True:
            c = self.read(1)
            if c:
                result += c
                if terminator in result:
                    break
                if size is not None and len(result) >= size:
                    break
                to.restart(timeout)
            if to.expired():
                raise SerialTimeoutException('Read timeout')
            await asyncio.sleep(0)
        return bytes(result)


class AsyncTDKLambda(TDKLambda):
    LOG_LEVEL = logging.DEBUG
    tasks = []

    def create_com_port(self):
        # if com port already exists
        for d in TDKLambda.devices:
            if d.port == self.port and d.com is not None:
                self.com = d.com
                return self.com
        # create new port
        try:
            if self.EMULATE:
                self.com = FakeAsyncComPort(self.port)
            else:
                if self.port.upper().startswith('COM'):
                    self.com = AsyncSerial(self.port, baudrate=self.baud, timeout=0.0, write_timeout=0.0)
                else:
                    self.com = MoxaTCPComPort(self.port)
            self.com._current_addr = -1
            self.com._lock = Lock()
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

    async def init(self):
        if self.com is None:
            self.suspend()
            return
        # set device address
        response = await self.set_addr()
        if not response:
            msg = 'Uninitialized TDKLambda device has been added to list'
            self.logger.info(msg)
            self.add_to_list()
            return
        # read device type
        self.id = await self.read_device_id()
        if self.id.find('LAMBDA') >= 0:
            # determine max current and voltage from model name
            n1 = self.id.find('GEN')
            n2 = self.id.find('-')
            if n1 >= 0 and n2 > n1:
                try:
                    self.max_voltage = float(self.id[n1+3:n2])
                    self.max_current = float(self.id[n2+1:])
                except:
                    pass
        # read device serial number
        self.sn = await self.read_serial_number()
        # add device to list
        self.add_to_list()
        msg = 'TDKLambda: %s SN:%s has been created' % (self.id, self.sn)
        self.logger.info(msg)

    async def read_device_id(self):
        try:
            if await self._send_command(b'IDN?'):
                device_id = self.response[:-1].decode()
                return device_id
            else:
                return 'Unknown Device'
        except:
            return 'Unknown Device'

    async def read_serial_number(self):
        try:
            if await self._send_command(b'SN?'):
                serial_number = int(self.response[:-1].decode())
                return serial_number
            else:
                return -1
        except:
            return -1

    async def set_addr(self):
        if self.com is None:
            self.logger.warning('%s port is not configured' % self.port)
            return False
        if hasattr(self.com, '_current_addr'):
            a0 = self.com._current_addr
        else:
            a0 = -1
        # a0 = self.com._current_addr
        result = await self._send_command(b'ADR %d' % self.addr)
        if result and self.check_response(b'OK'):
            self.com._current_addr = self.addr
            self.logger.debug('Address %d -> %d' % (a0, self.addr))
            return True
        else:
            self.logger.error('Error set address %d -> %d' % (a0, self.addr))
            # if self.com is not None:
            #     self.com._current_addr = -1
            return False

    async def is_suspended(self):
        if time.time() < self.suspend_to:   # if suspension does not expire
            return True
        else:                               # suspension expires
            if self.suspend_flag:           # if it was suspended and expires
                await self.reset()
                if self.com is None:        # if initialization was not successful
                    # suspend again
                    self.suspend()
                    return True
                else:                       # initialization was successful
                    self.unsuspend()
                    return False
            else:                           # it was not suspended
                return False

    async def _send_command(self, cmd: bytes):
        self.command = cmd
        self.response = b''
        if not cmd.endswith(b'\r'):
            cmd += b'\r'
        t1 = time.time()
        try:
            while self.com.async_lock.locked():
                await asyncio.wait(0)
            if cmd.startswith(b'PV') or cmd.startswith(b'PC'):
                print('*')
                print(self.com.async_lock.locked())
                #return True
            async with self.com.async_lock:
                if cmd.startswith(b'PV') or cmd.startswith(b'PC'):
                    print('*')
                    #return True
                t0 = time.time()
                # write command
                if not await self.write(cmd):
                    return False
                # read response (to CR by default)
                result = await self.read_response()
                dt = (time.time()-t0)*1000.0
                dt1 = (time.time()-t1)*1000.0
                self.logger.debug('%s -> %s %s %4.0f ms %4.0f ms' % (cmd, self.response, result, dt, dt1))
                return result
        except:
            print(self.com.async_lock.locked())
            self.logger.debug("", exc_info=True)
            return result

    async def send_command(self, cmd):
        t0 = time.time()
        if await self.is_suspended():
            self.command = cmd
            self.response = b''
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
            if self.com._current_addr != self.addr:
                result = await self.set_addr()
                if not result:
                    self.suspend()
                    self.response = b''
                    return False
            result = await self._send_command(cmd)
            if not result:
                self.logger.warning('Error executing %s, repeated' % cmd)
                result = await self._send_command(cmd)
            if not result:
                self.logger.error('Repeated error executing %s' % cmd)
                self.suspend()
                self.response = b''
            dt = (time.time()-t0)*1000.0
            self.logger.info('%s -> %s %s %4.0f ms' % (cmd, self.response, result, dt))
            return result
        except:
            self.logger.error('Unexpected exception')
            self.logger.debug("", exc_info=True)
            self.suspend()
            self.response = b''
            return b''

    async def write(self, cmd):
        t0 = time.time()
        try:
            # clear input buffer
            await self.clear_input_buffer()
            # write command
            length = await self.com.write(cmd)
            if len(cmd) == length:
                result = True
            else:
                result = False
            self.logger.debug('%s %s bytes in %4.0f ms %s' % (cmd, length, (time.time() - t0) * 1000.0, result))
            return result
        except SerialTimeoutException:
            self.logger.error('Writing timeout')
            return False
        except:
            self.logger.error('Unexpected exception')
            self.logger.debug("", exc_info=True)
            return False

    async def clear_input_buffer(self):
        await self.com.reset_input_buffer()

    async def read_response(self):
        result = await self.read_until(CR)
        self.response = result
        if CR not in result:
            self.logger.error('Response %s without CR' % self.response)
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
            if result[m+1:] != cs:
                self.logger.error('Incorrect checksum')
                self.error_count.inc()
                return False
            self.error_count.clear()
            self.response = result[:m]
            return True

    async def read_until(self, terminator=b'\r', size=None):
        result = b''
        t0 = time.time()
        while not await self.is_suspended() and terminator not in result:
            r = await self.read(1)
            if len(r) <= 0:
                self.suspend()
                dt = (time.time() - t0) * 1000.0
                self.logger.debug('Read error %s %4.0f ms', result, dt)
                return result
            result += r
            if size is not None and len(result) >= size:
                break
        dt = (time.time() - t0) * 1000.0
        self.logger.debug('%s %s bytes in %4.0f ms', result, len(result), dt)
        return result

    async def read(self, size=1, retries=3):
        counter = 0
        result = b''
        while counter <= retries:
            try:
                t0 = time.time()
                result = await self._read(size, self.read_timeout)
                dt = time.time() - t0
                new_timeout = min(max(2.0 * dt, self.min_timeout), self.max_timeout)
                if new_timeout != self.read_timeout:
                    self.read_timeout = min(max(2.0 * dt, self.min_timeout), self.max_timeout)
                    self.logger.debug('read: %s timeout corrected to %5.2f s', result, self.read_timeout)
                return result
            except SerialTimeoutException:
                counter += 1
                self.read_timeout = min(1.5 * self.read_timeout, self.max_timeout)
                self.logger.debug('Reading timeout - increased to %5.2f s', self.read_timeout)
            except:
                counter = retries
                self.logger.info('Unexpected exception', exc_info=True)
                self.logger.debug('', exc_info=True)
        return result

    async def _read(self, size=1, timeout=None):
        result = b''
        to = Timeout(timeout)
        while len(result) < size:
            r = await self.com.read(1)
            if len(r) > 0:
                result += r
                to.restart(timeout)
            else:
                if to.expired():
                    self.logger.debug('Read timeout')
                    raise SerialTimeoutException('Read timeout')
            await asyncio.sleep(0)
        return result

    async def read_float(self, cmd):
        try:
            if not await self.send_command(cmd):
                return float('Nan')
            v = float(self.response)
        except:
            self.logger.debug('%s is not a float', self.response)
            v = float('Nan')
        return v

    async def read_all(self):
        if not await self.send_command(b'DVC?'):
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
            return vals
        else:
            return vals[:6]

    async def read_value(self, cmd, v_type=type(str)):
        try:
            if await self.send_command(cmd):
                v = v_type(self.response)
            else:
                v = None
        except:
            self.logger.info('Can not convert %s to %s' % (self.response, v_type))
            v = None
        return v

    async def read_bool(self, cmd):
        if not await self.send_command(cmd):
            return None
        response = self.response
        if response.upper() in (b'ON', b'1'):
            return True
        if response.upper() in (b'OFF', b'0'):
            return False
        self.check_response(response=b'Not boolean:' + response)
        return False

    async def write_value(self, cmd: bytes, value, expect=b'OK'):
        cmd = cmd.upper().strip() + b' ' + str.encode(str(value))[:10] + b'\r'
        result = await self.send_command(cmd)
        if result:
            return self.check_response(expect)
        else:
            return False

    async def read_output(self):
        if not await self.send_command(b'OUT?'):
            return None
        response = self.response.upper()
        if response.startswith((b'ON', b'1')):
            return True
        if response.startswith((b'OFF', b'0')):
            return False
        self.logger.info('Unexpected response %s' % response)
        return None

    async def write_output(self, value):
        if value:
            t_value = 'ON'
        else:
            t_value = 'OFF'
        return await self.write_value(b'OUT', t_value)

    async def write_voltage(self, value):
        return await self.write_value(b'PV', value)

    async def write_current(self, value):
        return await self.write_value(b'PC', value)

    async def read_current(self):
        return await self.read_value(b'MC?', v_type=float)

    async def read_programmed_current(self):
        return await self.read_value(b'PC?', v_type=float)

    async def read_voltage(self):
        return await self.read_value(b'MV?', v_type=float)

    async def read_programmed_voltage(self):
        return await self.read_value(b'PV?', v_type=float)

    async def reset(self):
        self.logger.debug('Resetting %s' % self)
        if self.com is None:
            self.create_com_port()
            await self.init()
            return
        # check working devices on same port
        for d in TDKLambda.devices:
            if d.port == self.port and d.initialized() and d != self:
                if asyncio.iscoroutinefunction(d.read_device_id):
                    did = await d.init()
                else:
                    did = d.init()
                if did.initialized():
                    await self.init()
                    return
        # no working devices on same port so try to recreate com port
        self.close_com_port()
        self.create_com_port()
        await self.init()
        return

    def create_task(self, action):
        task1 = asyncio.create_task(action)
        AsyncTDKLambda.tasks.append(task1)

    async def wait_all_tasks(self):
        await asyncio.wait(AsyncTDKLambda.tasks)


def task_completed_callback(task):
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S,%f")
    print(current_time, 'Task', task, 'completed, result:', task.result(), file=sys.stderr)


async def main():
    pd1 = AsyncTDKLambda("COM6", 6)
    await pd1.init()
    pd2 = AsyncTDKLambda("COM7", 7)
    await pd2.init()
    task1 = asyncio.create_task(pd1.read_float("MC?"))
    task1.add_done_callback(task_completed_callback)
    task2 = asyncio.create_task(pd2.read_float("MC?"))
    task3 = asyncio.create_task(pd1.read_float("PC?"))
    task4 = asyncio.create_task(pd2.read_float("PC?"))
    task5 = asyncio.create_task(pd1.write_current(2.0))
    task6 = asyncio.create_task(pd2.write_current(3.0))
    t_0 = time.time()
    await asyncio.wait({task1, task2, task3, task4, task5, task6})
    #await asyncio.wait({task1})
    dt = int((time.time() - t_0) * 1000.0)    # ms
    v1 = task1.result()
    v2 = task2.result()
    v3 = task3.result()
    v4 = task4.result()
    v5 = task5.result()
    v6 = task6.result()
    print('1: ', '%4d ms ' % dt, 'MC?=', v1, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
    print('2: ', '%4d ms ' % dt, 'MC?=', v2, 'to=', '%5.3f' % pd2.read_timeout, pd2.port, pd2.addr)
    print('3: ', '%4d ms ' % dt, 'PC?=', v3, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
    print('4: ', '%4d ms ' % dt, 'PC?=', v4, 'to=', '%5.3f' % pd2.read_timeout, pd2.port, pd2.addr)
    print('5: ', '%4d ms ' % dt, 'PC set', v5, 'to=', '%5.3f' % pd1.read_timeout, pd1.port, pd1.addr)
    print('6: ', '%4d ms ' % dt, 'PC set', v6, 'to=', '%5.3f' % pd2.read_timeout, pd2.port, pd2.addr)
    print('Elapsed: %4d ms ' % dt)

if __name__ == "__main__":
    asyncio.run(main())
