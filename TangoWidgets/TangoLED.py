# coding: utf-8
'''
Created on Jan 1, 2020

@author: sanin
'''
from PyQt5.QtWidgets import QPushButton
from TangoWidgets.TangoWidget import TangoWidget


class TangoLED(TangoWidget):
    def __init__(self, name, widget: QPushButton):
        self.value = False
        super().__init__(name, widget)

    def set_widget_value(self):
        self.value = bool(self.attr.value)
        self.widget.setChecked(self.value)
        return self.value

    def decorate_error(self):
        self.widget.setDisabled(True)

    def decorate_invalid(self):
        self.widget.setDisabled(True)

    def decorate_valid(self):
        self.widget.setDisabled(False)
