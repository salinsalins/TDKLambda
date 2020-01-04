# coding: utf-8
'''
Created on Jan 3, 2020

@author: sanin
'''
import sys
from PyQt5.QtWidgets import QAbstractSpinBox
import tango
from TangoWidget import TangoWidget


class TangoAbstractSpinBox(TangoWidget):
    def __init__(self, attribute, widget: QAbstractSpinBox):
        super().__init__(attribute, widget)
        self.widget.setKeyboardTracking(False)
        self.widget.valueChanged.connect(self.callback)

    def set_value(self):
        self.value = self.attr.value
        self.widget.setValue(self.value)
        return self.value

    def callback(self, value):
        #print('callback', self, value)
        try:
            self.attr_proxy.write(value)
        except:
            self.logger.debug('Exception in callback', sys.exc_info()[0])
            self.decorate_error()
            #print_exception_info()
