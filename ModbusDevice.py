import logging
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
APPLICATION_NAME = 'Modbus Device sceleton module Python API'
APPLICATION_NAME_SHORT = 'ModbusDevice'
APPLICATION_VERSION = '1.0'


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


class ModbusDevice:
    _devices = []
    _lock = Lock()
    SUSPEND_DELAY = 5.0
    READ_TIMEOUT = 1.0

    def __init__(self, port: str, addr: int, **kwargs):
        # default com port, id, serial number, and ...
        self.com = EmptyComPort()
        self.id = 'Unknown Device'
        self.sn = ''
        self.suspend_to = 0.0
        self.port = str(port).strip()
        self.addr = int(addr)
        self.error = 0
        self.command = 0
        self.request = b''
        self.response = b''
        self.read_timeout = kwargs.pop('read_timeout', ModbusDevice.READ_TIMEOUT)
        self.suspend_delay = kwargs.pop('suspend_delay', ModbusDevice.SUSPEND_DELAY)
        # logger
        self.logger = kwargs.get('logger', config_logger(level=logging.DEBUG))
        # logs prefix
        self.pre = f'{self.id} at {self.port}: {self.addr} '
        # additional arguments for COM port creation
        self.kwargs = kwargs
        # create COM port
        self.create_com_port()
        # check device address
        if self.addr <= 0:
            self.warning('Wrong address')
            self.suspend(1e6)
            return
        # check if port:address is in use
        with ModbusDevice._lock:
            for d in ModbusDevice._devices:
                if d != self and d.port == self.port and d.addr == self.addr and d.state > 0:
                    self.warning('Address is in use')
                    self.suspend(1e6)
                    return
        # add device to list
        with ModbusDevice._lock:
            if self not in ModbusDevice._devices:
                ModbusDevice._devices.append(self)
        if not self.com.ready:
            self.info('COM port not ready')
            self.suspend()
            return
        self.id = 'Modbus device'
        self.pre = f'{self.id} at {self.port}: {self.addr} '
        self.debug(f'has been initialized')
        return

    def __del__(self):
        with ModbusDevice._lock:
            if self in ModbusDevice._devices:
                self.close_com_port()
                ModbusDevice._devices.remove(self)
                self.debug('has been deleted')

    def remove(self):
        with ModbusDevice._lock:
            if self in ModbusDevice._devices:
                self.close_com_port()
                ModbusDevice._devices.remove(self)
                self.debug('has been removed')

    def debug(self, msg, *args, **kwargs):
        sl = kwargs.pop('stacklevel', 1)
        if sys.version_info.major >= 3 and sys.version_info.minor >= 8:
            kwargs['stacklevel'] = sl + 2
        self.logger.debug(f'{self.pre} {msg}', *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        sl = kwargs.pop('stacklevel', 1)
        if sys.version_info.major >= 3 and sys.version_info.minor >= 8:
            kwargs['stacklevel'] = sl + 2
        self.logger.info(f'{self.pre} {msg}', *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        sl = kwargs.pop('stacklevel', 1)
        if sys.version_info.major >= 3 and sys.version_info.minor >= 8:
            kwargs['stacklevel'] = sl + 2
        self.logger.warning(f'{self.pre} {msg}', *args, **kwargs)

    def create_com_port(self):
        if 'baudrate' not in self.kwargs:
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
        self.debug('suspended for %5.2f sec', duration)

    @staticmethod
    def checksum(cmd: bytes) -> bytes:
        return modbus_crc(cmd).to_bytes(2, 'little')

    def add_checksum(self, cmd: bytes) -> bytes:
        return cmd + self.checksum(cmd)

    def verify_checksum(self, cmd: bytes) -> bool:
        cs = self.checksum(cmd[:-2])
        return cmd[-2:] == cs

    def write(self, cmd) -> bool:
        if not self.ready:
            self.error = 262
            return False
        if isinstance(cmd, str):
            cmd = cmd.encode()
        if not isinstance(cmd, bytes):
            return False
        self.error = 0
        self.com.reset_input_buffer()
        self.com.reset_output_buffer()
        self.com.read()
        # while self.com.in_waiting > 0:
        #     self.com.read()
        cmd = self.add_checksum(cmd)
        self.request = cmd
        n = self.com.write(cmd)
        if len(cmd) != n:
            self.error = 263
            self.suspend()
            return False
        return True

    def read(self, extra_bytes=5) -> bool:
        if not self.ready:
            self.error = 262
            return False
        self.error = 0
        self.response = b''
        self.read_timeout = time.time() + self.READ_TIMEOUT
        while time.time() < self.read_timeout and len(self.response) < 3:
            self.response += self.com.read(1000)
        # read timeout
        if time.time() >= self.read_timeout:
            self.error = 259
            self.suspend()
            return False
        # addr check
        if int(self.response[0]) != self.addr:
            self.error = 260
            return False
        # op code check
        op = int(self.response[1])
        if op != self.command and op != (self.command + 128):
            self.error = 261
            return False
        # calculate expected length of input
        if op > 128:
            # 5 bytes for error response
            k = 5
        elif op > 4 and op < 17:
            # single-byte operations
            k = 8
        else:
            # multi-byte operations
            k = int(self.response[2]) + extra_bytes
        # wait for next bytes
        while time.time() < self.read_timeout and len(self.response) < k:
            self.response += self.com.read(1000)
        if time.time() >= self.read_timeout:
            self.error = 259
            self.suspend()
            return False
        return self.check_response(self.response)

    def check_response(self, cmd: bytes) -> bool:
        self.error = 0
        if cmd[0] != self.addr:
            self.error = 257
            self.debug('Wrong address %d returned', cmd[0])
            return False
        op = int(cmd[1])
        if op > 127:
            self.error = int.from_bytes(cmd[2:3], byteorder='big')
            self.debug('Error code %d returned for command %d', self.error, op-127)
            return False
        if int(cmd[1]) != self.command:
            self.error = 258
            self.debug('Wrong command code %d returned', op)
            return False
        return self.verify_checksum(cmd)

    def modbus_read(self, start: int, length: int=1, address=None, command=3):
        self.command = command
        if address is None:
            address = self.addr
        msg = address.to_bytes(1, byteorder='big') + self.command.to_bytes(1, byteorder='big')
        msg += int.to_bytes(start, 2, byteorder='big')
        msg += int.to_bytes(length, 2, byteorder='big')
        data = []
        if not self.write(msg):
            return data
        if not self.read():
            return data
        for i in range(length):
            data.append(int.from_bytes(self.response[2 * i + 3:2 * i + 5], byteorder='big'))
        return data

    def modbus_write(self, start: int, data, address=None, command=16) -> int:
        if isinstance(data, int):
            data = [data,]
        try:
            if len(data) <= 0:
                return 0
        except:
            return 0
        self.command = command
        if address is None:
            address = self.addr
        msg = address.to_bytes(1, byteorder='big') + self.command.to_bytes(1, byteorder='big')
        msg += int.to_bytes(start, 2, byteorder="big")
        out = b''
        for d in data:
            if isinstance(d, int):
                out += d.to_bytes(2, byteorder='big')
            elif isinstance(d, bytes):
                out += d
            else:
                self.debug('Wrong data format for write')
                return 0
        length = len(out)
        msg += int.to_bytes(length // 2, 2, byteorder="big")
        msg += int.to_bytes(length, 1, byteorder='big')
        msg += out
        if not self.write(msg):
            return 0
        if not self.read():
            return 0
        data = int.from_bytes(self.response[4:6], byteorder='big')
        return data

    @property
    def ready(self):
        if time.time() < self.suspend_to:
            return False
        # was suspended try to init
        if self.suspend_to > 0.0:
            self.__del__()
            self.__init__(self.port, self.addr, **self.kwargs)
        return self.suspend_to <= 0.0


def print_ints(arr, r, base=None):
    d = 3
    n = 0
    rr = r[d:]
    for i in arr[d:]:
        if n % 2 == 0:
            j = int(i)
        else:
            k = 256*j + int(i)
            if len(r) > n:
                val = int(rr[n-1])*256 + int(rr[n])
                if k != val:
                    val = "{:05d}".format(val)
                else :
                    val = ''
            else:
                val = ''
            if base is not None:
                bases = "{:05d}: ".format(base + n // 2)
            else:
                bases = ''
            print(bases, "{:05d}".format(k), "{:03d}".format(j),"{:03d}".format(i), "{:08b}".format(j), "{:08b}".format(i), val)
        n += 1


if __name__ == "__main__":
    print('')
    md1 = ModbusDevice("COM10", 1, baudrate=57600, parity='E')

    r1 = []
    r2 = []
    print('')
    while True:
        a01 = 4096
        t_0 = time.time()
        v1 = md1.modbus_read(a01, 18, command=3)
        dt = int((time.time() - t_0) * 1000.0)  # ms
        a1 = '%s %s %s %s %s' % (md1.port, md1.addr, 'modbus_read->', v1, '%4d ms ' % dt)
        print(a1)
        print(md1.request)
        print(md1.response)
        if len(md1.response) > 2 and md1.response[1] > 127:
            print("ERROR", md1.response[2])
        print_ints(md1.response, r1, base=a01)
        r1 = list(md1.response)
        print('')
        oa = []
        n = 0
        for i in md1.response:
            if n % 2 == 0:
                j = i
            else:
                j = j * 256 + i
                oa.append(j)
            n += 1

        a02 = 6144
        t_0 = time.time()
        v2 = md1.modbus_read(a02, 20, command=3)
        dt = int((time.time() - t_0) * 1000.0)  # ms
        a2 = '%s %s %s %s %s' % (md1.port, md1.addr, 'modbus_read->', v2, '%4d ms ' % dt)
        print(a2)
        print(md1.request)
        print(md1.response)
        print_ints(md1.response, r2, base=a02)
        r2 = list(md1.response)
        print('')

        t_0 = time.time()
        # v = md1.modbus_write(4100, [2731, 4096])
        v = md1.modbus_write(4105, [2222, 333])
        # v = md1.modbus_write(4106, [640])
        # v = md1.modbus_write(16, [1, 0, 10, 0, 400])
        # dt = int((time.time() - t_0) * 1000.0)  # ms
        # a = '%s %s %s %s %s' % (md1.port, md1.addr, 'modbus_write->', v, '%4d ms ' % dt)
        # print(a)
        print(md1.request)
        print(md1.response)
        print('')

        v1 = md1.modbus_read(a01, 18, command=3)
        print_ints(md1.response, r1, base=a01)
        print('')
        v2 = md1.modbus_read(a02, 20, command=3)
        print_ints(md1.response, r2, base=a02)

        exit()



    print('Finished')
