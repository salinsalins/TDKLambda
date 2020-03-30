#!/usr/bin/env python
# -*- coding: utf-8 -*-

import serial
from Utils import *

logger = config_logger(level=logging.DEBUG)


class FakeLambdaAtCom:
    SERIAL_NUMBER = 56789
    devices = {}

    def __init__(self, port, addr, checksum=False, baud_rate=9600):
        # input parameters
        self.port = port.upper().strip()
        self.addr = addr
        self.check = checksum
        self.baud = baud_rate
        # create variables
        self.input = b''
        # default com port, id, and serial number
        self.com = None
        self.id = None
        self.sn = None
        self.max_voltage = float('inf')
        self.max_current = float('inf')
        # check device address
        if self.addr <= 0:
            logger.critical('Wrong device address')
            exit(-4)
        # check if address is in use
        for self.addr in FakeLambdaAtCom.devices:
            logger.critical('Address is in use')
            exit(-2)
        # assign com port
        if not self.init_com_port():
            logger.critical('Can not create COM port')
            exit(-3)
        # device type
        self.id = b'FAKE_TDK_LAMBDA GEN10-100'
        # determine max current and voltage from model name
        n1 = self.id.find(b'GEN')
        n2 = self.id.find(b'-')
        if n1 >= 0 and n2 >= 0:
            try:
                self.max_voltage = float(self.id[n1 + 3:n2])
                self.max_current = float(self.id[n2 + 1:])
            except:
                pass
        # read device serial number
        self.serial_number = str(FakeLambdaAtCom.SERIAL_NUMBER).encode()
        FakeLambdaAtCom.SERIAL_NUMBER += 1
        # voltage and current
        self.pv = 0.0
        self.pc = 0.0
        self.mv = 0.0
        self.mc = 0.0
        self.out = False
        # add device to list
        FakeLambdaAtCom.devices[self.addr] = self
        logger.info('TDKLambda: %s has been created' % self.id)

    def init_com_port(self):
        if len(FakeLambdaAtCom.devices) > 0:
            self.com = next(iter(FakeLambdaAtCom.devices.values())).com
            logger.debug('Assigned existing COM %s' % self.port)
            return
        self.close_com_port()
        try:
            self.com = serial.Serial(self.port, baudrate=self.baud, timeout=0)
            self.com.write_timeout = 0
            self.com.writeTimeout = 0
            self.com._current_addr = -1
            logger.debug('COM port %s created' % self.port)
            return True
        except:
            logger.error('COM port %s creation error' % self.port)
            logger.debug('', exc_info=True)
            return False

    def close_com_port(self):
        try:
            self.com.close()
        except:
            pass

    def read(self):
        data = self.com.read(10000)
        while len(data) <= 0:
            return
        logger.debug('%s received' % data)
        self.input += data
        # check for CR
        if b'\r' in self.input:
            self.input = self.input.replace(b'\n', b'')
        if b'\n' in self.input:
            self.input = self.input.replace(b'\n', b'\r')
        if b'\r' not in self.input:
            return
        # interpret command
        commands = self.input.split(b'\r')
        for cmd in commands[:-1]:
            self.execute_command(cmd)
            self.input = self.input[len(cmd)+1:]
        return

    def execute_command(self, cmd):
        cmd = cmd.upper().strip(b'\n')
        logger.debug('Executing %s' % cmd)
        if len(cmd) == 0:  # empty command just CR
            self.com.write(b'OK\r')
            return
        if cmd.startswith(b'ADR?'):
            self.com.write(str(self.addr).encode() + b'\r')
        elif cmd.startswith(b'IDN?'):
            self.com.write(self.id + b'\r')
        elif cmd.startswith(b'SN?'):
            self.com.write(self.serial_number + b'\r')
        elif cmd.startswith(b'PV?'):
            self.com.write(str(self.pv).encode() + b'\r')
        elif cmd.startswith(b'PC?'):
            self.com.write(str(self.pc).encode() + b'\r')
        elif cmd.startswith(b'MV?'):
            if self.out:
                self.mv = self.pv
            else:
                self.mv = 0.0
            self.com.write(str(self.mv).encode() + b'\r')
        elif cmd.startswith(b'MC?'):
            if self.out:
                self.mc = self.pc
            else:
                self.mc = 0.0
            self.com.write(str(self.mc).encode() + b'\r')
        elif cmd.startswith(b'OUT?'):
            if self.out:
                self.com.write(b'ON\r')
            else:
                self.com.write(b'OFF\r')
        elif cmd.startswith(b'MODE?'):
            if self.out:
                self.com.write(b'CV\r')
            else:
                self.com.write(b'OFF\r')
        elif cmd.startswith(b'DVC?'):
            if self.out:
                self.mc = self.pc
                self.mv = self.pv
            else:
                self.mc = 0.0
                self.mv = 0.0
            self.com.write(b'%f, %f, %f, %f, 0.0, 0.0\r' % (self.mv, self.pv, self.mc, self.pc))
        elif cmd.startswith(b'ADR '):
            ad = int(cmd[3:])
            if ad != self.addr:
                if ad not in FakeLambdaAtCom.devices:
                    logger.error('Device with address %d does not exists' % ad)
                    self.com.write(b'C05\r')
                    return
                self.addr = ad
                self.pv = FakeLambdaAtCom.devices[ad].pv
                self.pc = FakeLambdaAtCom.devices[ad].pc
                self.mv = FakeLambdaAtCom.devices[ad].mv
                self.mc = FakeLambdaAtCom.devices[ad].mc
                self.out = FakeLambdaAtCom.devices[ad].out
                self.serial_number = FakeLambdaAtCom.devices[ad].serial_number
                self.id = FakeLambdaAtCom.devices[ad].id
            self.com.write(b'OK\r')
        elif cmd.startswith(b'PV '):
            try:
                v = float(cmd[3:])
                if v > self.max_voltage or v < 0.0:
                    logger.error('Out of range in %s' % cmd)
                    self.com.write(b'C05\r')
                else:
                    self.pv = v
                    self.com.write(b'OK\r')
            except:
                logger.error('Illegal parameter in %s' % cmd)
                self.com.write(b'C03\r')
        elif cmd.startswith(b'PC '):
            try:
                c = float(cmd[3:])
                if c > self.max_current or c < 0.0:
                    logger.error('Out of range in %s' % cmd)
                    self.com.write(b'C05\r')
                else:
                    self.pc = c
                    self.com.write(b'OK\r')
            except:
                logger.error('Illegal parameter in %s' % cmd)
                self.com.write(b'C03\r')
        elif cmd.startswith(b'OUT '):
            if cmd[4:] == b'ON':
                self.out = True
                self.com.write(b'OK\r')
            elif cmd[4:] == b'OFF':
                self.out = False
                self.com.write(b'OK\r')
            else:
                logger.error('Illegal parameter in %s' % cmd)
                self.com.write(b'C03\r')
        else:
            logger.warning('Unsupported command %s' % cmd)
            self.com.write(b'C01\r')

    def clear_input_buffer(self):
        self.com.read(10000)
        self.input = b''


if __name__ == "__main__":
    dev1 = FakeLambdaAtCom("COM3", 6)
    t0 = time.time()
    while True:
        dev1.read()
        time.sleep(0.1)
