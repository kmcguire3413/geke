from PyQt4 import QtCore as qtcore4
from PyQt4 import QtGui as qtgui4
import PyQt4 as pyqt4

from gnuradio import gr
from gnuradio import blocks, analog, filter, qtgui, audio, fft

import types
import math

import lib.qfastfft as qfastfft
import lib.yaesu.chanoverview as chanoverview
import lib.qlcdnumberadjustable as qlcdnumberadjustable
import lib.yaesu.mode_am as mode_am

def quick_layout(widget, widgets, horizontal=True):
	if horizontal:
		layout = qtgui4.QHBoxLayout()
	else:
		layout = qtgui4.QVBoxLayout()
	for w in widgets:
		layout.addWidget(w)
	widget.setLayout(layout)
	return layout

class ChanOverProxy:
	pass

class YaesuBC(qtgui4.QWidget):
	def __init__(self):
		qtgui4.QWidget.__init__(self)
		self.tb = gr.top_block()

		self.overlay = qtgui4.QVBoxLayout()
		self.lmidr_lay = qtgui4.QGridLayout()

		self.lmidr = qtgui4.QWidget()
		self.lmidr.setLayout(self.lmidr_lay)

		self.top = qtgui4.QWidget()
		self.middle = qfastfft.QFastFFT(tb=self.tb)
		self.left = qtgui4.QWidget()
		self.right = qtgui4.QWidget()

		self.overlay.addWidget(self.top)
		self.overlay.addWidget(self.lmidr)		
		self.setLayout(self.overlay)

		self.lmidr_lay.addWidget(self.left, 0, 0)
		self.lmidr_lay.addWidget(self.middle, 0, 1)
		self.lmidr_lay.addWidget(self.right, 0, 2)

		self.right_lay = qtgui4.QVBoxLayout()

		self.right.setLayout(self.right_lay)

		self.left_upper = qtgui4.QWidget(self.right)
		self.right_upper = qtgui4.QWidget(self.right)

		self.left_bottom = qtgui4.QWidget()
		self.right_bottom = qtgui4.QWidget()

		self.mode_select = qtgui4.QComboBox()

		for k in ['AM', 'FM', 'SSB']:
			self.mode_select.addItem(k)

		#quick_layout(self.left, [
		#	self.left_upper, self.left_bottom
		#], horizontal=False)

		self.left_upper.setParent(self.left)
		self.left_bottom.setParent(self.left)

		def right_resizeEvent(xself, event):
			self.right_upper.setGeometry(0, 0, self.right_upper.width(), self.right_upper.height())
			self.right_bottom.setGeometry(0, self.right_upper.height(), self.right_bottom.width(), self.right_bottom.height())

		self.right.resizeEvent = types.MethodType(right_resizeEvent, self.right)
		right_resizeEvent(None, None)

		def left_resizeEvent(xself, event):
			self.left_upper.setGeometry(0, 0, self.left_upper.width(), self.left_upper.height())
			self.left_bottom.setGeometry(0, self.left_upper.height(), self.left_bottom.width(), self.left_bottom.height())

		self.left.resizeEvent = types.MethodType(left_resizeEvent, self.left)
		left_resizeEvent(None, None)

		'''
			The number of supported channels. This is arbitrary but
			helps to set an upper limit and give the channel view a
			static size in the user interface for design.
		'''
		chan_count = 8

		self.q_ccndx = qtgui4.QLCDNumber(3)
		self.q_map = chanoverview.ChanOverview(chan_count, 300, 200)

		self.resize(300 + 300 + 500, 700)
		self.top.setMaximumSize(1100, 100)
		self.lmidr.resize(300 + 300 + 500, 500)
		self.left.resize(300, 600)
		self.right.resize(300, 600)
		#self.left_upper.setWidth()
		self.right_upper.resize(300, 200)
		#self.left_bottom.resize(300, 200)

		def change_freq(value):
			self.rx.set_center_freq(value)

		def change_rxgain(value):
			if value > 73:
				value = 73
			self.rx.set_gain(value)
		
		def change_bw(value):
			self.rx.set_bandwidth(value)
		
		def change_sps(value):
			self.rx.set_samp_rate(value)

		def change_vol(value):
			pass

		def change_chan(value):
			self.set_cur_vchan(value)

		start_sps = 60000

		self.q_cfreq = qlcdnumberadjustable.QLCDNumberAdjustable(label='GHZ', digits=12, signal=change_freq, xdef=101900000)
		self.q_gain = qlcdnumberadjustable.QLCDNumberAdjustable(label='RXGAIN', digits=2, signal=change_rxgain, xdef=70)
		self.q_bw = qlcdnumberadjustable.QLCDNumberAdjustable(label='BANDWIDTH', digits=9, signal=change_bw, xdef=63500)
		self.q_sps = qlcdnumberadjustable.QLCDNumberAdjustable(label='SPS', digits=9, signal=change_sps, xdef=start_sps)
		self.q_vol = qlcdnumberadjustable.QLCDNumberAdjustable(label='VOL', digits=2, signal=change_vol, xdef=50)
		self.q_chan = qlcdnumberadjustable.QLCDNumberAdjustable(label='CHAN', digits=2, signal=change_chan, xdef=0, max=16)

		self.top.lay = quick_layout(self.top, [
			self.q_cfreq, self.q_gain, self.q_bw, self.q_sps, self.q_vol, self.q_chan
		])

		self.q_map.setParent(self.right_upper)

		#self.right.setStyleSheet('background-color: blue;')
		#self.right_bottom.setStyleSheet('background-color: yellow');
		#self.right_upper.setStyleSheet('background-color: green')
		#self.q_map.setStyleSheet('background-color: black;')	

		self.q_map.resize(300, 200)
		self.right_upper.resize(300, 200)
		self.right_bottom.resize(300, 300)

		quick_layout(self.right, [
			self.right_upper, self.right_bottom
		], horizontal=False)

		'''
			Selection of RX input.
		'''

		'''
		self.rx = uhd.usrp_source(device_addr='', stream_args=uhd.stream_args('fc32'))
		self.rx.set_center_freq(101900000)
		self.rx.set_bandwidth(63500)
		self.rx.set_gain(70)
		self.rx.set_antenna('RX2')
		self.rx.set_samp_rate(600000)
		'''

		#self.rx_noise = analog.fastnoise_source_c(analog.GR_GAUSSIAN, 1.0)
		#self.rx = analog.sig_source_c(600000, analog.GR_SIN_WAVE, 2000, 1.0)
		self.sigsrc = blocks.vector_source_c(
			[0.0, 1.0, 1.0, 0.0, 0.5, 0.5], True
		)
		self.rx = blocks.throttle(8, start_sps, True)
		self.tb.connect(self.sigsrc, self.rx)

		#self.rx = blocks.add_cc()
		#self.tb.connect(self.rx_noise, (self.rx, 0))
		#self.tb.connect(self.rx_sin, (self.rx, 1))

		self.middle.set_src_blk(self.rx)
		self.middle.change(64, 1024 * 100)

		self.tb.start()

		self.vchannels = []

		#self.audio_sink = audio.sink(16000, "", True)
		#self.audio_adder = blocks.add_ff()
		self.audio_adder = None

		#self.tb.connect(self.audio_adder, self.audio_sink)

		self.audio_out = []
		for x in xrange(0, chan_count):
			self.audio_out.append((self.audio_adder, x))

		'''
			Configure the channels.
		'''
		for x in xrange(0, chan_count):
			self.q_map.set_chan_volume(x, 0.5)
			self.q_map.set_chan_active(x, False)
			self.q_map.set_chan_volume(x, 0.8)
			self.q_map.set_chan_audio_level(x, 0.0)	

			xself = self		

			def __change_volume(self, volume):
				print 'set volume %s on channel %s' % (volume, self.ndx)
				xself.q_map.set_chan_volume(self.ndx, volume)

			def __change_squelch(self, squelch):
				xself.q_map.set_squelch(self.ndx, squelch)

			chanover = ChanOverProxy()
			chanover.ndx = x
			chanover.change_volume = types.MethodType(__change_volume, chanover)
			chanover.change_squelch = types.MethodType(__change_squelch, chanover)

			block = mode_am.AM(self.tb, self.rx, self.audio_out[x], chanover)
			# The `start_sps` is needed as the control can not be accurately read
			# until later even though it has been set with this value.
			block.update(start_sps)

			self.vchannels.append(block)


		def _mode_change(index):
			modes = {
				'FM': YaesuBC_FM,
				'AM': YaesuBC_AM,
				'SSB': YaesuBC_SSB,
			}
			mode = self.mode_select.currentText()
			self.vchannels[self.cur_chan].deinit()
			self.vchannels[self.cur_chan].get_left().setParent(None)
			self.vchannels[self.cur_chan].get_right().setParent(None)
			self.vchannels[self.cur_chan] = modes[mode]()
			chan = self.vchannels[self.cur_chan]
			left = chan.get_left()
			right = chan.get_right()
			left.setParent(self.left_bottom)
			right.setParent(self.right_bottom)
			left.move(0, 0)
			right.move(0, 0)	

		self.mode_select.currentIndexChanged.connect(_mode_change)

		self.left_upper.resize(100, 25)
		self.left_upper.lay = quick_layout(self.left_upper, [self.mode_select], horizontal=False)
		self.left_upper.lay.setSpacing(2)
		self.left_upper.lay.setMargin(0)

		for chan in self.vchannels:
			left = chan.get_left()
			right = chan.get_right()
			left.setParent(self.left_bottom)
			right.setParent(self.right_bottom)
			left.move(0, 0)
			right.move(0, 0)
			left.resize(300, 600)
			left.hide()
			right.hide()

		self.cur_chan = 0
		self.set_cur_vchan(0)

	def set_cur_vchan(self, ndx):
		chan = self.vchannels[self.cur_chan]
		#chan.get_left().hide()
		#chan.get_right().hide()
		self.cur_chan = ndx
		self.q_map.set_chan_current(ndx)
		chan = self.vchannels[self.cur_chan]
		print '$$1', chan.get_left().show()
		print '$$2', chan.get_right().show()