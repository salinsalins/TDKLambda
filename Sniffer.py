# coding: utf-8
from datetime import datetime
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
APPLICATION_NAME = 'Sniffer'
APPLICATION_NAME_SHORT = APPLICATION_NAME
APPLICATION_VERSION = '0.1'
CONFIG_FILE = APPLICATION_NAME_SHORT + '.json'
UI_FILE = APPLICATION_NAME_SHORT + '.ui'

# Globals
TIMER_PERIOD = 50  # ms


class MainWindow(QMainWindow):
    def __init__(self):
        # Initialization of the superclass
        super().__init__()
        # logging config
        self.logger = config_logger()
        # members definition
        self.com1 = None
        self.cts1 = None
        self.rts1 = None
        self.com2 = None
        self.cts2 = None
        self.rts2 = None
        self.connected = False
        # Load the Qt UI
        uic.loadUi(UI_FILE, self)
        # Default main window parameters
        self.resize(QSize(480, 640))                 # size
        self.move(QPoint(50, 50))                    # position
        self.setWindowTitle(APPLICATION_NAME)        # title
        # Welcome message
        print(APPLICATION_NAME + ' version ' + APPLICATION_VERSION + ' started')
        #
        restore_settings(self, file_name=CONFIG_FILE, widgets=(self.lineEdit, self.lineEdit_2,
                                                               self.lineEdit_3, self.lineEdit_4))
        self.connect_ports()
        # Connect signals with slots
        self.pushButton.clicked.connect(self.clear_button_clicked)
        self.pushButton_2.clicked.connect(self.connect_ports)
        #self.pushButton_2.clicked.connect(self.connect_port)
        # Defile callback task and start timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.timer_handler)
        self.timer.start(TIMER_PERIOD)
        self.logger.info('\n---------- Config Finished -----------\n')

    def connect_ports(self):
        try:
            self.com1.close()
            self.com2.close()
        except:
            pass
        port = ''
        try:
            port = str(self.lineEdit.text())
            param = str(self.lineEdit_2.text())
            params = param.split(' ')
            kwargs = {}
            for p in params:
                p1 = p.strip().split('=')
                kwargs[p1[0].strip()] = p1[1].strip()
            if 'timeout' not in kwargs:
                kwargs['timeout'] = 0
            self.com1 = serial.Serial(port, **kwargs)
            # self.com1.ctsrts = True
            #
            port = str(self.lineEdit_3.text())
            param = str(self.lineEdit_4.text())
            params = param.split(' ')
            kwargs = {}
            for p in params:
                p1 = p.strip().split('=')
                kwargs[p1[0].strip()] = p1[1].strip()
            if 'timeout' not in kwargs:
                kwargs['timeout'] = 0
            self.com2 = serial.Serial(port, **kwargs)
            # self.com2.ctsrts = True
            self.connected = True
            self.plainTextEdit_2.appendPlainText('%s Ports connected successfully' % dts())
        except:
            self.plainTextEdit_2.setPlainText('Port %s connection error' % port)

    def hex_from_str(self, v):
        h = ''
        for i in v:
            h += hex(i) + ' '
        return h

    def str_from_hex(self, v):
        vs = v.split(' ')
        h = ''
        for i in vs:
            v = i.strip()
            if v != '':
                h += chr(int(v, 16))
        return h

    def dec_from_str(self, v):
        h = ''
        for i in v:
            h += str(i) + ' '
        return h

    def clear_button_clicked(self):
        self.plainTextEdit_2.setPlainText('')

    def on_quit(self) :
        # Save global settings
        save_settings(self, file_name=CONFIG_FILE, widgets=(self.lineEdit, self.lineEdit_2,
                                                            self.lineEdit_3, self.lineEdit_4))

    def read_port(self, port):
        result = b''
        r = port.read(1)
        while len(r) > 0:
            result += r
            r = port.read(1)
        return result

    def timer_handler(self):
        if not self.connected:
            self.plainTextEdit_2.setPlainText('Not connected')
            return
        v = self.com1.cts
        if self.cts1 != v:
            self.logger.debug('CTS1 %s', v)
            self.cts1 = v
            # self.com2.rts = v
        v = self.com1.rts
        if self.rts1 != v:
            self.logger.debug('RTS1 %s', v)
            self.rts1 = v
        result = self.read_port(self.com1)
        dt = dts()
        if len(result) > 0:
            m = self.com2.write(result)
            self.logger.debug('Port1 received %s bytes: %s %s', len(result), result, m)
            if self.pushButton_3.isChecked():
                n = self.comboBox.currentIndex()
                r = ''
                if n == 0:
                    r = str(result)
                elif n == 1:
                    r = self.hex_from_str(result)
                elif n == 2:
                    r = self.dec_from_str(result)
                self.plainTextEdit_2.appendPlainText('%s 1>2 %s' % (dt, r))
        # COM2
        v = self.com2.cts
        if self.cts2 != v:
            self.logger.debug('CTS2 %s', v)
            self.cts2 = v
            # self.com1.rts = v
        v = self.com2.rts
        if self.rts2 != v:
            self.logger.debug('RTS2 %s', v)
            self.rts2 = v
        result = self.read_port(self.com2)
        dt = dts()
        if len(result) > 0:
            m = self.com1.write(result)
            self.logger.debug('Port2 received %s bytes: %s %s', len(result), result, m)
            if self.pushButton_3.isChecked():
                n = self.comboBox.currentIndex()
                r = ''
                if n == 0:
                    r = str(result)
                elif n == 1:
                    r = self.hex_from_str(result)
                elif n == 2:
                    r = self.dec_from_str(result)
                self.plainTextEdit_2.appendPlainText('%s 2>1 %s' % (dt, r))


def dts():
    #return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    return datetime.utcnow().strftime('%H:%M:%S.%f')[:-3]


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
    status = app.exec_()
    sys.exit(status)
