import logging
import os
import time
import sys

if os.path.realpath('../TangoUtils') not in sys.path: sys.path.append(os.path.realpath('../TangoUtils'))
if os.path.realpath('../IT6900') not in sys.path: sys.path.append(os.path.realpath('../IT6900'))

from config_logger import config_logger
from log_exception import log_exception
from Moxa import MoxaTCPComPort
from TDKLambda import TDKLambda

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'Small Lauda Python API'
APPLICATION_NAME_SHORT = 'LaudaSmall'
APPLICATION_VERSION = '1.0'

# Write commands
"""
OUT_PV_05_XXX.XX External temperature to be set through the interface.
OUT_SP_00_XXX.XX Setpoint transfer with up to 3 places before the decimal point and up to 2 places behind.
OUT_SP_01_XXX Pump power level 1 to 8.
OUT_SP_02_XXX Cooling operating mode cooling (0 = OFF / 1 = ON / 2 = AUTOMATIC).
OUT_SP_04_XXX.X TiH outflow temperature high limit.
OUT_SP_05_XXX.X TiL outflow temperature low limit.
OUT_SP_06_X.XX Set pressure (with pressure control)
OUT_PAR_00_XXX Setting of the control parameter Xp.
OUT_PAR_01_XXX Setting of the control parameter Tn (5...180s; 181 = Off).
OUT_PAR_02_XXX Setting of the control parameter Tv.
OUT_PAR_03_XX.X Setting of the control parameter Td.
OUT_PAR_04_XX.XX Setting of the control parameter KpE.
OUT_PAR_05_XXX Setting of the control parameter TnE (0...979s; 980 = Off).
OUT_PAR_06_XXX Setting of the control parameter TvE (0 = OFF).
OUT_PAR_07_XXXX.X Setting of the control parameter TdE.
OUT_PAR_09_XXX.X Setting of the correction limitation
OUT_PAR_10_XX.X Setting of the control parameter XpF.
OUT_PAR_14_XXX.X Setting of the setpoint offset.
OUT_PAR_15_XXX Setting of the control parameter PropE
OUT_MODE_00_X Master keyboard: 0 = free / 1 = locked (corresponds to “KEY”).
OUT_MODE_01_X Control: 0 = internal / 1 = external Pt100 / 2 = external analogue / 3 = external serial.
OUT_MODE_03_X Command remote control keyboard: 0 = free / 1 = locked
OUT_MODE_04_X Setpoint offset source: 0=normal / 1=ext. Pt / 2=ext. analog / 3=ext. serial.
START Switches the device on (after Standby). See safety information (þ 7.9.3).
STOP Switches the device into Standby (pump, heater, cooling unit OFF).
RMP_SELECT_X Selection of program (1...5) to which the further instructions apply. When the device is switched on, program 5 is selected automatically.
RMP_START Start the programmer.
RMP_PAUSE Hold (pause) the programmer.
RMP_CONT Restart the programmer after pause.
RMP_STOP Terminate the program.
RMP_RESET Delete the program (all Segments).
RMP_OUT_00_XXX.XX_XXXXX_XXX.XX_X Sets a programmer segment (temperature, time, tolerance and pump level). A segment is added and appropriate values are applied to it.
RMP_OUT_02_XXX Number of program loops: 0 = endless / 1...250.
"""
# Read commands
"""
IN_PV_00 Query of outflow temperature.
IN_PV_01 Query of controlled temperature (int./ext. Pt/ext. Analogue/ext. Serial).
IN_PV_02 Query of outflow pump pressure in bar.
IN_PV_03 Query of external temperature TE (Pt100).
IN_PV_04 Query of external temperature TE (Analogue input).
IN_PV_05 Query of bath level.
IN_PV_10 Query of outflow temperature in 0.001 °C.
IN_PV_13 Query of external temperature TE (Pt100) in 0.001 °C.
IN_SP_00 Query of temperature setpoint.
IN_SP_01 Query of current pump power level
IN_SP_02 Query of cooling operation mode (0 = OFF / 1 = ON / 2 = AUTOMATIC).
IN_SP_03 Query of current overtemperature switch-off point.
IN_SP_04 Query of current outflow temperature limit TiH.
IN_SP_05 Query of current outflow temperature limit TiL.
IN_SP_06 Query of set pressure (at pressure control)
IN_PAR_00 Query of control parameter Xp.
IN_PAR_01 Query of control parameter Tn (181 = OFF).
IN_PAR_02 Query of control parameter Tv.
IN_PAR_03 Query of control parameter Td.
IN_PAR_04 Query of control parameter KpE.
IN_PAR_05 Query of control parameter TnE (980 = OFF).
IN_PAR_06 Query of control parameter TvE (0 = OFF)
IN_PAR_07 Query of control parameter TdE.
IN_PAR_09 Query of correction limitation
IN_PAR_10 Query of the control parameter XpF.
IN_PAR_14 Query of setpoint offset.
IN_PAR_15 Query of control parameter PropE
IN_DI_01 Status of contact input 1: 0 = open/ 1 = closed.
IN_DI_02 Status of contact input 2: 0 = open/ 1 = closed.
IN_DI_03 Status of contact input 3: 0 = open/ 1 = closed.
IN_DO_01 State of Contact output 1: 0 = make-contact open / 1 = make-contact closed.
IN_DO_02 State of Contact output 2: 0 = make-contact open / 1 = make-contact closed.
IN_DO_03 State of Contact output 3: 0 = make-contact open / 1 = make-contact closed.
IN_MODE_00 Master keyboard: 0 = free / 1 = locked
IN_MODE_01 Control: 0 = int. / 1 = ext. Pt100 / 2 = ext. analogue / 3 = ext. serial.
IN_MODE_02 Standby: 0 = Unit ON / 1 = Unit OFF.
IN_MODE_03 Command remote control keyboard: 0 = free / 1 = locked
IN_MODE_04 Setpoint offset source: 0=normal / 1=ext. Pt / 2=ext. analogue / 3=ext. serial.
TYPE Query of device type (response = “XT”)
VERSION_R Query of software version number of control system.
VERSION_S Query of software version number of protection system.
VERSION_B Query of software version number of Command.
VERSION_T Query of software version number of cooling system.
VERSION_A Query of software version number of analogue module.
VERSION_V Query of software version number of RS232/485 module.
VERSION_Y Query of software version number of Ethernet module
VERSION_Z Query of software version number of EtherCAT module
VERSION_D Query of software version number of digital (contact l/ 0) module.
VERSION_M_0 Query of software version number of solenoid valve (cooling water)
VERSION_M_3 Query of software version number of solenoid valve (reverse flow protection device 1)
VERSION_M_4 Query of software version number of solenoid valve (reverse flow protection device 2)
VERSION_P_0 Query of software version number of pump module 0
VERSION_P_1 Query of software version number of pump module 1
VERSION_P_2 Query of software version number of pump module 2
VERSION_P_3 Query of software version number of pump module 3
STATUS Query of the equipment status 0 = OK, -1 = error.
STAT Query for the error diagnosis response: XXXXXXX ® X = 0 no error, X = 1 error.
1st character = error.
2nd character = Alarm.
3rd character = Warning.
4th character = over temperature.
5th character = low level error.
6th character = high level error (at adjustment alarm).
7th character = no external control variable.
RMP_IN_00_XXX Query of a program segment XXX (response: e. g. 030.00_010.00 => set point temperature 30.00 °C, time = 10 min, tolerance = 5.00 K, pump level = 1).
RMP_IN_01 Query of the current segment number.
RMP_IN_02 Query of the set number of program loops
RMP_IN_03 Query of the current program loops
RMP_IN_04 Query of the program to which further instructions apply.
RMP_IN_05 Query of which program is currently running (0 = none).
LOG_IN_00_XXXX Query of a measuring point XXXX from data logger (Reply: e. g. 020.00_021.23_030.50 => set point temperature = 20.00 °C, outflow temperature = 21.23 °C, external temperature = 30.5 °C).
LOG_IN_01 Query of all measuring points from data logger As a difference to the command “LOG_IN_00”, a tabulator is used here as separator instead of ,_’ . The measuring points are separated by CR and LF. The end is marked by CR LF CR LF.
LOG_IN_02 Query of the start time from the data logger (Reply: e.g. 20_14_12_20 => day 20, 14:12:20).
LOG_IN_03 Query of acquisition interval from the data logger (Reply in seconds).
"""

"""
ERR_2 Wrong input (e.g. buffer overflow).
ERR_3 Wrong command.
ERR_5 Syntax error in value.
ERR_6 Illegal value.
ERR_8 Module (ext. temperature) not available.
ERR_30 Programmer, all segments occupied.
ERR_31 Set point not possible, analogue set point input ON.
ERR_32 TiH <= TiL.
ERR_33 No external sensor.
ERR_34 Analogue value not available.
ERR_35 Automatic is selected.
ERR_36 No set point input possible. Programmer is running or is paused.
ERR_37 No start from programmer possible, analogue setpoint input is switched on.
"""

WRITE_COMMANDS = (b"OUT", b"START", b"STOP")
READ_COMMANDS = (b"IN", b"TYPE", b"VERSION", b"STATUS", b'STAT', b'RMP_IN', b'LOG_IN')
LAUDA_ERRORS = {
b"ERR_2": "Wrong input (e.g. buffer overflow)",
b"ERR_3": "Wrong command",
b"ERR_5": "Syntax error in value",
b"ERR_6": "Illegal value",
b"ERR_8": "Module (ext. temperature) not available",
b"ERR_30": "Programmer, all segments occupied",
b"ERR_31": "Set point not possible, analogue set point input ON",
b"ERR_32": "TiH <= TiL",
b"ERR_33": "No external sensor:",
b"ERR_34": "Analogue value not available",
b"ERR_35": "Automatic is selected",
b"ERR_36": "No set point input possible. Programmer is running or is paused",
b"ERR_37": "No start from programmer possible, analogue setpoint input is switched on"
}

# os.environ["TANGO_HOST"] = '192.168.1.41:10000'
# db = tango.Database('192.168.1.41', '10000')

class LaudaSmall(TDKLambda):
    def __init__(self, port, addr: int=None, **kwargs):
        kwargs['baudrate'] = 9600
        self.addr_prefix = b''
        self.name = 'LAUDA'
        super().__init__(port, addr, **kwargs)

    def init(self):
        self.suspend_to = 0.0
        if self.addr is not None:   # RS485 connection
            self.pre = f'LAUDA at {self.port}:{self.addr}'
            try:
                if self.com.device is not MoxaTCPComPort and (self.addr) >= 0 and int(self.addr) < 128:
                    self.addr_prefix = ('A%03i_' % int(self.addr)).encode()
                else:
                    self.state = -1
                    self.info(self.STATES[self.state])
                    self.suspend(1e6)
                    return False
            except:
                self.state = -1
                self.info(self.STATES[self.state])
                self.suspend()
                return False
        else:   # RS232 or Ethernet connection
            self.pre = f'LAUDA at {self.port}'
            self.addr_prefix = b''
        self.id = 'LAUDA'
        # check if port:address is in use
        with TDKLambda._lock:
            for d in TDKLambda._devices:
                if d != self and d.port == self.port and d.addr == self.addr and d.state > 0:
                    self.state = -2
                    self.info(self.STATES[self.state])
                    self.suspend()
                    return False
        if not self.com.ready:
            self.state = -5
            self.info(self.STATES[self.state])
            self.suspend()
            return False
        # read device type
        self.id = self.read_device_id()
        self.pre = self.pre.replace('LAUDA ', f'LAUDA {self.id} ')
        self.state = 1
        self.info('has been initialized')
        return True

    def read_device_id(self):
        try:
            if self.send_command(b'TYPE') and self.check_response():
                return self.response.decode()
            else:
                return 'Unknown Device'
        except KeyboardInterrupt:
            raise
        except:
            log_exception(self.logger)
            return 'Unknown Device'

    def send_command(self, cmd) -> bool:
        self.response = b''
        # unify command
        if isinstance(cmd, str):
            cmd = str.encode(cmd)
        self.command = cmd
        try:
            if not self.ready:
                return False
            #
            cmd_out = self.addr_prefix + cmd
            #
            n = 0
            while n < self.read_retries:
                n += 1
                result = self._send_command(cmd_out)
                self.read_until(b'\n')
                if cmd.startswith(WRITE_COMMANDS):
                    if result == self.addr_prefix + b'OK':
                        return True
                else:
                    if result:
                        return True
                self.info(f'Command {cmd} retry {n} of {self.read_retries}')
            self.info(f'Can not send command {cmd}')
            self.response = b''
            self.suspend()
            return False
        except KeyboardInterrupt:
            raise
        except:
            self.response = b''
            self.suspend()
            log_exception(self.logger, f'{self.pre} Exception sending {cmd}')
            return False

    def check_response(self, expected=b'OK', response=None):
        if response is None:
            response = self.response
        if self.command.startswith(WRITE_COMMANDS):
            if response == self.addr_prefix + b'OK':
                return True
        else:
            if response:
                if response.startswith(self.addr_prefix):
                    return True
        self.debug(f'Unexpected response {response}')
        return False

    def debug(self, msg, *args, **kwargs):
        self.logger.debug(f'{self.pre} {msg}', *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.logger.info(f'{self.pre} {msg}', *args, **kwargs)

    def _set_addr(self):
        return True

    def add_checksum(self, cmd):
        return cmd

    @staticmethod
    def checksum(cmd):
        return b''

    def verify_checksum(self, value):
        return True

    def read_value(self, command: str, result_type=float):
        self.send_command(command)
        if self.check_response():
            if not self.command.startswith(WRITE_COMMANDS):
                try:
                    value = result_type(self.response.replace(self.addr_prefix, b''))
                    return value
                except KeyboardInterrupt:
                    raise
            return self.response.replace(self.addr_prefix, b'').decode()
        # self.debug(f'{command} -> read value error')
        return None

    def write_value(self, cmd, value, expect=b'OK'):
        if not cmd.startswith(WRITE_COMMANDS):
            self.debug(f'Not write command {cmd}')
            return False
        try:
            cmd = f'{cmd}_{value:.2f}'
        except KeyboardInterrupt:
            raise
        self.send_command(cmd)
        return self.check_response()


if __name__ == "__main__":
    logger = config_logger()
    print(f'Simple Small LAUDA control utility ver.{APPLICATION_VERSION}')
    port = input('LAUDA Port <COM4>: ')
    if not port:
        port = 'COM4'
    addr = input('LAUDA Address: ')
    if not addr:
        lda = LaudaSmall(port)
    else:
        lda = LaudaSmall(port, int(addr))
    while True:
        command = input('Send command: ')
        command = command.strip()
        if not command:
            break
        t_0 = time.time()
        v1 = lda.send_command(command)
        r1 = lda.response
        dt1 = int((time.time() - t_0) * 1000.0)  # ms
        a = f'{lda.pre} {command} -> {r1} in {dt1} ms {lda.check_response()}'
        print(a)
    del lda
    print('Finished')
