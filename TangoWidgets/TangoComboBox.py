# coding: utf-8
'''
Created on Jan 3, 2020

@author: sanin
'''
import sys
import time
from PyQt5.QtWidgets import QComboBox
from TangoWidgets.TangoWidget import TangoWidget


class TangoComboBox(TangoWidget):
    def __init__(self, name, widget: QComboBox):
        super().__init__(name, widget)
        #self.items = self.widget.view()
        #self.widget.currentIndexChanged.connect(self.callback)
        self.widget.activated.connect(self.callback)

    def set_value(self):
        self.value = None
        try:
            self.value = int(self.attr.value)
            self.widget.setCurrentIndex(self.value)
        except:
            pass
        return self.value

    def decorate_error(self):
        self.widget.setStyleSheet('color: gray')

    def callback(self, value):
        if self.connected:
            try:
                self.attr_proxy.write(int(value))
                self.decorate_valid()
            except:
                self.logger.debug('Exception %s in callback', sys.exc_info()[0])
                self.decorate_error()
        else:
            if time.time() - self.time > TangoWidget.RECONNECT_TIMEOUT:
                self.create_attribute_proxy(self.attr_proxy)
            else:
                self.decorate_error()
