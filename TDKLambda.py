#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import os
import logging
import serial

MAX_TIMEOUT = 1.5   # sec
MIN_TIMEOUT = 0.1   # sec
RETRIES = 3
SUSPEND = 1.0
SLEEP = 0.03
SLEEP_SMALL = 0.005
MAX_ERROR_COUNT = 4

class TDKLambda():
    devices = []
    ports = []

    def __init__(self, port: str, addr=6, checksum=False, auto_addr = True, baudrate=9600, timeout=0, logger=None):
        #print('__init__', port, addr)
        # create variables
        self.last_command = b''
        self.last_response = b''
        self.error_count = 0
        self.auto_addr = auto_addr
        self.check = checksum
        self.time = time.time()
        self.suspend_to = time.time()
        self.retries = 0
        self.timeout = MIN_TIMEOUT
        if logger is None:
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.INFO)
            #log_formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
            #                                  datefmt='%H:%M:%S')
            log_formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                                              datefmt='%H:%M:%S')
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(log_formatter)
            self.logger.addHandler(console_handler)
        else:
            self.logger = logger
        self.port = port.upper().strip()
        self.addr = addr
        self.com = None
        # check if port an addr are in use
        for d in TDKLambda.devices:
            if d.port == self.port and d.addr == self.addr:
                msg = 'Address %s is in use for port %s' % (self.addr, self.port)
                self.logger.error(msg)
                return
        # assign com port
        for d in TDKLambda.devices:
            # com port alredy created
            if d.port == self.port:
                self.com = d.com
        if self.com is None:
            # create new port
            try:
                self.com = serial.Serial(self.port, baudrate=baudrate, timeout=timeout)
            except:
                self.com = None
                msg = 'Port %s open error' % self.port
                self.logger.error(msg)
                return
        # set device address and check 'OK' response
        response = self.set_addr()
        if response:
            self.com._current_addr = self.addr
        else:
            self.com = None
            msg = 'Error address set for %s : %d' % (self.port, self.addr)
            # print(msg)
            self.logger.error(msg)
            return
        # initialize device type and serial number
        self.id = self._send_command(b'IDN?').decode()
        # determine max current and voltage from model name
        self.max_voltage = float('inf')
        self.max_current = float('inf')
        n1 = self.id.find('GEN')
        n2 = self.id.find('-')
        if n1 >= 0 and n2 >= 0:
            try:
                self.max_voltage = float(self.id[n1:n2])
                self.max_current = float(self.id[n2+1:])
            except:
                pass
        self.serial_number = self._send_command(b'SN?').decode()
        # add device to list
        TDKLambda.devices.append(self)
        msg = 'TDKLambda %s at %s : %d has been created' % (self.id, self.port, self.addr)
        self.logger.info(msg)

    def __del__(self):
        #print('__del__', self.port, self.addr)
        if self in TDKLambda.devices:
            TDKLambda.devices.remove(self)
        close_flag  = True
        for d in TDKLambda.devices:
            if d.port == self.port:
                close_flag = False
                break
        if close_flag:
            self.com.close()

    @staticmethod
    def checksum(cmd):
        s = 0
        for b in cmd:
            s += int(b)
        result = str.encode(hex(s)[-2:])
        return result.upper()

    def _send_command(self, cmd):
        # print('_send_command: ', self.port, self.addr, end='')
        #t0 = time.time()
        if self.com is None:
            #print('-offfline-')
            msg = 'Device %s : %d is offline' % (self.port, self.addr)
            self.logger.debug(msg)
            return b''
        if time.time() < self.suspend_to:
            #print('-suspended-')
            msg = 'Device %s : %d is suspended' % (self.port, self.addr)
            self.logger.debug(msg)
            return b''
        if isinstance(cmd, str):
            cmd = str.encode(cmd)
        if cmd[-1] != b'\r'[0]:
            cmd += b'\r'
        cmd = cmd.upper().strip()
        if self.check:
            cs = self.checksum(cmd)
            cmd = b'%s$%s\r' % (cmd[:-1], cs)
        self.last_command = cmd
        # clear input buffer
        self.com.read(10000)
        #print('t1=', time.time() - t0, end='')
        self.com.write(cmd)
        time.sleep(SLEEP)
        result = self.read_to_cr()
        if result is None:
            msg = 'Writing error for %s : %d %s, repeat command' % (self.port, self.addr, cmd)
            self.logger.warning(msg)
            time.sleep(SLEEP)
            # clear input buffer
            self.com.read(10000)
            self.com.write(cmd)
            time.sleep(SLEEP)
            result = self.read_to_cr()
            if result is None:
                msg = 'Repeated writing error for %s : %d %s, suspended' % (self.port, self.addr, cmd)
                self.logger.error(msg)
                self.suspend()
                result = b''
        #print(result, 't2=', time.time() - t0)
        return result

    def send_command(self, cmd):
        if self.auto_addr and self.com._current_addr != self.addr:
            result = self.set_addr()
            if result:
                self.com._current_addr = self.addr
                result = self._send_command(cmd)
            else:
                self.com._current_addr = -1
                self.suspend()
                result = b''
        else:
            result = self._send_command(cmd)
        #print('send_command', cmd, result)
        return result

    def check_response(self, expect=b'OK', response=None):
        if self.com is None or self.is_suspended():
            # do not shout if device is suspended
            return False
        if response is None:
            response = self.last_response
        if not response.startswith(expect):
            msg = 'Unexpected response %s (%s) from %s : %d' % (response, expect, self.port, self.addr)
            self.logger.debug(msg)
            msg = 'Too many unexpected responses from %s : %d, suspended' % (self.port, self.addr)
            self.inc_error_count(msg)
            return False
        self.error_count = 0
        return True

    def _read(self):
        if self.com is None or time.time() < self.suspend_to:
            return None
        time0 = time.time()
        data = self.com.read(10000)
        dt = time.time() - time0
        #n = 0
        while len(data) <= 0:
            if dt > self.timeout:
                self.timeout = min(1.5*self.timeout, MAX_TIMEOUT)
                msg = 'Timeout increased to %f for %s : %d' % (self.timeout, self.port, self.addr)
                self.logger.debug(msg)
                #print(' ')
                return None
            time.sleep(SLEEP / 10.0)
            data = self.com.read(10000)
            dt = time.time() - time0
            #print('_read', n, len(data), dt)
            #if n % 100 == 0:
            #    print('*', end='')
            #n += 1
        #print(' ')
        self.suspend_to = time.time() - 1.0
        dt = time.time() - time0
        self.timeout = max(2.0*dt, MIN_TIMEOUT)
        msg = 'Timeout set to %f for %s : %d' % (self.timeout, self.port, self.addr)
        self.logger.debug(msg)
        #print(msg)
        return data

    def read(self):
        #time0 = time.time()
        if self.com is None or time.time() < self.suspend_to:
            return None
        data = self._read()
        while data is None:
            self.retries += 1
            if self.retries >= RETRIES:
                self.suspend()
                return None
            # dt = time.time() - time0
            # print('read1', dt)
            data = self._read()
        #dt = time.time() - time0
        #print('read2', dt)
        self.retries = 0
        return data

    def inc_error_count(self, msg=None):
        self.error_count += 1
        if self.error_count > MAX_ERROR_COUNT:
            if msg is None:
                msg = 'Error count exceeded for device at %s : %d' % (self.port, self.addr)
            self.logger.debug(msg)
            self.suspend()
            return True
        return False

    def suspend(self, msg=None, duration=SUSPEND):
        if msg is None:
            msg = 'Device at %s : %d is suspended for %d sec' % (self.port, self.addr, duration)
        self.logger.debug(msg)
        self.suspend_to = time.time() + duration
        self.error_count = 0
        self.com.send_break()
        self.com.reset_input_buffer()
        self.com.reset_output_buffer()
        time.sleep(SLEEP)
        self.com.read(10000)

    def is_suspended(self):
        return time.time() < self.suspend_to

    def read_to_cr(self):
        result = b''
        data = self.read()
        while data is not None:
            self.suspend_to = time.time()
            result += data
            if b'\r' in data:
                n = result.find(b'\r')
                m = n
                self.last_response = result[:n]
                if self.check:
                    m = result.find(b'$')
                    if m < 0:
                        self.logger.error('Incorrect checksum')
                        self.inc_error_count()
                        return result[:m]
                    else:
                        cs = self.checksum(result[:m])
                        if result[m+1:n] != cs:
                            self.logger.error('Incorrect checksum')
                            self.inc_error_count()
                        else:
                            self.error_count = 0
                        return result[:m]
                return result[:m]
            data = self.read()
        self.logger.debug('Response without CR')
        self.inc_error_count()
        #dt = time.time() - time0
        #print('read_to_cr2', dt)
        self.last_response = result
        return result

    def set_addr(self):
        self._send_command(b'ADR %d' % self.addr)
        if self.check_response():
            return True
        else:
            msg = 'Cannot set address for %s : %d' % (self.port, self.addr)
            self.logger.debug(msg)
            return False

    def read_float(self, cmd):
        #t0 = time.time()
        reply = b''
        try:
            reply = self.send_command(cmd)
            #dt = time.time() - t0
            #print('read_float1', cmd, reply, dt)
            v = float(reply)
        except:
            self.check_response(response=b'Not a float: '+reply)
            v = float('Nan')
        #dt = time.time() - t0
        #print('read_float2', dt)
        return v

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
        cmd = cmd.upper() + b' ' + str.encode(str(value))[:10] + b'\r'
        self.send_command(cmd)
        return self.check_response(expect)

if __name__ == "__main__":
    pdl = TDKLambda("COM3", 6)
    pd2 = TDKLambda("COM3", 7)
    while True:
        t0 = time.time()
        v1 = pdl.read_float("PC?")
        dt1 = int((time.time()-t0)*1000.0)    #ms
        print('1: ', '%4d ms ' % dt1,'PC?=', v1, 'to=', '%5.3f' % pdl.timeout, pdl.port, pdl.addr)
        #t0 = time.time()
        #v2 = pd2.read_float("PC?")
        #dt2 = int((time.time()-t0)*1000.0)    #ms
        #print('2: ', '%4d ms '%dt2,'PC?=', v2, 'to=', '%5.3f'%pdl.timeout, pd2.port, pd2.addr)
