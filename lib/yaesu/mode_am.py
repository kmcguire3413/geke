from PyQt4 import QtCore as qtcore4
from PyQt4 import QtGui as qtgui4
import PyQt4 as pyqt4

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

class AM(ModeShell):
	def __init__(self, tb, rx, audio, chanover):):
		uicfg = {
			'freq': {
				'type':     'lcdnum',
				'digits': 	9,
				'negative': True,
				'xdef': 	5000,
				'label': 	'CEN FREQ',
			},
			'bw': {
				'type':     'lcdnum',
				'digits':   6,
				'xdef':     1000,
				'label':    'BW',
			},
			'bwdrop': {
				'type':     'lcdnum',
				'label':	'BW DROP',
				'digits':    3,
				'xdef':      900,
			},
			'gain': {
				'type':     'lcdnum',
				'label':	'GAIN DB',
				'digits':   3,
				'max':      1000,
				'xdef':     3,
			}
			'volume': {
				'type':     'lcdnum',
				'label':    'VOLUME',
				'digits':   3,
				'xdef':     50,
				'max':      100,
			},
			'sps': {
				'type':     'lcdnum',
				'label':   	'ASPS',
				'digits':   6,
				'xdef':     16000,
				'max':      1000000,
			}
			'squelch': {
				'type':     'lcdnum',
				'label':	'SQUELCH',
				'digits':   3,
				'xdef':     50,
				'max':      100,
			}
		}
		ModeShell.__init__(self, uicfg, tb, rx, audio, chanover)
	def update(self, sps):
		pass

	def on(self):
		pass

	def off(self):
		pass


class ModeShell:
	def __init__(self, icfg, tb, rx, audio, chanover):
		self.left = qtgui4.QWidget()
		self.right = qtgui4.QWidget()

		self.audio_disconnect_node = None

		self.chanover = chanover
		self.tb = tb
		self.rx = rx
		self.audio = audio
		self.active = False

		def change_volume(value):
			chanover.change_volume(value)
			self.update(self.sps)

		def change_squelch(value):
			chanover.change_squelch(value)
			self.update(self.sps)

		def change_frequency(value):
			chanover.change_center_freq(value)
			self.update(self.sps)

		def change_bw(value):
			chanover.change_width(value)
			self.update(self.sps)

		def change_nonspecific(value):
			self.update(self.sps)

		for k in icfg:
			ecfg = icfg[k]
			args = []
			for kk in ecfg:
				if kk != 'type':
					args[kk] = ecfg[kk]
			if k == 'volume':
				args['signal'] = change_volume
			elif k == 'squelch':
				args['signal'] = change_squelch
			elif k == 'freq':
				args['signal'] = change_frequency
			elif k == 'bw':
				args['signal'] = change_bw
			else:
				args['signal'] = change_nonspecific
			qel = qlcdnumberadjustable.QLCDNumberAdjustable(**args)
			setattr(self, k, qel)

		self.freq = qlcdnumberadjustable.QLCDNumberAdjustable(label='CEN FREQ', digits=9, xdef=5000, signal=change_frequency)
		self.bw = qlcdnumberadjustable.QLCDNumberAdjustable(label='BW', digits=6, xdef=1000, signal=change_bw)

		self.bwdrop = qlcdnumberadjustable.QLCDNumberAdjustable(label='BW DROP', digits=3, xdef=900, signal=change_bwdrop)
		self.gain = qlcdnumberadjustable.QLCDNumberAdjustable(label='GAIN DB', digits=3, max=100, xdef=1, signal=change_gain)
		self.vol = qlcdnumberadjustable.QLCDNumberAdjustable(label='VOLUME', digits=3, xdef=50, max=100, signal=change_volume)
		chanover.change_volume(50)
		self.isps = qlcdnumberadjustable.QLCDNumberAdjustable(label='SPS', digits=6, xdef=16000, max=1000000, signal=change_isps)
		self.sq = qlcdnumberadjustable.QLCDNumberAdjustable(label='SQUELCH', digits=3, xdef=50, max=100, signal=change_squelch)
		chanover.change_squelch(50)

		self.shiftsrc = None
		self.shifter = None
		self.decfilter = None
		self.amper = None		

		self.left.lay = quick_layout(self.left, [
			self.freq, self.bw, self.bwdrop, self.gain, self.vol, self.isps, self.sq
		], horizontal=False)

	def set_active(self, active):
		if active:
			self.on()
		else:
			self.off()

	def update(self, sps, fast=False):
		"""
		Updates the module by its parameters. Supports a full reconfiguration
		and a fast reconfiguration for only simple changes such as volume, squelch,
		frequency, and audiosps which can be changed without much computational expense.
		"""
		sps = float(sps)
		self.sps = sps

		# self.freq, self.bw, self.bwdrop, self.gain, self.vol, self.isps, self.sq

		freq = self.freq.get_value()
		bw = self.bw.get_value()
		bwdrop = self.bwdrop.get_value()
		gain = self.gain.get_value()
		vol = self.vol.get_value()
		isps = self.isps.get_value()
		sq = self.sq.get_value()

		print 'sps:%s freq:%s bw:%s bwdrop:%s gain:%s vol:%s isps:%s sq:%s' % (sps, freq, bw, bwdrop, gain, vol, isps, sq)

		taps = filter.firdes.low_pass(gain, isps, bw, bwdrop, filter.firdes.WIN_BLACKMAN)

		# Turn it off to disconnect them before the variable contents
		# below are replaced.
		was_active = self.active
		self.off()

		self.shiftsrc = analog.sig_source_c(sps, analog.GR_COS_WAVE, -freq, 0.1, 0)
		self.shifter = blocks.multiply_cc()
		self.decfilter = filter.fir_filter_ccf(int(sps / isps) // 2, taps)
		self.amper = blocks.complex_to_mag_squared()

		if was_active:
			self.on()
		else:
			self.off()

	def is_on(self):
		return self.active

	def on(self):
		if self.active:
			return
		self.active = True
		self.tb.lock()
		self.tb.connect(self.shiftsrc, (self.shifter, 0), self.decfilter, self.amper)
		self.tb.connect(self.rx, (self.shifter, 1))
		self.audio_disconnect_node = self.audio.connect(self.amper)
		self.tb.unlock() 
		self.chanover.change_active(True)
		print 'ON'

	def off(self):
		if not self.active:
			return
		self.active = False
		self.tb.lock()
		if self.shiftsrc is not None:
			self.tb.disconnect(self.rx, (self.shifter, 1))
			self.tb.disconnect(self.shiftsrc, (self.shifter, 0))
			self.tb.disconnect(self.shifter, self.decfilter)
			self.tb.disconnect(self.decfilter, self.amper)
		if self.audio_disconnect_node is not None:
			self.audio_disconnect_node.disconnect()
			self.audio_disconnect_node = None
		self.tb.unlock()
		self.chanover.change_active(False)
		print 'OFF'

	def get_left(self):
		return self.left 

	def get_right(self):
		return self.right

	def deinit(self):
		pass