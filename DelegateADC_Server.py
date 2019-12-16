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
        if self.atts[name]['last_shot'] == self.read_shot():
            val = self.atts[name]['last_data']
        else:
            val = self.read_attribute_value(name)
        attr.set_value(val)
        attr.set_quality(tango.AttrQuality.ATTR_VALID)

    # read shot number
    def read_shot(self):
        shattr = self.device.read_attribute('Shot_id')
        return shattr.value

    # read attribute value
    def read_attribute_value(self, name):
        at = self.device.read_attribute(name)

        return at.value

    def init_atts(self):
        self.info_stream(self, 'init_atts')
        self.atts = {}
        if self.device is None:
            self.info_stream(self, 'Inintialized device')
            return
        shot = self.read_shot()
        # copy attributes from original device
        attributes = self.device.get_attribute_list()
        for atbt in attributes:
            # save last attribute value and shot number
            atp = {}
            atp['last_shot'] = shot
            # read attribute
            old_attr = self.device.read_attribute(atbt)
            val = old_attr.value
            db = tango.Database()
            # read attribute properties
            props = db.get_device_attribute_property(self.adc, atbt)
            # average attribute value
            avgc = 0
            if atbt.startswith("chanx"):
                atbt_y = atbt.replace('x', 'y')
                props_y = db.get_device_attribute_property(self.adc, atbt_y)
                if 'save_avg' in props_y[atbt_y]:
                    try:
                        avgc = int(props[atbt]['save_avg'][0])
                    except:
                        pass
            if 'save_avg' in props[atbt]:
                try:
                    avgc = int(props[atbt]['save_avg'][0])
                except:
                    self.error_stream(self, 'save_avg invalid for %s' % atbt)
            if avgc > 0:
                m = len(val)
                m1 = int(m/avgc)
                value = numpy.zeros(m1)
                for n in numpy.arange(m1):
                    value[n] = numpy.average(val[n*avgc:(n+1)*avgc])
                props[atbt]['save_avg'] = ['1']
            else:
                value = val
            atp['lasd_data'] = value
            self.atts[atbt] = atp
            # create new attribute
            # read AttributeInfoEx
            old_aie = self.device.get_attribute_config_ex(atbt)
            old_aie.max_dim_x = len(value)
            new_attr = tango.Attr(atbt, tango.DevDouble, tango.AttrWriteType.READ)
            new_attr
            # copy attribute properties
            # TO-DO
            # add new attribute
            self.add_attribute(new_attr, self.read_general)
            print('attribute %s added' % atbt)
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
            msg = 'Connected to Adlink ADC %s' % self.adc
        except:
            self.device = None
            msg = 'Adlink ADC %s connection errror' % self.adc
        DelegateADC_Server.devices.append(self)
        print(msg)
        self.info_stream(msg)
        # set proper device state
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
        dev.init_atts()
        print(' ')

if __name__ == "__main__":
    #if len(sys.argv) < 3:
        #print("Usage: python ET7000_server.py device_name ip_address")
        #exit(-1)
    DelegateADC_Server.run_server(post_init_callback=post_init_callback)
