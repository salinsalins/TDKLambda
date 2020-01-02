# coding: utf-8
'''
Created on Jan 1, 2020

@author: sanin
'''

import sys
import logging

from PyQt5.QtWidgets import QWidget
import tango

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
f_str = '%(asctime)s,%(msecs)d %(funcName)s(%(lineno)s) ' + \
        '%(levelname)-7s %(message)s'
log_formatter = logging.Formatter(f_str, datefmt='%H:%M:%S')
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)

class TangoWidget():
    def __init__(self, attribute, widget: QWidget):
        self.logger = logger
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
        self.widget = widget
        self.attr = None

    def read(self):
        self.attr = None
        try:
            self.attr = self.attr_proxy.read()
        except:
            self.logger.debug('Exception reading', sys.exc_info()[0])
        return self.attr

    def update(self):
        self.logger.error('Unsupported widget')
        return
