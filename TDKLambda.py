#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import os
import logging
import serial

MAX_TIMEOUT = 1.5   # sec
MIN_TIMEOUT = 0.1   # sec
RETRIES = 3
SUSPEND = 5.0
SLEEP = 0.03
MAX_ERROR_COUNT = 4

class TDKLambda():
    devices = []
    ports = []

    def __init__(self, port: str, addr=6, checksum=False, auto_addr = True, baudrate=9600, timeout=0, logger=None):
        print('__init__', port, addr)
        # create variables
        self.last_command = b''
        self.last_response = b''
        self.error_count = 0
        self.auto_addr = auto_addr
        self.com = None
        self.check = checksum
        self.time = time.time()
        self.suspend_to = time.time()
        self.retries = 0
        self.timeout = 2.0*MIN_TIMEOUT
        self.sleep = SLEEP
        if logger is None:
            #self.logger = logging.getLogger()
            #self.logger.setLevel(logging.DEBUG)
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
        self.port = port.upper()
        self.addr = addr
        # check if port an addr are in use
        for d in TDKLambda.devices:
            if d.port == self.port and d.addr == self.addr:
                msg = 'Address %s is in use for port %s device %s' % (self.addr, self.port, self)
                self.logger.error(msg)
                return
        # assign com port
        for p in TDKLambda.ports:
            # com port exists
            if p.name == self.port:
                self.com = p
                p._addr_list.append(self.addr)
        if self.com is None:
            # create new port
            try:
                self.com = serial.Serial(self.port, baudrate=baudrate, timeout=timeout)
                self.com._addr_list = [self.addr]
                TDKLambda.ports.append(self.com)
            except:
                self.com = None
                msg = 'Error open %s port' % self.port
                print(msg)
                self.logger.error(msg)
                return
        # set device address and check 'OK' response
        response = self.set_addr()
        if response:
            self.com._current_addr = self.addr
        else:
            self.com._current_addr = -1
        # initialize device type and serial number
        self.id = self._send_command(b'IDN?')
        self.serial_number = self._send_command(b'SN?')
        # add device to list
        TDKLambda.devices.append(self)
        msg = 'TDKLambda device at %s : %d has been created' % (self.port, self.addr)
        self.logger.info(msg)

    def __del__(self):
        print('__del__', self.port, self.addr)
        if self in TDKLambda.devices:
            TDKLambda.devices.remove(self)
        if self.com is not None:
            if self.addr in self.com._addr_list:
                self.com._addr_list.remove(self.addr)
            if len(self.com._addr_list) <= 0:
                self.com.close()
                TDKLambda.ports.remove(self.com)

    @staticmethod
    def checksum(cmd):
        s = 0
        for b in cmd:
            s += int(b)
        result = str.encode(hex(s)[-2:])
        return result.upper()

    def _send_command(self, cmd):
        #t0 = time.time()
        if self.com is None or time.time() < self.suspend_to:
            return b''
        if isinstance(cmd, str):
            cmd = str.encode(cmd)
        if cmd[-1] != b'\r'[0]:
            cmd += b'\r'
        cmd = cmd.upper()
        if self.check:
            cs = self.checksum(cmd)
            cmd = b'%s$%s\r' % (cmd[:-1], cs)
        self.last_command = cmd
        self.logger.debug(b'Send: '+cmd)
        #if self.com.in_waiting() > 0:
        #    self.com.reset_input_buffer()
        self.com.read(10000)
        #dt = time.time() - t0
        #print('send_command1', dt)
        self.com.write(cmd)
        time.sleep(self.sleep)
        result = self.read_to_cr()
        if result is None:
            msg = 'Writing error, repeat command %s' % cmd
            self.logger.warning(msg)
            # if self.com.in_waiting() > 0:
            #    self.com.reset_input_buffer()
            self.com.read(10000)
            self.com.write(cmd)
            time.sleep(self.sleep)
            result = self.read_to_cr()
            if result is None:
                msg = 'Repeated writing error for %s' % cmd
                self.logger.error(msg)
                self.suspend()
                result = b''
        #dt = time.time() - t0
        #print('send_command2', dt)
        self.logger.debug(b'Send result: ' + result)
        return result

    def send_command(self, cmd):
        if self.auto_addr and self.com._current_addr != self.addr:
            if self.set_addr():
                self.com._current_addr = self.addr
                return self._send_command(cmd)
            else:
                self.com._current_addr = -1
                self.inc_error_count()
                return b''

    def check_response(self, expect=b'OK', response=None):
        if self.com is None or time.time() < self.suspend_to:
            # do not shout if device is suspended
            return False
        if response is None:
            response = self.last_response
        if not response.startswith(expect):
            msg = 'Unexpected response %s from %s : %d' % (response, self.port, self.addr)
            #print(msg)
            self.logger.warning(msg)
            msg = 'Too many unexpected responses from %s : %d, suspended' % (self.port, self.addr)
            self.suspend(msg)
            return False
        self.error_count = 0
        return True

    def _read(self):
        if self.com is None or time.time() < self.suspend_to:
            return None
        time0 = time.time()
        data = self.com.read(10000)
        dt = time.time() - time0
        #n = 1
        while len(data) <= 0:
            if dt > self.timeout:
                self.timeout = min(1.5*dt, MAX_TIMEOUT)
                msg = 'Timeout increased to %f' % self.timeout
                self.logger.info(msg)
                return None
            data = self.com.read(10000)
            #dt = time.time() - time0
            #n += 1
            #print('_read', n, len(data), dt)
        self.retries = 0
        self.time = time.time()
        #self.suspend = time.time()
        self.timeout = max(2.0*dt, MIN_TIMEOUT)
        #msg = 'Timeout set to %f' % self.timeout
        #self.logger.debug(msg)
        #print('_read', dt)
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

    def inc_error_count(self, msg='Device is suspended for %d sec'%SUSPEND):
        self.error_count += 1
        if self.error_count > MAX_ERROR_COUNT:
            self.suspend(msg)
            return True
        return False

    def suspend(self, msg='Device is suspended for %d sec'%SUSPEND):
        self.suspend_to = time.time()
        self.error_count = 0
        self.logger.error(msg)
        self.com.send_break()
        self.com.reset_input_buffer()
        self.com.reset_output_buffer()

    def read_to_cr(self):
        #time0 = time.time()
        result = b''
        data = self.read()
        while data is not None:
            result += data
            if b'\r' in data:
                n = result.find(b'\r')
                self.last_response = result[:n]
                if self.check:
                    m = result.find(b'$')
                    if m < 0:
                        self.logger.error('Incorrect checksum')
                        self.inc_error_count()
                    else:
                        cs = self.checksum(result[:m])
                        if result[m+1:n] != cs:
                            self.logger.error('Incorrect checksum')
                            self.inc_error_count()
                        else:
                            self.error_count = 0
                #dt = time.time() - time0
                #print('read_to_cr1', dt)
                return result[:n]
            data = self.read()
        self.logger.error('Response without CR')
        self.inc_error_count()
        #dt = time.time() - time0
        #print('read_to_cr2', dt)
        self.last_response = result
        return result

    def set_addr(self):
        self._send_command(b'ADR %d' % self.addr)
        return self.check_response()

    def read_float(self, cmd):
        #t0 = time.time()
        reply = b''
        try:
            reply = self.send_command(cmd)
            v = float(reply)
        except:
            self.check_response(response=b'Not a float: '+reply)
            v = float('Nan')
        #dt = time.time() - t0
        #print('read_value', dt)
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
    while False:
        t0 = time.time()
        v1 = pdl.read_float("PC?")
        dt1 = int((time.time()-t0)*1000.0)    #ms
        print('1: ', '%4d ms ' % dt1,'PC?=', v1, 'to=', '%5.3f' % pdl.timeout)
        t0 = time.time()
        v2 = pd2.read_float("PC?")
        dt2 = int((time.time()-t0)*1000.0)    #ms
        print('2: ', '%4d ms '%dt2,'PC?=', v2, 'to=', '%5.3f'%pdl.timeout)
