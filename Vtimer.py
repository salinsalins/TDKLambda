import time

from ModbusDevice import ModbusDevice

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'Vtimer I/O modules Python API'
APPLICATION_NAME_SHORT = 'Vtimer'
APPLICATION_VERSION = '1.0'


class Vtimer(ModbusDevice):
    def __init__(self, port: str, addr: int, **kwargs):
        super().__init__(port, addr, **kwargs)
        self.id = 'Timer'
        self.pre = f'{self.id} at {self.port}: {self.addr} '
        self.config = {'settings': [0, 0, 0, 1, 1], 'channels': [[0, 0, 0, 0, 1, 0, 1, 1] for i in range(13)]}
        errors = 0
        if not hasattr(self, 'initialized'):
            self.initialized = False
            self.start = [0] * 12
            self.stop = [1] * 12
            self.enable = [0] * 12
            self.duration = 1
            self.mode = 0
            self.output = 1
        v = self.modbus_write(0, self.config['settings'])
        if v != 5:
            self.debug(f'Settings initialization error')
            errors += 1
        for i in range(1, 13):
            v = self.modbus_write(16 * i, self.config['channels'][i])
            if v != 8:
                self.debug(f'Channel {i} initialization error')
                errors += 1
        if errors == 0:
            self.initialized = True
            self.info('has been initialized')
        else:
            self.initialized = False
            self.info('has been initialized with errors')

    @property
    def ready(self):
        if time.time() < self.suspend_to:
            return False
        # was suspended try to init
        if self.suspend_to > 0.0:
            self.__del__()
            self.__init__(self.port, self.addr, **self.kwargs)
            if self.initialized:
                self.write_duration(self.duration)
                self.write_mode(self.mode)
                for i in range(12):
                    self.write_channel_stop(i+1, self.stop[i])
                    self.write_channel_start(i+1, self.start[i])
                    self.write_channel_enable(i+1, self.enable[i])
        return self.suspend_to <= 0.0

    def read_channel_start(self, n: int) -> int:
        delay = self.modbus_read(16 * n + 1, 2)
        if delay:
            v= delay[0] * 0x10000 + delay[1]
            self.start[n-1] = v
            return v
        return -1

    def read_channel_stop(self, n: int) -> int:
        delay = self.modbus_read(16 * n + 3, 2)
        if delay:
            v = delay[0] * 0x10000 + delay[1]
            self.stop[n-1] = v
            return v
        return -1

    def read_channel_enable(self, n: int) -> int:
        data = self.modbus_read(16 * n, 1)
        if data:
            self.enable[n-1] = data[0]
            return data[0]
        else:
            return -1

    def read_channel(self, n: int) -> [int]:
        result = self.modbus_read(16 * n, 5)
        if len(result) != 5:
            return []
        return result

    def read_run(self) -> int:
        data = self.modbus_read(0, 1)
        if data:
            return data[0]
        else:
            return -1

    def read_mode(self) -> int:
        data = self.modbus_read(1, 1)
        if data:
            self.mode = data[0]
            return data[0]
        else:
            return -1

    def read_status(self) -> int:
        data = self.modbus_read(5, 1)
        if data:
            return data[0]
        else:
            # self.debug(' Status register read error')
            return -1

    def read_output(self) -> int:
        data = self.modbus_read(4, 1)
        if data:
            self.output = data[0]
            return data[0]
        else:
            # self.debug(' Output register read error')
            return -1

    def read_fault(self) -> int:
        data = self.modbus_read(1, 1)
        if data:
            return data[0]
        else:
            # self.debug(' Fault register read error')
            return -1

    def read_duration(self) -> int:
        data = self.modbus_read(2, 2)
        if data:
            v = data[0] * 0x10000 + data[1]
            self.duration = v
            return v
        else:
            # self.debug(' Script duration read error')
            return -1

    def read_last(self) -> int:
        data = self.modbus_read(7, 2)
        if data:
            return data[0] * 65536 + data[1]
        else:
            # self.debug(' Last pulse duration read error')
            return -1

    def write_channel_start(self, n: int, v: int) -> bool:
        delay = [0, 0]
        delay[0] = v // 0x10000
        delay[1] = v % 0x10000
        result = self.modbus_write(16 * n + 1, delay)
        if result != 2:
            return False
        self.start[n-1] = v
        return True

    def write_channel_stop(self, n: int, v: int) -> bool:
        delay = [0, 0]
        delay[0] = v // 0x10000
        delay[1] = v % 0x10000
        result = self.modbus_write(16 * n + 3, delay)
        if result != 2:
            return False
        self.stop[n-1] = v
        ms = max(self.stop)
        if self.duration != ms:
            return self.write_duration(ms)
        return True

    def write_channel_enable(self, n: int, v: int) -> bool:
        result = self.modbus_write(16 * n, int(bool(v)))
        if result != 1:
            return False
        self.enable[n-1] = v
        return True

    def enable_channel(self, n: int) -> bool:
        return self.write_channel_enable(n, 1)

    def disable_channel(self, n: int) -> bool:
        return self.write_channel_enable(n, 0)

    def write_run(self, n: int) -> bool:
        m = self.modbus_write(0, n)
        return m == 1

    def write_mode(self, n: int) -> bool:
        result = self.modbus_write(1, n)
        if result != 1:
            return False
        self.mode = n
        return True

    def write_output(self, n: int) -> bool:
        result = self.modbus_write(4, n)
        if result != 1:
            return False
        self.output = n
        return True

    def write_duration(self, n: int) -> bool:
        v = [0, 0]
        v[0] = n // 0x10000
        v[1] = n % 0x10000
        result = self.modbus_write(2, v)
        if result != 2:
            return False
        self.duration = n
        return True


if __name__ == "__main__":
    ot1 = Vtimer("COM17", 1)
    t_0 = time.time()
    v = ot1.read_run()
    dt = int((time.time() - t_0) * 1000.0)  # ms
    a = '%s:%s %s %s %s' % (ot1.port, ot1.addr, 'read_run->', v, '%4d ms ' % dt)
    print(a)
    print('')

    n = 100
    t_0 = time.time()
    for i in range(n):
        # v = ot1.write_channel_stop(1, 100)
        v = ot1.modbus_read(16, 5)
    dt = ((time.time() - t_0) * 1000.0)  # ms
    a = '%s:%s %s %s %s' % (ot1.port, ot1.addr, 'write_stop(1)->', v, '%4f ms ' % (dt/n))
    print(a)
    print('')

    t_0 = time.time()
    v = ot1.read_channel_start(1)
    dt = int((time.time() - t_0) * 1000.0)  # ms
    a = '%s:%s %s %s %s' % (ot1.port, ot1.addr, 'read_start(1)->', v, '%4d ms ' % dt)
    print(a)
    print('')

    t_0 = time.time()
    v = ot1.read_channel_stop(1)
    dt = ((time.time() - t_0) * 1000.0)  # ms
    a = '%s:%s %s %s %s' % (ot1.port, ot1.addr, 'read_stop(1)->', v, '%4d ms ' % dt)
    print(a)
    print('')

    t_0 = time.time()
    n = 500
    v0 = ot1.write_output(1)
    v1 = ot1.write_duration(12 * n + 1)
    for i in range(1, 13):
        v3 = ot1.write_channel_stop(i, i * n)
        v2 = ot1.write_channel_start(i, (i - 1) * n)
        v6 = ot1.enable_channel(i)
    v8 = ot1.write_run(3)
    v = ot1.write_run(1)
    f = ot1.read_fault()
    # while ot1.read_status():
    #     pass
    l = ot1.read_last()

    dt = int((time.time() - t_0) * 1000.0)  # ms
    a = '%s:%s %s %s %s %s %s' % (ot1.port, ot1.addr, '->', v, f, l, '%4d ms ' % dt)
    print(a)
    print('')

    print('Finished')
