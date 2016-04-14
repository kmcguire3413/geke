"""
	"... I find then a law, that is evil is present with me, the one who wills to do good. ..." (Romans 7, NKJV)
"""

from PyQt4 import QtCore as qtcore4
from PyQt4 import QtGui as qtgui4
import PyQt4 as pyqt4

from gnuradio import gr
from gnuradio import blocks, analog, filter, qtgui, audio, fft

import types
import math
import numpy
import cmath

from gnuradio import uhd

import lib.qfastfft as qfastfft
import lib.yaesu.chanoverview as chanoverview
import lib.qlcdnumberadjustable as qlcdnumberadjustable
import lib.yaesu.mode_am as mode_am
import lib.yaesu.mode_fm as mode_fm

class Limiter(gr.sync_block):
	"""
	A block that applies a complex number magnitude limiting value
	and performs a multiplications afterwards.
	"""
	def __init__(self):
		gr.sync_block(
			self, 
			input_signature=[numpy.complex64], 
			output_signature=[numpy.complex64]
		)
		self.mulval = 0.0
		self.limval = 0.0

	def work(noutput_items, input_items, output_items):
		if len(input_items) != 1:
			raise Exception('The number of input items should be one only.')
		out = numpy.fmin(out, self.limval)
		out = numpy.multiply(input_items[0], self.mulval)
		output_items[:] = out

	def set_mulval(mulval):
		self.mulval = mulval

	def set_limval(limval):
		self.limval = limval

class BlockMultipleAdd:
	class DisconnectNode:
		def __init__(self):
			pass

		def disconnect(self):
			self.am.disconnect(self.rxblock)

	def __init__(self, tb, block, limit=None, bcomplex=False):
	"""
		The limit is the maximum output magnitude from this block.
	"""
		self.bcomplex = bcomplex
		self.tb = tb
		self.audio_sink = block
		self.ins = []
		self.adds = []
		self.pwrcal = 

	def recalpwrpri(self):
		tot = 0.0
		for x in xrange(0, len(self.ins)):
			ain = self.ins[x]
			tot += ain[3].get_value()
		for x in xrange(0, len(self.ins)):
			ain = self.ins[x]
			self.ins[x][0].set_mulval(ain.get_value() / tot)

	def tick(self):
		# Recalculate power for power priorities.
		self.recalpwrpri()

	def connect(self, rxblock, pwrprimon=None):
		if rxblock in self.ins:
			return False
		self.__disconnect_all()
		if pwrprimon is not None:
			moder = Limiter()
			moder.set_limval(1.0)
			moder.set_mulval(0.0)
			self.ins.append([
				moder, None, rxblock, pwrprimon
			])
			self.tbconnect(rxblock, moder, 'RXBLOCKMODER')
		else:
			self.ins.append([rxblock, None, None, pwrprimon])
		dnode = BlockMultipleAdd.DisconnectNode()
		dnode.rxblock = rxblock
		dnode.am = self
		self.__connect_all()
		return dnode

	def disconnect(self, rxblock):
		self.__disconnect_all()
		for x in xrange(0, len(self.ins)):
			if self.ins[x][0] is rxblock:
				self.ins.pop(x)
				break
		self.__connect_all()

	def __disconnect_all(self):
		self.tb.lock()
		'''try:
			self.tbdisconnect(self.throttle, self.audio_sink, 'A')
		except:
			# This is okay to happen. It will not be connected
			# the very first time and we support recurrent calling
			# of this function for safety.
			pass
		'''
		for x in xrange(0, len(self.ins)):
			if x == 0:
				try:
					self.tbdisconnect(self.ins[x][0], self.block_sink, 'B')
				except:
					pass
			else:
				try:
					self.tbdisconnect(self.ins[x][1], self.ins[x-1][1], 'C')
				except:
					pass
				if self.ins[x][1] is not None:
					try:
						self.tbdisconnect(self.ins[x][0], self.ins[x][1], 'D')
					except:
						pass
		self.tb.unlock()

	def tbdisconnect(self, a, b, tag):
		print 'disconnect [%s] %s ---> %s' % (tag, a, b)
		self.tb.disconnect(a, b)

	def tbconnect(self, a, b, tag):
		print 'connect [%s] %s ---> %s' % (tag, a, b)
		self.tb.connect(a, b)

	def __connect_all(self):
		self.tb.lock()
		for x in xrange(0, len(self.ins)):
			if x == len(self.ins) - 1:
				self.ins[x][1] = None
			else:
				if self.ins[x][1] is None:
					if self.bcomplex:
						self.ins[x][1] = blocks.add_ff()
					else:
						self.ins[x][1] = blocks.add_cc()
					self.ins[x][1].set_min_noutput_items(8192 * 32)
		print 'graph', self.ins
		if len(self.ins) == 0:
			self.tb.unlock()
			return True
		if len(self.ins) == 1:
			#self.tbconnect(self.throttle, self.audio_sink, 'Z2')
			self.tbconnect(self.ins[0][0], self.block_sink, 'Z1')
			self.tb.unlock()
			return True 
		#self.tbconnect(self.throttle, self.audio_sink, 'A')
		for x in xrange(0, len(self.ins)):
			if x == len(self.ins) - 1:
				# Do not connect across, but at a diagonal.
				self.tbconnect(self.ins[x][0], (self.ins[x-1][1], 1), 'C' + str(x))
			else:
				# Connect across, then connect down in preparation
				# for a connection from the next level up.
				if x == 0:
					self.tbconnect(self.ins[x][1], self.block_sink, 'F' + str(x))
				else:
					self.tbconnect(self.ins[x][1], (self.ins[x-1][1], 1), 'D' + str(x))
				self.tbconnect(self.ins[x][0], self.ins[x][1], 'E' + str(x))
		print 'DONE'
		self.tb.unlock()
		return True

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

		self.lmidr = qtgui4.QWidget(self)

		self.top = qtgui4.QWidget(self)
		self.middle = qfastfft.QFastFFT(tb=self.tb)
		self.qfft = self.middle
		self.left = qtgui4.QWidget(self.lmidr)
		self.right = qtgui4.QWidget(self.lmidr)

		self.left_upper = qtgui4.QWidget(self.right)
		self.right_upper = qtgui4.QWidget(self.right)

		self.left_bottom = qtgui4.QWidget(self.left)
		self.right_bottom = qtgui4.QWidget(self.left)

		self.mode_select = qtgui4.QComboBox()
		self.enable_channel = qtgui4.QPushButton("Toggle")

		self.mode_select.setParent(self.left_upper)
		self.enable_channel.setParent(self.left_upper)

		chan_count = 8
		self.q_map = chanoverview.ChanOverview(chan_count)	

		self.left_upper.setParent(self.left)
		self.left_bottom.setParent(self.left)
		self.middle.setParent(self.lmidr)
		self.q_map.setParent(self.left_upper)		

		self.q_map.move(0, 0)

		self.resize(1280, 800)

		self.right.move(0, 0)

		self.left.move(0, 0)
		self.middle.move(100, 0)
		self.top.move(0, 0)
		self.lmidr.move(0, 50)
		self.left_upper.move(0, 0)
		self.left_bottom.move(0, 125)
		self.right_upper.move(0, 0)
		self.right_bottom.move(0, 200)

		self.top.resize(1280, 50)

		yrem = 800 - 50

		self.lmidr.resize(1280, yrem)

		self.middle.resize(1280 - 100, 700)

		self.right.resize(0, 0)
		self.right_upper.resize(100, 100)	
		self.q_map.resize(100, 100)

		self.right_bottom.resize(150, 300)	

		self.mode_select.move(0, 100)
		self.mode_select.resize(50, 25)
		self.enable_channel.move(50, 100)
		self.enable_channel.resize(50, 25)

		self.left.resize(100, yrem)
		self.left_upper.resize(100, 120)
		self.left_bottom.resize(100, yrem - 300)

		self.right_upper.hide()
		self.right_bottom.hide()
		self.right.hide()		

		for k in ['AM', 'FM', 'SSB']:
			self.mode_select.addItem(k)

		def __enable_clicked():
			chan = self.get_cur_vchan()
			if chan.is_on():
				chan.off()
			else:
				chan.on()

		self.enable_channel.clicked.connect(__enable_clicked)

		#quick_layout(self.left, [
		#	self.left_upper, self.left_bottom
		#], horizontal=False)

		self.q_ccndx = qtgui4.QLCDNumber(3)

		self.top.setMaximumSize(1100, 100)

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

		start_sps = 64000

		self.qfft.set_sps(start_sps)

		self.q_rx_cfreq = qlcdnumberadjustable.QLCDNumberAdjustable(label='RX FREQ', digits=12, signal=change_freq, xdef=101900000)
		self.q_rx_gain = qlcdnumberadjustable.QLCDNumberAdjustable(label='RX GAIN', digits=2, signal=change_rxgain, xdef=0)
		self.q_rx_bw = qlcdnumberadjustable.QLCDNumberAdjustable(label='RX BW', digits=9, signal=change_bw, xdef=63500)
		self.q_rx_sps = qlcdnumberadjustable.QLCDNumberAdjustable(label='RX SPS', digits=4, mul=16000, signal=change_sps, xdef=start_sps)

		self.q_tx_cfreq = qlcdnumberadjustable.QLCDNumberAdjustable(label='TX FREQ', digits=12, signal=change_freq, xdef=101900000)
		self.q_tx_gain = qlcdnumberadjustable.QLCDNumberAdjustable(label='TX GAIN', digits=2, signal=change_rxgain, xdef=0)
		self.q_tx_bw = qlcdnumberadjustable.QLCDNumberAdjustable(label='TX BW', digits=9, signal=change_bw, xdef=63500)
		self.q_tx_sps = qlcdnumberadjustable.QLCDNumberAdjustable(label='TX SPS', digits=4, mul=16000, signal=change_sps, xdef=start_sps)

		self.q_vol = qlcdnumberadjustable.QLCDNumberAdjustable(label='VOL', digits=2, signal=change_vol, xdef=50)
		self.q_chan = qlcdnumberadjustable.QLCDNumberAdjustable(label='CHAN', digits=2, signal=change_chan, xdef=0, max=chan_count - 1)

		self.top.lay = quick_layout(self.top, [
			self.q_rx_cfreq, self.q_rx_gain, self.q_rx_bw, self.q_rx_sps,
			self.q_tx_cfreq, self.q_tx_gain, self.q_tx_bw, self.q_tx_sps,
		])

		'''
			Initialize the independent RX source and TX sink or emulate them as being
			independent if only half-duplex.
		'''
		self.rx = uhd.usrp_source(device_addr='', stream_args=uhd.stream_args('fc32'))
		self.rx.set_center_freq(self.q_rx_cfreq.get_value())
		self.rx.set_bandwidth(self.q_rx_bw.get_value())
		self.rx.set_gain(0)
		self.rx.set_antenna('RX2')
		self.rx.set_samp_rate(self.q_rx_sps.get_value())

		self.btx = uhd.usrp_sink(device_addr='', stream_args=uhd.stream_args('fc32'))
		self.btx.set_center_freq(self.q_tx_cfreq.get_value())
		self.btx.set_bandwidth(self.q_tx_bw.get_value())
		self.btx.set_gain(0)
		self.btx.set_antenna('TX/RX')
		self.btx.set_samp_rate(self.q_tx_sps.get_value())

		self.tx = BlockMultipleAdd(self.tb, self.btx, limit=0.75, bcomplex=True)

		'''
		samps = []
		limit = int(start_sps)
		for x in xrange(0, limit):
			a = abs(math.sin((float(x) / float(start_sps)) * 1000.0 * math.pi * 2.0))
			theta = (float(x) / float(start_sps)) * 5000.0 * math.pi * 2.0
			samps.append(cmath.rect(a, theta))

		self.rx_noise = analog.fastnoise_source_c(analog.GR_GAUSSIAN, 0.7)
		self.rx_add = blocks.add_cc()
		self.rx_vsrc = blocks.vector_source_c(samps, True)
		#self.rx_file = blocks.file_sink(8, '/home/kmcguire/dump.base')
		self.rx = blocks.throttle(8, start_sps)

		#self.tb.connect(self.rx, self.rx_file)
		self.tb.connect(self.rx_vsrc, (self.rx_add, 0))
		self.tb.connect(self.rx_noise, (self.rx_add, 1))
		self.tb.connect(self.rx_add, self.rx)
		'''

		self.middle.set_src_blk(self.rx)
		self.middle.change(4096, 1024)

		self.tb.start()

		self.vchannels = []

		self.audio_sink = BlockMultipleAdd(self.tb, audio.sink(16000, '', True))
		self.audio_source = audio.source(16000)

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
				xself.q_map.set_chan_squelch(self.ndx, squelch)

			def __change_active(self, active):
				self.active = active 
				xself.q_map.set_chan_active(self.ndx, active)

			def __change_center_freq(self, center_freq):
				xself.qfft.set_center_freq(self.ndx, center_freq)
				xself.qfft.set_center_active(self.ndx, self.active)

			def __change_width(self, width_hz):
				xself.qfft.set_center_width(self.ndx, width_hz)

			chanover = ChanOverProxy()
			chanover.ndx = x
			chanover.active = False
			chanover.change_volume = types.MethodType(__change_volume, chanover)
			chanover.change_squelch = types.MethodType(__change_squelch, chanover)
			chanover.change_active = types.MethodType(__change_active, chanover)
			chanover.change_center_freq = types.MethodType(__change_center_freq, chanover)
			chanover.change_width = types.MethodType(__change_width, chanover)

			block = mode_am.AM(self.tb, self.rx, self.tx, self.audio_sink, self.audio_source, chanover)
			# The `start_sps` is needed as the control can not be accurately read
			# until later even though it has been set with this value.
			block.update(0.0, 0.0, float(start_sps), float(start_sps))

			self.vchannels.append(block)


		def _mode_change(index):
			modes = {
				'FM': mode_fm,
				'AM': mode_am,
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


		for chan in self.vchannels:
			left = chan.get_left()
			right = chan.get_right()
			left.setParent(self.left_bottom)
			right.setParent(self.right_bottom)
			left.move(0, 0)
			right.move(0, 0)
			left.resize(100, self.left_bottom.height())
			left.hide()
			right.hide()

		self.cur_chan = 0
		self.set_cur_vchan(0)

	def get_cur_vchan(self):
		return self.vchannels[self.cur_chan]

	def set_cur_vchan(self, ndx):
		chan = self.vchannels[self.cur_chan]
		chan.get_left().hide()
		chan.get_right().hide()
		self.cur_chan = int(ndx)
		self.q_map.set_chan_current(ndx % len(self.vchannels))
		chan = self.vchannels[self.cur_chan]
		print '$$1', chan.get_left().show()
		print '$$2', chan.get_right().show()