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

    def init(self):
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
        if self.id != 'Unknown Device':
            pass


        if self.name == '0000':
            self.logger.error(f'ADAM at {self.port}:{self.addr} is not recognized')
            self.state = -4
            self.suspend()
            return False
        # self.ai_n = ADAM_DEVICES[self.name]['ai']
        # self.ai_masks = [True] * self.ai_n
        # if self.ai_n > 0:
        #     self.ai_masks = self.read_masks()
        # self.ao_n = ADAM_DEVICES[self.name]['ao']
        # self.ao_masks = [True] * self.ao_n
        # # if self.ao_n > 0:
        # #     self.ao_masks = self.read_masks()
        # self.di_n = ADAM_DEVICES[self.name]['di']
        # self.do_n = ADAM_DEVICES[self.name]['do']
        self.ai_ranges = [self.read_range(c) for c in range(self.ai_n)]
        self.ai_min = [i[0] for i in self.ai_ranges]
        self.ai_max = [i[1] for i in self.ai_ranges]
        self.ai_units = [i[2] for i in self.ai_ranges]
        self.ao_ranges = [self.read_range(c) for c in range(self.ao_n)]
        self.ao_min = [i[0] for i in self.ao_ranges]
        self.ao_max = [i[1] for i in self.ao_ranges]
        self.ao_units = [i[2] for i in self.ao_ranges]
        self.state = 1
        self.logger.debug(f'ADAM-{self.name} at {self.port}:{self.addr} has been initialized')
        return True

    def _set_addr(self):
        return True

    def add_checksum(self, cmd):
        return cmd

    def verify_checksum(self, result):
        return True

    def send_command(self, cmd, prefix=b'$', addr=True, value=b'') -> bool:
        if isinstance(cmd, str):
            cmd = cmd.encode()
        cmd_out = prefix
        if addr:
            cmd_out += self.addr_hex
        return super().send_command(cmd_out + cmd + value)

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
        try:
            if self.send_command(b'M') and self.check_response():
                return self.response[3:-1].decode()
            else:
                return 'Unknown Device'
        except KeyboardInterrupt:
            raise
        except:
            log_exception(self.logger)
            return 'Unknown Device'

    def read_di_do(self):
        do = []
        di = []
        try:
            if self.send_command(b'6'):
                if not self.response.startswith(b'!') or not self.response.endswith(b'00\r'):
                    self.logger.info('Wrong response %s', self.response)
                    return do, di
                val = self.response[1:-3]
                ival = int(val, 16)
                for i in range(self.di_n):
                    di.append(bool(ival & (2 ** i)))
                for i in range(self.do_n):
                    do.append(bool(ival & (2 ** (i + 8))))
        except KeyboardInterrupt:
            raise
        except:
            log_exception(self.logger, 'Error reading DI/DO')
        return do, di

    def read_masks(self):
        result = []
        try:
            if self.send_command(b'6'):
                if not self.check_response():
                    self.logger.info('Wrong response %s', self.response)
                    return result
                val = self.response[3:-1]
                ival = int(val, 16)
                for i in range(8):
                    result.append(bool(ival & (2 ** i)))
        except KeyboardInterrupt:
            raise
        except:
            log_exception(self.logger)
        return result

    def read_di(self, chan=None):
        try:
            do, di = self.read_di_do()
            if chan is None:
                return di
            if len(di) > chan:
                return di[chan]
            return None
        except KeyboardInterrupt:
            raise
        except:
            log_exception(self.logger)
            return None

    def read_do(self, chan=None):
        try:
            do, di = self.read_di_do()
            if chan is None:
                return do
            if len(do) > chan:
                return do[chan]
            return None
        except KeyboardInterrupt:
            raise
        except:
            log_exception(self.logger)
            return None

    def write_do(self, chan=None, value=None):
        cmd = b'#' + self.addr_hex + (b'1%01X' % chan)
        try:
            if self.send_command(cmd + b'0%01X' % value, prefix=b'', addr=False):
                if self.response.startswith(b'>'):
                    return True
                self.logger.debug('Wrong response %s', self.response)
                return False
        except KeyboardInterrupt:
            raise
        except:
            log_exception(self.logger)

    def read_ai(self, chan=None):
        if chan is None:
            cmd = b'#' + self.addr_hex
        else:
            cmd = b'#' + self.addr_hex + (b'%01X' % chan)
        val = b''
        try:
            if self.send_command(cmd, prefix=b'', addr=False):
                if not self.response.startswith(b'>') or not self.response.endswith(b'\r'):
                    self.logger.debug('Wrong response %s', self.response)
                    return None
                val = self.response[1:-1]
            if chan is None:
                val = val.replace(b'+', b';+')
                val = val.replace(b'-', b';-')
                val = val.split(b';')[1:]
                val = [float(i) for i in val]
            else:
                if val:
                    val = float(val)
                else:
                    self.logger.debug('Empty response')
                    return None
        except KeyboardInterrupt:
            raise
        except:
            log_exception(self.logger)
            return None
        return val

    def write_ao(self, chan: int, value: float):
        cmd = b'#%sC%1d%+07.3f' % (self.addr_hex, chan, value)
        rsp = b'!%s' % self.addr_hex
        try:
            if self.send_command(cmd, prefix=b'', addr=False):
                if not self.response.startswith(rsp):
                    self.logger.debug('Wrong response %s', self.response)
                    return False
            return True
        except KeyboardInterrupt:
            raise
        except:
            log_exception(self.logger)
            return False

    def read_ao(self, chan: int):
        cmd = b'$%s6C%1d' % (self.addr_hex, chan)
        rsp = b'!%s' % self.addr_hex
        try:
            if self.send_command(cmd, prefix=b'', addr=False):
                if not self.response.startswith(rsp):
                    self.logger.debug('Wrong response %s', self.response)
                    return None
            return float(self.response[3:])
        except KeyboardInterrupt:
            raise
        except:
            log_exception(self.logger)
            return None

    def read_config(self):
        try:
            if self.send_command(b'2'):
                if not self.check_response():
                    return None
            type_code = self.response[3:5]
            baud = ADAM_BAUDS[self.response[5:7]]
            data_format = self.response[7:9]
            return type_code, baud, data_format
        except KeyboardInterrupt:
            raise
        except:
            log_exception(self)

    def read_range(self, chan):
        cmd = b'$%s8C%X' % (self.addr_hex, chan)
        rsp = b'!%sC%X' % (self.addr_hex, chan)
        try:
            if self.send_command(cmd, prefix=b'', addr=False):
                if not self.response.startswith(rsp):
                    return None
            if self.response[5:6] == b'R':
                r = ADAM_RANGES[self.response[6:8]]
            else:
                r = ADAM_RANGES[self.response[5:7]]
            return r
        except KeyboardInterrupt:
            raise
        except:
            log_exception(self)


if __name__ == "__main__":
    pd1 = Lauda("COM12", 11, baudrate=38400)
    pd2 = Lauda("COM12", 14, baudrate=38400)
    t_0 = time.time()
    v1 = pd1.read_device_id()
    dt1 = int((time.time() - t_0) * 1000.0)  # ms
    a = '%s %s %s %s %s' % (pd1.port, pd1.addr, 'read_device_id ->', v1, '%4d ms ' % dt1)
    # pd1.logger.debug(a)
    print(a)

    t_0 = time.time()
    v2 = pd2.read_device_id()
    dt2 = int((time.time() - t_0) * 1000.0)  # ms
    # pd2.logger.debug('%s %s %s %s %s %s', pd2.port, pd2.addr, 'read_device_id ->', v2, '%4d ms ' % dt2,
    #                  '%5.3f' % pd2.min_read_time)
    a = '%s %s %s %s %s' % (pd2.port, pd2.addr, 'read_device_id ->', v2, '%4d ms ' % dt2)
    print(a)
    d = pd1
    v = d.read_di(3)
    print(d.name, 'r di[3]=', v, d.response)
    v = d.read_di()
    print(d.name, 'r di[*]=', v, d.response)
    v = d.read_do()
    print(d.name, 'r do=[*]', v, d.response)
    v = d.write_do(3, False)
    print(d.name, 'w do[3]=', v, d.response)
    v = d.read_di()
    print(d.name, 'r di=[*]', v, d.response)
    v = d.read_do()
    print(d.name, 'r do=[*]', v, d.response)
    v = d.read_di(3)
    print(d.name, 'r di[3]=', v, d.response)
    v = d.read_do(3)
    print(d.name, 'r do[3]=', v, d.response)
    v = d.read_do()
    print(d.name, 'r do=[*]', v, d.response)
    #
    v2 = pd1.read_ai(3)
    print(pd1.name, 'r ai[3]=', v2, pd1.response)
    v2 = pd1.read_ai()
    print(pd1.name, 'r ai[*]=', v2, pd1.response)
    v2 = pd1.read_di()
    print(pd1.name, 'r di[*]=', v2, pd1.response)
    #
    ao = -1.5
    v2 = pd2.write_ao(1, ao)
    print(pd2.name, 'w ao[1]=', v2, ao, pd2.response)
    v2 = pd2.read_ao(1)
    print(pd2.name, 'r ao[1]=', v2, pd2.response)

    del pd1
    del pd2
    print('Finished')
