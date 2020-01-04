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

    def decorate_error(self):
        self.widget.setDisabled(True)

    def decorate_invalid(self):
        self.widget.setDisabled(True)

    def decorate_valid(self):
        self.widget.setDisabled(False)
        self.widget.setChecked(self.attr.value)
