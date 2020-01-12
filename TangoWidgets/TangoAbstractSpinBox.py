# coding: utf-8
'''
Created on Jan 3, 2020

@author: sanin
'''
import sys
import time
from PyQt5.QtWidgets import QAbstractSpinBox
from TangoWidgets.TangoWidget import TangoWidget


class TangoAbstractSpinBox(TangoWidget):
    def __init__(self, attribute, widget: QAbstractSpinBox, readonly=False):
        super().__init__(attribute, widget, readonly)
        self.widget.setKeyboardTracking(False)
        if not readonly:
            self.widget.valueChanged.connect(self.callback)

    def decorate_error(self):
        self.widget.setStyleSheet('color: gray')

    def decorate_invalid(self):
        self.widget.setStyleSheet('color: red')

    def decorate_valid(self):
        self.widget.setStyleSheet('color: black')

    def set_value(self):
        self.value = self.attr.value
        bs = self.widget.blockSignals(True)
        self.widget.setValue(self.value)
        self.widget.blockSignals(bs)
        return self.value
