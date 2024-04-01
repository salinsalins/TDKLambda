import os
import sys
import time
from threading import Lock

util_path = os.path.realpath('../TangoUtils')
if util_path not in sys.path:
    sys.path.append(util_path)
del util_path

from ComPort import EmptyComPort, ComPort
from config_logger import config_logger
from log_exception import log_exception

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'Otimer I/O modules Python API'
APPLICATION_NAME_SHORT = 'Otimer'
APPLICATION_VERSION = '0.1'


def modbus_crc(msg: bytes) -> int:
    crc = 0xFFFF
    for n in range(len(msg)):
        crc ^= msg[n]
        for i in range(8):
            if crc & 1:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc


class Otimer:
    _devices = []
    _lock = Lock()
    SUSPEND_DELAY = 5.0
    READ_TIMEOUT = 1.0
    READ_RETRIES = 2
    STATES = {
        1: 'Initialized',
        0: 'Pre init state',
        -1: 'Wrong address',
        -2: 'Address is in use',
        -3: 'Address set error',
        -4: 'Device is not recognized',
        -5: 'COM port not ready'}

    def __init__(self, port: str, addr: int, **kwargs):
        # default com port, id, serial number, and ...
        self.com = EmptyComPort()
        self.id = 'Unknown Device'
        self.sn = ''
        self.suspend_to = 0.0
        self.suspend_flag = False
        self.state = 0
        self.status = ''
        self.port = str(port).strip()
        self.addr = int(addr)
        self.command = 0
        self.request = b''
        self.response = b''
        self.read_timeout = kwargs.pop('read_timeout', Otimer.READ_TIMEOUT)
        self.read_retries = kwargs.pop('read_retries', Otimer.READ_RETRIES)
        self.suspend_delay = kwargs.pop('suspend_delay', Otimer.SUSPEND_DELAY)
        # logger
        self.logger = kwargs.get('logger', config_logger())
        # logs prefix
        self.pre = f'{self.id} at {self.port}: {self.addr} '
        # additional arguments for COM port creation
        self.kwargs = kwargs
        # create COM port
        self.create_com_port()
        # add device to list
        with Otimer._lock:
            if self not in Otimer._devices:
                Otimer._devices.append(self)
        # check device address
        if self.addr <= 0:
            self.state = -1
            self.logger.warning(f'{self.pre} ' + self.STATES[self.state])
            self.suspend()
            return
        # check if port:address is in use
        with Otimer._lock:
            for d in Otimer._devices:
                if d != self and d.port == self.port and d.addr == self.addr and d.state > 0:
                    self.state = -2
                    self.logger.warning(f'{self.pre} ' + self.STATES[self.state])
                    self.suspend()
                    return
        if not self.com.ready:
            self.state = -5
            self.logger.warning(f'{self.pre} ' + self.STATES[self.state])
            self.suspend()
            return

        self.logger.debug(f'{self.pre} has been initialized')
        return

    def __del__(self):
        with Otimer._lock:
            if self in Otimer._devices:
                self.close_com_port()
                Otimer._devices.remove(self)
                self.logger.debug(f'{self.pre} has been deleted')

    def create_com_port(self):
        self.kwargs['baudrate'] = 115200
        self.com = ComPort(self.port, emulated=EmptyComPort, **self.kwargs)
        return self.com

    def close_com_port(self):
        try:
            self.com.close()
        except KeyboardInterrupt:
            raise
        except:
            log_exception(self, f'{self.pre} COM port close exception')

    def suspend(self, duration=None):
        if time.time() < self.suspend_to:
            return
        if duration is None:
            duration = self.suspend_delay
        self.suspend_to = time.time() + duration
        self.logger.debug(f'{self.pre} suspended for %5.2f sec', duration)

    @staticmethod
    def checksum(cmd: bytes) -> bytes:
        return modbus_crc(cmd).to_bytes(2, 'little')

    def add_checksum(self, cmd: bytes) -> bytes:
        return cmd + self.checksum(cmd)

    def verify_checksum(self, cmd: bytes) -> bool:
        cs = self.checksum(cmd[:-2])
        return cmd[-2:] == cs

    def write(self, cmd) -> bool:
        if isinstance(cmd, str):
            cmd = cmd.encode()
        if not isinstance(cmd, bytes):
            return False
        return self.com.write(cmd)

    def read(self) -> bool:
        self.response = b''
        while time.time() < self.read_timeout and len(self.response) < 3:
            self.response += self.com.read(1000)
        if time.time() >= self.read_timeout:
            return False
        # addr check
        if int(self.response[0]) != self.addr:
            return False
        # op code check
        op = int(self.response[1])
        if op != self.command and op != (self.command + 128):
            return False
        # calculate expected length of input
        if op > 128:
            # 5 bytes for error response
            n = 5
        elif op > 4:
            # single-byte operations
            n = 8
        else:
            # multi-byte operations
            n = int(self.response[2]) + 5
        # wait for next bytes
        while time.time() < self.read_timeout and len(self.response) < n:
            self.response += self.com.read(1000)
        if time.time() >= self.read_timeout:
            return False
        return self.check_response(self.response)

    def check_response(self, cmd: bytes) -> bool:
        if int(cmd[0]) != self.addr:
            return False
        if int(cmd[1]) != self.command:
            return False
        if not self.verify_checksum(cmd):
            return False
        return True

    def modbus_read(self, addr: int, start: int, length: int):
        msg = addr.to_bytes(1) + b'\x03'
        msg += int.to_bytes(start, 2)
        msg += int.to_bytes(length, 2)
        msg += modbus_crc(msg)
        if self.write(msg) != len(msg):
            return []
        if not self.read():
            return []
        data = []
        for i in range(length):
            data.append(int.from_bytes(self.response[i + 3:i + 5], 'little'))
        return data

    def modbus_write(self, addr: int, start: int, data):
        if isinstance(data, int):
            length = 2
            data = int.to_bytes(10,2)
            msg = addr.to_bytes(1) + b'\x06'
        length = len(data)
        msg = addr.to_bytes(1) + b'\x10'
        msg += int.to_bytes(start, 2)
        msg += int.to_bytes(length, 2)
        msg += data
        msg += modbus_crc(msg)
        if self.write(msg) != len(msg):
            return []
        if not self.read():
            return []
        data = []
        for i in range(length):
            data.append(int.from_bytes(self.response[i + 3:i + 5], 'little'))
        return data

    def read_start(self, n) -> int:
        cmd = self.addr.to_bytes(1) + b'\x03'
        cmd += int.to_bytes(16 * n + 1, 2)
        cmd += b'\x00\x02'
        self.write(self.add_checksum(cmd))
        if not self.read():
            return False
        delay = int.from_bytes(self.response[3:7], 'little')
        return delay

    def read_run(self) -> int:
        cmd = self.addr.to_bytes(1) + b'\x03'
        cmd += b'\x00\x00'
        cmd += b'\x00\x01'
        cmd += self.add_checksum(cmd)
        self.write(cmd)
        if not self.read():
            return False
        data = int.from_bytes(self.response[3:7], 'little')
        return data


class FakeOtimer(Otimer):
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
        with Otimer._lock:
            for d in Otimer._devices:
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
    ot1 = Otimer("COM16", 11)
    t_0 = time.time()
    v = ot1.read_run()
    dt = int((time.time() - t_0) * 1000.0)  # ms
    a = '%s %s %s %s %s' % (ot1.port, ot1.addr, 'read_run ->', v, '%4d ms ' % dt)
    print(a)
    print('Finished')
