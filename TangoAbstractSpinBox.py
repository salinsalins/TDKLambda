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
        self.value = None
        super().__init__(attribute, widget)
        self.config = self.attr_proxy.get_config()
        self.widget.setKeyboardTracking(False)
        self.update()
        self.widget.valueChanged.connect(self.callback)

    def update(self) -> None:
        try:
            #attr = self.read()
            attr = self.attr_proxy.read()
            if attr.data_format != tango._tango.AttrDataFormat.SCALAR:
                self.logger.error('Non sclar attribute')
                self.decorate_error()
                return
            #ac = self.attr_proxy.get_config()
            #self.value = ac.format % attr.value
            if attr.quality == tango._tango.AttrQuality.ATTR_VALID:
                self.widget.setValue(self.value)
                self.decorate_valid()
            else:
                self.widget.setValue(self.value)
                self.decorate_invalid()
        except:
            self.logger.debug('Exception updating widget', sys.exc_info()[0])
            ##self.widget.setValue(self.value)
            self.decorate_error()

    def callback(self, value=None):
        #print('callback', self, value)
        try:
            self.attr_proxy.write(value)
        except:
            self.logger.debug('Exception in callback', sys.exc_info()[0])
            self.decorate_error()
            #print_exception_info()
