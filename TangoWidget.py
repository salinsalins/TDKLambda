# coding: utf-8
'''
Created on Jan 1, 2020

@author: sanin
'''

import sys
import logging

from PyQt5.QtWidgets import QWidget
import tango


class TangoWidget():
    def __init__(self, attribute, widget: QWidget):
        self.widget = widget
        self.attr = None
        # Configure logging
        self.logger = logging.getLogger(__name__)
        self.logger.propagate = False
        self.logger.setLevel(logging.DEBUG)
        f_str = '%(asctime)s,%(msecs)d %(funcName)s(%(lineno)s) ' + \
                '%(levelname)-7s %(message)s'
        log_formatter = logging.Formatter(f_str, datefmt='%H:%M:%S')
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_formatter)
        self.logger.addHandler(console_handler)
        # create attribute proxy
        if isinstance(attribute, tango.AttributeProxy):
            self.attr_proxy = attribute
        elif isinstance(attribute, str):
            try:
                self.attr_proxy = tango.AttributeProxy(attribute)
            except:
                self.attr_proxy = None
        else:
            self.logger.warning('tango.AttributeProxy or name<str> required')
            self.attr_proxy = None

    def decorate_error(self):
        if hasattr(self.widget, 'setText'):
            self.widget.setText('****')
        self.widget.setStyleSheet('color: gray')

    def decorate_invalid(self):
        self.set_value()
        self.widget.setStyleSheet('color: red')

    def decorate_valid(self):
        self.set_value()
        self.widget.setStyleSheet('color: black')

    def read(self):
        self.attr = None
        self.attr = self.attr_proxy.read()
        return self.attr

    def set_value(self, value=None):
        if value is None:
            value = self.attr.value
        if hasattr(self.widget, 'setText'):
            self.widget.setText(str(value))
        elif hasattr(self.widget, 'setValue'):
            self.widget.setValue(value)
        else:
            pass
        return value

    def update(self) -> None:
        try:
            attr = self.read()
            if attr.data_format != tango._tango.AttrDataFormat.SCALAR:
                self.logger.debug('Non sclar attribute')
                self.decorate_error()
                return
            if attr.quality == tango._tango.AttrQuality.ATTR_VALID:
                self.decorate_valid()
            else:
                self.decorate_invalid()
        except:
            self.logger.debug('Exception updating widget', sys.exc_info()[0])
            self.decorate_error()

    def callback(self, value=None):
        self.logger.debug('Callback of unsupported widget')
        return
