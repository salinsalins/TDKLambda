from ModbusDevice import *

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'CKD Python API'
APPLICATION_NAME_SHORT = 'CKD'
APPLICATION_VERSION = '1.0'


class CKD(ModbusDevice):

    def __init__(self, port: str, addr: int=1, **kwargs):
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

    def read_one(self, addr, length=1):
        v = self.modbus_read(addr, length=1)
        if v:
            if length > 1:
                return v
            return v[0]
        else:
            return None

    def read_set_voltage(self):
        return self.read_one(4105)

    def read_set_current(self):
        return self.read_one(4106)

    def read_out_voltage(self):
        return self.read_one(6146)

    def read_out_current(self):
        return self.read_one(6147)

    def read_rectifier_current_k(self):
        return self.read_one(6148)

    def read_rectifier_current_l(self):
        return self.read_one(6148)

    def read_status(self):
        return self.read_one(6160)

    def read_error(self):
        return self.read_status() > 127

    def modbus_write_ckd(self, start: int, data, length = False, address=None, command=38) -> int:
        if isinstance(data, float):
            data = [int(data * 64.),]
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
        if length:
            length = len(out)
            msg += int.to_bytes(length // 2, 2, byteorder="big")
            msg += int.to_bytes(length, 1, byteorder='big')
        msg += out
        if not self.write(msg):
            return 0
        if not self.read():
            return 0
        data_out = int.from_bytes(self.response[4:6], byteorder='big')
        if data[0] == data_out:
            return 2 * len(data)
        return 0

    def modbus_read_ckd(self, start: int, length: int=1, address=None, command=35):
        self.command = command
        if address is None:
            address = self.addr
        msg = address.to_bytes(1, byteorder='big')
        msg += self.command.to_bytes(1, byteorder='big')
        msg += int.to_bytes(start, 2, byteorder='big')
        msg += int.to_bytes(length, 2, byteorder='big')
        data = []
        if not self.write(msg):
            return data
        if not self.read():
            return data
        data_length = self.response[2]
        for i in range(data_length):
            data.append(self.response[3 + i])
        if length == 1:
            return data[0] * 256 + data[1]
        return data


def print_ints(arr, r=None, d=3, base=None):
    if r is None:
        r = []
    n = 0
    for i in arr:
        if n < d:
            print("{:03d}".format(int(i)))
        else:
            if (n-d) % 2 == 0:
                j = int(i)
            else:
                k = 256*j + int(i)
                if len(r) > n:
                    val = int(r[n-1])*256 + int(r[n])
                    if k != val:
                        val = "{:05d}".format(val)
                    else :
                        val = ''
                else:
                    val = ''
                if base is not None:
                    bases = "{:05d}: ".format(base + (n-d) // 2)
                else:
                    bases = '       '
                print(bases, "{:05d}".format(k), "{:03d}".format(j),"{:03d}".format(i), "{:08b}".format(j), "{:08b}".format(i), val)
        n += 1


if __name__ == "__main__":
    print('')
    md1 = CKD("COM10")
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
        # print(md1.request)
        # print(md1.response)
        if md1.response[1] > 127:
            print("ERROR", md1.response[2])
        print('request')
        print_ints(md1.request, d=2)
        print('response')
        print_ints(md1.response, r1, base=a01)
        r1 = list(md1.response)
        print('')

        # a02 = 6144
        # t_0 = time.time()
        # v2 = md1.modbus_read(a02, 20, command=3)
        # dt = int((time.time() - t_0) * 1000.0)  # ms
        # a2 = '%s %s %s %s %s' % (md1.port, md1.addr, 'modbus_read->', v2, '%4d ms ' % dt)
        # # print(a2)
        # # print(md1.request)
        # # print(md1.response)
        # # print_ints(md1.response, r2, base=a02)
        # if md1.response[1] > 127:
        #     print("ERROR", md1.response[2])
        # print('request')
        # print_ints(md1.request)
        # print('response')
        # print_ints(md1.response, r2, base=a02)
        # r2 = list(md1.response)
        # print('')
        t_0 = time.time()
        v = md1.modbus_write(4096, [256,])
        dt = int((time.time() - t_0) * 1000.0)  # ms
        a1 = '%s %s %s %s %s' % (md1.port, md1.addr, 'modbus_write->', v, '%4d ms ' % dt)
        print(a1)
        if md1.response[1] > 127:
            print("ERROR", md1.response[2])
        print('request')
        print_ints(md1.request, d=2)
        print('response')
        print_ints(md1.response, d=2)
        print('')
        # md1.modbus_write(4097, [1,])

        t_0 = time.time()
        v = md1.modbus_write_ckd(171, 1280)
        dt = int((time.time() - t_0) * 1000.0)  # ms
        a1 = '%s %s %s %s %s' % (md1.port, md1.addr, 'modbus_write_ckd->', v, '%4d ms ' % dt)
        print(a1)
        if md1.response[1] > 127:
            print("ERROR", md1.response[2])
        print('request')
        print_ints(md1.request, d=2)
        print('response')
        print_ints(md1.response, d=2)
        print('')

        t_0 = time.time()
        v = md1.modbus_read_ckd(171)
        dt = int((time.time() - t_0) * 1000.0)  # ms
        a1 = '%s %s %s %s %s' % (md1.port, md1.addr, 'modbus_read_ckd->', v, '%4d ms ' % dt)
        print(a1)
        if md1.response[1] > 127:
            print("ERROR", md1.response[2])
        print('request')
        print_ints(md1.request, d=2)
        print('response')
        print_ints(md1.response, d=2)
        print('')

        a01 = 4096
        t_0 = time.time()
        v1 = md1.modbus_read(a01, 18, command=3)
        dt = int((time.time() - t_0) * 1000.0)  # ms
        a1 = '%s %s %s %s %s' % (md1.port, md1.addr, 'modbus_read->', v1, '%4d ms ' % dt)
        print(a1)
        # print(md1.request)
        # print(md1.response)
        if md1.response[1] > 127:
            print("ERROR", md1.response[2])
        print('request')
        print_ints(md1.request, d=2)
        print('response')
        print_ints(md1.response, r1, base=a01)
        r1 = list(md1.response)
        print('')

        exit()



    print('Finished')
