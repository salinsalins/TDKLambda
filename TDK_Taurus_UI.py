import sys
from taurus.external.qt import Qt
from taurus.qt.qtgui.application import TaurusApplication

from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from taurus.qt.qtgui.input import TaurusValueCheckBox, TaurusValueSpinBoxEx

app = TaurusApplication(sys.argv, cmd_line_parser=None,)
panel = Qt.QWidget()
layout = Qt.QVBoxLayout()
panel.setLayout(layout)

layout1 = Qt.QHBoxLayout()
led = TaurusLed()
layout1.addWidget(led)
led.model = 'binp/nbi/magnet1/out'
v = TaurusLabel()
layout1.addWidget(v)
v.model = 'binp/nbi/magnet1/voltage'
c = TaurusLabel()
layout1.addWidget(c)
c.model = 'binp/nbi/magnet1/current'

layout.addChildLayout(layout)
panel.show()
sys.exit(app.exec_())
