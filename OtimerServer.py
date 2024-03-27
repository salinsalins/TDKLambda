#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Oreshonok timer tango device server"""
import os
import sys
util_path = os.path.realpath('../TangoUtils')
if util_path not in sys.path:
    sys.path.append(util_path)
del util_path

import json
import math
import time
from threading import Lock

import tango

from log_exception import log_exception

from tango import AttrQuality, AttrWriteType, DispLevel
from tango import DevState, AttrDataFormat
from tango.server import attribute, command

from Adam import Adam, ADAM_DEVICES, FakeAdam
from TangoServerPrototype import TangoServerPrototype

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'Adam I/O modules Tango Server'
APPLICATION_NAME_SHORT = 'AdamServer'
APPLICATION_VERSION = '2.2'


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

# ******** init_device ***********
    def init_device(self):
        super().init_device()
        self.pre = f'{self.get_name()} Adam'
        msg = 'Initialization start'
        self.log_debug(msg)
        self.set_state(DevState.INIT, msg)
        # self.configure_tango_logging()
        self.lock = Lock()
        self.init_io = True
        self.init_po = True
        self.dynamic_attributes = {}
        #
        name = self.config.get('name', '')
        description = json.loads(self.config.get('description', '[]'))
        if name and description:
            ADAM_DEVICES.update({name: description})
            self.log_debug(f'New device type {name}: {description} registered')
        self.show_disabled_channels = bool(self.config.get('show_disabled_channels', 1))
        # create adam device
        port = self.config.get('port', 'COM3')
        addr = self.config.get('addr', 6)
        kwargs = {'baudrate': self.config.get('baudrate', 38400),
                  'logger': self.logger,
                  'read_retries': self.config.get('read_retries', 2),
                  'suspend_delay': self.config.get('suspend_delay', 10.0)}
        emulate = self.config.get('emulate', 0)
        if emulate:
            self.adam = FakeAdam(port, addr, **kwargs)
        else:
            self.adam = Adam(port, addr, **kwargs)
        self.pre = f'{self.get_name()} {self.adam.pre}'
        # execute init sequence
        init_command = self.config.get('init_command', '')
        if init_command:
            commands = init_command.split(';')
            stat = ''
            for c in commands:
                s = self.send_adam_command(c)
                stat += f'{s}; '
            self.log_debug(f'Initialization commands {init_command} executed with result {stat}')
        # check if device OK
        if self.adam.ready:
            # if device was initiated before
            if hasattr(self, 'deleted') and self.deleted:
                self.add_io()
                self.restore_polling()
                self.init_io = False
                self.init_po = False
                self.deleted = False
            # change state to running
            msg = 'Created successfully'
            self.set_state(DevState.RUNNING, msg)
            self.log_info(msg)
        else:
            msg = 'Created with errors'
            self.set_state(DevState.FAULT, msg)
            self.log_error(msg)

    def delete_device(self):
        self.save_polling_state()
        # self.stop_polling()
        self.remove_io()
        # tango.Database().delete_device_property(self.get_name(), 'polled_attr')
        self.adam.__del__()
        msg = 'Device has been deleted'
        self.log_info(msg)
        self.deleted = True
        super().delete_device()

# ******** attribute r/w procedures ***********
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

    def read_general(self, attr: tango.Attribute):
        with self.lock:
            val = self._read_io(attr)
            if val is None:
                msg = 'Is not ready reading %s' % attr.get_name()
                self.log_debug(msg)
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
                msg = "Write to unknown attribute %s" % attr_name
                self.log_error(msg)
                attr.set_quality(tango.AttrQuality.ATTR_INVALID)
                return
            if result:
                attr.set_quality(tango.AttrQuality.ATTR_VALID)
            else:
                #     if mask:
                #         self.error_time = time.time()
                #         self.error_count += 1
                #         msg = "Error writing %s" % attr_name
                #         self.log_error(msg)
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
            msg = "Read unknown attribute %s" % attr_name
            self.log_error(msg)
            return None
        if val is not None and not math.isnan(val):
            return val
        msg = "Error reading %s = %s" % (attr_name, val)
        self.log_error(msg)
        return None

# ******** commands ***********
    @command(dtype_in=str, doc_in='Directly send command to the Adam',
             dtype_out=str, doc_out='Response from Adam without final <CR>')
    def send_adam_command(self, cmd):
        self.adam.send_command(cmd)
        rsp = self.adam.response[:-1].decode()
        msg = 'Command %s -> %s' % (cmd, rsp)
        self.log_debug(msg)
        return rsp

# ******** additional helper functions ***********
    @staticmethod
    def set_error_attribute_value(attr: tango.Attribute):
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

    def add_io(self):
        with self.lock:
            nai = 0
            nao = 0
            ndi = 0
            ndo = 0
            try:
                if self.adam.name == '0000':
                    msg = 'No IO attributes added for unknown device'
                    self.log_warning(msg)
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
                                self.dynamic_attributes[attr_name] = attr
                                nai += 1
                            else:
                                self.log_info('%s is disabled', attr_name)
                        except KeyboardInterrupt:
                            raise
                        except:
                            self.log_exception('Exception adding AI %s' % attr_name)
                    msg = '%d of %d analog inputs initialized' % (nai, self.adam.ai_n)
                    self.log_info(msg)
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
                                self.dynamic_attributes[attr_name] = attr
                                v = self.adam.read_ao(k)
                                attr.get_attribute(self).set_write_value(v)
                                nao += 1
                            # else:
                            #     self.log_info('%s is disabled', attr_name)
                        except KeyboardInterrupt:
                            raise
                        except:
                            self.log_exception('Exception adding IO channel %s' % attr_name)
                    msg = '%s of %d of %d analog outputs initialized' % (self.get_name(), nao, self.adam.ao_n)
                    self.log_info(msg)
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
                            self.dynamic_attributes[attr_name] = attr
                            ndi += 1
                        except KeyboardInterrupt:
                            raise
                        except:
                            self.log_exception('Exception adding IO channel %s' % attr_name)
                    msg = '%s of %d digital inputs initialized' % (self.get_name(), ndi)
                    self.log_info(msg)
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
                            self.dynamic_attributes[attr_name] = attr
                            v = self.adam.read_do(k)
                            attr.get_attribute(self).set_write_value(v)
                            ndo += 1
                        except KeyboardInterrupt:
                            raise
                        except:
                            self.log_exception('Exception adding IO channel %s' % attr_name)
                    msg = '%s of %d digital outputs initialized' % (self.get_name(), ndo)
                    self.log_info(msg)
                self.set_state(DevState.RUNNING, 'IO addition completed')
            except KeyboardInterrupt:
                raise
            except:
                self.log_exception('Error adding IO channels')
                self.set_state(DevState.FAULT, msg)
            self.init_io = False
            self.init_po = True
            # self.restore_polling()
            return nai + nao + ndi + ndo

    def remove_io(self):
        with self.lock:
            try:
                for attr_name in self.dynamic_attributes:
                    self.remove_attribute(attr_name)
                    self.log_debug(' Attribute %s removed' % attr_name)
                self.dynamic_attributes = {}
                self.set_state(DevState.CLOSE, 'All IO channels removed')
                self.init_io = True
            except KeyboardInterrupt:
                raise
            except:
                self.log_exception(self.logger, 'Error deleting IO channels')
                # self.set_state(DevState.FAULT)

    # def save_polling_state(self, target_property='_polled_attr'):
    #     try:
    #         if self.adam.name == '0000':
    #             self.log_info(f'Polling not saved for unknown device {self.get_name()}')
    #             return False
    #         super().save_polling_state(target_property)
    #     except KeyboardInterrupt:
    #         raise
    #     except:
    #         self.log_exception('')


# def looping():
#     # print('loop entry')
#     post_init_callback()
#     time.sleep(1.0)
#     # print('loop exit')


def post_init_callback():
    # called once at server initiation
    for dev in AdamServer.devices:
        v = AdamServer.devices[dev]
        if v.init_io:
            v.add_io()
    for dev in AdamServer.devices:
        v = AdamServer.devices[dev]
        if v.init_po:
            v.restore_polling()
            v.init_po = False


if __name__ == "__main__":
    db = tango.Database()
    sn = os.path.basename(sys.argv[0]).replace('.py', '')
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
