#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import os
import logging
import serial
from threading import Thread, Lock

LOG_LEVEL = logging.INFO
EMULATE = False
MAX_TIMEOUT = 1.5   # sec
MIN_TIMEOUT = 0.1   # sec
RETRIES = 3
SUSPEND = 2.0
SLEEP_SMALL = 0.015


class FakeComPort():
    SN = 123456
    RESPONSE = 0.035

    def __init__(self, port, *args, **kwargs):
        #super().__init__(self, port, args, kwargs)
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

    def read(self, *args):
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
            return b'%f, %f, %f, %f, 0.0, 0.0\r' % (self.mv[self.last_address], self.pv[self.last_address], self.mc[self.last_address], self.pc[self.last_address])
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


class TDKLambda():
    devices = []
    ports = []

    def __init__(self, port: str, addr=6, checksum=False, baudrate=9600, logger=None):
        #print('__init__', port, addr)

        # input parameters
        self.port = port.upper().strip()
        self.addr = addr
        self.check = checksum # = False
        self.baud = baudrate
        self.logger = logger
        self.auto_addr = True
        self.com_timeout = 0.0
        # create variables
        self.last_command = b''
        self.last_response = b''
        self.error_count = 0
        self.time = time.time()
        self.suspend_to = time.time()
        self.suspend_flag = False
        self.retries = 0
        # timeouts
        self.min_timeout = MIN_TIMEOUT
        self.max_timeout = MAX_TIMEOUT
        self.timeout = MIN_TIMEOUT
        self.timeout_cear_input = 0.5
        # sleep timings
        self.sleep_small = SLEEP_SMALL
        self.sleep_after_write = 0.02
        self.sleep_cear_input = 0.0
        # default com port, id, and serial number
        self.com = None
        self.id = None
        self.sn = None
        self.max_voltage = float('inf')
        self.max_current = float('inf')

        # configure logger
        if self.logger is None:
            self.logger = logging.getLogger(str(self))
            self.logger.propagate = False
            self.logger.setLevel(LOG_LEVEL)
            #log_formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
            #                                  datefmt='%H:%M:%S')
            f_str = '%(asctime)s,%(msecs)3d %(levelname)-7s [%(process)d:%(thread)d] %(filename)s ' \
                    '%(funcName)s(%(lineno)s) ' + '%s:%d ' % (self.port, self.addr) + '%(message)s'
            log_formatter = logging.Formatter(f_str, datefmt='%H:%M:%S')
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(log_formatter)
            if not self.logger.hasHandlers():
                self.logger.addHandler(console_handler)
            ##print('***', self.logger)

        # check if port and addr are in use
        for d in TDKLambda.devices:
            if d.port == self.port and d.addr == self.addr:
                self.logger.error('Address is in use')
                self.com = None
                # suspend for a year
                self.suspend(3.1e7)
                msg = 'Uninitialized TDKLambda device added to list'
                self.logger.debug(msg)
                TDKLambda.devices.append(self)
                return

        # assign com port
        for d in TDKLambda.devices:
            # if com port already created
            if d.port == self.port:
                if d.com is not None:
                    self.com = d.com
        if self.com is None:
            self.init_com_port()
        if self.com is None:
            self.suspend()

        if self.addr <= 0:
            self.logger.error('Wrong device address')
            self.suspend(3.1e7)

        # set device address and check response
        response = self.set_addr()
        if response:
            # initialize device type and serial number
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
            self.serial_number = self._send_command(b'SN?').decode()
            msg = 'TDKLambda: %s has been created' % self.id
            self.logger.info(msg)
        else:
            msg = 'Uninitialized TDKLambda device added to list'
            self.logger.info(msg)
        # add device to list
        TDKLambda.devices.append(self)

    def __del__(self):
        #print(self.port, self.addr, '__del__')
        if self in TDKLambda.devices:
            TDKLambda.devices.remove(self)
        self.close_com_port()

    def close_com_port(self):
        if self.com is not None:
            for d in TDKLambda.devices:
                if d.port == self.port:
                    return False
            self.com.close()
            return True
        return False

    def switch_off_com_port(self):
        try:
            self.com.close()
        except:
            pass
        self.com = None
        for d in TDKLambda.devices:
            if d.port == self.port:
                d.com = self.com

    def init_com_port(self):
        # try to close port
        try:
            if self.com is not None:
                self.com.close()
                self.logger.debug('COM port closed')
            else:
                for d in TDKLambda.devices:
                    if d.port == self.port:
                        if d.com is not None:
                            d.com.close()
                            d.com = None
                            self.logger.debug('COM port closed')
        except:
            self.logger.debug('COM port can not be closed')
        # try to create port
        try:
            if EMULATE:
                self.com = FakeComPort(self.port, baudrate=self.baud, timeout=self.com_timeout)
            else:
                self.com = serial.Serial(self.port, baudrate=self.baud, timeout=self.com_timeout)
            self.com.write_timeout = 0
            self.com.writeTimeout = 0
            self.logger.debug('COM port created')
            self.com.last_addr = -1
        except:
            self.com = None
            self.logger.error('Port creation error')
            self.logger.log(logging.DEBUG, "Exception Info:", exc_info=True)
        # update com for other devices with the same port
        for d in TDKLambda.devices:
            if d.port == self.port:
                d.com = self.com

    @staticmethod
    def checksum(cmd):
        s = 0
        for b in cmd:
            s += int(b)
        result = str.encode(hex(s)[-2:].upper())
        return result

    def clear_input_buffer(self):
        t0 = time.time()
        time.sleep(self.sleep_cear_input)
        #self.logger.debug('1 %4.0f ms', (time.time() - t0) * 1000.0)
        smbl = self.com.read(10000)
        #self.logger.debug('2 %4.0f ms', (time.time() - t0) * 1000.0)
        n = 0
        while len(smbl) > 0:
            if time.time() - t0 > self.timeout_cear_input:
                raise IOError('Clear input buffer timeout')
            time.sleep(self.sleep_cear_input)
            smbl = self.com.read(10000)
            n += 1
            #self.logger.debug('3 %4.0f ms', (time.time() - t0) * 1000.0)
        self.logger.debug('%d %4.0f ms', n, (time.time() - t0) * 1000.0)
        return n

    def _write(self, cmd):
        t0 = time.time()
        try:
            # clear input buffer
            self.clear_input_buffer()
            # write command
            self.com.write(cmd)
            time.sleep(self.sleep_after_write)
            self.logger.debug('%s %4.0f ms' % (cmd, (time.time() - t0) * 1000.0))
            return True
        except:
            self.logger.error('Exception during _write')
            self.logger.debug('%s %4.0f ms' % (cmd, (time.time() - t0) * 1000.0))
            self.logger.debug("Exception Info:", exc_info=True)
            return False

    def _send_command(self, cmd):
        try:
            cmd = cmd.upper().strip()
            if isinstance(cmd, str):
                cmd = str.encode(cmd)
            if cmd[-1] != b'\r'[0]:
                cmd += b'\r'
            # if operations with checksum
            if self.check:
                cs = self.checksum(cmd[:-1])
                cmd = b'%s$%s\r' % (cmd[:-1], cs)
            self.last_command = cmd
            t0 = time.time()
            # write command
            self._write(cmd)
            result = self.read_to_cr()
            self.logger.debug('%s -> %s %4.0f ms' % (cmd, result, (time.time()-t0)*1000.0))
            if result is None:
                self.logger.warning('Writing error, repeat %s' % cmd)
                self._write(cmd)
                result = self.read_to_cr()
                self.logger.debug('%s -> %s %4.0f ms' % (cmd, result, (time.time() - t0) * 1000.0))
                if result is None:
                    self.logger.error('Repeated writing error')
                    self.suspend()
                    self.last_response = b''
                    result = b''
            return result
        except:
            self.logger.error('Unexpected exception')
            self.logger.log(logging.DEBUG, "Exception Info:", exc_info=True)
            self.suspend()
            self.switch_off_com_port()
            self.last_response = b''
            return b''

    def send_command(self, cmd):
        if self.suspended():
            self.last_command = cmd
            self.last_response = b''
            return b''
        if self.auto_addr and self.com._current_addr != self.addr:
            result = self.set_addr()
            if result:
                return self._send_command(cmd)
            else:
                return b''
        else:
            return self._send_command(cmd)

    def check_response(self, expect=b'OK', response=None):
        if self.suspended():
            return False
        if response is None:
            response = self.last_response
        if not response.startswith(expect):
            msg = 'Unexpected response %s (not %s)' % (response, expect)
            self.logger.info(msg)
            return False
        return True

    def _read(self):
        t0 = time.time()
        data = self.com.read(10000)
        dt = time.time() - t0
        n = 0
        #self.logger.debug('%s %d %4.0f ms' % (data, n, (time.time() - t0) * 1000.0))
        while len(data) <= 0:
            if dt > self.timeout:
                self.timeout = min(2.0 * self.timeout, self.max_timeout)
                msg = 'Reading timeout, increased to %5.2f s' % self.timeout
                self.logger.info(msg)
                self.logger.debug('%s %d %4.0f ms' % (data, n, (time.time() - t0) * 1000.0))
                return None
            time.sleep(self.sleep_small)
            data = self.com.read(10000)
            dt = time.time() - t0
            n += 1
        dt = time.time() - t0
        self.timeout = max(2.0 * dt, self.min_timeout)
        #self.logger.debug('%s %d %4.0f ms' % (data, n, (time.time() - t0) * 1000.0))
        return data

    def read(self):
        if self.suspended():
            return None
        t0 = time.time()
        data = None
        try:
            data = self._read()
            if data is None:
                self.logger.debug('Retry reading')
                time.sleep(self.sleep_after_write)
                data = self._read()
            if data is None:
                self.logger.warning('Retry reading ERROR')
            self.logger.debug('%s %4.0f ms' % (data, (time.time() - t0) * 1000.0))
            return data
        except:
            self.logger.error('Exception during read. Switching COM port OFF.')
            self.logger.log(logging.DEBUG, "Exception Info:", exc_info=True)
            self.suspend()
            self.switch_off_com_port()
            self.logger.debug('%s %4.0f ms' % (data, (time.time() - t0) * 1000.0))
            return None

    def suspend(self, duration=5.0):
        msg = 'Suspended for %5.2f sec' % duration
        self.logger.warning(msg)
        self.suspend_to = time.time() + duration
        self.suspend_flag = True

    def suspended(self):
        if time.time() < self.suspend_to:
            # suspension does not expire
            return True
        else:
            if self.suspend_flag:
                # it was suspended and suspension expires
                if self.com is None:
                    # problem with com port
                    self.logger.debug('Initiating the COM port')
                    self.init_com_port()
                    if self.com is None:
                        self.suspend()
                        return True
                    # try to set device address
                    result = self._set_addr()
                    if result:
                        self.suspend_flag = False
                        return False
                    else:
                        self.suspend()
                        return True
                else:
                    # problem with device
                    # try to set device address
                    result = self._set_addr()
                    if result:
                        self.suspend_flag = False
                        return False
                    else:
                        self.suspend()
                        return True
            else:
                # it was not suspended
                return False

    def read_to_cr(self):
        result = b''
        data = self.read()
        while data is not None:
            result += data
            n = result.find(b'\r')
            if n >= 0:
                n1 = result[n+1:].find(b'\r')
                if n1 >= 0:
                    self.logger.warning('Second CR in response %s, %s used' % (result, result[n+1:]))
                    result = result[n+1:]
                    n = result.find(b'\r')
                m = n
                self.last_response = result[:n]
                if self.check:
                    m = result.find(b'$')
                    if m < 0:
                        self.logger.error('No checksum')
                        return None
                    else:
                        cs = self.checksum(result[:m])
                        if result[m+1:n] != cs:
                            self.logger.error('Incorrect checksum')
                            return None
                        self.error_count = 0
                        return result[:m]
                self.error_count = 0
                return result[:m]
            data = self.read()
        self.logger.warning('Response without CR')
        self.last_response = result
        return None

    def _set_addr(self):
        if hasattr(self.com, '_current_addr'):
            a0 = self.com._current_addr
        else:
            a0 = -1
        self._send_command(b'ADR %d' % abs(self.addr))
        if self.check_response():
            #self.addr = abs(self.addr)
            self.com._current_addr = self.addr
            self.logger.debug('Set address %d -> %d' % (a0, self.addr))
            return True
        else:
            self.logger.error('Error set address %d -> %d' % (a0, self.addr))
            #self.addr = -abs(self.addr)
            if self.com is not None:
                self.com._current_addr = -1
            return False

    def set_addr(self):
        if self.suspended():
            return False
        count = 0
        result = self._set_addr()
        while count < 2:
            if result:
                return True
            count +=1
            self.logger.info('Set address repeated')
            result = self._set_addr()
        if result:
            return True
        self.logger.error('Cannot repeatedly set address')
        self.suspend()
        if hasattr(self.com, '_current_addr'):
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
        print('1: ', '%4d ms ' % dt1,'PC?=', v1, 'to=', '%5.3f' % pd1.timeout, pd1.port, pd1.addr)
        t0 = time.time()
        v1 = pd1.read_float("MV?")
        dt1 = int((time.time()-t0)*1000.0)    #ms
        print('1: ', '%4d ms ' % dt1,'MV?=', v1, 'to=', '%5.3f' % pd1.timeout, pd1.port, pd1.addr)
        t0 = time.time()
        v1 = pd1.send_command("PV 1.0")
        dt1 = int((time.time()-t0)*1000.0)    #ms
        print('1: ', '%4d ms ' % dt1,'PV 1.0', v1, 'to=', '%5.3f' % pd1.timeout, pd1.port, pd1.addr)
        t0 = time.time()
        v1 = pd1.read_float("PV?")
        dt1 = int((time.time()-t0)*1000.0)    #ms
        print('1: ', '%4d ms ' % dt1,'PV?=', v1, 'to=', '%5.3f' % pd1.timeout, pd1.port, pd1.addr)
        t0 = time.time()
        v3 = pd1.read_all()
        dt1 = int((time.time()-t0)*1000.0)    #ms
        print('1: ', '%4d ms ' % dt1,'DVC?=', v3, 'to=', '%5.3f' % pd1.timeout, pd1.port, pd1.addr)
        t0 = time.time()
        v2 = pd2.read_float("PC?")
        dt2 = int((time.time()-t0)*1000.0)    #ms
        print('2: ', '%4d ms ' % dt2,'PC?=', v2, 'to=', '%5.3f' % pd2.timeout, pd2.port, pd2.addr)
        t0 = time.time()
        v4 = pd2.read_all()
        dt1 = int((time.time()-t0)*1000.0)    #ms
        print('2: ', '%4d ms ' % dt1,'DVC?=', v4, 'to=', '%5.3f' % pd2.timeout, pd2.port, pd2.addr)
        time.sleep(0.1)
