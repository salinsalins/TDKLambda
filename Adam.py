import sys; sys.path.append('../TangoUtils'); sys.path.append('../IT6900')
from TDKLambda import TDKLambda


class Adam(TDKLambda):

    def init(self):
        if isinstance(self.adr, int):
            self.adr = ('%X' % self.adr).encode()
            self.head_ok = b'!' + self.addr
            self.head_err = b'?' + self.addr
        self.suspend_to = 0.0
        self.suspend_flag = False
        if not self.com.ready:
            self.suspend()
            return
        # read device type
        self.id = self.read_device_id()
        if 'LAMBDA' in self.id:
            self.state = 1
            # determine max current and voltage from model name
            try:
                ids = self.id.split('-')
                mv = ids[-2].split('G')
                self.max_current = float(ids[-1])
                self.max_voltage = float(mv[-1][2:])
            except:
                self.logger.warning('Can not set max values')
        else:
            msg = 'LAMBDA device is not recognized'
            self.logger.error(msg)
            self.state = -4
            return
        # msg = 'TDKLambda: %s SN:%s has been initialized' % (self.id, self.sn)
        self.logger.debug(f'TDKLambda at {self.port}:{self.addr} has been initialized')

    def _set_addr(self):
        return True

    def add_checksum(self, cmd):
        return cmd

    def verify_checksum(self, result):
        return True

    def send_command(self, cmd, prefix=b'$', addr=True) -> bool:
        cmd_out = prefix
        if addr:
            cmd_out += self.addr
        return super().send_command(cmd_out + cmd)

    def read_device_id(self):
        try:
            if self.send_command(b'M'):
                return self.response[:-1].decode()
            else:
                return 'Unknown Device'
        except:
            return 'Unknown Device'

