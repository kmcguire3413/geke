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
import time
import sys
import threading

from gnuradio import uhd

import lib.debug as debug
import lib.qfastfft as qfastfft
import lib.yaesu.chanoverview as chanoverview
import lib.qlcdnumberadjustable as qlcdnumberadjustable
import lib.yaesu.mode_am as mode_am
import lib.yaesu.mode_fm as mode_fm

class OneShot(gr.sync_block):
	"""
	A block that emits a specific value until provided with
	samples which then emits those samples and afterwards 
	provides zeros. This block allows the ability to inject
	values into the stream disjointly.
	"""
	def __init__(self, dtype, value):
		gr.sync_block.__init__(self, 'PyOneShot', in_sig=[], out_sig=[numpy.dtype(dtype)])
		self.tosend = value
		self.needsend = False
		self.empty = ''
		self.callcount = 0
		self.last_t = time.time()
		self.start_t = time.time()

	def send(self):
		self.needsend = True

	def work(self, input_items, output_items):
		self.callcount += 1
		needout = len(output_items[0])

		if time.time() - self.last_t > 5:
			self.last_t = time.time()
			cps = self.callcount / (time.time() - self.start_t)
			print 'cps is %s while total time is %s and call count is %s' % (cps, time.time() - self.start_t, self.callcount)

		if len(self.empty) < needout:
			print 'empty', needout
			self.empty = numpy.array([0] * needout)

		if self.needsend:
			send = self.tosend
			print 'needout:%s len(send):%s' % (needout, len(send))
			output_items[0][:] = numpy.concatenate((send, self.empty[0:needout - len(send)]))
			self.needsend = False
			return needout

		output_items[0][:] = self.empty[0:needout]
		return needout

class Limiter(gr.sync_block):
	"""
	A block that applies a complex number magnitude limiting value
	and performs a multiplications afterwards.
	"""
	def __init__(self):
		gr.sync_block.__init__(self, 'PyLimiter', in_sig=[numpy.dtype(numpy.complex64)], out_sig=[numpy.dtype(numpy.complex64)])
		self.mulval = 0.0
		self.limval = 0.0
		self.count = 0

	def work(self, input_items, output_items):
		self.count += 1
		#print 'working in[0].real[0]:%s' % input_items[0].real[0] 
		if len(input_items) != 1:
			raise Exception('The number of input items should be one only.')
		out = input_items[0]
		out = numpy.fmin(out, self.limval)
		out = numpy.multiply(out, self.mulval)
		if self.count % 1000 == 0:
			self.count = 0
			print 'DBG:LIMITER<%s> out.real[0]:%f out.imag[0]:%f limval:%s mulval:%s' % (self, out.real[0], out.imag[0], self.limval, self.mulval)
		output_items[0][:] = out
		return len(out)

	def set_mulval(self, mulval):
		self.mulval = mulval

	def set_limval(self, limval):
		self.limval = limval

class LimiterMultiplexer(gr.sync_block):
	"""
		But Jesus beheld them, and said unto them, With men this is impossible; but with God all things are possible.
	"""
	class DisconnectObject:
		def __init__(self, lm, xin):
			self.lm = lm
			self.xin = xin

		def disconnect(self):
			self.lm.disconnect_input(self.xin)

	def __init__(self, tb, dtype, dtsize, maxinputs):
		gr.sync_block.__init__(self, 'PyCombiner', in_sig=[numpy.dtype(dtype)] * maxinputs, out_sig=[numpy.dtype(dtype)])
		self.limvals = [1.0] * maxinputs
		self.mulvals = [0.0] * maxinputs
		self.mlimstage = True
		self.dtype = numpy.dtype(dtype)
		self.input_blocks = [None] * maxinputs
		self.tb = tb
		self.null_src = blocks.null_source(dtsize)
		self.mon = [None] * maxinputs
		for indx in xrange(0, len(self.input_blocks)):
			self.input_blocks[indx] = self.null_src
			self.tb.connect(self.null_src, (self, indx))

	def tick(self):
		s = 0.0
		for x in xrange(0, len(self.input_blocks)):
			if self.mon[x] is not None:
				s = s + self.mon[x].get_value()
		for x in xrange(0, len(self.input_blocks)):
			if s == 0.0 or self.mon[x] is None:
				r = 0.0
			else:
				r = self.mon[x].get_value() / s
			self.mulvals[x] = r
			#print 'mulvals dtype:%s x:%s r:%s' % (self.dtype, x, self.mulvals[x])

	def disconnect_all_inputs(self):
		self.tb.lock()
		for blk in self.input_blocks:
			self.tb.disconnect(blk, self)
		self.tb.unlock()

	def disconnect_input(self, f):
		self.tb.lock()
		found = False
		for x in xrange(0, len(self.input_blocks)):
			if self.input_blocks[x] is f:
				self.input_blocks[x] = None
				self.tb.disconnect(f, (self, x))
				self.input_blocks[x] = self.null_src
				self.tb.connect(self.null_src, (self, x))
				self.mon[x] = None
				found = True
				break
		if not found:
			raise Exception('The block could not be found.')
		self.tb.unlock()

	def connect(self, txblock, pwrprimon=None, lim=1.0):
		return self.connect_input(txblock, pwrprimon=pwrprimon, lim=lim)

	def get_free_input_index(self):
		for x in xrange(0, len(self.input_blocks)):
			if self.input_blocks[x] is self.null_src:
				return x
		return None

	def connect_input(self, f, pwrprimon=None, lim=1.0):
		self.tb.lock()
		indx = self.get_free_input_index()
		self.tb.disconnect(self.input_blocks[indx], (self, indx), guard=True)
		self.input_blocks[indx] = f
		self.mon[indx] = pwrprimon
		self.limvals[indx] = lim
		self.tb.connect(f, (self, indx))
		self.tb.unlock()
		return LimiterMultiplexer.DisconnectObject(self, f)

	def connect_output(self, into):
		self.tb.lock()
		self.tb.connect(self, into)
		self.tb.unlock()

	def work(self, input_items, output_items):
		if self.mlimstage:
			for x in xrange(0, len(input_items)):
				try:
					if self.input_blocks[x] is self.null_src:
						continue
				except Exception as e:
					print 'x:%s len(input_items):%s len(input_blocks):%s' % (x, len(input_items), len(self.input_blocks))
					raise e
				ia = input_items[x]
				numpy.fmin(ia, self.limvals[x], ia)
				numpy.multiply(ia, self.mulvals[x], ia)
				input_items[x] = ia

		cur = None
		for x in xrange(0, len(input_items)):
			if self.input_blocks[x] is self.null_src:
				continue
			if cur is None:
				cur = input_items[x]
			else:
				numpy.add(cur, input_items[x], cur)
		bsize = len(output_items[0])
		if cur is None:
			output_items[0][:] = numpy.zeros(bsize, self.dtype)
		else:
			output_items[0][:] = cur
		return bsize

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
	def update_all_channels(self):
		self.tb.lock()
		for channel in self.vchannels:
			channel.update(
				self.q_rx_cfreq.get_value(), 
				self.q_tx_cfreq.get_value(), 
				self.q_rx_sps.get_value(), 
				self.q_tx_sps.get_value()
			)
		self.tb.unlock()

	def __init__(self):
		qtgui4.QWidget.__init__(self)
		self.tb = gr.top_block()

		self.tb.lockdepth = 0
		self.tb.lastunlock = 0

		# TODO: see if speed locking can still actually lock
		#       but just use no timeout
		#
		# INFO: the timeout is a workaround for the USRP which
		#       can not handle the fast locking and unlocking
		def __checkdelaylocking(self):
			if time.time() - self.tb.lastunlock < 1.0:
				time.sleep(0.1)
			self.tb.lastunlock = time.time()

		def __unlock(self):
			tident = threading.current_thread().ident
			print 'top_block unlock called by thread:%s' % tident
			self.lockdepth -= 1
			if self.lockdepth == 0:
				print 'UNLOCKED'
				self.old_unlock()

		def __lock(self):
			tident = threading.current_thread().ident
			print 'top_block LOCK called by thread:%s' % tident
			if self.lockdepth == 0:
				time.sleep(0.1)
				self.old_lock()
				time.sleep(0.1)
			self.lockdepth += 1

		def __connect(self, *args):
			tident = threading.current_thread().ident
			for x in xrange(1, len(args)):
				a = args[x - 1]
				b = args[x]
				sys.stderr.write('CONNECT %s -> %s\n' % (a, b))
			self.old_connect(*args)

		def __disconnect(self, a, b, guard=False):
			self.old_disconnect(a, b)
			sys.stderr.write('DISCONNECT %s -> %s\n' % (a, b))
			#if guard is False:
			#	raise Exception('@@@')

		setattr(self.tb, 'old_disconnect', self.tb.disconnect)
		setattr(self.tb, 'disconnect', types.MethodType(__disconnect, self.tb))
		setattr(self.tb, 'old_unlock', self.tb.unlock)
		setattr(self.tb, 'unlock', types.MethodType(__unlock, self.tb))
		setattr(self.tb, 'old_lock', self.tb.lock)
		setattr(self.tb, 'lock', types.MethodType(__lock, self.tb))
		setattr(self.tb, 'old_connect', self.tb.connect)
		setattr(self.tb, 'connect', types.MethodType(__connect, self.tb))

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

		chan_count = 4
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

		for k in ['AM', 'FM']:
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

		def change_freq(dev, value):
			dev.set_center_freq(value)
			self.update_all_channels()

		def change_gain(dev, value):
			# TODO: check maximum gain levels of device
			#       used and also check since they are
			#       different per RX and TX
			if value > 73:
				# OK, for USRP B200
				value = 73
			dev.set_gain(value)
			self.update_all_channels()
		
		def change_bw(dev, value):
			dev.set_bandwidth(value)
			self.update_all_channels()
		
		def change_sps(dev, value):
			print 'SPS SET for %s to %s' % (dev, value)
			dev.set_samp_rate(value)
			self.update_all_channels()

		def change_vol(value):
			pass

		def change_chan(value):
			self.set_cur_vchan(value)

		# TODO: match below in controls for default to reduce programmer bugs
		start_sps = 16000 * 4

		self.qfft.set_sps(start_sps)

		self.q_rx_cfreq = qlcdnumberadjustable.QLCDNumberAdjustable(label='RX FREQ', digits=12, signal=lambda v: change_freq(self.rx, v), xdef=146410000)
		self.q_rx_gain = qlcdnumberadjustable.QLCDNumberAdjustable(label='RX GAIN', digits=2, signal=lambda v: change_gain(self.rx, v), xdef=70)
		self.q_rx_bw = qlcdnumberadjustable.QLCDNumberAdjustable(label='RX BW', digits=9, signal=lambda v: change_bw(self.rx, v), xdef=63500)
		self.q_rx_sps = qlcdnumberadjustable.QLCDNumberAdjustable(label='RX SPS', digits=4, mul=16000, signal=lambda v: change_sps(self.rx, v), xdef=4)

		self.q_tx_cfreq = qlcdnumberadjustable.QLCDNumberAdjustable(label='TX FREQ', digits=12, xdef=146410000, signal=lambda v: change_freq(self.btx, v))
		self.q_tx_gain = qlcdnumberadjustable.QLCDNumberAdjustable(label='TX GAIN', digits=2, xdef=0, signal=lambda v: change_gain(self.btx, v))
		self.q_tx_bw = qlcdnumberadjustable.QLCDNumberAdjustable(label='TX BW', digits=9, xdef=63500, signal=lambda v: change_bw(self.btx, v))
		self.q_tx_sps = qlcdnumberadjustable.QLCDNumberAdjustable(label='TX SPS', digits=4, mul=16000, xdef=4, signal=lambda v: change_sps(self.btx, v))

		self.q_vol = qlcdnumberadjustable.QLCDNumberAdjustable(label='VOL', digits=2, signal=change_vol, xdef=50)
		self.q_tx_pwr_max = qlcdnumberadjustable.QLCDNumberAdjustable(label='TX PWR MAX', digits=3, signal=change_vol, xdef=50, max=100)
		self.q_chan = qlcdnumberadjustable.QLCDNumberAdjustable(label='CHAN', digits=2, signal=change_chan, xdef=0, max=chan_count - 1)

		self.top.lay = quick_layout(self.top, [
			self.q_rx_cfreq, self.q_rx_gain, self.q_rx_bw, self.q_rx_sps,
			self.q_tx_cfreq, self.q_tx_gain, self.q_tx_bw, self.q_tx_sps,
			self.q_vol, self.q_chan, self.q_tx_pwr_max
		])

		'''
			Initialize the independent RX source and TX sink or emulate them as being
			independent if only half-duplex.
		'''
		self.rx = uhd.usrp_source(device_addr='', stream_args=uhd.stream_args('fc32'))
		self.rx.set_center_freq(self.q_rx_cfreq.get_value())
		self.rx.set_bandwidth(self.q_rx_bw.get_value())
		self.rx.set_gain(73)
		self.rx.set_antenna('RX2')
		self.rx.set_samp_rate(self.q_rx_sps.get_value())

		self.btx = uhd.usrp_sink(device_addr='', stream_args=uhd.stream_args('fc32'))
		self.btx.set_center_freq(self.q_tx_cfreq.get_value())
		self.btx.set_bandwidth(self.q_tx_bw.get_value())
		self.btx.set_gain(1)
		self.btx.set_antenna('TX/RX')
		self.btx.set_samp_rate(self.q_tx_sps.get_value())
		
		#self.btx = debug.Debug(numpy.dtype(numpy.complex64), tag='USRPTX')

		#self.btx = blocks.file_sink(8, '/home/kmcguire/dump.test')

		self.tx = LimiterMultiplexer(tb=self.tb, dtype=numpy.complex64, dtsize=8, maxinputs=8)
		self.tb.connect(self.tx, self.btx)

		def __tick_tx():
			# This tick allows the transmit multiplexer to calculate
			# power allocates and adjust the limiter and gates so that
			# each channel can transmit using a certain percentage of
			# the total avaliable power without flucuations. This ticks
			# at a low speed.
			self.tx.tick()
			# Also, the audio sink is multiplexed exactly the same, but it
			# uses a float-32, of of this moment, type in the stream instead
			# of a complex-64 item type.
			self.audio_sink.tick()

		def __tick_qmap():
			# This allows the channel overview to perform any needed
			# updates. It ticks at a moderate speed.
			self.q_map.tick()

		self.tx_tick = qtcore4.QTimer(self)
		self.tx_tick.timeout.connect(__tick_tx)
		self.tx_tick.start(1000)

		self.qmap_tick = qtcore4.QTimer(self)
		self.qmap_tick.timeout.connect(__tick_qmap)
		self.qmap_tick.start(250)


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
		self.middle.change(512, 64)

		self.tb.start()	

		self.vchannels = []

		self.b = audio.sink(16000, '', True)

		self.audio_sink_base = audio.sink(16000) 
		self.audio_sink = LimiterMultiplexer(tb=self.tb, dtype=numpy.float32, dtsize=4, maxinputs=8)
		self.tb.connect(self.audio_sink, self.audio_sink_base)
		self.tb.connect(self.audio_sink, debug.Debug(xtype=numpy.dtype(numpy.float32), tag='FROM RX LAST BLOCK'))

		self.audio_source = audio.source(16000)
		#self.audio_source = blocks.file_source(4, '/home/kmcguire/')

		'''
			Configure the channels.
		'''
		xself = self
		self.tb.lock()
		for x in xrange(0, chan_count):
			self.q_map.set_chan_volume(x, 0.5)
			self.q_map.set_chan_active(x, False)
			self.q_map.set_chan_volume(x, 0.8)
			self.q_map.set_chan_audio_level(x, 0.0)			

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

			def __set_audio_strength_query_func(self, f):
				xself.q_map.set_audio_strength_query_func(self.ndx, f)

			chanover = ChanOverProxy()
			chanover.ndx = x
			chanover.active = False
			chanover.change_volume = types.MethodType(__change_volume, chanover)
			chanover.change_squelch = types.MethodType(__change_squelch, chanover)
			chanover.change_active = types.MethodType(__change_active, chanover)
			chanover.change_center_freq = types.MethodType(__change_center_freq, chanover)
			chanover.change_width = types.MethodType(__change_width, chanover)
			chanover.set_audio_strength_query_func = types.MethodType(__set_audio_strength_query_func, chanover)

			block = mode_am.AM(self.tb, self.rx, self.tx, self.audio_sink, self.audio_source, chanover, self.beep)
			# The `start_sps` is needed as the control can not be accurately read
			# until later even though it has been set with this value.
			block.update(self.q_rx_cfreq.get_value(), self.q_tx_cfreq.get_value(), float(start_sps), float(start_sps))

			self.vchannels.append(block)
		self.tb.unlock()

		def _mode_change(index):
			modes = {
				'FM': mode_fm,
				'AM': mode_am,
			}
			mode = self.mode_select.currentText()
			self.vchannels[self.cur_chan].deinit()
			self.vchannels[self.cur_chan].get_left().setParent(None)
			self.vchannels[self.cur_chan].get_right().setParent(None)
			print 'mode="%s"' % mode
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

		beep = []
		for x in xrange(0, 4000):
			theta = float(x) / 16000.0 * (1000.0 + float(x) * 0.20) * math.pi * 2.0
			beep.append(math.sin(theta))

		# A custom block may be well in this situation. Capable
		# of doing a one shot operation.
		self.uibeeper = OneShot(numpy.float32, numpy.array(beep))
		self.audio_sink.connect(self.uibeeper)

		self.cur_chan = 0
		self.set_cur_vchan(0)

	def beep(self):
		print 'BEEP BEEP BEEP'
		self.uibeeper.rewind()

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