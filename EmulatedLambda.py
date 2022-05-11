# -*- coding: utf-8 -*-

import time
from threading import Lock

COMMANDS = (b'DVC?', b'PV?', b'MV?', b'PC?', b'MC?', b'IDN?', b'SN?')

class FakeComPort:
    SN = 123456
    RESPONSE_DELAY = 0.035
    ID = b'FAKELAMBDA GEN10-100'

    def __init__(self, port, *args, **kwargs):
        self.port = port
        self.last_address = -1
        self.lock = Lock()
        self.online = False
        self.last_write = b''
        self.pv = {}
        self.pc = {}
        self.mv = {}
        self.mc = {}
        self.out = {}
        self.sn = {}
        self.id = {}
        self.t = {}
        self.write_error = False
        self.add_device()

    def close(self):
        self.last_write = b''
        self.online = False
        return True

    def add_device(self):
        if self.last_address not in self.pv:
            self.id[self.last_address] = FakeComPort.ID
            self.pv[self.last_address] = 0.0
            self.pc[self.last_address] = 0.0
            self.mv[self.last_address] = 0.0
            self.mc[self.last_address] = 0.0
            self.out[self.last_address] = False
            self.sn[self.last_address] = str(FakeComPort.SN).encode()
            FakeComPort.SN += 1

    def write(self, cmd, timeout=None):
        self.last_write = cmd
        self.write_error = False
        try:
            if self.last_write.startswith(b'ADR '):
                self.last_address = int(self.last_write[4:])
                self.add_device()
            elif self.last_write.startswith(b'PV '):
                self.pv[self.last_address] = float(cmd[3:])
            elif self.last_write.startswith(b'PC '):
                self.pc[self.last_address] = float(cmd[3:])
            elif self.last_write.startswith(b'OUT ON') or self.last_write.startswith(b'OUT 1'):
                self.out[self.last_address] = True
            elif self.last_write.startswith(b'OUT OF') or self.last_write.startswith(b'OUT 0'):
                self.out[self.last_address] = False
            else:
                if cmd[:-1] not in COMMANDS:
                    self.write_error = True
            self.t[self.last_address] = time.perf_counter()
            return len(cmd)
        except:
            self.write_error = True
            self.t[self.last_address] = time.perf_counter()
            return len(cmd)

    def read(self, size=1, timeout=None):
        if self.last_write == b'':
            return b''
        if time.perf_counter() - self.t[self.last_address] < self.RESPONSE_DELAY:
            return b''
        self.t[self.last_address] = time.perf_counter()
        if self.write_error:
            self.last_write = b''
            return b'E1\r'
        if self.last_write.startswith(b'ADR '):
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

    def reset_input_buffer(self, timeout=None):
        return True

    def isOpen(self):
        return True

