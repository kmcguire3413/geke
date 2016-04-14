from PyQt4 import QtCore as qtcore4
from PyQt4 import QtGui as qtgui4
import PyQt4 as pyqt4

import math

class QLCDNumberAdjustable(qtgui4.QWidget):
	def __init__(self, label, digits, mul=None, signal=None, xdef=None, max=None, negative=False):
		qtgui4.QWidget.__init__(self)
		self.label = label
		self.digits = float(digits)
		self.signal = signal
		self.xdef = float(xdef)
		self.negative = negative
		if max is not None:
			self.max = float(max)
		else:
			self.max = None
		if negative:
			digits = digits + 1
		self.mul = mul
		self.cur_digits = [0] * int(digits)
		self.cur_digits[0] = '+'
		if xdef is not None:
			self.set_value(xdef)
		self.mouse_over_digit = None
		self.halfed = 0.5

		self.setMouseTracking(True)

	def get_value(self):
		txt = []
		for x in xrange(0, len(self.cur_digits)):
			txt.append(str(self.cur_digits[x]))
		txt = int(''.join(txt))
		return txt

	def leaveEvent(self, event):
		self.mouse_over_digit = None
		self.update()

	def mouseMoveEvent(self, event):
		w = float(self.width())
		h = float(self.height())
		x = float(event.x())
		y = float(event.y())

		if y > h * self.halfed:
			# Highlite the digit that the mouse is over only
			# if it has changed.
			weach = (w / self.digits)
			weach = min(weach, self.height() - self.height() * self.halfed)
			tmp = math.floor(x / weach)
			if tmp != self.mouse_over_digit:
				self.mouse_over_digit = int(tmp)
			if y > h * self.halfed + (h - h * self.halfed) * 0.5:
				self.mouse_portion = 1.0
			else:
				self.mouse_portion = 0.0
		else:
			self.mouse_over_digit = None
		self.update()

	def set_value(self, value):
		xdef = str(int(value))
		self.cur_digits = [0] * int(self.digits)
		if self.negative:
			if value < 0:
				self.cur_digits[0] = '-'
			else:
				self.cur_digits[0] = '+'
		for x in xrange(0, len(xdef)):
			self.cur_digits[len(self.cur_digits) - len(xdef) + x] = int(xdef[x])

	def mouseReleaseEvent(self, event):
		if self.mouse_over_digit is not None:
			if self.negative and self.mouse_over_digit == 0:
				if self.cur_digits[0] == '+':
					self.cur_digits[0] = '-'
				else:
					self.cur_digits[0] = '+'
			else:
				if self.mouse_portion > 0.0:
					self.cur_digits[self.mouse_over_digit] = (self.cur_digits[self.mouse_over_digit] - 1) % 10
				else:
					self.cur_digits[self.mouse_over_digit] = (self.cur_digits[self.mouse_over_digit] + 1) % 10
		if self.max is not None and self.get_value() > self.max:
			self.set_value(self.max)
		if self.signal:
			self.signal(self.get_value())
		self.update()

	def paintEvent(self, event):
		qp = qtgui4.QPainter(self)
		font = qtgui4.QFont()
		font.setPixelSize(10)
		qp.setFont(font)
		if self.mul is None:
			label_text = self.label
		else:
			label_text = self.label + '(' + str(self.get_value() * self.mul) + ')'
		qp.drawText(0, 0, self.width(), self.height() * self.halfed, 0, label_text)
		color_hoverbg = qtgui4.QColor(90, 90, 90)
		color_halfbg = qtgui4.QColor(120, 120, 120)
		bothalf_height = self.height() - self.height() * self.halfed
		# Draw each digit.
		weach = float(self.width()) / float(len(self.cur_digits))
		weach = min(weach, bothalf_height)
		font.setPixelSize(min(bothalf_height, weach))
		y = float(self.height()) * self.halfed

		for i in xrange(0, len(self.cur_digits)):
			x = weach * i
			if self.mouse_over_digit == i:
				qp.fillRect(qtcore4.QRectF(x, y, weach, self.height() * self.halfed), color_hoverbg)
				qp.fillRect(qtcore4.QRectF(x, y + bothalf_height * 0.5 * self.mouse_portion, weach, bothalf_height * 0.5), color_halfbg)
			qp.drawText(x, y, weach, self.height() * self.halfed, 0, '%s' % self.cur_digits[i])
		qp.end()

class QLCDNumberAdjustable2(qtgui4.QWidget):
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