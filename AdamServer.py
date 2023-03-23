#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TDK Lambda Genesis series power supply tango device server"""
import sys
if '../TangoUtils' not in sys.path: sys.path.append('../TangoUtils')
if '../IT6900' not in sys.path: sys.path.append('../IT6900')
import json
import math
import os

import time
from threading import Lock

import tango

from log_exception import log_exception

from tango import AttrQuality, AttrWriteType, DispLevel
from tango import DevState, AttrDataFormat
from tango.server import attribute, command

from Adam import Adam, ADAM_DEVICES
from TangoServerPrototype import TangoServerPrototype

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'Adam I/O modules Tango Server'
APPLICATION_NAME_SHORT = 'AdamServer'
APPLICATION_VERSION = '2.1'


# db = tango.Database('192.168.1.41', '10000')
# dn = 'binp/nbi/adam4055'
# pn = 'polled_attr'
# pr = db.get_device_property(dn, pn)
# db.delete_device_property(dn, pn)
# tango.ApiUtil.get_env_var("TANGO_HOST")
# tango.__version_info__
# dp = tango.DeviceProxy('tango://192.168.1.41:10000/binp/nbi/adam4055')
# an = 'do00'
# dp.is_attribute_polled(an)
# dp.get_attribute_poll_period(an)
# dp.poll_attribute(an, 2000)


class AdamServer(TangoServerPrototype):
    server_version_value = APPLICATION_VERSION
    server_name_value = APPLICATION_NAME_SHORT
    POLLING_ENABLE_DELAY = 0.2

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
        self.init_po = False
        self.ceated_attributes = {}
        #
        name = self.config.get('name', '')
        description = json.loads(self.config.get('description', '[]'))
        if name and description:
            ADAM_DEVICES.update({name: description})
            self.logger.debug(f'New device type {name}: {description} registered')
        self.show_disabled_channels = bool(self.config.get('show_disabled_channels', 1))
        # create adam device
        port = self.config.get('port', 'COM3')
        addr = self.config.get('addr', 6)
        kwargs = {'baudrate': self.config.get('baudrate', 38400),
                  'logger': self.logger,
                  'read_retries': self.config.get('read_retries', 2),
                  'suspend_time': self.config.get('suspend_time', 10.0)}
        self.adam = Adam(port, addr, **kwargs)
        # add device to list
        if self not in AdamServer.device_list:
            AdamServer.device_list.append(self)
        # else:
        #     self.logger.info(f'Duplicated device declaration for {self}')
        # execute init sequence
        init_command = self.config.get('init_command', '')
        if init_command:
            commands = init_command.split(';')
            stat = ''
            for c in commands:
                s = self.send_adam_command(c)
                stat += f'{s}; '
            self.logger.debug(f'Initialization commands {init_command} executed with result {stat}')
        #
        # self.write_config_to_properties()
        # check if device OK
        if self.adam.ready:
            # change state to running
            msg = 'Adam %s created successfully at %s:%d' % (self.adam.id, self.adam.port, self.adam.addr)
            self.set_state(DevState.RUNNING, msg)
            self.logger.info(msg)
        else:
            msg = 'Adam %s at %s:%d created with errors' % (self.adam.id, self.adam.port, self.adam.addr)
            self.set_state(DevState.FAULT, msg)
            self.logger.error(msg)

    def delete_device(self):
        if self in AdamServer.device_list:
            self.save_polling_state()
            self.stop_polling()
            tango.Database().delete_device_property(self.get_name(), 'polled_attr')
            AdamServer.device_list.remove(self)
            self.adam.__del__()
            msg = ' %s:%d Adam device has been deleted' % (self.adam.port, self.adam.addr)
            self.logger.info(msg)
        super().delete_device()

    def read_port(self):
        if self.adam.ready:
            self.set_running()
        else:
            self.set_fault()
        return self.adam.port

    def read_address(self):
        if self.adam.ready:
            self.set_running()
        else:
            self.set_fault()
        return str(self.adam.addr)

    def read_device_type(self):
        if self.adam.ready:
            self.set_running()
            return self.adam.id
        else:
            self.set_fault()
            return "Uninitialized"

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
            attr.set_value(value)
            attr.set_quality(tango.AttrQuality.ATTR_VALID)
            self.set_running()
            return value
        else:
            self.set_fault()
            return self.set_error_attribute_value(attr)

    def read_general(self, attr: tango.Attribute):
        with self.lock:
            val = self._read_io(attr)
            if val is None:
                msg = '%s ADAM is not ready reading %s' % (self.get_name(), attr.get_name())
                self.logger.debug(msg)
            self.set_attribute_value(attr, val)
            return val

    def write_general(self, attr: tango.WAttribute):
        with self.lock:
            attr_name = attr.get_name()
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
                attr.set_quality(tango.AttrQuality.ATTR_INVALID)
                return
            if result:
                attr.set_quality(tango.AttrQuality.ATTR_VALID)
            else:
            #     if mask:
            #         self.error_time = time.time()
            #         self.error_count += 1
            #         msg = "%s Error writing %s" % (self.get_name(), attr_name)
            #         self.logger.error(msg)
            #         # self.error_stream(msg)
            #         self.set_error_attribute_value(attr)
                attr.set_quality(tango.AttrQuality.ATTR_INVALID)

    def _read_io(self, attr: tango.Attribute):
        attr_name = attr.get_name()
        chan = int(attr_name[-2:])
        ad = attr_name[:2]
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
            return None
        if val is not None and not math.isnan(val):
            return val
        msg = "%s Error reading %s %s" % (self.get_name(), attr_name, val)
        self.logger.error(msg)
        return None

    @command(dtype_in=str, doc_in='Directly send command to the Adam',
             dtype_out=str, doc_out='Response from Adam without final <CR>')
    def send_adam_command(self, cmd):
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
                    self.init_po = False
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
                                                 format='%6.3f',
                                                 min_value=self.adam.ai_min[k],
                                                 max_value=self.adam.ai_max[k])
                                # add attr to device
                                self.add_attribute(attr)
                                self.ceated_attributes[attr_name] = attr
                                # self.restore_polling(attr_name)
                                nai += 1
                            else:
                                self.logger.info('%s is disabled', attr_name)
                        except KeyboardInterrupt:
                            raise
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
                                                 format='%6.3f',
                                                 min_value=self.adam.ao_min[k],
                                                 max_value=self.adam.ao_max[k])
                                self.add_attribute(attr)
                                self.ceated_attributes[attr_name] = attr
                                v = self.adam.read_ao(k)
                                attr.get_attribute(self).set_write_value(v)
                                nao += 1
                            # else:
                            #     self.logger.info('%s is disabled', attr_name)
                        except KeyboardInterrupt:
                            raise
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
                            self.ceated_attributes[attr_name] = attr
                            ndi += 1
                        except KeyboardInterrupt:
                            raise
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
                            self.ceated_attributes[attr_name] = attr
                            v = self.adam.read_do(k)
                            attr.get_attribute(self).set_write_value(v)
                            ndo += 1
                        except KeyboardInterrupt:
                            raise
                        except:
                            log_exception('%s Exception adding IO channel %s' % (self.get_name(), attr_name))
                    msg = '%s %d digital outputs initialized' % (self.get_name(), ndo)
                    self.logger.info(msg)
                self.set_state(DevState.RUNNING, 'IO addition completed')
            except KeyboardInterrupt:
                raise
            except:
                log_exception('%s Error adding IO channels' % self.get_name())
                self.set_state(DevState.FAULT, msg)
            self.init_io = False
            self.init_po = True
            # self.restore_polling()
            return nai + nao + ndi + ndo

    # def restore_polling(self, attr_name=None):
    #     dp = tango.DeviceProxy(self.get_name())
    #     for name in self.ceated_attributes:
    #         if attr_name is None or attr_name == name:
    #             pp = self.get_saved_polling_period(name)
    #             if pp > 0:
    #                 dp.poll_attribute(name, pp)
    #                 # workaround to prevent tango feature
    #                 time.sleep(self.POLLING_ENABLE_DELAY)
    #                 self.logger.info(f'Polling for {self.get_name()} {name} of {pp} restored')

    # def get_saved_polling_period(self, attr_name, prop_name='_polled_attr'):
    #     try:
    #         pa = self.properties.get(prop_name)
    #         i = pa.index(attr_name)
    #         if i < 0:
    #             return -1
    #         return int(pa[i + 1])
    #     except:
    #         return -1

    def remove_io(self):
        with self.lock:
            try:
                for attr_name in self.ceated_attributes:
                    self.remove_attribute(attr_name)
                    self.logger.debug('%s attribute %s removed' % (self.get_name(), attr_name))
                self.ceated_attributes = {}
                self.set_state(DevState.CLOSE, 'All IO channels removed')
                self.init_io = True
            except KeyboardInterrupt:
                raise
            except:
                log_exception(self.logger, '%s Error deleting IO channels' % self.get_name())
                # self.set_state(DevState.FAULT)

    def save_polling_state(self, target_property='_polled_attr'):
        try:
            if self.adam.name == '0000':
                self.logger.info(f'Polling was not saved for unknown device {self.get_name()}')
                return False
            super().save_polling_state(target_property)
        except KeyboardInterrupt:
            raise
        except:
            log_exception()

def looping():
    # print('loop entry')
    post_init_callback()
    time.sleep(1.0)
    # print('loop exit')


def post_init_callback():
    # called once at server initiation
    for dev in AdamServer.device_list:
        if dev.init_io:
            dev.add_io()
    for dev in AdamServer.device_list:
        if dev.init_po:
            dev.restore_polling()
            dev.init_po = False


if __name__ == "__main__":
    db = tango.Database()
    sn = os.path.basename(sys.argv[0]).replace('.py','')
    # os.path.basename(__file__)
    # sn = 'AdamServer'
    pn = 'polled_attr'
    dcl = db.get_device_class_list(sn + '/' + sys.argv[1])
    st = dcl.value_string
    i = 0
    for s in st:
        if s == sn:
            dn = st[i - 1]
            db.delete_device_property(dn, pn)
            # pr = db.get_device_property(dn, pn)[pn]
            # if (len(pr) % 2) != 0:
            #     # db.delete_device_property(dn, pn)
            #     print('Cleaning', pn, 'for', dn, pr)
        i += 1
    #
    AdamServer.run_server(post_init_callback=post_init_callback)
    # AdamServer.run_server(event_loop=looping, post_init_callback=post_init_callback)
    # AdamServer.run_server(event_loop=looping)
    # AdamServer.run_server()
