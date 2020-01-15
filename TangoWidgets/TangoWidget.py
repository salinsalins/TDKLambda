# coding: utf-8
'''
Created on Jan 1, 2020

@author: sanin
'''

import sys
import time
import logging

from PyQt5.QtWidgets import QWidget
import tango


class TangoWidget:
    ERROR_TEXT = '****'
    RECONNECT_TIMEOUT = 3.0    # seconds

    def __init__(self, name: str, widget: QWidget, readonly=False):
        # defaults
        self.time = time.time()
        self.name = name
        self.widget = widget
        self.readonly = readonly
        self.connected = False
        self.attr_proxy = None
        self.attr = None
        self.attr_config = None
        self.value = None
        self.requested = False
        self.ready = False
        self.update_dt = 0.0
        self.ex_count = 0
        # Configure logging
        self.logger = logging.getLogger(__name__)
        if not self.logger.hasHandlers():
            self.logger.propagate = False
            self.logger.setLevel(logging.DEBUG)
            f_str = '%(asctime)s,%(msecs)d %(funcName)s(%(lineno)s) ' + \
                    '%(levelname)-7s %(message)s'
            log_formatter = logging.Formatter(f_str, datefmt='%H:%M:%S')
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(log_formatter)
            self.logger.addHandler(console_handler)
        # create attribute proxy
        self.create_attribute_proxy(name)
        self.update()

    def disconnect_attribute_proxy(self):
        self.ex_count += 1
        if self.ex_count > 3:
            self.time = time.time()
            self.connected = False
            self.attr_proxy = None
            self.ex_count = 0
            self.logger.debug('Attribute %s disconnected', self.name)

    def create_attribute_proxy(self, name: str = None):
        if name is None:
            name = self.name
        self.time = time.time()
        try:
            if isinstance(self.attr_proxy, tango.AttributeProxy):
                self.attr_proxy.ping()
                self.connected = True
                self.logger.debug('Reconnected to Attribute %s', name)
            elif isinstance(name, str):
                self.attr_proxy = tango.AttributeProxy(name)
                self.connected = True
                self.logger.debug('Connected to Attribute %s', name)
            else:
                self.logger.warning('<str> required for attribute name')
                self.name = str(name)
                self.attr_proxy = None
                self.connected = False
        except:
            self.logger.error('Can not create attribute %s', name)
            self.name = str(name)
            self.attr_proxy = None
            self.connected = False

    def decorate_error(self):
        if hasattr(self.widget, 'setText'):
            self.widget.setText(TangoWidget.ERROR_TEXT)
        self.widget.setStyleSheet('color: gray')

    def decorate_invalid(self):
        self.widget.setStyleSheet('color: red')

    def decorate_valid(self):
        self.widget.setStyleSheet('color: black')

    def read(self):
        self.attr = None
        try:
            if self.attr_proxy.is_polled():
                try:
                    self.attr = self.attr_proxy.history(1)[0]
                except Exception as ex:
                    self.disconnect_attribute_proxy()
                    raise ex
            else:
                self.attr = self.attr_proxy.read()
        except Exception as ex:
            self.disconnect_attribute_proxy()
            raise ex
        self.ex_count = 0
        return self.attr

    def set_value(self):
        if hasattr(self.attr, 'value'):
            try:
                self.attr_config = self.attr_proxy.get_config()
                self.value = self.attr_config.format % self.attr.value
            except:
                self.value = str(self.attr.value)
            if hasattr(self.widget, 'setText'):
                self.widget.setText(self.value)
            elif hasattr(self.widget, 'setValue'):
                self.widget.setValue(self.value)
            else:
                pass
        else:
            self.value = None
        return self.value

    def update(self, decorate_only=False) -> None:
        #if self.update_dt > 0.05:
        t0 = time.time()
        try:
            attr = self.read()
            if attr.data_format != tango._tango.AttrDataFormat.SCALAR:
                self.logger.debug('Non scalar attribute')
                self.decorate_error()
            else:
                if attr.quality == tango._tango.AttrQuality.ATTR_VALID:
                    if not decorate_only:
                        self.set_value()
                    self.decorate_valid()
                else:
                    if not decorate_only:
                        self.set_value()
                    self.decorate_invalid()
        except:
            if self.connected:
                self.logger.debug('Exception %s updating widget', sys.exc_info()[0])
                self.disconnect_attribute_proxy()
            else:
                if (time.time() - self.time) > self.RECONNECT_TIMEOUT:
                    self.create_attribute_proxy()
            self.decorate_error()
        self.update_dt = time.time() - t0
        #print('update', self.attr_proxy, int(self.update_dt*1000.0), 'ms')

    def callback(self, value):
        if self.connected:
            try:
                self.attr_proxy.write(value)
                self.decorate_valid()
            except:
                self.logger.debug('Exception %s in callback', sys.exc_info()[0])
                self.decorate_error()
        else:
            if time.time() - self.time > TangoWidget.RECONNECT_TIMEOUT:
                self.create_attribute_proxy(self.attr_proxy)
                self.decorate_error()
            else:
                self.decorate_error()
