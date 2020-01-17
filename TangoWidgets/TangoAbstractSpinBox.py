# coding: utf-8
'''
Created on Jan 3, 2020

@author: sanin
'''
from PyQt5 import QtCore
from PyQt5.QtWidgets import QAbstractSpinBox
from TangoWidgets.TangoWidget import TangoWidget


class TangoAbstractSpinBox(TangoWidget):
    def __init__(self, name, widget: QAbstractSpinBox, readonly=False):
        super().__init__(name, widget, readonly)
        self.widget.setKeyboardTracking(False)
        #self.widget.keyPressEvent = self.keyPressEvent
        if not readonly:
            self.widget.valueChanged.connect(self.callback)

    def decorate_error(self):
        self.widget.setStyleSheet('color: gray')
        self.widget.setEnabled(False)

    def decorate_invalid(self, text: str = None):
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
        self.value = self.attr.value
        bs = self.widget.blockSignals(True)
        self.widget.setValue(self.value)
        self.widget.blockSignals(bs)
        return self.value

    def keyPressEvent(self, e):
        k = e.key()
        #print(k)
        #if k == QtCore.Qt.Key_Escape:
        #    print('esc')
        if k == QtCore.Qt.Key_Enter or k == QtCore.Qt.Key_Return:
            self.callback(self.widget.value())
            #print('enter')
