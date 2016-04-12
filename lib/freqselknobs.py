from PyQt4 import QtCore as qtcore4
from PyQt4 import QtGui as qtgui4
import PyQt4 as pyqt4

class QFrequencySelectorKnob(qtgui4.QWidget):
	def __init__(self, defval=0, postfix='?', _min=0, _max=1000):
		qtgui4.QWidget.__init__(self)
		self.layout = qtgui4.QVBoxLayout()
		self.label = qtgui4.QLabel()
		self.dial = qtgui4.QDial()
		self.dial.setValue(defval)
		self.dial.setMinimum(_min)
		self.dial.setMaximum(_max)
		self.dial.setNotchesVisible(True)
		self.dial.setSingleStep(1)
		self.dial.setWrapping(True)
		self.dial.setMaximumSize(100, 100)
		self.label.setMaximumSize(100, 30)
		self.label.setText('%s%s' % (defval, postfix))
		self.layout.addWidget(self.label)
		self.layout.addWidget(self.dial)
		self.setLayout(self.layout)
		self.setMaximumSize(100, 130)

		def __valchg(self):
			self.label.setText(self.value)

		self.dial.label = self.label
		self.dial.__valchg = types.MethodType(__valchg, self.dial)
		self.dial.valueChanged.connect(self.dial.__valchg)

class QFrequencySelectorKnobs(qtgui4.QWidget):
	def __init__(self):
		qtgui4.QWidget.__init__(self)

		self.layout = qtgui4.QHBoxLayout()
		obj = QFrequencySelectorKnob(postfix='GHZ')
		self.layout.addWidget(obj)
		obj = QFrequencySelectorKnob(postfix='MHZ')
		self.layout.addWidget(obj)
		obj = QFrequencySelectorKnob(postfix='KHZ')
		self.layout.addWidget(obj)
		obj = QFrequencySelectorKnob(postfix='HZ')
		self.layout.addWidget(obj)
		self.setLayout(self.layout)