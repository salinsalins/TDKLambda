# coding: utf-8
'''
Created on Jan 3, 2020

@author: sanin
'''
import sys
from PyQt5.QtWidgets import QLabel
import tango
from TangoWidget import TangoWidget


class TangoLabel(TangoWidget):
    def __init__(self, attribute, widget: QLabel):
        super().__init__(attribute, widget)
