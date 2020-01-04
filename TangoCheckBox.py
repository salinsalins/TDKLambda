# coding: utf-8
'''
Created on Jan 3, 2020

@author: sanin
'''
import sys
from PyQt5.QtWidgets import QCheckBox
import tango
from TangoWidget import TangoWidget


class TangoCheckBox(TangoWidget):
    def __init__(self, attribute, widget: QCheckBox):
        super().__init__(attribute, widget)
        self.widget.valueChanged.connect(self.callback)

    def callback(self, value):
        #print('callback', self, value)
        try:
            self.attr_proxy.write(bool(value))
        except:
            self.logger.debug('Exception in callback', sys.exc_info()[0])
            self.decorate_error()
            #print_exception_info()
