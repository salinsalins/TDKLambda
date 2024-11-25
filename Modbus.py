import os
import sys

util_path = os.path.realpath('../TangoUtils')
if util_path not in sys.path:
    sys.path.append(util_path)
del util_path


ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'Vtimer I/O modules Python API'
APPLICATION_NAME_SHORT = 'Adam'
APPLICATION_VERSION = '0.1'


def modbusCRC(msg: bytes) -> int:
    crc = 0xFFFF
    for n in range(len(msg)):
        crc ^= msg[n]
        for i in range(8):
            if crc & 1:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc


class MODBUS:

    def __init__(self):
        pass

    @staticmethod
    def checksum(cmd: bytes):
        s = 0
        for b in cmd:
            s += int(b)
        #return bytes([s // 256, s % 256])
        return modbusCRC(cmd).to_bytes(2, 'little')

    def add_checksum(self, cmd: bytes):
        return cmd + self.checksum(cmd)

    def verify_checksum(self, cmd: bytes):
        cs = self.checksum(cmd[:-2])
        return cmd[-2:] == cs

    def send(self, cmd: bytes) -> bool:
        ml = int.from_bytes(cmd[1:3])
        if len(cmd) != ml + 3:
            return False
        cmd_cs = self.add_checksum(cmd)
        for i in cmd_cs:
            if not self.send_byte(i):
                return False
        return True

    def send_byte(self, byte) -> bool:
        return True


if __name__ == "__main__":
    mb = MODBUS()
    cmd = bytes.fromhex('1103006B0003')
    cs = bytes.fromhex('7687')
    print(cmd, cs, mb.checksum(cmd), cs == mb.checksum(cmd))

    cmd = bytes.fromhex('110306AE4156524340')
    cs = bytes.fromhex('49AD')
    print(cmd, cs, mb.checksum(cmd), cs == mb.checksum(cmd))

    cmd = bytes.fromhex('110306AE4156524340')
    cs = bytes.fromhex('49AD')
    print(cmd, cs, mb.checksum(cmd), cs == mb.checksum(cmd))

    print('Finished')
