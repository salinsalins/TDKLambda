#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TDK Lambda Genesis series power supply tango device server"""
import json
import sys
from threading import Lock

sys.path.append('../TangoUtils')
sys.path.append('../IT6900')

import logging
import time
from math import isnan

from tango import AttrQuality, AttrWriteType, DispLevel
from tango import DevState
from tango.server import attribute, command

from Adam import Adam, ADAM_DEVICES
from TangoServerPrototype import TangoServerPrototype

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'Adam I/O modules Tango Server'
APPLICATION_NAME_SHORT = 'AdamServer'
APPLICATION_VERSION = '1.0'


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
        self.info('Adam Initialization')
        self.set_state(DevState.INIT, 'Adam Initialization')
        self.configure_tango_logging()
        self.lock = Lock()
        self.error_count = 0
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
        kwargs = {}
        kwargs['baudrate'] = baud
        kwargs['logger'] = self.logger
        self.adam = Adam(port, addr, **kwargs)
        # add device to list
        if self not in AdamServer.device_list:
            AdamServer.device_list.append(self)
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
            self.set_state(DevState.RUNNING, f'Adam {self.adam.id[-4:]} initialized')
            msg = 'Adam %s created successfully at %s:%d' % (self.adam.id[-4:], self.adam.port, self.adam.addr)
            self.info(msg)
        else:
            msg = 'Adam %s at %s:%d created with errors' % (self.adam.id[-4:], self.adam.port, self.adam.addr)
            self.error(msg)
            self.set_state(DevState.FAULT, 'Adam initialization error')

    def delete_device(self):
        super().delete_device()
        if self in AdamServer.device_list:
            AdamServer.device_list.remove(self)
            self.adam.__del__()
            msg = ' %s:%d Adam device has been deleted' % (self.adam.port, self.adam.addr)
            # del self.adam
            # self.adam = None
            self.info(msg)

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
            return self.adam.id[-4:].decode()
        return "Uninitialized"

    def read_all(self):
        t0 = time.time()
        try:
            values = self.adam.read_all()
            self.values = values
            self.time = time.time()
            msg = '%s:%d read_all %s ms %s' % \
                  (self.adam.port, self.adam.addr, int((self.time - t0) * 1000.0), values)
            self.debug(msg)
        except:
            self.set_fault()
            msg = '%s:%d read_all error' % (self.adam.port, self.adam.addr)
            self.log_exception(msg)

    # @command
    # def reset_ps(self):
    #     msg = '%s:%d Reset Adam PS' % (self.adam.port, self.adam.addr)
    #     self.info(msg)
    #     self.adam._send_command(b'RST\r')

    @command(dtype_in=str, doc_in='Directly send command to the Adam',
             dtype_out=str, doc_out='Response from Adam without final <CR>')
    def send_command(self, cmd):
        self.adam.send_command(cmd)
        rsp = self.adam.response[:-1].decode()
        msg = '%s:%d %s -> %s' % (self.adam.port, self.adam.addr, cmd, rsp)
        self.debug(msg)
        # if self.adam.com is None:
        #     msg = '%s COM port is None' % self
        #     self.debug(msg)
        #     self.set_state(DevState.FAULT)
        #     return
        return rsp

    def add_io(self):
        with self.lock:
            nai = 0
            nao = 0
            ndi = 0
            ndo = 0
            try:
                if self.adam.name == '0000':
                    self.error_time = time.time()
                    self.error_count += 1
                    msg = '%s No IO attributes added for unknown device' % self.get_name()
                    self.logger.warning(msg)
                    # self.error_stream(msg)
                    self.set_state(DevState.FAULT, msg)
                    return
                self.error_time = 0.0
                self.error_count = 0
                self.set_state(DevState.INIT, 'Attributes creation')
                attr_name = ''
                # ai
                nai = 0
                if self.adam.ai_n > 0:
                    for k in range(self.adam.ai_n):
                        try:
                            attr_name = 'ai%02d' % k
                            if True:
                                attr = tango.server.attribute(name=attr_name, dtype=float,
                                                              dformat=tango.AttrDataFormat.SCALAR,
                                                              access=tango.AttrWriteType.READ,
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
                            msg = '%s Exception adding AI %s' % (self.get_name(), attr_name)
                            self.logger.warning(msg)
                            self.logger.debug('', exc_info=True)
                    msg = '%s %d of %d analog inputs initialized' % (self.get_name(), nai, self.adam.ai_n)
                    self.logger.info(msg)
                    # self.info_stream(msg)
                # ao
                nao = 0
                if self.adam.ao_n > 0:
                    for k in range(self.adam.ao_n):
                        try:
                            attr_name = 'ao%02d' % k
                            if True:
                                attr = tango.server.attribute(name=attr_name, dtype=float,
                                                              dformat=tango.AttrDataFormat.SCALAR,
                                                              access=tango.AttrWriteType.READ_WRITE,
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
                                # self.restore_polling(attr_name)
                                nao += 1
                            else:
                                self.logger.info('%s is disabled', attr_name)
                        except:
                            msg = '%s Exception adding AO %s' % (self.get_name(), attr_name)
                            self.logger.warning(msg)
                            self.logger.debug('', exc_info=True)
                    msg = '%s %d of %d analog outputs initialized' % (self.get_name(), nao, self.adam.ao_n)
                    self.logger.info(msg)
                    # self.info_stream(msg)
                # di
                ndi = 0
                if self.adam.di_n > 0:
                    for k in range(self.adam.di_n):
                        try:
                            attr_name = 'di%02d' % k
                            attr = tango.server.attribute(name=attr_name, dtype=tango.DevBoolean,
                                                          dformat=tango.AttrDataFormat.SCALAR,
                                                          access=tango.AttrWriteType.READ,
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
                            msg = '%s Exception adding IO channel %s' % (self.get_name(), attr_name)
                            self.logger.warning(msg)
                            self.logger.debug('', exc_info=True)
                    msg = '%s %d digital inputs initialized' % (self.get_name(), ndi)
                    self.logger.info(msg)
                    # self.info_stream(msg)
                # do
                ndo = 0
                if self.adam.do_n > 0:
                    for k in range(self.adam.do_n):
                        try:
                            attr_name = 'do%02d' % k
                            attr = tango.server.attribute(name=attr_name, dtype=tango.DevBoolean,
                                                          dformat=tango.AttrDataFormat.SCALAR,
                                                          access=tango.AttrWriteType.READ_WRITE,
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
                            # self.restore_polling(attr_name)
                            ndo += 1
                        except:
                            msg = '%s Exception adding IO channel %s' % (self.get_name(), attr_name)
                            self.logger.warning(msg)
                            self.logger.debug('', exc_info=True)
                    msg = '%s %d digital outputs initialized' % (self.get_name(), ndo)
                    self.logger.info(msg)
                    # self.info_stream(msg)
                self.set_state(DevState.RUNNING)
            except:
                self.error_time = time.time()
                self.error_count += 1
                msg = '%s Error adding IO channels' % self.get_name()
                self.logger.error(msg)
                self.logger.debug('', exc_info=True)
                # self.error_stream(msg)
                self.set_state(DevState.FAULT)
                return
            self.init_io = False
            return nai + nao + ndi + ndo

    def remove_io(self):
        with self.lock:
            try:
                for attr_name in self.attributes:
                    self.remove_attribute(attr_name)
                    self.logger.debug('%s attribute %s removed' % (self.get_name(), attr_name))
                self.attributes = {}
                self.set_state(DevState.UNKNOWN)
                self.init_io = True
            except:
                msg = '%s Error deleting IO channels' % self.get_name()
                self.logger.error(msg)
                self.logger.debug('', exc_info=True)
                # self.error_stream(msg)
                # self.set_state(DevState.FAULT)


def looping():
    # AdamServer.LOGGER.debug('loop entry')
    for dev in AdamServer.device_list:
        if dev.init_io:
            dev.add_io()
        # if dev.error_time > 0.0 and dev.error_time - time.time() > dev.reconnect_timeout:
        #     dev.reconnect()
    time.sleep(1.0)
    # AdamServer.LOGGER.debug('loop exit')


# def post_init_callback():
#     print('post_init_callback')
#     pass


if __name__ == "__main__":
    # AdamServer.run_server(post_init_callback=post_init_callback)
    # AdamServer.run_server(event_loop=looping)
    AdamServer.run_server()
