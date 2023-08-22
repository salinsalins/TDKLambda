import logging
import sys

from config_logger import config_logger

if '../TangoUtils' not in sys.path: sys.path.append('../TangoUtils')
if '../IT6900' not in sys.path: sys.path.append('../IT6900')
import time

from log_exception import log_exception
from TDKLambda import TDKLambda

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'Lauda Python API'
APPLICATION_NAME_SHORT = 'Lauda'
APPLICATION_VERSION = '1.0'


# os.environ["TANGO_HOST"] = '192.168.1.41:10000'
# db = tango.Database('192.168.1.41', '10000')

class Lauda(TDKLambda):
    def __init__(self, port, addr=5, **kwargs):
        self.cs = b'\x00'
        kwargs['bytesize'] = 7
        kwargs['parity'] = 'E'
        kwargs['baudrate'] = 38400
        super().__init__(port, addr, **kwargs)

    def init(self):
        self.suspend_to = 0.0
        self.pre = f'LAUDA at {self.port}:{self.addr}'
        self.addr_hex = (b'%02X' % self.addr)[:2]
        self.name = 'LAUDA'
        # check device address
        if self.addr <= 0:
            self.state = -1
            self.logger.info(f'{self.pre} ' + self.STATES[self.state])
            self.suspend()
            return False
        # check if port:address is in use
        with TDKLambda._lock:
            for d in TDKLambda._devices:
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
        self.id = self.read_device_id()
        # if self.name == '0000':
        #     self.logger.error(f'ADAM at {self.port}:{self.addr} is not recognized')
        #     self.state = -4
        #     self.suspend()
        #     return False
        self.state = 1
        self.logger.info(f'{self.pre} has been initialized {self.read_retries} {self.read_timeout}')
        return True

    def _set_addr(self):
        return True

    def add_checksum(self, cmd):
        return cmd

    @staticmethod
    def checksum(cmd):
        s = 0
        for b in cmd:
            s = s ^ int(b)
        s = s ^ 3
        return s.to_bytes(1, 'little')

    def verify_checksum(self, value):
        if b'=' in self.command:
            return value == b'\x06'
        #
        csr = self.read(1)
        if csr == b'':
            self.logger.debug(f'{self.pre} No expected checksum in response')
            return False
        cs = self.checksum(value[1:-1])
        if csr != cs:
            self.logger.debug(f'{self.pre} Incorrect checksum in response')
            return False
        if self.response[:1] != b'\x02':
            self.logger.debug(f'{self.pre} Wrong response')
            return False
        return True

    def send_command(self, cmd) -> bool:
        self.response = b''
        # unify command
        if isinstance(cmd, str):
            cmd = str.encode(cmd)
        self.command = cmd
        try:
            if not self.ready:
                return False
            #
            cmd_out = b'\x04' + self.addr_hex
            if b'=' in cmd:
                cmd_out += b'\x02' + cmd
                cmd_out += b'\x03' + self.checksum(cmd)
                t = (b'\x06', b'\x15')
            else:
                cmd_out += cmd + b'\x05'
                t = b'\x03'
            #
            n = 0
            while n < self.read_retries:
                n += 1
                result = self._send_command(cmd_out, terminator=t)
                if result:
                    return True
                self.logger.info(f'{self.pre} Command {cmd} retry {n} of {self.read_retries}')
            if b'=' in self.command and self.response == b'\x15':
                self.logger.debug(f'{self.pre} Unrecognized command {cmd}')
                return False
            self.response = b''
            self.suspend()
            self.logger.info(f'{self.pre} Can not send command {cmd}')
            return False
        except KeyboardInterrupt:
            raise
        except:
            self.response = b''
            self.suspend()
            log_exception(self.logger, f'{self.pre} Exception sending {cmd}')
            return False

    def get_response(self):
        if b'=' in self.command:
            if self.response == b'\x15':
                return f'Unrecognized command'
            if self.response == b'\x06':
                return f'Command sent OK'
            return f'I/O Error'
        return str(self.response[1:-1].decode())

    def read_device_id(self):
        return 'LAUDA'
        # try:
        #     if self.send_command(b'M') and self.check_response():
        #         return self.response[3:-1].decode()
        #     else:
        #         return 'Unknown Device'
        # except KeyboardInterrupt:
        #     raise
        # except:
        #     log_exception(self.logger)
        #     return 'Unknown Device'

    def read_value(self, param: str, result_type=float):
        resp = self.send_command(param)
        if resp:
            try:
                v = self.get_response()
                v1 = v.split('=')
                value = result_type(v1[-1])
                return value
            except KeyboardInterrupt:
                raise
            except:
                pass
        msg = f'{self.pre} {param} read error'
        self.logger.debug(msg)
        return None

    def read_bit(self, param: str, n):
        resp = self.send_command(param)
        if resp:
            try:
                v = self.get_response()
                v1 = v.split('=')
                value = bool(int(v1[-1]) & 2 ** n)
                return value
            except KeyboardInterrupt:
                raise
            except:
                pass
        msg = f'{self.pre} p{param} read error'
        self.logger.debug(msg)
        return None

    def write_value(self, param: str, value, *args):
        resp = self.send_command(f'{param}={value}')
        if resp:
            return True
        msg = f'{self.pre} {param} write error'
        self.logger.debug(msg)
        return False

    def write_bit(self, param: str, bit, value):
        v0 = self.read_value(param, int)
        if v0 is None:
            msg = f'{self.pre} {param}_{bit} write error'
            self.logger.debug(msg)
            return False
        if value:
            v1 = int(v0) | 2 ** bit
        else:
            v1 = int(v0) & ~(2 ** bit)
        return self.write_value(param, v1)


if __name__ == "__main__":
    print(f'Simple LAUDA control utility ver.{APPLICATION_VERSION}')
    port = input('LAUDA Port <COM4>:')
    if not port:
        port = 'COM4'
    addr = input('LAUDA Address <5>:')
    if not addr:
        addr = 5
    logger = config_logger()
    logger.setLevel(logging.ERROR)
    lda = Lauda(port, int(addr))
    while True:
        command = input('Send command:')
        if not command:
            break
        if command.startswith('read'):
            command = command.replace('read ', '')
        elif command.startswith('write'):
            command = command.replace('write ', '')
        t_0 = time.time()
        v1 = lda.send_command(command)
        r1 = lda.get_response()
        dt1 = int((time.time() - t_0) * 1000.0)  # ms
        a = f'{lda.pre} {command} -> {r1} in {dt1} ms'
        print(a)
    del lda
    print('Finished')
