import sys;

from log_exception import log_exception

sys.path.append('../TangoUtils');
sys.path.append('../IT6900')
import time

from TDKLambda import TDKLambda

ADAM_DEVICES = {
    '0000': {'di': 0, 'do': 0, 'ai': 0, 'ao': 0},
    '4117': {'di': 0, 'do': 0, 'ai': 8, 'ao': 0},
    '4118': {'di': 0, 'do': 0, 'ai': 8, 'ao': 0},
    '4024': {'di': 4, 'do': 0, 'ai': 0, 'ao': 4},
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


class Adam(TDKLambda):

    def init(self):
        self.addr_hex = (b'%02X' % self.addr)[:2]
        self.head_ok = b'!' + self.addr_hex
        self.head_err = b'?' + self.addr_hex
        self.suspend_to = 0.0
        self.suspend_flag = False
        self.id = b'Uninitialized'
        # self.state = 0
        if not self.com.ready:
            self.suspend()
            return
        # read device type
        self.id = self.read_device_id()
        self.name = self.id
        if self.id != 'Unknown Device':
            self.state = 1
            if self.id not in ADAM_DEVICES:
                self.name = '0000'
                for key in ADAM_DEVICES:
                    if self.id[-2:] == key[-2:]:
                        self.logger.info(f'Using {key} instead of {self.id} for devise type')
                        self.name = key
                        break
        if self.name == '0000':
            self.logger.error(f'ADAM at {self.port}:{self.addr} is not recognized')
            self.state = -4
            return
        self.ai_n = ADAM_DEVICES[self.name]['ai']
        self.ao_n = ADAM_DEVICES[self.name]['ao']
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
        self.logger.debug(f'ADAM-{self.name} at {self.port}:{self.addr} has been initialized')

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
            return 'Unknown Device'

    def read_di_do(self):
        do = []
        di = []
        try:
            if self.send_command(b'6'):
                if not self.response.startswith(b'!') or not self.response.endswith(b'00\r'):
                    self.logger.info('Wrong response %s', self.response)
                    return None
                val = self.response[1:-3]
                ival = int(val, 16)
                for i in range(8):
                    do.append(bool(ival & (2 ** i)))
                    di.append(bool(ival & (2 ** (2 * i))))
        except KeyboardInterrupt:
            raise
        except:
            log_exception(self.logger, 'Error reading DI/DO')
        return do, di

    def read_di(self, chan=None):
        try:
            do, di = self.read_di_do()
            if chan is None:
                return di
            return di[chan]
        except KeyboardInterrupt:
            raise
        except:
            return None

    def read_do(self, chan=None):
        try:
            do, di = self.read_di_do()
            if chan is None:
                return do
            return do[chan]
        except KeyboardInterrupt:
            raise
        except:
            return None

    def write_do(self, chan=None, value=None):
        cmd = b'#' + self.addr_hex + (b'1%01X' % chan)
        try:
            if self.send_command(cmd + b'0%01X' % value, prefix=b'', addr=False):
                if self.response.startswith(b'>'):
                    return True
                self.logger.info('Wrong response %s', self.response)
                return False
        except KeyboardInterrupt:
            raise
        except:
            self.logger.info('Wrong response %s', self.response)

    def read_ai(self, chan=None):
        if chan is None:
            cmd = b'#' + self.addr_hex
        else:
            cmd = b'#' + self.addr_hex + (b'%01X' % chan)
        val = b''
        try:
            if self.send_command(cmd, prefix=b'', addr=False):
                if not self.response.startswith(b'>') or not self.response.endswith(b'\r'):
                    self.logger.info('Wrong response %s', self.response)
                    return None
                val = self.response[1:-1]
            if chan is None:
                val = val.replace(b'+', b';+')
                val = val.replace(b'-', b';-')
                val = val.split(b';')[1:]
                val = [float(i) for i in val]
            else:
                val = float(val)
        except KeyboardInterrupt:
            raise
        except:
            self.logger.info('Wrong response %s', self.response)
            return None
        return val

    def write_ao(self, chan: int, value: float):
        cmd = b'#%sC%1d%+07.3f' % (self.addr_hex, chan, value)
        rsp = b'!%s' % self.addr_hex
        try:
            if self.send_command(cmd, prefix=b'', addr=False):
                if not self.response.startswith(rsp):
                    self.logger.info('Wrong response %s', self.response)
                    return False
            return True
        except KeyboardInterrupt:
            raise
        except:
            self.logger.info('Wrong response %s', self.response)
            return False

    def read_ao(self, chan: int):
        cmd = b'$%s6C%1d' % (self.addr_hex, chan)
        rsp = b'!%s' % self.addr_hex
        try:
            if self.send_command(cmd, prefix=b'', addr=False):
                if not self.response.startswith(rsp):
                    self.logger.info('Wrong response %s', self.response)
                    return None
            return float(self.response[3:])
        except KeyboardInterrupt:
            raise
        except:
            self.logger.info('Wrong response %s', self.response)
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
    pd1 = Adam("COM12", 16, baudrate=38400)
    pd2 = Adam("COM12", 14, baudrate=38400)
    t_0 = time.time()
    v1 = pd1.read_device_id()
    dt1 = int((time.time() - t_0) * 1000.0)  # ms
    a = '%s %s %s %s %s %s' % (
        pd1.port, pd1.addr, 'read_device_id ->', v1, '%4d ms ' % dt1, '%5.3f' % pd1.min_read_time)
    # pd1.logger.debug(a)
    print(a)

    t_0 = time.time()
    v2 = pd2.read_device_id()
    dt2 = int((time.time() - t_0) * 1000.0)  # ms
    # pd2.logger.debug('%s %s %s %s %s %s', pd2.port, pd2.addr, 'read_device_id ->', v2, '%4d ms ' % dt2,
    #                  '%5.3f' % pd2.min_read_time)
    a = '%s %s %s %s %s %s' % (
        pd2.port, pd2.addr, 'read_device_id ->', v2, '%4d ms ' % dt2, '%5.3f' % pd2.min_read_time)
    print(a)
    v2 = pd2.read_di(3)
    print(v2, pd2.response)
    v2 = pd2.read_di()
    print(v2, pd2.response)
    v2 = pd2.write_do(3, True)
    print(v2, pd2.response)
    v2 = pd1.read_ai(3)
    print('Read ai3 =', v2, pd1.response)
    v2 = pd1.read_ai()
    print(v2, pd1.response)
    v2 = pd1.read_di()
    print(v2, pd1.response)
    v2 = pd2.write_ao(1, -16.0)
    print(v2, pd2.response)
    v2 = pd2.read_ao(1)
    print(v2, pd2.response)

    del pd1
    del pd2
    print('Finished')
