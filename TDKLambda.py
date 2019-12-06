#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import os
import logging
import serial
# chose an implementation, depending on os
if os.name == 'nt':  # sys.platform == 'win32':
    from serial.tools.list_ports_windows import comports
elif os.name == 'posix':
    from serial.tools.list_ports_posix import comports
else:
    raise ImportError("No implementation for platform ('{}') is available".format(os.name))

MAX_TIMEOUT = 1.5   # sec
MIN_TIMEOUT = 0.1   # sec
RETRIES = 3
SUSPEND = 5.0
SLEEP = 0.03

class TDKLambda():
    devices = []
    ports = []

    def __init__(self, port: str, addr=6, checksum=False, baudrate=9600, timeout=0, logger=None):
        # create variables
        self.last_response = b''
        self.unexpected_count = 0
        self.auto_addr = True
        self.last_command = b''
        self.com = None
        self.check = checksum
        self.time = time.time()
        self.suspend = time.time()
        #reconnect_timeout = self.get_device_property('reconnect_timeout', 5000)
        self.retries = RETRIES
        self.timeout = 2.0*MIN_TIMEOUT
        self.sleep = SLEEP
        if logger is None:
            self.logger = logging.getLogger()
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
        if self.com is None:
            # create new port
            try:
                self.com = serial.Serial(self.port, baudrate=baudrate, timeout=timeout)
                TDKLambda.ports.append(self.port)
            except:
                self.com = None
                msg = 'Error open %s port' % self.port
                self.logger.error(msg)
                return
        # set device address and check 'OK' response
        self.online = self.set_addr()
        # initialize device type and serial number
        self.id = self._send_command(b'IDN?')
        self.serial_number = self._send_command(b'SN?')
        # add device to list
        TDKLambda.devices.append(self)
        msg = 'TDKLambda device at %s %d has been created' % (self.port, self.addr)
        self.logger.info(msg)

    @staticmethod
    def checksum(cmd):
        s = 0
        for b in cmd:
            s += int(b)
        result = str.encode(hex(s)[-2:])
        return result.upper()

    def _send_command(self, cmd):
        if self.com is None or time.time() < self.suspend:
            return b''
        if isinstance(cmd, str):
            cmd = str.encode(cmd)
        if cmd[-1] != b'\r':
            cmd += b'\r'
        cmd = cmd.upper()
        self.last_command = cmd
        #t0 = time.time()
        #if self.com.in_waiting() > 0:
        #    self.com.reset_input_buffer()
        self.com.read(10000)
        #dt = time.time() - t0
        #print('send_command', dt)
        self.com.write(cmd)
        time.sleep(self.sleep)
        result = self.read_to_cr()
        if result is None:
            msg = 'Repeat command %s' % cmd
            self.logger.warning(msg)
            self.com.reset_input_buffer()
            self.com.write(cmd)
            time.sleep(self.sleep)
            result = self.read_to_cr()
        return result

    def send_command(self, cmd):
        if self.auto_addr:
            self.set_addr()
        return self._send_command(cmd)

    def _read(self):
        if self.com is None or time.time() < self.suspend:
            return None
        time0 = time.time()
        data = self.com.read(10000)
        dt = time.time() - time0
        #n = 1
        while len(data) <= 0:
            if dt > self.timeout:
                self.timeout = min(1.5*dt, MAX_TIMEOUT)
                self.timeout_flag = True
                msg = 'Timeout increase to %f' % self.timeout
                self.logger.info(msg)
                # resend command
                self._send_command(self.last_command)
                return None
            data = self.com.read(10000)
            dt = time.time() - time0
            #n += 1
            #print('_read', n, len(data), dt)
        self.time = time.time()
        self.suspend = time.time()
        self.timeout = max(2.0*dt, MIN_TIMEOUT)
        self.timeout_flag = False
        #msg = 'Timeout decrease to %f' % self.timeout
        #self.logger.error(msg)
        #print('_read', dt)
        return data

    def read(self):
        #time0 = time.time()
        if self.com is None or time.time() < self.suspend:
            return None
        count = self.retries
        data = None
        while data is None:
            data = self._read()
            count -= 1
            if count < 0:
                msg = 'No response from %s addr %d - suspended' % (self.port, self.addr)
                self.logger.error(msg)
                self.suspend = time.time() + SUSPEND
                return None
        #dt = time.time() - time0
        #print('read', dt)
        return data

    def read_to_cr(self):
        #time0 = time.time()
        result = b''
        data = self.read()
        while data is not None:
            result += data
            if b'\r' in data:
                n = result.find(b'\r')
                self.last_response = result[:n]
                #dt = time.time() - time0
                #print('read_to_cr1', dt)
                return result
            data = self.read()
        self.last_response = result
        #dt = time.time() - time0
        #print('read_to_cr2', dt)
        return result

    def set_addr(self):
        result = self._send_command(b'ADR %d\r' % self.addr)
        if not result.startswith(b'OK'):
            self.check_response(result)
            return False
        return True

    def read_float(self, cmd):
        #t0 = time.time()
        reply = b''
        try:
            reply = self.send_command(cmd)
            v = float(reply)
        except:
            self.check_response(response=b'Not a float:'+reply)
            v = float('Nan')
        #dt = time.time() - t0
        #print('read_value', dt)
        return v

    def read_value(self, cmd, vtype=float):
        #t0 = time.time()
        reply = b''
        try:
            reply = self.send_command(cmd)
            v = vtype(reply)
        except:
            self.check_response(b'!?!')
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
        msg = 'Ambiguous response %s for boolean, False returned.' % response
        self.logger.warning(msg)
        return False

    def write_value(self, cmd, value, response=b'OK'):
        cmd = cmd.upper() + b' ' + str.encode(str(value))[:10] + b'\r'
        self.send_command(cmd)
        return self.check_response(response)

    def check_response(self, expect=b'OK', response=None):
        if response is None:
            response = self.last_response
        if not response.startswith(expect):
            self.unexpected_count += 1
            msg = 'Unexpected response %s from %s : %d' % (response, self.port, self.addr)
            print(msg)
            #self.logger.error(msg)
            return False
        self.unexpected_count = 0
        return True

if __name__ == "__main__":
    pass
    pdl = TDKLambda("COM3", 6)
    while True:
        t0 = time.time()
        v = pdl.read_float("PC?")
        dt = time.time()-t0
        print('%5.3f'%dt,'PC?=', v, 'timeout=', '%5.3f'%pdl.timeout)
