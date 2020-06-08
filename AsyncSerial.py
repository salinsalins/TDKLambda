import time
import asyncio
import serial


class AsyncSerial(serial.Serial):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.read_lock = asyncio.Lock()
        self.write_lock = asyncio.Lock()

    async def read(self, size=1):
        async with self.read_lock:
            result = super().read(1)
            while len(result) < size:
                d = super().read(1)
                if d:
                    result += d
                if self.inter_byte_timeout is None:
                    delay = 0
                else:
                    delay = self.inter_byte_timeout
                await asyncio.sleep(delay)
        return result

    async def read_until(self, terminator=b'\n', size=None):
        async with self.read_lock:
            """\
            Read until a termination sequence is found ('\n' by default), the size
            is exceeded or until timeout occurs.
            """
            lenterm = len(terminator)
            line = bytearray()
            timeout = serial.Timeout(self._timeout)
            if self.inter_byte_timeout is None:
                delay = 0
            else:
                delay = self.inter_byte_timeout
            if size is None:
                size = 0
            while True:
                c = super().read(1)
                if c:
                    line += c
                    if line[-lenterm:] == terminator:
                        break
                    if len(line) >= size:
                        break
                else:
                    break
                if timeout.expired():
                    break
                await asyncio.sleep(delay)
        return bytes(line)


if __name__ == "__main__":
    for i in range(5):
        t0 = time.time()
        dt = time.time()-t0
        dtms = int((time.time()-t0)*1000.0)    #ms
        print('dt', dt)
