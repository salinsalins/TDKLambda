# coding: utf-8
'''
Created on Jan 3, 2020

@author: sanin
'''
import sys
from PyQt5.QtWidgets import QLabel
import tango
from TangoWidget import TangoWidget


class TangoLabel(TangoWidget):
    def __init__(self, attribute, widget: QLabel):
        self.value = None
        super().__init__(attribute, widget)
        self.update()

    def update(self) -> None:
        try:
            #attr = self.read()
            attr = self.attr_proxy.read()
            if attr.data_format != tango._tango.AttrDataFormat.SCALAR:
                self.logger.error('Non scalar attribute')
                self.decorate_error()
                return
            ac = self.attr_proxy.get_config()
            self.value = ac.format % attr.value
            if attr.quality == tango._tango.AttrQuality.ATTR_VALID:
                self.widget.setText(self.value)
                self.decorate_valid()
            else:
                self.widget.setText(self.value)
                self.decorate_invalid()
        except:
            self.logger.debug('Exception updating widget', sys.exc_info()[0])
            self.decorate_error()
