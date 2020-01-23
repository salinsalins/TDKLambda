# coding: utf-8
"""
Created on Jan 3, 2020

@author: sanin
"""

from PyQt5.QtWidgets import QPushButton
from TangoWidgets.TangoWriteWidget import TangoWriteWidget


class TangoPushButton(TangoWriteWidget):
    def __init__(self, name, widget: QPushButton, readonly=False):
        super().__init__(name, widget, readonly)
        self.widget.clicked.connect(self.clicked)
        self.widget.pressed.connect(self.pressed)
        self.widget.released.connect(self.released)

    def set_widget_value(self):
        self.widget.setChecked(bool(self.attr.value))
        return self.attr.value

    def write(self, value):
        if self.readonly:
            return
        self.attr_proxy.write(int(value))

    def released(self):
        if self.widget.isCheckable():
            return
        super().callback(0)

    def pressed(self):
        if self.widget.isCheckable():
            return
        super().callback(1)

    def clicked(self):
        if not self.widget.isCheckable():
            return
        super().callback(self.widget.isChecked())

    # compare widget displayed value and read attribute value
    def compare(self):
        if self.readonly:
            return True
        else:
            if self.widget.isCheckable():
                return self.attr.value == self.widget.isChecked()
            else:
                return True
