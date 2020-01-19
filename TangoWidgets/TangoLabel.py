# coding: utf-8
'''
Created on Jan 3, 2020

@author: sanin
'''
from PyQt5.QtWidgets import QLabel
from TangoWidgets.TangoWidget import TangoWidget


class TangoLabel(TangoWidget):
    def __init__(self, name, widget: QLabel, property=None, refresh=False):
        self.property = property
        self.refresh = refresh
        super().__init__(name, widget, readonly=True)

    def update(self, decorate_only=False) -> None:
        if self.property is None:
            super().update(decorate_only)
            return
        else:
            self.value = self.attr_proxy.get_property(property)[property][0]

