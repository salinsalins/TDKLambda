# coding: utf-8
'''
Created on Jan 17, 2020

@author: sanin
'''
from PyQt5 import QtCore
from PyQt5.QtWidgets import QAbstractSpinBox
from TangoWidgets.TangoWidget import TangoWidget


class TangoWriteWidget(TangoWidget):
    def __init__(self, name, widget: QAbstractSpinBox, readonly=False):
        super().__init__(name, widget, readonly)

    def decorate_error(self):
        self.widget.setStyleSheet('color: gray')
        self.widget.setEnabled(False)

    def decorate_invalid(self):
        self.widget.setStyleSheet('color: red')
        self.widget.setEnabled(True)

    def decorate_valid(self):
        self.widget.setStyleSheet('color: black')
        self.widget.setEnabled(True)

    # compare widget displayed value and read attribute value
    def compare(self):
        if self.readonly:
            return True
        else:
            try:
                if self.attr.value == self.widget.value():
                    return True
                else:
                    return False
            except:
                return False

    def set_widget_value(self):
        bs = self.widget.blockSignals(True)
        self.widget.setValue(self.attr.value)
        self.widget.blockSignals(bs)
        return self.attr.value

    def keyPressEvent(self, e):
        print(e.key())
        if e.key() == QtCore.Qt.Key_Escape:
            self.callback(self.widget.value())