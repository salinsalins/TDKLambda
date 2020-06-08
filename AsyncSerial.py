import time
import asyncio
import serial

readTimeoutException = serial.SerialTimeoutException('Read timeout')


class SerialTimeout(serial.Timeout):

    def check(self):
        if self.expired():
            raise readTimeoutException


class AsyncSerial(serial.Serial):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.read_lock = asyncio.Lock()
        self.write_lock = asyncio.Lock()

    async def read(self, size=1):
        async with self.read_lock:
            timeout = SerialTimeout(self._timeout)
            result = self.read_all()
            while len(result) < size:
                d = self.read_all()
                if d:
                    result += d
                timeout.check()
                await asyncio.sleep(0)
        return result

    async def read_until(self, terminator=b'\n', size=None):
        async with self.read_lock:
            """\
            Read until a termination sequence is found ('\n' by default), the size
            is exceeded or until timeout occurs.
            """
            line = bytearray()
            timeout = SerialTimeout(self._timeout)
            if size is None:
                size = 0
            while True:
                c = super().read_all()
                if c:
                    line += c
                    if terminator in line:
                        break
                    if len(line) >= size:
                        break
                timeout.check()
                await asyncio.sleep(0)
            return bytes(line)


if __name__ == "__main__":
    for i in range(5):
        t0 = time.time()
        dt = time.time()-t0
        dtms = int((time.time()-t0)*1000.0)    #ms
        print('dt', dt)
