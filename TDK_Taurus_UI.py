import sys
from taurus.qt.qtgui.panel import TaurusForm
from taurus.qt.qtgui.application import TaurusApplication

app = TaurusApplication(sys.argv, cmd_line_parser=None)

attrs = ['voltage', 'current', 'out', 'programmed_voltage', 'programmed_current']
model = ['binp/nbi/magnet1/%s' % attr for attr in attrs]

w = TaurusForm()
w.model = model
w.show()
sys.exit(app.exec_())