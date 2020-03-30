#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys

import serial
from Utils import *

logger = config_logger(level=logging.DEBUG)


class VirtualLambdaAtCom:
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
        if self.addr in VirtualLambdaAtCom.devices:
            logger.critical('Address is in use')
            exit(-2)
        # assign com port
        if not self.init_com_port():
            logger.critical('Can not create COM port')
            exit(-3)
        # device type
        self.id = b'VIRTUAL_TDK_LAMBDA GEN10-100'
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
        self.serial_number = str(VirtualLambdaAtCom.SERIAL_NUMBER).encode()
        VirtualLambdaAtCom.SERIAL_NUMBER += 1
        self.check = False
        # voltage and current
        self.pv = 0.0
        self.pc = 0.0
        self.mv = 0.0
        self.mc = 0.0
        self.out = False
        # add device to dict
        VirtualLambdaAtCom.devices[self.addr] = self
        logger.info('TDKLambda: %s has been created at %s:%d' % (self.id, self.port, self.addr))

    def init_com_port(self):
        if len(VirtualLambdaAtCom.devices) > 0:
            self.com = next(iter(VirtualLambdaAtCom.devices.values())).com
            logger.debug('Using existing %s' % self.port)
            return True
        self.close_com_port()
        try:
            self.com = serial.Serial(self.port, baudrate=self.baud, timeout=0)
            self.write_timeout = 0
            self.writeTimeout = 0
            self.com._current_addr = -1
            logger.debug('%s port is used' % self.port)
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
            self.write(b'OK\r')
            return
        if b'$' in cmd:
            self.check = True
            m = cmd.find(b'$')
            cs = self.checksum(cmd[:m])
            if cmd[m+1:] != cs:
                logger.error('Incorrect checksum in %s (%s)' % (cmd, cs))
                self.write(b'C04\r')
                return
            cmd = cmd[:m]
        else:
            self.check = False
        cd = VirtualLambdaAtCom.devices[self.addr]
        if cmd.startswith(b'ADR?'):
            self.write(str(cd.addr).encode() + b'\r')
        elif cmd.startswith(b'IDN?'):
            self.write(cd.id + b'\r')
        elif cmd.startswith(b'SN?'):
            self.write(cd.serial_number + b'\r')
        elif cmd.startswith(b'PV?'):
            self.write(str(cd.pv).encode() + b'\r')
        elif cmd.startswith(b'PC?'):
            self.write(str(self.pc).encode() + b'\r')
        elif cmd.startswith(b'MV?'):
            if cd.out:
                cd.mv = cd.pv
            else:
                cd.mv = 0.0
            self.write(str(cd.mv).encode() + b'\r')
        elif cmd.startswith(b'MC?'):
            if cd.out:
                cd.mc = cd.pc
            else:
                cd.mc = 0.0
            self.write(str(cd.mc).encode() + b'\r')
        elif cmd.startswith(b'OUT?'):
            if cd.out:
                cd.write(b'ON\r')
            else:
                cd.write(b'OFF\r')
        elif cmd.startswith(b'MODE?'):
            if cd.out:
                self.write(b'CV\r')
            else:
                self.write(b'OFF\r')
        elif cmd.startswith(b'DVC?'):
            if cd.out:
                cd.mc = cd.pc
                cd.mv = cd.pv
            else:
                cd.mc = 0.0
                cd.mv = 0.0
            self.write(b'%f, %f, %f, %f, 0.0, 0.0\r' % (cd.mv, cd.pv, cd.mc, cd.pc))
        elif cmd.startswith(b'ADR '):
            try:
                new_addr = int(cmd[3:])
            except:
                logger.error('Illegal parameter in %s' % cmd)
                self.write(b'C03\r')
                return
            if new_addr != self.addr:
                if new_addr not in VirtualLambdaAtCom.devices:
                    logger.error('Device with address %d does not exists' % new_addr)
                    self.write(b'C05\r')
                    return
                self.addr = new_addr
                #self.pv = FakeLambdaAtCom.devices[new_addr].pv
                #self.pc = FakeLambdaAtCom.devices[new_addr].pc
                #self.mv = FakeLambdaAtCom.devices[new_addr].mv
                #self.mc = FakeLambdaAtCom.devices[new_addr].mc
                #self.out = FakeLambdaAtCom.devices[new_addr].out
                #self.serial_number = FakeLambdaAtCom.devices[new_addr].serial_number
                #self.id = FakeLambdaAtCom.devices[new_addr].id
            self.write(b'OK\r')
        elif cmd.startswith(b'PV '):
            try:
                v = float(cmd[3:])
                if v > cd.max_voltage or v < 0.0:
                    logger.error('Out of range in %s' % cmd)
                    self.write(b'C05\r')
                else:
                    cd.pv = v
                    self.write(b'OK\r')
            except:
                logger.error('Illegal parameter in %s' % cmd)
                self.write(b'C03\r')
        elif cmd.startswith(b'PC '):
            try:
                c = float(cmd[3:])
                if c > cd.max_current or c < 0.0:
                    logger.error('Out of range in %s' % cmd)
                    self.write(b'C05\r')
                else:
                    cd.pc = c
                    self.write(b'OK\r')
            except:
                logger.error('Illegal parameter in %s' % cmd)
                self.write(b'C03\r')
        elif cmd.startswith(b'OUT '):
            if cmd[4:] == b'ON':
                cd.out = True
                self.write(b'OK\r')
            elif cmd[4:] == b'OFF':
                cd.out = False
                self.write(b'OK\r')
            else:
                logger.error('Illegal parameter in %s' % cmd)
                self.write(b'C03\r')
        else:
            logger.warning('Unsupported command %s' % cmd)
            self.write(b'C01\r')

    def write(self, st):
        if st.endswith(b'\r'):
            st = st[:-1]
        if self.check:
            cs = self.checksum(st)
            st = b'%s$%s\r' % (st, cs)
        if not st.endswith(b'\r'):
            st += b'\r'
        self.com.write(st)

    def clear_input_buffer(self):
        self.com.read(10000)
        self.input = b''

    @staticmethod
    def checksum(cmd):
        s = 0
        for b in cmd:
            s += int(b)
        result = str.encode(hex(s)[-2:].upper())
        return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        com_port = 'COM3'
    else:
        com_port = sys.argv[1]
    if len(sys.argv) < 3:
        addresses = [6]
    else:
        addresses = []
    for adr in sys.argv[2:]:
        try:
            addresses.append(int(adr))
        except:
            pass
    if len(addresses) <= 0:
        logger.critical('Wrong command line parameters. Use: COMxx ADR1 ADR2 ...')
        exit(-10)
    dev1 = VirtualLambdaAtCom(com_port, addresses[0])
    for ad in addresses[1:]:
        VirtualLambdaAtCom(com_port, ad)
    t0 = time.time()
    while True:
        dev1.read()
        time.sleep(0.1)
