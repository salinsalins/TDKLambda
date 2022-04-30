# -*- coding: utf-8 -*-

import time
from threading import Lock


class EmulatedIT6900:

    def __init__(self, port, *args, **kwargs):
        self.port = port
        self.ready = False
        self.last_write = b''
        self.pv = 0.0
        self.pc = 0.0
        self.mv = 0.0
        self.mc = 0.0
        self.out = False
        self.sn = 12345
        self.id = 'ITECH Ltd., IT6900_Emulated, 12345, 1.0'
        self.t = time.perf_counter()
        self.write_error = False

    def close(self):
        self.last_write = b''
        self.reday = False
        return True

    def write(self, cmd, *args, **kwargs):
        self.last_write = cmd
        self.write_error = False
        if cmd.startswith(b'OUTP '):
            if cmd[5:6] == b'ON':
                self.out = True
            elif cmd[5:7] == b'OFF':
                self.out = False
        return len(cmd)

    def read(self, *args, **kwargs):
        if self.last_write == b'':
            return b''
        if self.last_write.startswith(b'OUTP?'):
            if self.out:
                return b'1\r'
            else:
                return b'0\r'
        if b'MEAS:CURR?' in self.last_write:
            return str(self.mc).encode() + b'\r'
        return b'-200\r'

    def reset_input_buffer(self, timeout=None):
        return True

    def isOpen(self):
        return True

