import os
import sys
import time
from threading import Lock

from ModbusDevice import ModbusDevice

util_path = os.path.realpath('../TangoUtils')
if util_path not in sys.path:
    sys.path.append(util_path)
del util_path

from ComPort import EmptyComPort, ComPort
from config_logger import config_logger
from log_exception import log_exception

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'Vtimer I/O modules Python API'
APPLICATION_NAME_SHORT = 'Vtimer'
APPLICATION_VERSION = '0.1'


class Vtimer(ModbusDevice):

    def read_start(self, n) -> int:
        self.modbus_read(16*n + 1, 2)
        delay = int.from_bytes(self.response[3:7], 'little')
        return delay

    def read_run(self) -> int:
        self.modbus_read(0, 1)
        data = int.from_bytes(self.response[3:5], 'little')
        return data

    def write_output(self, v) -> int:
        self.modbus_write(4, int(bool(v)))
        delay = int.from_bytes(self.response[3:7], 'little')
        return delay

class FakeVtimer(Vtimer):
    commands = {b'$010': b'!AA',
                b'$011': b'!AA',
                b'$016': b'!AA',
                b'$015': b'!AA',
                b'#01N': b'>+2.2',
                b'#01': b'>+1.0+2.0+3.0+4.0+5.0+6.0+7.0+8.0',
                b'$01M': b'!AA4017',
                b'$01F': b'!AA10',
                b'$012': b'!AA',
                b'%01': b'!AA',
                }

    def __init__(self, *args, **kwargs):
        self.TTCCFF = b'000000'
        self.VV = b'FF'
        kwargs['auto_addr'] = False
        super().__init__(*args, **kwargs)

    def create_com_port(self):
        self.com = EmptyComPort(True)
        return self.com

    def _send_command(self, cmd, terminator=None):
        self.command = cmd
        self.response = b''
        AA = cmd[1:3]
        cmd = cmd[:1] + b'01' + cmd[3:-1]
        if cmd.startswith(b'$015'):
            self.VV = cmd[4:]
            cmd = b'$015'
        if cmd.startswith(b'%01'):
            self.TTCCFF = cmd[5:]
            cmd = b'%01'
        if cmd.startswith(b'#01') and len(cmd) > 3:
            cmd = b'#01N'
        if cmd not in self.commands:
            return b''
        v = self.commands[cmd]
        v = v.replace(b'AA', AA)
        if cmd.startswith(b'$012'):
            v += self.TTCCFF
        if cmd.startswith(b'$016'):
            v += self.VV
        self.response = v + b'\r'
        return v

    def init(self):
        self.suspend_to = 0.0
        self.pre = f'ADAMxxxx at {self.port}:{self.addr}'
        self.addr_hex = (b'%02X' % self.addr)[:2]
        self.head_ok = b'!' + self.addr_hex
        self.head_err = b'?' + self.addr_hex
        self.name = '0000'
        self.ai_n = 0
        self.ao_n = 0
        self.di_n = 0
        self.do_n = 0
        self.ao_masks = []
        self.ai_masks = []
        self.ai_ranges = []
        self.ai_min = []
        self.ai_max = []
        self.ai_units = []
        self.ao_ranges = []
        self.ao_min = []
        self.ao_max = []
        self.ao_units = []
        # check device address
        if self.addr <= 0:
            self.state = -1
            self.logger.info(f'{self.pre} ' + self.STATES[self.state])
            self.suspend()
            return False
        # check if port:address is in use
        with Vtimer._lock:
            for d in Vtimer._devices:
                if d != self and d.port == self.port and d.addr == self.addr and d.state > 0:
                    self.state = -2
                    self.logger.info(f'{self.pre} ' + self.STATES[self.state])
                    self.suspend()
                    return False
        if not self.com.ready:
            self.state = -5
            self.logger.info(f'{self.pre} ' + self.STATES[self.state])
            self.suspend()
            return False
        # read device type
        # self.id = self.read_device_id()
        n = 0
        self.id = 'Unknown Device'
        while n < self.read_retries:
            n += 1
            result = self._send_command(b'$' + self.addr_hex + b'M\r')
            if result and self.check_response():
                self.id = self.response[3:-1].decode()
                break
        #
        if self.id in ADAM_DEVICES:
            self.name = self.id
        else:
            self.name = '0000'
            for key in ADAM_DEVICES:
                if self.id[-2:] == key[-2:]:
                    self.logger.info(f'{self.pre} Using {key} instead of {self.id} for devise type')
                    self.name = key
                    break
        self.pre = f'FakeADAM{self.name} at {self.port}:{self.addr}'
        if self.name == '0000' or (self.name not in ADAM_DEVICES):
            self.logger.info(f'ADAM at {self.port}:{self.addr} is not recognized')
            self.state = -4
            self.suspend()
            return False
        self.ai_n = ADAM_DEVICES[self.name]['ai']
        self.ai_masks = [True] * self.ai_n
        if self.ai_n > 0:
            self.ai_masks = self.read_masks()
        self.ao_n = ADAM_DEVICES[self.name]['ao']
        self.ao_masks = [True] * self.ao_n
        # if self.ao_n > 0:
        #     self.ao_masks = self.read_masks()
        self.di_n = ADAM_DEVICES[self.name]['di']
        self.do_n = ADAM_DEVICES[self.name]['do']
        self.ai_ranges = [self.read_range(c) for c in range(self.ai_n)]
        self.ai_min = [i[0] for i in self.ai_ranges]
        self.ai_max = [i[1] for i in self.ai_ranges]
        self.ai_units = [i[2] for i in self.ai_ranges]
        self.ao_ranges = [self.read_range(c) for c in range(self.ao_n)]
        self.ao_min = [i[0] for i in self.ao_ranges]
        self.ao_max = [i[1] for i in self.ao_ranges]
        self.ao_units = [i[2] for i in self.ao_ranges]
        self.state = 1
        self.suspend_to = 0.0
        self.logger.debug(f'{self.pre} has been initialized')
        return True


if __name__ == "__main__":
    ot1 = ModbusDevice("COM17", 1)
    t_0 = time.time()
    # v = ot1.write_output(1)
    # v = ot1.write_output(0)
    v = ot1.modbus_read(0, 9)
    print(v)
    v = ot1.read_run()
    dt = int((time.time() - t_0) * 1000.0)  # ms
    a = '%s %s %s %s %s' % (ot1.port, ot1.addr, 'read_run->', v, '%4d ms ' % dt)
    print(a)
    print('Finished')
