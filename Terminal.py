# coding: utf-8

import os.path
import sys
import time

import serial
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5 import uic
from PyQt5.QtCore import QTimer, QSize, QPoint
import PyQt5.QtGui as QtGui

from TangoUtils import restore_settings, save_settings

sys.path.append('../TangoUtils')
from config_logger import config_logger
from log_exception import log_exception

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'Terminal'
APPLICATION_NAME_SHORT = APPLICATION_NAME
APPLICATION_VERSION = '0.1'
CONFIG_FILE = APPLICATION_NAME_SHORT + '.json'
UI_FILE = APPLICATION_NAME_SHORT + '.ui'

# Globals
TIMER_PERIOD = 300  # ms


class MainWindow(QMainWindow):
    def __init__(self):
        # Initialization of the superclass
        super().__init__()
        # logging config
        self.logger = config_logger()
        # members definition
        self.port = None
        self.baud = 9600
        self.send = ''
        # Load the Qt UI
        uic.loadUi(UI_FILE, self)
        # Default main window parameters
        self.resize(QSize(480, 640))                 # size
        self.move(QPoint(50, 50))                    # position
        self.setWindowTitle(APPLICATION_NAME)        # title
        # Welcome message
        print(APPLICATION_NAME + ' version ' + APPLICATION_VERSION + ' started')
        #
        restore_settings(self, file_name=CONFIG_FILE, widgets=(self.lineEdit, self.lineEdit_2, self.lineEdit_3, self.lineEdit_5))
        v = self.lineEdit_3.text()
        ve = v.encode()
        h = ''
        for i in ve:
            h += hex(i)[2:] + ' '
        self.lineEdit_4.setText(h)
        #
        self.port = str(self.lineEdit.text())
        self.baud = int(self.lineEdit_2.text())
        self.com = serial.Serial(self.port, baudrate=self.baud, timeout=0)
        # Connect signals with slots
        self.lineEdit_3.editingFinished.connect(self.send_changed)
        self.lineEdit_4.editingFinished.connect(self.hex_changed)
        # Defile callback task and start timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.timer_handler)
        self.timer.start(TIMER_PERIOD)
        self.logger.info('\n---------- Config Finished -----------\n')

    def hex_from_str(self, v):
        h = ''
        for i in v:
            h += hex(i)[2:] + ' '
        return h

    def str_from_hex(self, v):
        vs = v.split(' ')
        h = ''
        for i in vs:
            v = i.strip()
            if v != '':
                h += chr(int(v, 16))
        return h

    def send_changed(self):
        v = self.lineEdit_3.text()
        ve = v.encode()
        h = ''
        for i in ve:
            h += hex(i)[2:] + ' '
        self.lineEdit_4.setText(h)
        stat = self.com.write(ve)
        self.logger.debug('%s of %s bytes written', stat, len(ve))

    def hex_changed(self):
        v = self.lineEdit_4.text()
        vs = v.split(' ')
        h = ''
        for i in vs:
            v = i.strip()
            if v != '':
                h += chr(int(v, 16))
        self.logger.debug('%s', h)
        self.lineEdit_3.setText(h)
        stat = self.com.write(h.encode())
        self.logger.debug('%s of %s bytes written', stat, len(h))


    def on_quit(self) :
        # Save global settings
        save_settings(self, file_name=CONFIG_FILE, widgets=(self.lineEdit, self.lineEdit_2, self.lineEdit_3, self.lineEdit_5))

    def timer_handler(self):
        result = b''
        r = self.com.read(1)
        while len(r) > 0:
            result += r
            r = self.com.read(1)
        if len(result) > 0:
            self.logger.debug('%s', result)
            self.plainTextEdit.setPlainText(str(result))
            h = ''
            for i in result:
                h += hex(i) + ' '
            self.plainTextEdit_2.setPlainText(h)


if __name__ == '__main__':
    # Create the GUI application
    app = QApplication(sys.argv)
    # Instantiate the main window
    dmw = MainWindow()
    app.aboutToQuit.connect(dmw.on_quit)
    # Show it
    dmw.show()
    # Start the Qt main loop execution, exiting from this script
    # with the same return code of Qt application
    sys.exit(app.exec_())
