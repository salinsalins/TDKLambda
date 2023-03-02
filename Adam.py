import sys;
import time

sys.path.append('../TangoUtils');
sys.path.append('../IT6900')
from TDKLambda import TDKLambda


class Adam(TDKLambda):

    def init(self):
        self.addr_hex = (b'%02X' % self.addr)[:2]
        self.head_ok = b'!' + self.addr_hex
        self.head_err = b'?' + self.addr_hex
        self.suspend_to = 0.0
        self.suspend_flag = False
        if not self.com.ready:
            self.suspend()
            return
        # read device type
        self.id = self.read_device_id()
        if self.id.startswith(self.head_ok):
            self.state = 1
            # determine max current and voltage from model name
            # try:
            #     ids = self.id.split('-')
            #     mv = ids[-2].split('G')
            #     self.max_current = float(ids[-1])
            #     self.max_voltage = float(mv[-1][2:])
            # except:
            #     self.logger.warning('Can not set max values')
        else:
            self.logger.error(f'ADAM at {self.port}:{self.addr} is not recognized')
            self.state = -4
            return
        self.logger.debug(f'ADAM at {self.port}:{self.addr} has been initialized')

    def _set_addr(self):
        return True

    def add_checksum(self, cmd):
        return cmd

    def verify_checksum(self, result):
        return True

    def send_command(self, cmd, prefix=b'$', addr=True) -> bool:
        if isinstance(cmd, str):
            cmd = cmd.encode()
        cmd_out = prefix
        if addr:
            cmd_out += self.addr_hex
        return super().send_command(cmd_out + cmd)

    def check_response(self, expected=b'', response=None):
        if response is None:
            response = self.response
        if not expected:
            expected = self.head_ok
        if not response.startswith(expected):
            if response.startswith(self.head_err):
                msg = 'Error response %s' % response
            msg = 'Unexpected response %s (not %s)' % (response, expected)
            self.logger.info(msg)
            return False
        return True

    def read_device_id(self):
        try:
            if self.send_command(b'M'):
                return self.response[:-1]
            else:
                return 'Unknown Device'
        except KeyboardInterrupt:
            raise
        except:
            return 'Unknown Device'

    def read_di(self, chan=None):
        v = None
        try:
            if self.send_command(b'6'):
                if not self.response.startswith(b'!') or not self.response.endswith(b'00\r'):
                    self.logger.info('Wrong response format %s', self.response)
                    return None
                val = self.response[1:-3]
                if chan is None:
                    chan = [i for i in range(len(val) * 8)]
                if isinstance(chan, (list, tuple)):
                    v = []
                    for i in chan:
                        v.append(bool(int(val, 16) & (2 ** i)))
                else:
                    v = bool(int(val, 16) & (2 ** chan))
        except KeyboardInterrupt:
            raise
        except:
            self.logger.info('Wrong response %s format', self.response)
            return None
        return v

    def write_do(self, chan, value):
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


if __name__ == "__main__":
    pd1 = Adam("COM12", 16, baudrate=38400)
    pd2 = Adam("COM12", 11, baudrate=38400)
    t_0 = time.time()
    v1 = pd1.read_device_id()
    dt1 = int((time.time() - t_0) * 1000.0)  # ms
    pd1.logger.debug('test')
    a = '%s %s %s %s %s %s' % (
    pd1.port, pd1.addr, 'read_device_id ->', v1, '%4d ms ' % dt1, '%5.3f' % pd1.min_read_time)
    pd1.logger.debug(a)

    t_0 = time.time()
    v2 = pd2.read_device_id()
    dt2 = int((time.time() - t_0) * 1000.0)  # ms
    pd2.logger.debug('test')
    pd2.logger.debug('%s %s %s %s %s %s', pd2.port, pd2.addr, 'read_device_id ->', v2, '%4d ms ' % dt2,
                     '%5.3f' % pd2.min_read_time)
    v2 = pd2.read_di(3)
    print(v2, pd2.response)

    del pd1
    del pd2
    print('Finished')
