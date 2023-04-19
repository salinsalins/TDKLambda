import sys

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
            self.logger.error(self.STATES[self.state])
            self.suspend()
            return False
        # check if port:address is in use
        with TDKLambda._lock:
            for d in TDKLambda._devices:
                if d != self and d.port == self.port and d.addr == self.addr and d.state > 0:
                    self.state = -2
                    self.logger.error(self.STATES[self.state])
                    self.suspend()
                    return False
        if not self.com.ready:
            self.state = -5
            self.logger.error(self.STATES[self.state])
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
        self.logger.debug(f'{self.pre} has been initialized')
        return True

    def _set_addr(self):
        return True

    def add_checksum(self, cmd):
        return cmd

    def verify_checksum(self, result):
        if not b'=' in self.command:
            return True
        csr = self.read(1)
        if csr == b'':
            self.logger.debug(f'{self.pre} No expected checksum in response')
            return False
        else:
            cs = self.checksum(result[1:])
            if csr != cs:
                self.logger.debug(f'{self.pre} Incorrect checksum in response')
                return False
            self.response = result[1:-1]
            return True

    # def _send_command(self, cmd, terminator=b'\x03'):
    #     result = super()._send_command(cmd, terminator)

    def send_command(self, cmd) -> bool:
        if not self.ready:
            self.command = cmd
            self.response = b''
            return False
        try:
            # unify command
            if isinstance(cmd, str):
                cmd = str.encode(cmd)
            #
            cmd_out = b'\x04' + self.addr_hex + cmd
            if b'=' in cmd:
                # cmd_out += '%f5.2' % value
                cmd = self.add_checksum(cmd)
            else:
                cmd_out += b'\x05'
            #
            n = self.read_retries
            while n > 1:
                n -= 1
                result = self._send_command(cmd_out, terminator=b'\x03')
                if result:
                    return True
            self.suspend()
            self.response = b''
            self.logger.info(f'{self.pre} Can not send command %s' % cmd)
            return False
        except KeyboardInterrupt:
            raise
        except:
            log_exception(self.logger, f'{self.pre} Can not send command {cmd}')
            self.suspend()
            self.response = b''
            return False

    def check_response(self, expected=b'', response=None):
        if response is None:
            response = self.response
        if not expected:
            expected = self.head_ok
        if not response.startswith(expected):
            if response.startswith(self.head_err):
                msg = 'Error response %s' % response
            else:
                msg = 'Unexpected response %s (not %s)' % (response, expected)
            self.logger.info(msg)
            return False
        return True

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

    def read_config(self):
        try:
            pass
        except KeyboardInterrupt:
            raise
        except:
            log_exception(self)


if __name__ == "__main__":
    pd1 = Lauda("COM4")
    t_0 = time.time()
    cmd = '6230'
    v1 = pd1.send_command(cmd)
    dt1 = int((time.time() - t_0) * 1000.0)  # ms
    a = '%s %s %s %s %s %s' % (pd1.port, pd1.addr, cmd, '->', v1, '%4d ms ' % dt1)
    # pd1.logger.debug(a)
    print(a)

    del pd1
    print('Finished')
