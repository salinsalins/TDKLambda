#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TDK Lambda Genesis series power supply tango device server"""
import json
import math
import sys
from threading import Lock

import tango

from log_exception import log_exception

sys.path.append('../TangoUtils')
sys.path.append('../IT6900')

import logging
import time
from math import isnan

from tango import AttrQuality, AttrWriteType, DispLevel
from tango import DevState, AttrDataFormat
from tango.server import attribute, command

from Adam import Adam, ADAM_DEVICES
from TangoServerPrototype import TangoServerPrototype

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'Adam I/O modules Tango Server'
APPLICATION_NAME_SHORT = 'AdamServer'
APPLICATION_VERSION = '1.2'


class AdamServer(TangoServerPrototype):
    server_version_value = APPLICATION_VERSION
    server_name_value = APPLICATION_NAME_SHORT
    READING_VALID_TIME = 1.0

    port = attribute(label="Port", dtype=str,
                     display_level=DispLevel.OPERATOR,
                     access=AttrWriteType.READ,
                     unit="", format="%s",
                     doc="Adam port")

    address = attribute(label="Address", dtype=str,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ,
                        unit="", format="%s",
                        doc="Adam address")

    device_type = attribute(label="Adam Type", dtype=str,
                            display_level=DispLevel.OPERATOR,
                            access=AttrWriteType.READ,
                            unit="", format="%s",
                            doc="Adam device type")

    def init_device(self):
        super().init_device()
        self.set_state(DevState.INIT, 'Adam Initialization')
        # self.configure_tango_logging()
        self.lock = Lock()
        self.init_io = True
        self.attributes = {}
        self.values = [float('NaN')] * 6
        self.time = time.time() - 100.0
        self.READING_VALID_TIME = self.config.get('reading_valid_time', self.READING_VALID_TIME)
        # get port and address from property
        name = self.config.get('name', '')
        description = json.loads(self.config.get('description', '[]'))
        if name and description:
            ADAM_DEVICES.update({name: description})
        port = self.config.get('port', 'COM3')
        addr = self.config.get('addr', 6)
        baud = self.config.get('baudrate', 38400)
        read_retries = self.config.get('read_retries', 2)
        kwargs = {}
        kwargs['baudrate'] = baud
        kwargs['logger'] = self.logger
        kwargs['read_retries'] = read_retries
        self.show_disabled_channels = bool(self.config.get('show_disabled_channels', 1))
        self.adam = Adam(port, addr, **kwargs)
        # add device to list
        if self not in AdamServer.device_list:
            AdamServer.device_list.append(self)
        init_command = self.config.get('init_command', '')
        if init_command:
            commands = init_command.split(';')
            stat = ''
            for c in commands:
                s = self.send_command(c)
                stat += s
        self.write_config_to_properties()
        # check if device OK
        if self.adam.initialized():
            # if self.adam.max_voltage < float('inf'):
            #     self.programmed_voltage.set_max_value(self.adam.max_voltage)
            # if self.adam.max_current < float('inf'):
            #     self.programmed_current.set_max_value(self.adam.max_current)
            # self.programmed_voltage.set_write_value(self.read_programmed_voltage())
            # self.programmed_current.set_write_value(self.read_programmed_current())
            # self.output_state.set_write_value(self.read_output_state())
            # # set state to running
            self.set_state(DevState.RUNNING, f'Adam {self.adam.id} initialized')
            msg = 'Adam %s created successfully at %s:%d' % (self.adam.id, self.adam.port, self.adam.addr)
            self.logger.info(msg)
        else:
            msg = 'Adam %s at %s:%d created with errors' % (self.adam.id, self.adam.port, self.adam.addr)
            self.logger.error(msg)
            self.set_state(DevState.FAULT, 'Adam initialization error')

    def delete_device(self):
        super().delete_device()
        if self in AdamServer.device_list:
            AdamServer.device_list.remove(self)
            self.adam.__del__()
            msg = ' %s:%d Adam device has been deleted' % (self.adam.port, self.adam.addr)
            # del self.adam
            # self.adam = None
            self.logger.info(msg)

    def read_port(self):
        if self.adam.initialized():
            return self.adam.port
        return "Unknown"

    def read_address(self):
        if self.adam.initialized():
            return str(self.adam.addr)
        return "-1"

    def read_device_type(self):
        if self.adam.initialized():
            return self.adam.id
        return "Uninitialized"

    def is_connected(self):
        # if self.et is None or self.et.type == 0:
        #     if self.error_time > 0.0 and self.error_time - time.time() > self.reconnect_timeout:
        #         self.reconnect()
        #     return False
        # return True
        return self.adam.initialized()

    def set_error_attribute_value(self, attr: tango.Attribute):
        v = None
        if attr.get_data_format() == tango.DevBoolean:
            v = False
        elif attr.get_data_format() == tango.DevDouble:
            v = float('nan')
        if attr.get_data_type() == tango.SPECTRUM:
            v = [v]
        attr.set_value(v)
        attr.set_quality(tango.AttrQuality.ATTR_INVALID)
        return v

    def set_attribute_value(self, attr: tango.Attribute, value=None):
        if value is not None and not math.isnan(value):
            self.error_time = 0.0
            self.error_count = 0
            attr.set_value(value)
            attr.set_quality(tango.AttrQuality.ATTR_VALID)
            self.set_running()
            return value
        else:
            self.set_fault()
            return self.set_error_attribute_value(attr)

    def read_general(self, attr: tango.Attribute):
        with self.lock:
            # attr_name = attr.get_name()
            if self.is_connected():
                val = self._read_io(attr)
            else:
                val = None
                msg = '%s %s Waiting for reconnect' % (self.get_name(), attr.get_name())
                self.logger.debug(msg)
            self.set_attribute_value(attr, val)
            return val

    def write_general(self, attr: tango.WAttribute):
        with self.lock:
            attr_name = attr.get_name()
            # self.logger.debug('entry %s %s', self.get_name(), attr_name)
            value = attr.get_write_value()
            chan = int(attr_name[-2:])
            ad = attr_name[:2]
            if ad == 'ao':
                result = self.adam.write_ao(chan, value)
            elif ad == 'do':
                result = self.adam.write_do(chan, value)
            else:
                msg = "%s Write to unknown attribute %s" % (self.get_name(), attr_name)
                self.logger.error(msg)
                # self.error_stream(msg)
                # self.set_error_attribute_value(attr)
                # attr.set_quality(tango.AttrQuality.ATTR_INVALID)
                return
            if result:
                self.error_time = 0.0
                self.error_count = 0
                attr.set_quality(tango.AttrQuality.ATTR_VALID)
            # else:
            #     if mask:
            #         self.error_time = time.time()
            #         self.error_count += 1
            #         msg = "%s Error writing %s" % (self.get_name(), attr_name)
            #         self.logger.error(msg)
            #         # self.error_stream(msg)
            #         self.set_error_attribute_value(attr)
            #         # attr.set_quality(tango.AttrQuality.ATTR_INVALID)

    def _read_io(self, attr: tango.Attribute):
        attr_name = attr.get_name()
        chan = int(attr_name[-2:])
        ad = attr_name[:2]
        mask = True
        if ad == 'ai':
            val = self.adam.read_ai(chan)
        elif ad == 'di':
            val = self.adam.read_di(chan)
        elif ad == 'do':
            val = self.adam.read_do(chan)
        elif ad == 'ao':
            val = self.adam.read_ao(chan)
        else:
            msg = "%s Unknown attribute %s" % (self.get_name(), attr_name)
            self.logger.error(msg)
            return float('nan')
        if val is not None and not math.isnan(val):
            return val
        msg = "%s Error reading %s %s" % (self.get_name(), attr_name, val)
        self.logger.error(msg)
        return float('nan')

    # @command
    # def reset_ps(self):
    #     msg = '%s:%d Reset Adam PS' % (self.adam.port, self.adam.addr)
    #     self.logger.info(msg)
    #     self.adam._send_command(b'RST\r')

    @command(dtype_in=str, doc_in='Directly send command to the Adam',
             dtype_out=str, doc_out='Response from Adam without final <CR>')
    def send_command(self, cmd):
        self.adam.send_command(cmd)
        rsp = self.adam.response[:-1].decode()
        msg = '%s:%d %s -> %s' % (self.adam.port, self.adam.addr, cmd, rsp)
        self.logger.debug(msg)
        return rsp

    def add_io(self):
        with self.lock:
            nai = 0
            nao = 0
            ndi = 0
            ndo = 0
            try:
                if self.adam.name == '0000':
                    msg = '%s No IO attributes added for unknown device' % self.get_name()
                    self.logger.warning(msg)
                    self.set_state(DevState.FAULT, msg)
                    self.init_io = False
                    return
                self.set_state(DevState.INIT, 'Attributes creation')
                attr_name = ''
                # ai
                nai = 0
                if self.adam.ai_n > 0:
                    for k in range(self.adam.ai_n):
                        try:
                            attr_name = 'ai%02d' % k
                            if self.adam.ai_masks[k] or self.show_disabled_channels:
                                attr = attribute(name=attr_name, dtype=float,
                                                 dformat=AttrDataFormat.SCALAR,
                                                 access=AttrWriteType.READ,
                                                 max_dim_x=1, max_dim_y=0,
                                                 fget=self.read_general,
                                                 label=attr_name,
                                                 doc='Analog input %s' % k,
                                                 unit=self.adam.ai_units[k],
                                                 display_unit=1.0,
                                                 format='%f',
                                                 min_value=self.adam.ai_min[k],
                                                 max_value=self.adam.ai_max[k])
                                # add attr to device
                                self.add_attribute(attr)
                                self.attributes[attr_name] = attr
                                # self.restore_polling(attr_name)
                                nai += 1
                            else:
                                self.logger.info('%s is disabled', attr_name)
                        except:
                            log_exception('%s Exception adding AI %s' % (self.get_name(), attr_name))
                    msg = '%s %d of %d analog inputs initialized' % (self.get_name(), nai, self.adam.ai_n)
                    self.logger.info(msg)
                # ao
                nao = 0
                if self.adam.ao_n > 0:
                    for k in range(self.adam.ao_n):
                        try:
                            attr_name = 'ao%02d' % k
                            if True:
                                attr = attribute(name=attr_name, dtype=float,
                                                 dformat=AttrDataFormat.SCALAR,
                                                 access=AttrWriteType.READ_WRITE,
                                                 max_dim_x=1, max_dim_y=0,
                                                 fget=self.read_general,
                                                 fset=self.write_general,
                                                 label=attr_name,
                                                 doc='Analog output %s' % k,
                                                 unit=self.adam.ao_units[k],
                                                 display_unit=1.0,
                                                 format='%f',
                                                 min_value=self.adam.ao_min[k],
                                                 max_value=self.adam.ao_max[k])
                                self.add_attribute(attr)
                                self.attributes[attr_name] = attr
                                v = self.adam.read_ao(k)
                                attr.get_attribute(self).set_write_value(v)
                                # self.restore_polling(attr_name)
                                nao += 1
                            else:
                                self.logger.info('%s is disabled', attr_name)
                        except:
                            log_exception('%s Exception adding IO channel %s' % (self.get_name(), attr_name))
                    msg = '%s %d of %d analog outputs initialized' % (self.get_name(), nao, self.adam.ao_n)
                    self.logger.info(msg)
                # di
                ndi = 0
                if self.adam.di_n > 0:
                    for k in range(self.adam.di_n):
                        try:
                            attr_name = 'di%02d' % k
                            attr = attribute(name=attr_name, dtype=bool,
                                             dformat=AttrDataFormat.SCALAR,
                                             access=AttrWriteType.READ,
                                             max_dim_x=1, max_dim_y=0,
                                             fget=self.read_general,
                                             label=attr_name,
                                             doc='Digital input %s' % k,
                                             unit='',
                                             display_unit=1.0,
                                             format='')
                            self.add_attribute(attr)
                            self.attributes[attr_name] = attr
                            # self.restore_polling(attr_name)
                            ndi += 1
                        except:
                            log_exception('%s Exception adding IO channel %s' % (self.get_name(), attr_name))
                    msg = '%s %d digital inputs initialized' % (self.get_name(), ndi)
                    self.logger.info(msg)
                # do
                ndo = 0
                if self.adam.do_n > 0:
                    for k in range(self.adam.do_n):
                        try:
                            attr_name = 'do%02d' % k
                            attr = attribute(name=attr_name, dtype=bool,
                                             dformat=AttrDataFormat.SCALAR,
                                             access=AttrWriteType.READ_WRITE,
                                             max_dim_x=1, max_dim_y=0,
                                             fget=self.read_general,
                                             fset=self.write_general,
                                             label=attr_name,
                                             doc='Digital output %s' % k,
                                             unit='',
                                             display_unit=1.0,
                                             format='')
                            self.add_attribute(attr)
                            self.attributes[attr_name] = attr
                            v = self.adam.read_do(k)
                            attr.get_attribute(self).set_write_value(v)
                            # self.restore_polling(attr_name)
                            ndo += 1
                        except:
                            log_exception('%s Exception adding IO channel %s' % (self.get_name(), attr_name))
                    msg = '%s %d digital outputs initialized' % (self.get_name(), ndo)
                    self.logger.info(msg)
                self.set_state(DevState.RUNNING, 'IO addition completed')
            except:
                log_exception('%s Error adding IO channels' % self.get_name())
                self.set_state(DevState.FAULT, msg)
            self.init_io = False
            return nai + nao + ndi + ndo

    def remove_io(self):
        with self.lock:
            try:
                for attr_name in self.attributes:
                    self.remove_attribute(attr_name)
                    self.logger.debug('%s attribute %s removed' % (self.get_name(), attr_name))
                self.attributes = {}
                self.set_state(DevState.CLOSE, 'All IO channels removed')
                self.init_io = True
            except:
                log_exception(self.logger, '%s Error deleting IO channels' % self.get_name())
                # self.set_state(DevState.FAULT)


def looping():
    # print('loop entry')
    for dev in AdamServer.device_list:
        if dev.init_io:
            dev.add_io()
        # if dev.error_time > 0.0 and dev.error_time - time.time() > dev.reconnect_timeout:
        #     dev.reconnect()
    time.sleep(1.0)
    # print('loop exit')


# def post_init_callback():
#     # called once at server initiation
#     print('post_init_callback')
#     pass


if __name__ == "__main__":
    # AdamServer.run_server(event_loop=looping, post_init_callback=post_init_callback)
    AdamServer.run_server(event_loop=looping)
    # AdamServer.run_server()
