import time
import asyncio
import serial

readTimeoutException = serial.SerialTimeoutException('Read timeout')
writeTimeoutException = serial.SerialTimeoutException('Write timeout')


class AsyncSerial(serial.Serial):

    def __init__(self, *args, **kwargs):
        # should not block read or write
        kwargs['timeout'] = 0.0
        kwargs['write_timeout'] = 0.0
        super().__init__(*args, **kwargs)
        self.read_lock = asyncio.Lock()
        self.write_lock = asyncio.Lock()

    async def read(self, size=1, timeout=None):
        async with self.read_lock:
            to = serial.Timeout(timeout)
            result = super().read(1)
            while len(result) < size:
                d = super().read(1)
                if d:
                    result += d
                if to.expired():
                    raise readTimeoutException
                await asyncio.sleep(0)
        return result

    async def read_until(self, terminator=b'\n', size=None, timeout=None):
        async with self.read_lock:
            """\
            Read until a termination sequence is found ('\n' by default), the size
            is exceeded or until timeout occurs.
            """
            line = bytearray()
            to = serial.Timeout(timeout)
            while True:
                c = super().read(1)
                if c:
                    line += c
                    if terminator in line:
                        break
                    if size is not None and len(line) >= size:
                        break
                if to.expired():
                    raise readTimeoutException
                await asyncio.sleep(0)
            return bytes(line)

    async def write(self, data, timeout=None):
        async with self.write_lock:
            to = serial.Timeout(timeout)
            result = 0
            for d in data:
                result += super().write(d)
                if to.expired():
                    raise writeTimeoutException
                await asyncio.sleep(0)

    async def flush(self, timeout=None):
        """\
        Flush of file like objects. In this case, wait until all data
        is written.
        """
        to = serial.Timeout(timeout)
        while self.out_waiting:
            if to.expired():
                raise writeTimeoutException
            await asyncio.sleep(0.01)
        # XXX could also use WaitCommEvent with mask EV_TXEMPTY, but it would
        # require overlapped IO and it's also only possible to set a single mask
        # on the port---


if __name__ == "__main__":
    for i in range(5):
        t0 = time.time()
        dt = time.time()-t0
        dtms = int((time.time()-t0)*1000.0)    # ms
        print('dt', dt)
