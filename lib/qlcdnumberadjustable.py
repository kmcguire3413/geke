from PyQt4 import QtCore as qtcore4
from PyQt4 import QtGui as qtgui4
import PyQt4 as pyqt4

import math

class QLCDNumberAdjustable(qtgui4.QWidget):
	def __init__(self, label, digits, signal=None, xdef=None, max=None):
		qtgui4.QWidget.__init__(self)
		self.lay = qtgui4.QVBoxLayout()
		self.setLayout(self.lay)

		self.body = qtgui4.QWidget()
		self.dnum = qtgui4.QLCDNumber(digits)
		self.body.lay = qtgui4.QHBoxLayout()
		self.dials = []

		if xdef is None:
			xdef = 0

		self.value = xdef

		tmp = list('%s' % xdef)[::-1]

		parts = []
		while len(tmp) > 0:
			part = tmp[0:3][::-1]
			for x in xrange(0, len(part)):
				tmp.pop(0)
			parts.append(part)

		self.dnum.display(int(xdef))

		for x in xrange(0, int(math.ceil(float(digits) / 3.0))):
			dial = qtgui4.QDial()
			self.dials.append(dial)
			dial.setMinimumSize(35, 35)
			dial.setMaximumSize(35, 35)
			dial.setMinimum(0)
			dial.setMaximum(999)
			dial.setWrapping(True)
			dial.setSingleStep(1)
			if x >= len(parts):
				dnum = 0
			else:
				dnum = int(''.join(parts[x]))
			dial.setValue(int(dnum))
			self.body.lay.addWidget(dial)
			def _valchanged(_value):
				value = 0.0
				for x in xrange(0, len(self.dials)):
					tmp = self.dials[x].value()
					if tmp < 1.0:
						continue
					value += tmp * 10.0 ** float(x * 3)
				if max is not None:
					value = value % max
				self.dnum.display(value)
				self.value = value
				if signal is not None:
					signal(value)
			dial.valueChanged.connect(_valchanged)			

		self.body.lay.addWidget(self.dnum)
		self.body.setLayout(self.body.lay)

		if label is not None:
			self.label = qtgui4.QLabel()
			self.label.setText(label)
			self.lay.addWidget(self.label)

		self.lay.addWidget(self.body)

		self.dnum.setSegmentStyle(2)

		self.lay.setSpacing(2)
		self.lay.setMargin(0)
		self.body.lay.setSpacing(2)
		self.body.lay.setMargin(0)

		self.setStyleSheet(' \
			QLabel { font-family: monospace; font-size: 12pt; font-weight: bold; } \
			QDial { background-color: #333333; border: none; } \
			QLCDNumber { border: none; color: #888888; color: #ffff99; } \
		')
	def get_value(self):
		return self.value