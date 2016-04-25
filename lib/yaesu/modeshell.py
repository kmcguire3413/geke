from PyQt4 import QtCore as qtcore4
from PyQt4 import QtGui as qtgui4
import PyQt4 as pyqt4

import sys

from gnuradio import gr
from gnuradio import blocks, analog, filter, qtgui, audio, fft

import lib.qlcdnumberadjustable as qlcdnumberadjustable

def quick_layout(widget, widgets, horizontal=True):
	if horizontal:
		layout = qtgui4.QHBoxLayout()
	else:
		layout = qtgui4.QVBoxLayout()
	for w in widgets:
		layout.addWidget(w)
	widget.setLayout(layout)
	return layout

class QTXRXStatus(qtgui4.QWidget):
	def __init__(self):
		qtgui4.QWidget.__init__(self)
		self.rx_status = False
		self.tx_status = False
		self.enabled = False
		self.qidotred = qtgui4.QImage('./res/reddot.png')
		self.qidotyellow = qtgui4.QImage('./res/yellowdot.png')
		self.qidotblue = qtgui4.QImage('./res/bluedot.png')
		self.qidotgreen = qtgui4.QImage('./res/greendot.png')
		self.setToolTip('Shows the status of the RX and TX streams for this channel.\ngreen - enabled and inside bandwidth (on)\nblue - disabled but inside bandwidth (off)\nyellow - enabled but outside bandwidth (forced off)\nred - disabled and outside bandwidth (forced off)\nSee http://kmcg3413.net/geke.htm#rxtxdots')

	def set_rx_status(self, status):
		print 'rx status', status
		self.rx_status = status 
		self.update()

	def set_tx_status(self, status):
		self.tx_status = status
		self.update()

	def set_enabled(self, enabled):
		self.enabled = enabled
		self.update()

	def get_dot(self, enabled, status):
		if enabled:
			if status:
				return self.qidotgreen
			else:
				return self.qidotyellow
		else:
			if status:
				return self.qidotblue
			else:
				return self.qidotred

	def paintEvent(self, event):
		qp = qtgui4.QPainter(self)

		dw = float(self.width()) * 0.5
		dh = float(self.height()) * 0.5

		dd = min(dw, dh) - 10.0

		qidot = self.get_dot(self.enabled, self.rx_status)
		qp.drawImage(qtcore4.QRectF(0.0, 10.0, dd, dd), qidot)

		qidot = self.get_dot(self.enabled, self.tx_status)
		qp.drawImage(qtcore4.QRectF(dd, 10.0, dd, dd), qidot)

		font = qtgui4.QFont()
		font.setPixelSize(10)

		qp.setFont(font)

		qp.drawText(0, 0, dd, dd, 0, 'RX')
		qp.drawText(dd, 0, dd, dd, 0, 'TX')

		qp.end()

class ModeShell:
	def connect(self, *args):
		"""
		This is the same as calling `connect` on a `top_block` for
		GNU Radio except we also store the connection making it possible
		to call `ModeShell.disconnect_all` to disconnect all connections
		made using this call.

		Throws:
			Python Exceptions
		"""
		for x in xrange(1, len(args)):
			#print 'ModeShell.connect(%s, ...) connecting %s ---> %s' % (self, args[x - 1], args[x])
			self.tb.connect(args[x - 1], args[x])
			self.__connections.append((args[x - 1], args[x]))

	def make_cfg_lcdnum(self, digits, negative, xdef, label):
		return {
			'digits': digits,
			'negative': negative,
			'xdef': xdef,
			'label': label,
		}

	def disconnect_all(self):
		"""
		Disconnect any connections made using `ModeShell.connect`, thus,
		simplifying and reducing errors when coding.

		Throws:
			Python Exceptions
			GNU Radio Exceptions
		"""
		if len(self.__connections) > 0:
			print 'trying lock'
			sys.stdout.flush()
			self.tb.lock()
			print 'locked'
			sys.stdout.flush()
			for connection in self.__connections:
				self.tb.disconnect(connection[0], connection[1])
			self.tb.unlock()
			self.__connections = []

	def __init__(self, icfg, tb, rx, tx, audio_tx, audio_rx, chanover, beeper):
		self.left = qtgui4.QWidget()
		self.right = qtgui4.QWidget()

		self.audio_disconnect_node = None
		self.tx_disconnect_node = None

		self.beeper = beeper

		self.chanover = chanover
		self.tb = tb
		self.rx = rx
		self.tx = tx
		self.audio_tx = audio_tx
		self.audio_rx = audio_rx
		self.active = False

		self.__connections = []


		self.last_vol = 0.0
		self.last_sq = 0.0
		self.last_freq = 0.0
		self.last_bw = 0.0

		def change_volume(value):
			chanover.change_volume(value)
			self.update(self.rxcenter, self.txcenter, self.rxsps, self.txsps)
			self.key_changed = None
			self.last_vol = value 
			#self.beeper()

		def change_squelch(value):
			chanover.change_squelch(value)
			self.key_changed = 'vol'
			self.update(self.rxcenter, self.txcenter, self.rxsps, self.txsps)
			self.key_changed = None
			self.last_sq = value
			#self.beeper()

		def change_frequency(value):
			chanover.change_center_freq(value)
			self.key_changed = 'freq'
			self.update(self.rxcenter, self.txcenter, self.rxsps, self.txsps)
			self.key_changed = None
			self.last_freq = value
			#self.beeper()

		def change_bw(value):
			chanover.change_width(value)
			self.key_changed = 'bw'
			self.update(self.rxcenter, self.txcenter, self.rxsps, self.txsps)
			self.key_changed = None
			self.last_bw = value
			#self.beeper()

		def change_nonspecific(key, value):
			self.key_changed = key
			self.update(self.rxcenter, self.txcenter, self.rxsps, self.txsps)
			self.key_changed = None
			setattr(self, 'last_%s' % key, value)
			#self.beeper()

		self.key_changed = None

		def __mf(k):
			return lambda v: change_nonspecific(k, v)

		els = []
		for k in icfg:
			ecfg = icfg[k]
			args = {}
			for kk in ecfg:
				if kk != 'type':
					args[kk] = ecfg[kk]
			if k == 'vol':
				args['signal'] = change_volume
			elif k == 'sq':
				args['signal'] = change_squelch
			elif k == 'freq':
				args['signal'] = change_frequency
			elif k == 'bw':
				args['signal'] = change_bw
			else:
				args['signal'] = __mf(k)
			setattr(self, 'last_%s' % k, 0.0)
			qel = qlcdnumberadjustable.QLCDNumberAdjustable(**args)
			setattr(self, k, qel)
			els.append(qel)

		self.shiftsrc = None
		self.shifter = None
		self.decfilter = None
		self.amper = None


		self.rxtxstatus = QTXRXStatus()

		self.rxtxstatus.setMinimumSize(75, 55)

		els.insert(0, self.rxtxstatus)

		self.left.lay = quick_layout(self.left, els, horizontal=False)

	def set_active(self, active):
		if active:
			self.on()
		else:
			self.off()

	def update(self, rxcenter, txcenter, rxsps, txsps, fast=False):
		self.rxcenter = rxcenter
		self.txcenter = txcenter
		self.rxsps = rxsps
		self.txsps = txsps

	def is_on(self):
		return self.active

	def on(self):
		if self.active:
			return
		self.rxtxstatus.set_enabled(True)
		self.active = True

	def off(self):
		if not self.active:
			return
		self.rxtxstatus.set_enabled(False)
		self.active = False

	def get_left(self):
		return self.left 

	def get_right(self):
		return self.right

	def deinit(self):
		self.off()