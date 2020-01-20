# coding: utf-8
'''
Created on Jan 3, 2020

@author: sanin
'''
import math

from PyQt5 import QtCore
from PyQt5.QtWidgets import QAbstractSpinBox
from TangoWidgets.TangoWriteWidget import TangoWriteWidget


class TangoAbstractSpinBox(TangoWriteWidget):
    def __init__(self, name, widget: QAbstractSpinBox, readonly=False):
        super().__init__(name, widget, readonly)
        self.widget.setKeyboardTracking(False)
        self.widget.last_keyPressEvent = self.widget.keyPressEvent
        self.widget.keyPressEvent = self.keyPressEvent
        if not readonly:
            self.widget.valueChanged.connect(self.callback)

    def set_widget_value(self):
        if math.isnan(self.attr.value):
            self.widget.setValue(0.0)
        else:
            super().set_widget_value()

    def keyPressEvent(self, e):
        self.widget.last_keyPressEvent(e)
        k = e.key()
        if k == QtCore.Qt.Key_Enter or k == QtCore.Qt.Key_Return:
            self.callback(self.widget.value())
