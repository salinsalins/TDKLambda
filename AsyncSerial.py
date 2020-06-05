import time
import asyncio
import serial


class AsyncSerial(serial.Serial):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.read_lock = None
        self.write_lock = None

    async def read(self, size=1):
        result = super().read(1)
        while len(result) < size:
            d = super().read(1)
            result += d
            if self.inter_byte_timeout is None:
                delay = 0
            else:
                delay = self.inter_byte_timeout
            await asyncio.sleep(delay)
            # yield
        return result


if __name__ == "__main__":
    for i in range(5):
        t0 = time.time()
        dt = time.time()-t0
        dtms = int((time.time()-t0)*1000.0)    #ms
        print('dt', dt)
