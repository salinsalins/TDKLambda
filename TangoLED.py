# coding: utf-8
'''
Created on Jan 1, 2020

@author: sanin
'''
import sys
from PyQt5.QtWidgets import QPushButton
import tango
from TangoWidget import TangoWidget


class TangoLED(TangoWidget):
    def __init__(self, attribute, widget: QPushButton):
        super().__init__(attribute, widget)

    def update(self):
        try:
            attr = self.read()
            if attr.type == tango._tango.CmdArgType.DevBoolean and attr.data_format == tango._tango.AttrDataFormat.SCALAR:
                if attr.quality == tango._tango.AttrQuality.ATTR_VALID:
                    self.widget.setDisabled(False)
                    self.widget.setChecked(attr.value)
                else:
                    self.logger.debug('Attribute INVALID')
                    self.widget.setDisabled(True)
            else:
                self.logger.debug('Not scalar boolean attribute')
                self.widget.setDisabled(True)
        except:
            self.logger.debug('Exception updating widget', sys.exc_info()[0])
            # print_exception_info()
            self.widget.setDisabled(True)
