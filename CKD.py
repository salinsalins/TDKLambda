from ModbusDevice import *

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'CKD Python API'
APPLICATION_NAME_SHORT = 'CKD'
APPLICATION_VERSION = '1.0'


class CKD(ModbusDevice):

    def __init__(self, port: str, **kwargs):
        if 'baudrate' not in kwargs:
            kwargs['baudrate'] = 57600
        if 'parity' not in kwargs:
            kwargs['parity'] = 'E'
        super().__init__(port, 1, **kwargs)
        self.id = 'CKD'
        self.pre = f'{self.id} at {self.port}: {self.addr} '
        self.config = {'settings': []}
        errors = 0
        v = self.modbus_write(0, self.config['settings'])
        if v != len(self.config['settings']):
            self.debug(f'Settings initialization error')
            errors += 1
        if errors == 0:
            self.initialized = True
            self.suspend_to = 0.0
            self.info('has been initialized')
        else:
            self.initialized = False
            self.info('has been initialized with errors')
        return

    def write_set_voltage(self, v:int):
        return self.modbus_write(4105, [v,]) == 1

    def write_set_current(self, v:int):
        return self.modbus_write(4106, [v,]) == 1

    def write_error_state(self, v:bool):
        self.modbus_write(4096, [256,])
        return self.modbus_write(4097, [1,]) == 1

    def _read(self, addr, length=1):
        v = self.modbus_read(addr, length=1)
        if v:
            if length > 1:
                return v
            return v[0]
        else:
            return None

    def read_set_voltage(self):
        return self._read(4105)

    def read_set_current(self):
        return self._read(4106)

    def read_out_voltage(self):
        return self._read(6146)

    def read_out_current(self):
        return self._read(6147)

    def read_rectifier_current_k(self):
        return self._read(6148)

    def read_rectifier_current_l(self):
        return self._read(6148)

    def read_status(self):
        return self._read(6160)

    def read_error(self):
        return self.read_status() > 127


def print_ints(arr, r, base=None):
    d = 0
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
    md1 = CKD("COM14")
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
        if md1.response[1] > 127:
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
        v = md1.modbus_write_ckd(192, [1280, ], command=38)
        # v = md1.modbus_write(4105, [2000, 100])
        # v = md1.modbus_write(4106, [640])
        # v = md1.modbus_write(16, [1, 0, 10, 0, 400])
        # dt = int((time.time() - t_0) * 1000.0)  # ms
        # a = '%s %s %s %s %s' % (md1.port, md1.addr, 'modbus_write->', v, '%4d ms ' % dt)
        # print(a)
        print_ints(md1.request, r2, base=0)
        print(md1.request)
        print(md1.response)
        print_ints(md1.response, r2, base=0)
        print('')

        v1 = md1.modbus_read(a01, 18, command=3)
        print_ints(md1.response, r1, base=a01)
        print('')
        v2 = md1.modbus_read(a02, 20, command=3)
        print_ints(md1.response, r2, base=a02)

        exit()



    print('Finished')
