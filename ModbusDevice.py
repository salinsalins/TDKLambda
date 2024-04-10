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
            return False
        if isinstance(cmd, str):
            cmd = cmd.encode()
        if not isinstance(cmd, bytes):
            return False
        cmd = self.add_checksum(cmd)
        self.request = cmd
        n = self.com.write(cmd)
        if len(cmd) != n:
            self.suspend()
            return False
        return True

    def read(self) -> bool:
        if not self.ready:
            return False
        self.error = 0
        self.response = b''
        self.read_timeout = time.time() + self.READ_TIMEOUT
        while time.time() < self.read_timeout and len(self.response) < 3:
            self.response += self.com.read(1000)
        # read timeout
        if time.time() >= self.read_timeout:
            self.suspend()
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
            k = 5
        elif op > 4:
            # single-byte operations
            k = 8
        else:
            # multi-byte operations
            k = int(self.response[2]) + 5
        # wait for next bytes
        while time.time() < self.read_timeout and len(self.response) < k:
            self.response += self.com.read(1000)
        if time.time() >= self.read_timeout:
            self.suspend()
            return False
        return self.check_response(self.response)

    def check_response(self, cmd: bytes) -> bool:
        if cmd[0] != self.addr:
            self.debug('Wrong address %d returned', cmd[0])
            return False
        op = int(cmd[1])
        if op > 127:
            self.error = int.from_bytes(cmd[2:3])
            self.debug('Error code %d returned for command %d', self.error, op-127)
            return False
        if int(cmd[1]) != self.command:
            self.debug('Wrong command code %d returned', op)
            return False
        return self.verify_checksum(cmd)

    def modbus_read(self, start: int, length: int):
        self.command = 3
        msg = self.addr.to_bytes(1) + self.command.to_bytes(1)
        msg += int.to_bytes(start, 2)
        msg += int.to_bytes(length, 2)
        if not self.write(msg):
            return []
        if not self.read():
            return []
        data = []
        for i in range(length):
            data.append(int.from_bytes(self.response[2 * i + 3:2 * i + 5]))
        return data

    def modbus_write(self, start: int, data) -> int:
        self.command = 16
        if isinstance(data, int):
            out = int.to_bytes(data, 2)
        else:
            out = b''
            for d in data:
                if isinstance(d, int):
                    out += d.to_bytes(2)
                elif isinstance(d, bytes):
                    out += d
                else:
                    self.debug('Wrong data format for write')
                    return 0
        length = len(out)
        msg = self.addr.to_bytes(1) + self.command.to_bytes(1)
        msg += int.to_bytes(start, 2, byteorder="big")
        msg += int.to_bytes(length // 2, 2, byteorder="big")
        msg += int.to_bytes(length, 1)
        msg += out
        if not self.write(msg):
            return 0
        if not self.read():
            return 0
        data = int.from_bytes(self.response[4:6])
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


if __name__ == "__main__":
    md1 = ModbusDevice("COM17", 1)

    t_0 = time.time()
    v = md1.modbus_write(1, [0, 0, 400, 1])
    # v = md1.modbus_write(16, [1, 0, 10, 0, 400])
    dt = int((time.time() - t_0) * 1000.0)  # ms
    a = '%s %s %s %s %s' % (md1.port, md1.addr, 'modbus_write->', v, '%4d ms ' % dt)
    print(a)
    print(md1.request)
    print(md1.response)
    print('')

    t_0 = time.time()
    v = md1.modbus_read(0, 9)
    dt = int((time.time() - t_0) * 1000.0)  # ms
    a = '%s %s %s %s %s' % (md1.port, md1.addr, 'modbus_read->', v, '%4d ms ' % dt)
    print(a)
    print(md1.request)
    print(md1.response)
    print('')

    t_0 = time.time()
    v = md1.modbus_write(16, [1, 0, 0, 0, 400, 0, 1, 1])
    dt = int((time.time() - t_0) * 1000.0)  # ms
    a = '%s %s %s %s %s' % (md1.port, md1.addr, 'modbus_write->', v, '%4d ms ' % dt)
    print(a)
    print(md1.request)
    print(md1.response)
    print('')

    t_0 = time.time()
    v = md1.modbus_read(16, 8)
    dt = int((time.time() - t_0) * 1000.0)  # ms
    a = '%s %s %s %s %s' % (md1.port, md1.addr, 'modbus_read->', v, '%4d ms ' % dt)
    print(a)
    print(md1.request)
    print(md1.response)
    print('')

    # a = []
    # b = []
    # for i in range(5, 500):
    #     v = md1.modbus_write(i, [0, 0])
    #     if v:
    #         a.append(i)
    #     if md1.response[2] == 3:
    #         b.append(i)
    #         # print(hex(i), v)
    # print(a)
    # print(b)

    t_0 = time.time()
    v = md1.modbus_write(0, 3)
    # v = md1.modbus_write(16, [1, 0, 10, 0, 400])
    dt = int((time.time() - t_0) * 1000.0)  # ms
    a = '%s %s %s %s %s' % (md1.port, md1.addr, 'modbus_write->', v, '%4d ms ' % dt)
    print(a)

    t_0 = time.time()
    v = md1.modbus_write(0, 1)
    # v = md1.modbus_write(16, [1, 0, 10, 0, 400])
    dt = int((time.time() - t_0) * 1000.0)  # ms
    a = '%s %s %s %s %s' % (md1.port, md1.addr, 'modbus_write->', v, '%4d ms ' % dt)
    print(a)

    t_0 = time.time()
    v = md1.modbus_write(32 + 4, 200)
    # v = md1.modbus_write(16, [1, 0, 10, 0, 400])
    dt = int((time.time() - t_0) * 1000.0)  # ms
    a = '%s %s %s %s %s' % (md1.port, md1.addr, 'modbus_write->', v, '%4d ms ' % dt)
    print(a)

    t_0 = time.time()
    v = md1.modbus_read(16, 8)
    dt = int((time.time() - t_0) * 1000.0)  # ms
    a = '%s %s %s %s %s' % (md1.port, md1.addr, 'modbus_read->', v, '%4d ms ' % dt)
    print(a)

    print('Finished')
