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

class AM:
	def __init__(self, tb, rx, audio, chanover):
		self.left = qtgui4.QWidget()
		self.right = qtgui4.QWidget()

		self.chanover = chanover
		self.tb = tb
		self.rx = rx
		self.audio = audio
		self.active = False

		def change_volume(value):
			chanover.change_volume(value)

		def change_squelch(value):
			chanover.change_squelch(value)

		self.freq = qlcdnumberadjustable.QLCDNumberAdjustable(label='CENTER FREQUENCY HZ', digits=9, xdef=0)
		self.cutoff = qlcdnumberadjustable.QLCDNumberAdjustable(label='FREQ CUTOFF HZ', digits=6, xdef=1000)
		self.oob_atten = qlcdnumberadjustable.QLCDNumberAdjustable(label='OOB-BAND ATTENUATE DB', digits=3, max=100, xdef=2)
		self.oob_width = qlcdnumberadjustable.QLCDNumberAdjustable(label='OOB-BAND WIDTH HZ', digits=6, xdef=1000)
		self.audio_passband = qlcdnumberadjustable.QLCDNumberAdjustable(label='AUDIO PASSBAND', digits=6, xdef=5000)
		self.audio_cutoff = qlcdnumberadjustable.QLCDNumberAdjustable(label='AUDIO CUTOFF', digits=6, xdef=1000)
		self.gain = qlcdnumberadjustable.QLCDNumberAdjustable(label='GAIN DB', digits=3, max=100, xdef=20)
		self.vol = qlcdnumberadjustable.QLCDNumberAdjustable(label='VOLUME', digits=3, xdef=50, max=100, signal=change_volume)
		self.isps = qlcdnumberadjustable.QLCDNumberAdjustable(label='SPS', digits=6, xdef=50000, max=1000000)
		self.sq = qlcdnumberadjustable.QLCDNumberAdjustable(label='SQUELCH', digits=3, xdef=50, max=100, signal=change_squelch)

		self.left.lay = quick_layout(self.left, [
			self.freq, self.cutoff, self.oob_atten, self.oob_width,
			self.audio_passband, self.audio_cutoff, self.gain, self.vol, self.sq,
			self.isps
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

		freq = self.freq.get_value()
		audio_passband = self.audio_passband.get_value()
		audio_cutoff = self.audio_cutoff.get_value()
		cutoff = self.cutoff.get_value()
		oob_atten = self.oob_atten.get_value()
		oob_width = self.oob_width.get_value()
		gain = self.gain.get_value()
		vol = self.vol.get_value()
		sq = self.sq.get_value()
		isps = self.isps.get_value()

		taps = filter.firdes.low_pass(gain, sps, cutoff, oob_width, filter.firdes.WIN_BLACKMAN)

		self.tb.lock()

		if getattr(self, 'resampler', None) is None:
			self.resampler = filter.fractional_resampler_cc(
				0.5,
				float(sps) / float(isps)
			)
		else:
			self.resampler.set_resamp_ratio(sps / audiosps)

		if getattr(self, 'shift_filter', None) is not None:
			self.tb.disconnect(self.resampler, self.shift_filter)
			self.tb.disconnect(self.shift_filter, self.demod)
		
		# Can not unlock before demod is connected.
		if getattr(self, 'demod', None) is None:
			# This audio SPS need to be adjustable, but to reduce development
			# time it is being hard coded as 1600 globally.
			self.demod = analog.am_demod_cf(
				int(isps), 
				int(float(isps) / 16000.0), 
				int(audio_passband), 
				int(audio_passband + audio_cutoff)
			)
			#self.tb.connect(self.demod, self.audio)
			

		#print 'resampler:%s demod:%s audio:%s' % (self.resampler, self.demod, self.audio)

		freq = 1000
		print 'len(taps):%s freq:%s sps:%s' % (len(taps), freq, sps)

		# ERROR... dont recreate unless mandatory
		# TODO .... dont recreate if sps == self.last_sps
		# WARNING... dont recreate unless required
		self.shift_filter = filter.freq_xlating_fir_filter_ccf(
			1, taps, freq, sps
		)

		print '@@@@@@'

		self.null_sink = blocks.null_sink(4)
		self.null_source = blocks.null_source(4)

		#self.tb.connect(self.null_source, self.audio)

		print '######'

		self.audio = (self.audio[0], 0)

		if self.active:
			self.on()
		else:
			self.off()
		
		self.tb.unlock()

		print '!!!!!!'

		self.last_sps = sps

	def is_on(self):
		return self.active

	def on(self):
		if self.active:
			return
		self.active = True
		self.tb.lock()
		self.tb.connect(self.rx, self.resampler, self.shift_filter, self.demod, self.null_sink)
		self.tb.unlock() 
		self.chanover.change_active(True)

	def off(self):
		if not self.active:
			return
		self.active = False
		self.tb.lock()
		self.tb.disconnect(self.rx, self.resampler)
		self.tb.disconnect(self.resampler, self.shift_filter)
		self.tb.disconnect(self.shift_filter, self.demod)
		self.tb.disconnect(self.demod, self.null_sink)
		self.tb.unlock()
		self.chanover.change_active(False)

	def get_left(self):
		return self.left 

	def get_right(self):
		return self.right

	def deinit(self):
		pass