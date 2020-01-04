# coding: utf-8
'''
Created on Jul 28, 2019

@author: sanin
''' 

import os.path
import sys
import json
import logging
import time

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import qApp
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QComboBox
from PyQt5.QtWidgets import QCheckBox
from PyQt5.QtWidgets import QPlainTextEdit
from PyQt5.QtWidgets import QLineEdit
from PyQt5 import uic
from PyQt5.QtCore import QSize
from PyQt5.QtCore import QPoint
from PyQt5.QtCore import QTimer
import PyQt5.QtGui as QtGui

import tango

from TangoCheckBox import TangoCheckBox
from TangoLED import TangoLED
from TangoLabel import TangoLabel
from TangoAbstractSpinBox import TangoAbstractSpinBox
from TangoRadioButton import TangoRadioButton

ORGANIZATION_NAME = 'BINP'
APPLICATION_NAME = 'Magnets_UI'
APPLICATION_NAME_SHORT = 'Magnets_UI'
APPLICATION_VERSION = '1_0'
CONFIG_FILE = APPLICATION_NAME_SHORT + '.json'
UI_FILE = APPLICATION_NAME_SHORT + '.ui'

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
f_str = '%(asctime)s,%(msecs)d %(funcName)s(%(lineno)s) ' + \
        '%(levelname)-7s %(message)s'
log_formatter = logging.Formatter(f_str, datefmt='%H:%M:%S')
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)

# Global configuration dictionary
CONFIG = {}


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        global logger
        # Initialization of the superclass
        super(MainWindow, self).__init__(parent)

        # logging config
        self.logger = logger
        # members definition
        self.n = 0
        self.refresh_flag = False
        self.last_selection = -1
        self.elapsed = 0

        # Load the UI
        uic.loadUi(UI_FILE, self)
        # Default main window parameters
        ##self.setMinimumSize(QSize(480, 640))        # min size
        self.resize(QSize(480, 640))                # size
        self.move(QPoint(50, 50))                   # position
        self.setWindowTitle(APPLICATION_NAME)       # title
        self.setWindowIcon(QtGui.QIcon('icon.png')) # icon
        # Connect signals with slots
        ##self.plainTextEdit_1.textChanged.connect(self.refresh_on)
        ##self.checkBox_25.clicked.connect(self.phandler)
        # Connect menu actions
        self.actionQuit.triggered.connect(qApp.quit)
        self.actionPlot.triggered.connect(self.show_main_pane)
        self.actionParameters.triggered.connect(self.show_param_pane)
        self.actionAbout.triggered.connect(self.show_about)
        # Additional decorations
        ##self.radioButton.setStyleSheet('QRadioButton {background-color: red}')
        ##self.doubleSpinBox_4.setSingleStep(0.1)
        ##self.doubleSpinBox_21.setKeyboardTracking(False)
        # Clock at status bar
        self.clock = QLabel(" ")
        self.statusBar().addPermanentWidget(self.clock)

        print(APPLICATION_NAME + ' version ' + APPLICATION_VERSION + ' started')

        # find all controls in config tab
        self.config_widgets = []
        self.config_widgets = get_widgets(self.tabWidgetPage3)

        self.restore_settings(self.config_widgets)

        # read attributes TangoWidgets list
        self.rtwdgts = (TangoLED('binp/nbi/magnet1/output_state', self.pushButton_26),
                        TangoLabel('binp/nbi/magnet1/voltage', self.label_63),
                        TangoLabel('binp/nbi/magnet1/current', self.label_65),
                        TangoLED('binp/nbi/magnet/output_state', self.pushButton_27),
                        TangoLabel('binp/nbi/magnet/voltage', self.label_110),
                        TangoLabel('binp/nbi/magnet/current', self.label_112),
                        TangoLED('binp/nbi/magnet2/output_state', self.pushButton_28),
                        TangoLabel('binp/nbi/magnet2/voltage', self.label_104),
                        TangoLabel('binp/nbi/magnet2/current', self.label_106),
                        )
        # write attributes TangoWidgets list
        self.wtwdgts = (TangoAbstractSpinBox('binp/nbi/magnet1/programmed_current', self.doubleSpinBox_21),
                        TangoCheckBox('binp/nbi/magnet1/output_state', self.checkBox_25),
                        TangoAbstractSpinBox('binp/nbi/magnet1/programmed_voltage', self.doubleSpinBox_20),
                        TangoRadioButton('binp/nbi/magnet/output_state', self.radioButton_47),
                        TangoAbstractSpinBox('binp/nbi/magnet/programmed_voltage', self.doubleSpinBox_37),
                        TangoAbstractSpinBox('binp/nbi/magnet/programmed_voltage', self.doubleSpinBox_38),
                        )

    def get_widgets(self, obj, s=''):
        lout = obj.layout()
        for k in range(lout.count()):
            wgt = lout.itemAt(k).widget()
            #print(s, wgt)
            if wgt is not None and wgt not in self.config_widgets:
                self.config_widgets.append(wgt)
            if isinstance(wgt, QtWidgets.QFrame):
                self.get_widgets(wgt, s=s + '   ')

    def show_about(self):
        QMessageBox.information(self, 'About', APPLICATION_NAME + ' Version ' + APPLICATION_VERSION +
            '\nUser interface program to control TDK Lambda Genesis power supplies.', QMessageBox.Ok)

    def show_main_pane(self):
        self.stackedWidget.setCurrentIndex(0)
        self.actionPlot.setChecked(True)
        self.actionLog.setChecked(False)
        self.actionParameters.setChecked(False)

    def show_param_pane(self):
        self.stackedWidget.setCurrentIndex(2)
        self.actionPlot.setChecked(False)
        self.actionLog.setChecked(False)
        self.actionParameters.setChecked(True)

    def log_level_changed(self, m):
        levels = [logging.NOTSET, logging.DEBUG, logging.INFO,
                  logging.WARNING, logging.ERROR, logging.CRITICAL]
        if m >= 0:
            self.logger.setLevel(levels[m])

    def phandler(self, *args, **kwargs):
        print(args, kwargs)

    def sb_changed(self, value):
        #print(value)
        wgt = self.focusWidget()
        if isinstance(wgt, QCheckBox):
            value = bool(value)
        for w in self.watps:
            if wgt == w[1]:
                try:
                    w[0].write(value)
                except:
                    print_exception_info()
                    #print('except')

    def onQuit(self) :
        # Save global settings
        self.save_settings(self.config_widgets)
        timer.stop()
        
    def save_settings(self, widgets=(), file_name=CONFIG_FILE) :
        global CONFIG
        try:
            # Save window size and position
            p = self.pos()
            s = self.size()
            CONFIG['main_window'] = {'size':(s.width(), s.height()), 'position':(p.x(), p.y())}
            #get_state(self.comboBox_1, 'comboBox_1')
            for w in widgets:
                get_widget_state(w, CONFIG)
            with open(file_name, 'w') as configfile:
                configfile.write(json.dumps(CONFIG, indent=4))
            self.logger.info('Configuration saved to %s' % file_name)
            return True
        except :
            self.logger.log(logging.WARNING, 'Configuration save error to %s' % file_name)
            print_exception_info()
            return False
        
    def restore_settings(self, widgets=(), file_name=CONFIG_FILE) :
        global CONFIG
        try :
            with open(file_name, 'r') as configfile:
                s = configfile.read()
            CONFIG = json.loads(s)
            # Restore log level
            if 'log_level' in CONFIG:
                v = CONFIG['log_level']
                self.logger.setLevel(v)
                levels = [logging.NOTSET, logging.DEBUG, logging.INFO,
                          logging.WARNING, logging.ERROR, logging.CRITICAL, logging.CRITICAL+10]
                n = 1
                for m in range(len(levels)):
                    if v < levels[m]:
                        n = m
                        break
                self.comboBox_1.setCurrentIndex(n-1)
            # Restore window size and position
            if 'main_window' in CONFIG:
                self.resize(QSize(CONFIG['main_window']['size'][0], CONFIG['main_window']['size'][1]))
                self.move(QPoint(CONFIG['main_window']['position'][0], CONFIG['main_window']['position'][1]))
            #set_state(self.plainTextEdit_1, 'plainTextEdit_1')
            #set_state(self.comboBox_1, 'comboBox_1')
            for w in widgets:
                set_widget_state(w, CONFIG)
            self.logger.log(logging.INFO, 'Configuration restored from %s' % file_name)
            return True
        except :
            self.logger.log(logging.WARNING, 'Configuration restore error from %s' % file_name)
            print_exception_info()
            return False

    def timer_handler(self):
        t0 = time.time()
        self.elapsed += 1
        t = time.strftime('%H:%M:%S')
        self.clock.setText('%s' % t)
        #self.clock.setText('Elapsed: %ds    %s' % (self.elapsed, t))
        if len(self.rtwdgts) <= 0:
            return
        count = 0
        while time.time() - t0 < 0.2:
            if self.rtwdgts[self.n].widget.isVisible():
                self.rtwdgts[self.n].update()
            self.n += 1
            if self.n >= len(self.rtwdgts):
                self.n = 0
            count += 1
            if count == len(self.rtwdgts):
                break
        #print(int((time.time()-t0)*1000.0), 'ms')
        #time.sleep(1.0)


def get_widgets(obj: QtWidgets.QWidget):
    wgts = []
    lout = obj.layout()
    for k in range(lout.count()):
        wgt = lout.itemAt(k).widget()
        #if wgt is not None and not isinstance(wgt, QtWidgets.QFrame) and wgt not in wgts:
        #if wgt is not None and wgt not in wgts:
        if wgt is not None and isinstance(wgt, QtWidgets.QWidget) and wgt not in wgts:
            wgts.append(wgt)
        if isinstance(wgt, QtWidgets.QFrame):
            wgts1 = get_widgets(wgt)
            for wgt1 in wgts1:
                if wgt1 not in wgts:
                    wgts.append(wgt1)
    return wgts

def cb_set_color(cb: QCheckBox, m, colors=('green', 'red')):
    if isinstance(m, bool):
        if m:
            cb.setStyleSheet('QCheckBox::indicator { background: ' + colors[0] + ';}')
        else:
            cb.setStyleSheet('QCheckBox::indicator { background: ' + colors[1] + ';}')
            # cb.setStyleSheet('QCheckBox::indicator { background: red;}')
    if isinstance(m, str):
        cb.setStyleSheet('QCheckBox::indicator { background: ' + m + ';}')

def wdg_update(cb: QWidget, attr_proxy: tango.AttributeProxy):
    try:
        attr = attr_proxy.read()
        value = attr.value
        if attr.data_format != tango._tango.AttrDataFormat.SCALAR:
            logger.error('Non SCALAR attribute')
            return
        if isinstance(cb, QCheckBox):
            if attr.type == tango._tango.CmdArgType.DevBoolean:
                if attr.quality == tango._tango.AttrQuality.ATTR_VALID:
                    cb_set_color(cb, value)
                else:
                    cb_set_color(cb, 'gray')
            else:
                logger.error('Non boolean attribute for QCheckBox')
                cb_set_color(cb, 'gray')
    except:
        logger.debug('Exception updating widget', sys.exc_info()[0])
        cb_set_color(cb, 'gray')

def cb_update(cb: QCheckBox, attr_proxy: tango.AttributeProxy):
    try:
        attr = attr_proxy.read()
        value = attr.value
        if attr.type == tango._tango.CmdArgType.DevBoolean and attr.data_format == tango._tango.AttrDataFormat.SCALAR:
            if attr.quality == tango._tango.AttrQuality.ATTR_VALID:
                cb_set_color(cb, value)
            else:
                cb_set_color(cb, 'gray')
        else:
            print('Not scalar boolean attribute for QCheckBox')
            cb_set_color(cb, 'gray')
    except:
        logger.debug('Exception updating widget', sys.exc_info()[0])
        cb_set_color(cb, 'gray')

def pb_update(pb: QtWidgets.QPushButton, attr_proxy: tango.AttributeProxy):
    try:
        attr = attr_proxy.read()
        if attr.type == tango._tango.CmdArgType.DevBoolean and attr.data_format == tango._tango.AttrDataFormat.SCALAR:
            if attr.quality == tango._tango.AttrQuality.ATTR_VALID:
                pb.setDisabled(False)
                pb.setChecked(attr.value)
            else:
                logger.debug('Attribute INVALID')
                pb.setDisabled(True)
        else:
            logger.debug('Not scalar boolean attribute')
            pb.setDisabled(True)
    except:
        logger.debug('Exception updating widget', sys.exc_info()[0])
        #print_exception_info()
        pb.setDisabled(True)

def lbl_update(lbl: QLabel, attr_proxy: tango.AttributeProxy):
    try:
        attr = attr_proxy.read()
        if attr.data_format != tango._tango.AttrDataFormat.SCALAR:
            logger.debug('Non scalar attribute')
            lbl.setText('****')
            lbl.setStyleSheet('color: red')
            return
        ac = attr_proxy.get_config()
        value = ac.format % attr.value
        if attr.quality == tango._tango.AttrQuality.ATTR_VALID:
            lbl.setStyleSheet('color: black')
            lbl.setText(value)
        else:
            lbl.setStyleSheet('color: red')
            lbl.setText(value)
    except:
        logger.debug('Exception during update', sys.exc_info()[0])
        lbl.setText('****')
        lbl.setStyleSheet('color: red')

def get_widget_state(obj, config, name=None):
    try:
        if name is None:
            name = obj.objectName()
        if isinstance(obj, QLineEdit):
            config[name] = str(obj.text())
        if isinstance(obj, QComboBox):
            config[name] = {'items': [str(obj.itemText(k)) for k in range(obj.count())],
                            'index': obj.currentIndex()}
        if isinstance(obj, QtWidgets.QAbstractButton):
            config[name] = obj.isChecked()
        if isinstance(obj, QPlainTextEdit) or isinstance(obj, QtWidgets.QTextEdit):
            config[name] = str(obj.toPlainText())
    except:
        return

def set_widget_state(obj, config, name=None):
    try:
        if name is None:
            name = obj.objectName()
        if name not in config:
            return
        if isinstance(obj, QLineEdit):
            obj.setText(config[name])
        if isinstance(obj, QComboBox):
            obj.setUpdatesEnabled(False)
            obj.blockSignals(True)
            obj.clear()
            obj.addItems(config[name]['items'])
            obj.blockSignals(False)
            obj.setUpdatesEnabled(True)
            obj.setCurrentIndex(config[name]['index'])
            # Force index change event in the case of index=0
            if config[name]['index'] == 0:
                obj.currentIndexChanged.emit(0)
        if isinstance(obj, QtWidgets.QAbstractButton):
            obj.setChecked(config[name])
        if isinstance(obj, QPlainTextEdit) or isinstance(obj, QtWidgets.QTextEdit):
            obj.setPlainText(config[name])
    except:
        return

def print_exception_info(level=logging.DEBUG):
    logger.log(level, "Exception ", exc_info=True)


if __name__ == '__main__':
    # Create the GUI application
    app = QApplication(sys.argv)
    # Instantiate the main window
    dmw = MainWindow()
    app.aboutToQuit.connect(dmw.onQuit)
    # Show it
    dmw.show()
    # Defile and start timer task
    timer = QTimer()
    timer.timeout.connect(dmw.timer_handler)
    timer.start(300)
    # Start the Qt main loop execution, exiting from this script
    # with the same return code of Qt application
    sys.exit(app.exec_())
