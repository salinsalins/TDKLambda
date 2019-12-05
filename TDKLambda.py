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

class TDKLambda():
    devices = []
    ports = []

    def __init__(self, port: str, addr=6, checksum=False, baudrate=9600, timeout=0, logger=None):
        # create variables
        self.last_command = b''
        self.com = None
        self.check = checksum
        self.time = time.time()
        self.suspend = time.time()
        #reconnect_timeout = self.get_device_property('reconnect_timeout', 5000)
        self.retries = RETRIES
        self.timeout = 2.0*MIN_TIMEOUT
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
        # add device to list
        TDKLambda.devices.append(self)
        msg = 'TDKLambda device at %s %d has been created' % (self.port, self.addr)
        self.logger.info(msg)
        # initialize device type
        #self.type = self.read_devicetype()

    @staticmethod
    def checksum(cmd):
        s = 0
        for b in cmd:
            s += int(b)
        result = str.encode(hex(s)[-2:])
        return result.upper()

    def send_command(self, cmd):
        if self.com is None or time.time() < self.suspend:
            return b''
        if isinstance(cmd, str):
            cmd = str.encode(cmd)
        if cmd[-1] != b'\r':
            cmd += b'\r'
        self.last_command = cmd
        self.com.reset_input_buffer()
        self.com.write(cmd)
        result = self.read_to_cr()
        return result

    def _read(self):
        if self.com is None or time.time() < self.suspend:
            return None
        time0 = time.time()
        data = self.com.read(100)
        dt = time.time() - time0
        while len(data) <= 0:
            if dt > self.timeout:
                self.timeout = min(1.5*dt, MAX_TIMEOUT)
                self.timeout_flag = True
                # resend command
                self.send_command(self.last_command)
                return None
            data = self.com.read(100)
            dt = time.time() - time0
        self.time = time.time()
        self.suspend = time.time()
        self.timeout = max(2.0*dt, MIN_TIMEOUT)
        self.timeout_flag = False
        return data

    def read(self):
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
        return data

    def read_to_cr(self):
        result = b''
        data = self.read()
        while data is not None:
            result += data
            if b'\r' in data:
                return result
            data = self.read()
        return result

    def set_addr(self):
        result = self.send_command(b'ADR %d\r' % self.addr)
        if not result.startswith(b'OK'):
            #self.io_error()
            return False
        return True

    # process error reading or writing
    def io_error(self):
        return True

    # process error reading or writing
    def unexpected_reply(self):

        return True

if __name__ == "__main__":
    pass
    pdl = TDKLambda("COM3", 6)
    while True:
        print(time.time(), pdl.send_command("PC?"), pdl.timeout)
