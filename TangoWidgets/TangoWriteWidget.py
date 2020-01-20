# coding: utf-8
'''
Created on Jan 17, 2020

@author: sanin
'''
from PyQt5.QtWidgets import QWidget
from TangoWidgets.TangoWidget import TangoWidget


class TangoWriteWidget(TangoWidget):
    def __init__(self, name, widget: QWidget, readonly=False):
        super().__init__(name, widget, readonly)

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
                #if (self.attr.value * self.coeff) == self.widget.value():
                if abs(((self.attr.value * self.coeff) - self.widget.value())) <= (1e-5 * self.widget.value()):
                        return True
                else:
                    #print(self.attr.value, self.widget.value())
                    return False
            except:
                return False
