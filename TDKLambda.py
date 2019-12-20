#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import os
import logging
import serial

MAX_TIMEOUT = 1.5   # sec
MIN_TIMEOUT = 0.1   # sec
RETRIES = 3
SUSPEND = 2.0
SLEEP = 0.03
SLEEP_SMALL = 0.015
MAX_ERROR_COUNT = 4

class TDKLambda():
    devices = []
    ports = []

    def __init__(self, port: str, addr=6, checksum=False, auto_addr = True, baudrate=9600, timeout=0, logger=None):
        #print('__init__', port, addr)
        # input parameters
        self.port = port.upper().strip()
        self.addr = addr
        #self.check = checksum
        self.check = False
        self.auto_addr = auto_addr
        self.baud = baudrate
        # create variables
        self.last_command = b''
        self.last_response = b''
        self.error_count = 0
        self.time = time.time()
        self.suspend_to = time.time()
        self.retries = 0
        self.min_timeout = MIN_TIMEOUT
        self.max_timeout = MAX_TIMEOUT
        self.timeout = MIN_TIMEOUT
        self.sleep_small = SLEEP_SMALL
        self.sleep = SLEEP
        self.com = None
        self.id = None
        self.sn = None
        if logger is not None:
            self.logger = logger
        else:
            self.logger = logging.getLogger(str(self))
            self.logger.propagate = False
            self.logger.setLevel(logging.INFO)
            #log_formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
            #                                  datefmt='%H:%M:%S')
            f_str = '%(asctime)s %(funcName)s(%(lineno)s) ' +\
                    '%s:%d ' % (self.port, self.addr) +\
                    '%(levelname)-7s %(message)s'
            log_formatter = logging.Formatter(f_str, datefmt='%H:%M:%S')
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(log_formatter)
            self.logger.addHandler(console_handler)
        # check if port an addr are in use
        for d in TDKLambda.devices:
            if d.port == self.port and d.addr == self.addr:
                msg = 'Address is in use'
                self.logger.error(msg)
                return
        # assign com port
        for d in TDKLambda.devices:
            # com port alredy created
            if d.port == self.port:
                self.com = d.com
        if self.com is None:
            # create new port
            try:
                self.com = serial.Serial(self.port, baudrate=baudrate, timeout=timeout)
            except:
                self.com = None
                msg = '%s open error' % self.port
                self.logger.error(msg)
                #print(self.logger.findCaller())
                #self.logger.debug(msg, stack_info=True)
                return
        # set device address and check 'OK' response
        response = self.set_addr()
        if response:
            self.com._current_addr = self.addr
        else:
            self.com = None
            self.logger.error('Error address set')
            return
        # initialize device type and serial number
        self.id = self._send_command(b'IDN?').decode()
        # determine max current and voltage from model name
        self.max_voltage = float('inf')
        self.max_current = float('inf')
        n1 = self.id.find('GEN')
        n2 = self.id.find('-')
        if n1 >= 0 and n2 >= 0:
            try:
                self.max_voltage = float(self.id[n1+3:n2])
                self.max_current = float(self.id[n2+1:])
            except:
                pass
        self.serial_number = self._send_command(b'SN?').decode()
        # add device to list
        TDKLambda.devices.append(self)
        msg = 'TDKLambda %s has been created' % self.id
        self.logger.info(msg)

    def __del__(self):
        #print(self.port, self.addr, '__del__')
        if self in TDKLambda.devices:
            TDKLambda.devices.remove(self)
        self.close_com_port()

    def close_com_port(self):
        if self.com is not None:
            for d in TDKLambda.devices:
                if d.port == self.port:
                    return False
            self.com.close()
            return True
        return False

    @staticmethod
    def checksum(cmd):
        s = 0
        for b in cmd:
            s += int(b)
        result = str.encode(hex(s)[-2:].upper())
        return result

    def clear_input_buffer(self):
        t0 = time.time()
        time.sleep(self.sleep_small)
        smbl = self.com.read(10000)
        while len(smbl) > 0:
            if time.time() - t0 > self.max_timeout:
                self.logger.error('Timeout clear input buffer')
                return False
            time.sleep(self.sleep_small)
            smbl = self.com.read(10000)
        return True

    def _send_command(self, cmd):
        try:
            if self.offline():
                self.logger.debug('Device is offline')
                print('Device is offline')
                return b''
            cmd = cmd.upper().strip()
            if isinstance(cmd, str):
                cmd = str.encode(cmd)
            if cmd[-1] != b'\r'[0]:
                cmd += b'\r'
            # commands with checksumm
            if self.check:
                cs = self.checksum(cmd)
                cmd = b'%s$%s\r' % (cmd[:-1], cs)
                self.logger.debug('Command with checksum %s' % cmd)
            self.last_command = cmd
            ##self.logger.debug('%s' % cmd)
            t0 = time.time()
            # clear input buffer
            time.sleep(self.sleep_small)
            smbl = self.com.read(10000)
            while len(smbl) > 0:
                if time.time() - t0 > self.max_timeout:
                    self.logger.error('Timeout clear input buffer')
                    self.suspend()
                    return b''
                time.sleep(self.sleep_small)
                smbl = self.com.read(10000)
                self.logger.error('Clear input buffer')
            # write command
            self.com.write(cmd)
            time.sleep(self.sleep)
            result = self.read_to_cr()
            self.logger.debug('%s -> %s %4.0f ms' % (cmd, result, (time.time()-t0)*1000.0))
            ##self.logger.debug('%4d ms' % int((time.time()-t0)*1000.0))
            if result is None:
                self.logger.warning('Writing error, repeat %s' % cmd)
                time.sleep(self.sleep)
                # clear input buffer
                self.com.read(10000)
                self.com.write(cmd)
                time.sleep(self.sleep)
                result = self.read_to_cr()
                self.logger.debug('%s -> %s %4.0f ms' % (cmd, result, (time.time() - t0) * 1000.0))
                if result is None:
                    self.logger.error('Repeated writing error')
                    self.suspend()
                    result = b''
            return result
        except:
            self.logger.error('Unexpected exception')
            self.logger.log(logging.DEBUG, "Exception Info:", exc_info=True)

    def send_command(self, cmd):
        if self.offline():
            self.logger.debug('Device is offline')
            return b''
        if self.auto_addr and self.com._current_addr != self.addr:
            result = self.set_addr()
            if result:
                result = self._send_command(cmd)
            else:
                result = b''
        else:
            result = self._send_command(cmd)
        return result

    def check_response(self, expect=b'OK', response=None):
        if self.offline():
            self.logger.debug('Device is offline')
            return False
        if response is None:
            response = self.last_response
        if not response.startswith(expect):
            msg = 'Unexpected response %s (%s)' % (response, expect)
            self.logger.info(msg)
            self.inc_error_count()
            return False
        self.error_count = 0
        return True

    def _read(self):
        if self.offline():
            self.logger.debug('Device is offline')
            return None
        t0 = time.time()
        data = self.com.read(10000)
        dt = time.time() - t0
        n = 0
        while len(data) <= 0:
            if dt > self.timeout:
                self.timeout = min(1.5*self.timeout, self.max_timeout)
                msg = 'reading timeout, increased to %5.2f s' % self.timeout
                self.logger.info(msg)
                return None
            time.sleep(self.sleep_small)
            data = self.com.read(10000)
            dt = time.time() - t0
            n += 1
        self.suspend_to = time.time()
        dt = time.time() - t0
        self.timeout = max(2.0*(dt+self.sleep), self.min_timeout)
        self.logger.debug('-> %s %d %4.0f ms' % (data, n, (time.time() - t0) * 1000.0))
        return data

    def read(self):
        t0 = time.time()
        if self.offline():
            self.logger.debug('Device is offline')
            return None
        data = self._read()
        while data is None:
            self.retries += 1
            if self.retries >= RETRIES:
                self.logger.warning('Reading retries limit')
                self.suspend()
                return None
            # print('t1=', time.time() - t0, end='')
            self.logger.debug('Retry reading %d' % self.retries)
            time.sleep(self.sleep)
            data = self._read()
        self.retries = 0
        self.suspend_to = time.time()
        self.logger.debug('-> %s %4.0f ms' % (data, (time.time() - t0) * 1000.0))
        return data

    def inc_error_count(self, msg=None):
        self.error_count += 1
        if self.error_count > MAX_ERROR_COUNT:
            if msg is None:
                msg = 'Error count exceeded'
            self.logger.warning(msg)
            self.suspend()
            return True
        return False

    def suspend(self, msg=None, duration=SUSPEND):
        if msg is None:
            msg = 'Suspended for %5.2f sec' % duration
        self.logger.warning(msg)
        self.suspend_to = time.time() + duration
        self.error_count = 0
        #self.com.send_break()
        #self.com.reset_input_buffer()
        #self.com.reset_output_buffer()
        time.sleep(self.sleep)
        self.com.read(10000)

    def suspended(self):
        if time.time() < self.suspend_to:
            ##self.logger.debug('Device is suspended')
            return True
        return False

    def offline(self):
        if self.com is None:
            ##self.logger.debug('Device is offline')
            return True
        return self.suspended()

    def read_to_cr(self):
        result = b''
        data = self.read()
        while data is not None:
            self.suspend_to = time.time()
            result += data
            n = result.find(b'\r')
            if n >= 0:
                n1 = result[n+1:].find(b'\r')
                if n1 >= 0:
                    self.logger.warning('Second CR in response %s, %s used' % (result, result[n+1:]))
                    result = result[n+1:]
                    n = result.find(b'\r')
                m = n
                self.last_response = result[:n]
                if self.check:
                    m = result.find(b'$')
                    if m < 0:
                        self.logger.error('No checksum')
                        self.inc_error_count()
                        return None
                    else:
                        cs = self.checksum(result[:m])
                        if result[m+1:n] != cs:
                            self.logger.error('Incorrect checksum')
                            self.inc_error_count()
                            return None
                        self.error_count = 0
                        return result[:m]
                self.error_count = 0
                return result[:m]
            data = self.read()
        self.logger.warning('Response without CR')
        self.inc_error_count()
        self.last_response = result
        return None

    def _set_addr(self):
        if hasattr(self.com, '_current_addr'):
            a0 = self.com._current_addr
        else:
            a0 = -1
        self._send_command(b'ADR %d' % self.addr)
        if self.check_response():
            self.com._current_addr = self.addr
            self.logger.debug('address %d -> %d' % (a0, self.addr))
            return True
        else:
            self.logger.warning('Cannot set address %d -> %d' % (a0, self.addr))
            if self.com is not None:
                self.com._current_addr = -1
            return False

    def set_addr(self):
        count = 0
        result = self._set_addr()
        while count < MAX_ERROR_COUNT:
            if result:
                return True
            else:
                ##self.logger.warning('Set address error. %s %d' % (self.last_response, self.com._current_addr) )
                count +=1
                time.sleep(2*self.sleep)
                self.com.read(10000)
                result = self._set_addr()
        if result:
            return True
        self.logger.error('Cannot set address with retries')
        self.suspend()
        #self.logger.error('Cannot set address. Device is switched off.')
        #self.com = None
        return False

    def read_float(self, cmd):
        reply = self.send_command(cmd)
        try:
            v = float(reply)
        except:
            self.logger.error('%s is not a float' % reply)
            v = float('Nan')
        return v

    def read_value(self, cmd, vtype=str):
        #t0 = time.time()
        reply = b''
        try:
            reply = self.send_command(cmd)
            v = vtype(reply)
        except:
            self.check_response(response=b'Wrong format:'+reply)
            v = None
        #dt = time.time() - t0
        #print('read_value', dt)
        return v

    def read_bool(self, cmd):
        response = self.send_command(cmd)
        if response.upper() in (b'ON', b'1'):
            return True
        if response.upper() in (b'OFF', b'0'):
            return False
        self.check_response(response=b'Not boolean:' + response)
        return False

    def write_value(self, cmd: bytes, value, expect=b'OK'):
        cmd = cmd.upper().strip() + b' ' + str.encode(str(value))[:10] + b'\r'
        self.send_command(cmd)
        return self.check_response(expect)

    def reset(self):
        self.__del__()
        self.__init__(self.port, self.addr, self.check, self.auto_addr, self.baud, 0, self.logger)


if __name__ == "__main__":
    pdl = TDKLambda("COM4", 6)
    pd2 = TDKLambda("COM4", 7)
    for i in range(10):
        t0 = time.time()
        v1 = pdl.read_float("PC?")
        dt1 = int((time.time()-t0)*1000.0)    #ms
        print('1: ', '%4d ms ' % dt1,'PC?=', v1, 'to=', '%5.3f' % pdl.timeout, pdl.port, pdl.addr)
        t0 = time.time()
        v2 = pd2.read_float("PC?")
        dt2 = int((time.time()-t0)*1000.0)    #ms
        print('2: ', '%4d ms '%dt2,'PC?=', v2, 'to=', '%5.3f'%pdl.timeout, pd2.port, pd2.addr)
