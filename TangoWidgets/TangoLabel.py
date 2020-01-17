# coding: utf-8
'''
Created on Jan 3, 2020

@author: sanin
'''
from PyQt5.QtWidgets import QLabel
from TangoWidgets.TangoWidget import TangoWidget


class TangoLabel(TangoWidget):
    def __init__(self, name, widget: QLabel):
        super().__init__(name, widget, True)
