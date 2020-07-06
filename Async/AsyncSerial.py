import time
import threading
import asyncio
import serial
from serial import SerialTimeoutException

# from PyQt5.QtCore import QTimer

readTimeoutException = SerialTimeoutException('Read timeout')
writeTimeoutException = SerialTimeoutException('Write timeout')


class AsyncTimeout(serial.Timeout):
    def __init__(self, duration, expired_action=None, *args, **kwargs):
        super().__init__(duration)
        self.expired_action = None
        self.args = args
        self.kwargs = kwargs
        if isinstance(self.expired_action, Exception) or callable(self.expired_action):
            self.expired_action = expired_action
        else:
            raise TypeError('Unsupported timeout action')

    def check_expired(self):
        return self.expired()

    def expired(self):
        if self.expired_action is None:
            return self.target_time is not None and self.time_left() <= 0
        if isinstance(self.expired_action, Exception):
            raise self.expired_action
        if callable(self.expired_action):
            return self.expired_action(*self.args, **self.kwargs)
        raise TypeError('Unsupported timeout action')

    # # with protocol
    # def __enter__(self):
    #     return self
    #
    # def __exit__(self, exc_type, exc_val, exc_tb):
    #     if exc_type is None:
    #         return True
    #     return False

    def restart(self, duration=None):
        if duration is not None:
            self.duration = duration
        self.target_time = self.TIME() + self.duration


class AsyncSerial(serial.Serial):

    def __init__(self, *args, **kwargs):
        # Should not block read or write
        kwargs['timeout'] = 0.0
        kwargs['write_timeout'] = 0.0
        super().__init__(*args, **kwargs)
        self.async_lock = asyncio.Lock()

    async def read(self, size=1, timeout=None):
        # Non locking operation. Use read_until() to prevent concurrent reading form the port.
        result = bytes()
        if size < 0:
            size = self.in_waiting
        if size == 0:
            return result
        to = AsyncTimeout(timeout, readTimeoutException)
        while len(result) < size:
            d = super().read(1)
            if d:
                result += d
                to.restart()
            to.check_expired()
            await asyncio.sleep(0)
        return result

    async def read_until(self, terminator=b'\r', size=None, timeout=None):
        """
        Read until a termination sequence is found ('\r' by default),
        the size is exceeded or timeout occurs.
        """
        result = bytearray()
        to = AsyncTimeout(timeout, readTimeoutException)
        async with self.async_lock:
            while True:
                c = super().read(1)
                if c:
                    result += c
                    if terminator in result:
                        break
                    if size is not None and len(result) >= size:
                        break
                    to.restart()
                to.check_expired()
                await asyncio.sleep(0)
        return bytes(result)

    async def write(self, data, timeout=None):
        to = serial.Timeout(timeout)
        result = 0
        async with self.async_lock:
            for d in data:
                n = super().write(d)
                if n <= 0:
                    raise SerialTimeoutException('Write error')
                result += n
                if to.expired():
                    raise writeTimeoutException
                await asyncio.sleep(0)
        return result

    async def flush(self, timeout=None):
        to = serial.Timeout(timeout)
        async with self.async_lock:
            while self.in_waiting > 0:
                if to.expired():
                    raise writeTimeoutException
                await asyncio.sleep(0.01)

    async def reset_input_buffer(self, timeout=None):
        """Clear input buffer, discarding all that is in the buffer."""
        to = serial.Timeout(timeout)
        async with self.async_lock:
            while self.in_waiting > 0:
                super().reset_input_buffer()
                if to.expired():
                    raise SerialTimeoutException('Read buffer reset timeout')
                await asyncio.sleep(0)

    async def reset_output_buffer(self, timeout=None):
        """Clear output buffer, discarding all that is in the buffer."""
        to = serial.Timeout(timeout)
        async with self.async_lock:
            while self.out_waiting > 0:
                super().reset_output_buffer()
                if to.expired():
                    raise SerialTimeoutException('Write buffer reset timeout')
                await asyncio.sleep(0)

def timeout_expires(text):
    print(text)
# timeout test
with AsyncTimeout(1.0, Exception('aa')) as to:
    t0 = time.time()
    a=0
    while time.time() - t0 < 2.1:
        #print('qq')
        a += 1
        pass

print('pp')