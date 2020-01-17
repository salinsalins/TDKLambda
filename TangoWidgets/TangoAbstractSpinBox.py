# coding: utf-8
'''
Created on Jan 3, 2020

@author: sanin
'''
from PyQt5 import QtCore
from PyQt5.QtWidgets import QAbstractSpinBox
from TangoWidgets.TangoWriteWidget import TangoWriteWidget


class TangoAbstractSpinBox(TangoWriteWidget):
    def __init__(self, name, widget: QAbstractSpinBox, readonly=False):
        super().__init__(name, widget, readonly)
        self.widget.setKeyboardTracking(False)
        #self.widget.keyPressEvent = self.keyPressEvent
        if not readonly:
            self.widget.valueChanged.connect(self.callback)

    def keyPressEvent(self, e):
        k = e.key()
        #print(k)
        #if k == QtCore.Qt.Key_Escape:
        #    print('esc')
        if k == QtCore.Qt.Key_Enter or k == QtCore.Qt.Key_Return:
            self.callback(self.widget.value())
            #print('enter')
