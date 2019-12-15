#!/usr/bin/env python
# -*- coding: utf-8 -*-

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'DelegateADC_Server'
APPLICATION_VERSION = '0_0'
#CONFIG_FILE = APPLICATION_NAME + '.json'
#UI_FILE = APPLICATION_NAME + '.ui'

"""Adlink ADC Delegate tango device server"""

import sys
import time
import numpy
import traceback

import tango
from tango import AttrQuality, AttrWriteType, DispLevel, DevState, DebugIt
from tango.server import Device, attribute, command, pipe, device_property


class DelegateADC_Server(Device):
    devices = []

    device_name = attribute(label="type", dtype=str,
                        display_level=DispLevel.OPERATOR,
                        access=AttrWriteType.READ,
                        unit="", format="%s",
                        doc="Initial Adlink ADC tango device server")

    def read_device_name(self):
        return self.adc

    def read_general(self, attr: tango.Attribute):
        #print("Reading attribute %s %s" % (self.ip, attr.get_name()))
        #self.info_stream("Reading attribute %s", attr.get_name())
        name = attr.get_name()
        chan = int(name[-2:])
        ad = name[:2]
        if ad == 'ai':
            val = self.et.read_AI_channel(chan)
        elif ad == 'di':
            val = self.et.read_DI_channel(chan)
        elif ad == 'do':
            val = self.et.read_DO_channel(chan)
        elif ad == 'ao':
            val = self.et.read_AO_channel(chan)
        else:
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)
            self.error_stream("Read for unknown attribute %s", name)
            return
        if val is not None:
            self.time = None
            self.error_count = 0
            attr.set_value(val)
            attr.set_quality(tango.AttrQuality.ATTR_VALID)
        else:
            self.error_count += 1
            self.error_stream("Error reading %s", name)
            if ad == 'ai':
                attr.set_value(float('nan'))
            elif ad == 'ao':
                attr.set_value(float('nan'))
            elif ad == 'di':
                attr.set_value(False)
            elif ad == 'do':
                attr.set_value(False)
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)
            if self.time is None:
                self.time = time.time()
            else:
                if time.time() - self.time > self.reconnect_timeout/1000.0:
                    self.error_stream("Reconnect timeout exceeded for %s", name)
                    self.Reconnect()
                    self.time = None

    def write_general(self, attr: tango.WAttribute):
        #print("Writing attribute %s %s" % (self.ip, attr.get_name()))
        #self.info_stream("Writing attribute %s", attr.get_name())
        if self.et is None:
            return
        #attr.set_quality(tango.AttrQuality.ATTR_CHANGING)
        #lst = []
        value = attr.get_write_value()
        #print(value, lst)
        name = attr.get_name()
        chan = int(name[-2:])
        ad = name[:2]
        if ad  == 'ao':
            #print(chan, value)
            result = self.et.write_AO_channel(chan, value)
        elif ad == 'do':
            result = self.et.write_DO_channel(chan, value)
        else:
            print("Write to unknown attribute %s" % name)
            self.error_stream("Write to unknown attribute %s", name)
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)
            return
        if result:
            self.time = None
            self.error_count = 0
            attr.set_quality(tango.AttrQuality.ATTR_VALID)
        else:
            self.error_count += 1
            self.error_stream("Error writing %s", name)
            attr.set_quality(tango.AttrQuality.ATTR_INVALID)
            if self.time is None:
                self.time = time.time()
            else:
                if time.time() - self.time > self.reconnect_timeout/1000.0:
                    self.error_stream("Reconnect timeout exceeded for %s", name)
                    self.Reconnect()
                    self.time = None

    @command
    def Reconnect(self):
        self.info_stream(self, 'Reconnect')
        if self.et is None:
            self.init_device()
            if self.et is None:
                return
        self.remove_io()
        self.add_io()
        # if device type is recognized
        if self.et._name != 0:
            # set state to running
            self.set_state(DevState.RUNNING)
        else:
            # unknown device type
            self.set_state(DevState.FAULT)

    def init_attr(self):
        #self.info_stream(self, 'init_attr')
        # copy attributes
        attributes = self.device.get_attribute_list()
        for atn in attributes:
            #AttributeInfoEx
            aie = self.device.get_attribute_config_ex(atn)
            attr = tango.AttrData(attr_info=aie)
            self.add_attribute(attr, self.read_general)
            print('attribute %s added' % atn)
            # copy attribute properties
            # TO-DO
        self.set_state(DevState.RUNNING)

    def get_device_property(self, prop: str, default=None):
        name = self.get_name()
        # device proxy
        dp = tango.DeviceProxy(name)
        # read property
        pr = dp.get_property(prop)[prop]
        result = None
        if len(pr) > 0:
            result = pr[0]
        if default is None:
            return result
        try:
            if result is None or result == '':
                result = default
            else:
                result = type(default)(result)
        except:
            return result

    def init_device(self):
        self.set_state(DevState.INIT)
        Device.init_device(self)
        # get adc from property
        self.adc = self.get_device_property('adc', 'binp/nbi/adc')
        # create ADC device
        try:
            self.device = tango.DeviceProxy(self.adc)
        except:
            self.device = None
        DelegateADC_Server.devices.append(self)
        msg = 'Connected to Adlink ADC %s' % self.adc
        print(msg)
        self.info_stream(msg)
        # if device type is recognized
        if self.device is not None:
            # set state to running
            self.set_state(DevState.RUNNING)
        else:
            # unknown device type
            self.set_state(DevState.FAULT)

def post_init_callback():
    for dev in DelegateADC_Server.devices:
        #print(dev)
        #if hasattr(dev, 'init_attr'):
        dev.init_attr()
        print(' ')

if __name__ == "__main__":
    #if len(sys.argv) < 3:
        #print("Usage: python ET7000_server.py device_name ip_address")
        #exit(-1)
    DelegateADC_Server.run_server(post_init_callback=post_init_callback)
