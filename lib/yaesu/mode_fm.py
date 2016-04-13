from PyQt4 import QtCore as qtcore4
from PyQt4 import QtGui as qtgui4
import PyQt4 as pyqt4

from gnuradio import gr
from gnuradio import blocks, analog, filter, qtgui, audio, fft

import lib.qlcdnumberadjustable as qlcdnumberadjustable
import lib.yaesu.modeshell as modeshell

ModeShell = modeshell.ModeShell

class FM(ModeShell):
	def __init__(self, tb, rx, audio, chanover):
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
			},
			'vol': {
				'type':     'lcdnum',
				'label':    'VOLUME',
				'digits':   3,
				'xdef':     50,
				'max':      100,
			},
			'sq': {
				'type':     'lcdnum',
				'label':	'SQUELCH',
				'digits':   3,
				'xdef':     50,
				'max':      100,
			}
			'tau': {
				'type':     'lcdnum',
				'label':    'TAU',
				'digits':   6,
				'xdef':     7500,
			}
			'dev': {
				'type':		'lcdnum',
				'label':    'DEVIAT',
				'digits':   6,
				'xdef':     5000,
			}
		}
		ModeShell.__init__(self, uicfg, tb, rx, audio, chanover)

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
		sq = self.sq.get_value()
		dev = self.dev.get_value()

		taps = filter.firdes.low_pass(gain, sps, bw, bwdrop, filter.firdes.WIN_BLACKMAN)

		# Turn it off to disconnect them before the variable contents
		# below are replaced.
		was_active = self.active
		self.off()

		self.shiftsrc = analog.sig_source_c(sps, analog.GR_COS_WAVE, -freq, 0.1, 0)
		self.shifter = blocks.multiply_cc()
		self.decfilter = filter.fir_filter_ccf(1, taps)

		self.fmdemod = analog.nbfm_rx(
			audio_rate=16000,
			quad_rate=sps,
			tau=float(tau) * 0.000000001,
			max_dev=dev,
		)
		
		self.sqblock = analog.standard_squelch(isps)
		self.sqblock.set_threshold(float(sq) / 100.0)
		self.volblock = blocks.multiply_const_ff(float(vol) / 70.0)

		if was_active:
			self.on()
		else:
			self.off()

	def on(self):
		ModeShell.on(self)
		self.tb.lock()
		self.tb.connect(self.shiftsrc, (self.shifter, 0), self.decfilter, self.fmdemod, self.sqblock, self.volblock)
		self.tb.connect(self.rx, (self.shifter, 1))
		self.audio_disconnect_node = self.audio.connect(self.volblock)
		self.tb.unlock() 
		self.chanover.change_active(True)
		print 'ON'

	def off(self):
		ModeShell.off(self)
		self.tb.lock()
		if self.shiftsrc is not None:
			try:
				self.tb.disconnect(self.rx, (self.shifter, 1))
				self.tb.disconnect(self.shiftsrc, (self.shifter, 0))
				self.tb.disconnect(self.shifter, self.decfilter)
				self.tb.disconnect(self.decfilter, self.fmdemod)
				self.tb.disconnect(self.fmdemod, self.sqblock)
				self.tb.disconnect(self.sqblock, self.volblock)
			except:
				pass
		if self.audio_disconnect_node is not None:
			self.audio_disconnect_node.disconnect()
			self.audio_disconnect_node = None
		self.tb.unlock()
		self.chanover.change_active(False)
		print 'OFF'
