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
    ERROR_TEXT = '****'

    def __init__(self, attribute, widget: QWidget):
        # defaults
        self.attr_proxy = None
        self.widget = widget
        self.attr = None
        self.attr_config = None
        self.value = None
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
            self.attr_proxy = tango.AttributeProxy(attribute)
        else:
            self.logger.warning('<tango.AttributeProxy> or <str> required')
        self.update()

    def decorate_error(self):
        if hasattr(self.widget, 'setText'):
            self.widget.setText(TangoWidget.ERROR_TEXT)
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

    def set_value(self):
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
        return self.value

    def update(self) -> None:
        try:
            attr = self.read()
            if attr.data_format != tango._tango.AttrDataFormat.SCALAR:
                self.logger.debug('Non sclar attribute')
                self.decorate_error()
            else:
                if attr.quality == tango._tango.AttrQuality.ATTR_VALID:
                    self.decorate_valid()
                else:
                    self.decorate_invalid()
        except:
            self.logger.debug('Exception updating widget', sys.exc_info()[0])
            self.decorate_error()

    def callback(self, value):
        self.logger.debug('Callback of unsupported widget')
        return
