import sys
if '../TangoUtils' not in sys.path: sys.path.append('../TangoUtils')
if '../IT6900' not in sys.path: sys.path.append('../IT6900')
import time

from log_exception import log_exception
from TDKLambda import TDKLambda

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'Adam I/O modules Python API'
APPLICATION_NAME_SHORT = 'Adam'
APPLICATION_VERSION = '2.0'

ADAM_DEVICES = {
    '0000': {'di': 0, 'do': 0, 'ai': 0, 'ao': 0},
    '4017+': {'di': 0, 'do': 0, 'ai': 8, 'ao': 0},
    '4017': {'di': 0, 'do': 0, 'ai': 8, 'ao': 0},
    '4117': {'di': 0, 'do': 0, 'ai': 8, 'ao': 0},
    '4118': {'di': 0, 'do': 0, 'ai': 8, 'ao': 0},
    '4024': {'di': 0, 'do': 0, 'ai': 0, 'ao': 4},
    '4055': {'di': 8, 'do': 8, 'ai': 0, 'ao': 0}
}
ADAM_RANGES = {
    b'00': [-15, 15, 'mV'],
    b'01': [-50, 50, 'mV'],
    b'02': [-100, 100, 'mV'],
    b'03': [-500, 500, 'mV'],
    b'04': [-1, 1, 'V'],
    b'05': [-2.5, 2.5, 'V'],
    b'06': [-20, 20, 'mA'],
    b'07': [4, 20, 'mA'],
    b'08': [-10, 10, 'V'],
    b'09': [-5, 5, 'V'],
    b'0A': [-1, 1, 'V'],
    b'0B': [-500, 500, 'mV'],
    b'0C': [-150, 150, 'mV'],
    b'0D': [-20, 20, 'mA'],
    b'0E': [0, 760, 'C'],
    b'0F': [0, 1370, 'C'],
    b'10': [-100, 400, 'C'],
    b'11': [0, 1000, 'C'],
    b'12': [500, 1750, 'C'],
    b'13': [500, 1750, 'C'],
    b'14': [500, 1800, 'C'],
    b'15': [-15, 15, 'V'],
    b'18': [-200, 1300, 'C'],
    b'20': [-50, 150, 'C'],
    b'21': [0, 100, 'C'],
    b'22': [0, 200, 'C'],
    b'23': [0, 400, 'C'],
    b'24': [-200, 200, 'C'],
    b'25': [-50, 150, 'C'],
    b'26': [0, 100, 'C'],
    b'27': [0, 200, 'C'],
    b'28': [0, 400, 'C'],
    b'29': [-200, 200, 'C'],
    b'2A': [-40, 160, 'C'],
    b'2B': [-30, 120, 'C'],
    b'40': [0, 15, 'mV'],
    b'30': [0, 20, 'mA'],
    b'31': [4, 20, 'mA'],
    b'32': [-10, 10, 'V'],
    b'41': [0, 50, 'mV'],
    b'42': [0, 100, 'mV'],
    b'43': [0, 500, 'mV'],
    b'44': [0, 1, 'V'],
    b'45': [0, 2.5, 'V'],
    b'46': [0, 20, 'mV'],
    b'48': [0, 10, 'V'],
    b'49': [0, 5, 'V'],
    b'4A': [0, 1, 'V'],
    b'4B': [0, 500, 'mV'],
    b'4C': [0, 150, 'mV'],
    b'4D': [0, 20, 'mV'],
    b'55': [0, 15, 'V']
}
ADAM_BAUDS = {
    b'03': 1200,
    b'04': 2400,
    b'05': 4800,
    b'06': 9600,
    b'07': 19200,
    b'08': 38400,
    b'09': 57600,
    b'0A': 115200,
    b'0B': 230400
}


# os.environ["TANGO_HOST"] = '192.168.1.41:10000'
# db = tango.Database('192.168.1.41', '10000')

class Adam(TDKLambda):

    # def __init__(self, port, addr, **kwargs):
    #     super().__init__(port, addr, **kwargs)
    #
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
        # self.id = self.read_device_id()
        n = 0
        self.id = 'Unknown Device'
        while n < self.read_retries:
            n += 1
            result = self._send_command(b'$'+self.addr_hex + b'M\r')
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
        self.pre = f'ADAM{self.name} at {self.port}:{self.addr}'
        if self.name == '0000':
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
        if self.di_n <= 0:
            return None
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
                f = float(self.response[3:])
                return f
            return None
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
        no_8c_modules = ['4017']
        if self.name in no_8c_modules:
            cmd = b'$%s2' % self.addr_hex
            rsp = b'!%s' % self.addr_hex
            try:
                if self.send_command(cmd, prefix=b'', addr=False):
                    if not self.response.startswith(rsp):
                        return None
                r = ADAM_RANGES[self.response[3:5]]
                return r
            except KeyboardInterrupt:
                raise
            except:
                log_exception(self.logger, 'Error respotce %s', self.response)
                return None
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
            log_exception(self.logger, 'Error: Response = %s', self.response)


if __name__ == "__main__":
    pd1 = Adam("192.168.1.203", 15, baudrate=38400)
    pd2 = Adam("192.168.1.203", 7, baudrate=38400)
    pd = [pd1, pd2]
    n = 1
    while n:
        n -= 1
        for p in pd:
            t_0 = time.time()
            v = p.read_device_id()
            dt = int((time.time() - t_0) * 1000.0)  # ms
            a = '%s %s %s %s %s' % (p.port, p.addr, 'read_device_id ->', v, '%4d ms ' % dt)
            d = p
            if d.di_n > 0:
                v = d.read_di(3)
                print(d.name, 'r di[3]=', v, d.response)
                v = d.read_di()
                print(d.name, 'r di[*]=', v, d.response)
                v = d.read_do()
                print(d.name, 'r do=[*]', v, d.response)
                v = d.write_do(3, True)
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
            if d.ai_n > 0:
                v2 = p.read_ai(3)
                print(p.name, 'r ai[3]=', v2, p.response)
                v2 = p.read_ai()
                print(p.name, 'r ai[*]=', v2, p.response)
                v2 = p.read_di()
                print(p.name, 'r di[*]=', v2, p.response)
            #
            if d.ao_n > 0:
                ao = -1.5
                v2 = p.write_ao(1, ao)
                print(p.name, 'w ao[1]=', v2, ao, p.response)
                v2 = p.read_ao(1)
                print(p.name, 'r ao[1]=', v2, p.response)

            del p
    print('Finished')
