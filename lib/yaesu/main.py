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

class LimterMultiplexer(gr.sync_block):
	class DisconnectObject:
		def __init__(self, lm, xin):
			self.lm = lm
			self.xin = xin

		def disconnect(self):
			self.lm.disconnect_input(self.xin)

	def __init__(self, tb, dtype, dtsize, maxinputs):
		gr.sync_block.__init__(self, 'PyCombiner', in_sig=[numpy.dtype(dtype)] * maxinputs, out_sig=[numpy.dtype(dtype)])
		self.limvals = [0.0] * maxinputs
		self.mulvals = [0.0] * maxinputs
		self.mlimstage = True
		self.dtype = numpy.dtype(dtype)
		self.input_blocks = [None] * maxinputs
		self.tb = tb
		self.null_src = blocks.null_source(dtsize)
		for indx in xrange(0, len(self.input_blocks)):
			self.input_blocks[indx] = self.null_src
			self.tb.connect(self.null_src, (self, indx))

	def disconnect_all_inputs(self):
		self.tb.lock()
		for blk in self.input_blocks:
			self.tb.disconnect(blk, self)
		self.tb.unlock()

	def disconnect_input(self, f):
		self.tb.lock()
		for x in xrange(0, len(self.input_blocks)):
			if self.input_blocks[x] is f:
				self.input_blocks.pop(x)
				self.tb.disconnect(f, (self, x))
				self.input_blocks[x] = self.null_src
				self.tb.connect(self.null_src, (self, x))
				break
		self.tb.unlock()
		return LimterMultiplexer.DisconnectObject(self, f)

	def connect(self, f):
		return self.connect_input(f)

	def get_free_input_index(self):
		for x in xrange(0, len(self.input_blocks)):
			if self.input_blocks[x] is self.null_src:
				return x
		return None

	def connect_input(self, f):
		self.tb.lock()
		indx = self.get_free_input_index()
		self.tb.disconnect(self.input_blocks[indx], (self, indx))
		self.input_blocks[indx] = f
		self.tb.connect(f, (self, indx))
		self.tb.unlock()

	def connect_output(self, into):
		self.tb.lock()
		self.tb.connect(self, into)
		self.tb.unlock()

	def work(self, input_items, output_items):
		if self.mlimstage:
			for x in xrange(0, len(input_items)):
				if self.input_blocks[x] is self.null_src:
					continue
				ia = input_items[x]
				ia = numpy.fmin(ia, self.limvals[x])
				ia = numpy.multiply(ia, self.mulvals[x])
				input_items[x] = ia

		bsize = len(output_items[0])

		cur = numpy.zeros(bsize, self.dtype)
		for x in xrange(0, len(input_items)):
			if self.input_blocks[x] is self.null_src:
				continue
			numpy.add(cur, input_items[x], cur)

		output_items[0] = cur
		return len(cur)

class BlockMultipleAdd:
	"""
	Gracefully handles providing multiple outputs by addition to a single block
	that only supports a single input and supports limiting and power priority
	over float and complex streams.
	"""
	class DisconnectNode:
		def __init__(self):
			pass

		def disconnect(self):
			self.am.disconnect(self.txblock)

	def __init__(self, tb, block, throttle=None, limit=None, bcomplex=False):
		"""
		The limit is the maximum output magnitude from this block.
		"""
		self.bcomplex = bcomplex
		self.tb = tb
		self.block_sink = block
		if throttle is not None:
			if bcomplex:
				self.throttle = blocks.throttle(8, throttle)
			else:
				self.throttle = blocks.throttle(4, throttle)
			self.block_sink2 = self.block_sink
			self.block_sink = self.throttle
		else:
			self.throttle = None

		self.ins = []
		self.adds = []

	def recalpwrpri(self):
		tot = 0.0
		# TODO: this can be optimized better
		for x in xrange(0, len(self.ins)):
			ain = self.ins[x]
			if ain[3] is not None:
				tot += ain[3].get_value()
		for x in xrange(0, len(self.ins)):
			ain = self.ins[x]
			if ain[3] is not None:
				if tot == 0.0:
					# If no total then avoid division by zero below.
					self.ins[x][0].set_mulval(0.0)
				else:
					self.ins[x][0].set_mulval(ain[3].get_value() / tot)

	def tick(self):
		# Recalculate power for power priorities.
		self.recalpwrpri()

	def connect(self, txblock, pwrprimon=None):
		print 'CONNECT_ALL_MAP'
		for ain in self.ins:
			print ain

		for x in xrange(0, len(self.ins)):
			if self.ins[x][0] is txblock or self.ins[x][2] is txblock:
				return False
		self.__disconnect_all()
		if pwrprimon is not None:
			moder = Limiter()
			moder.set_limval(1.0)
			moder.set_mulval(0.0)
			self.ins.append([moder, None, txblock, pwrprimon])
		else:
			self.ins.append([txblock, None, None, pwrprimon])
		dnode = BlockMultipleAdd.DisconnectNode()
		dnode.txblock = txblock
		dnode.am = self
		self.__connect_all()		
		return dnode

	def disconnect(self, txblock):
		self.tb.lock()
		self.__disconnect_all()
		for x in xrange(0, len(self.ins)):
			# Check both basic TXBLOCK and also limited TXBLOCK
			#print '  check %s and %s against %s' % (self.ins[x][0], self.ins[x][3], txblock)
			if self.ins[x][0] is txblock or self.ins[x][2] is txblock:
				tmp = self.ins.pop(x)
				print '  found; removed', tmp
				break
		self.__connect_all()
		self.tb.unlock()

	def __disconnect_all(self):
		sys.stdout.flush()
		self.tb.lock()
		sys.stdout.flush()

		print 'DISCONNECT_ALL_MAP'
		for ain in self.ins:
			print ain

		try:
			if self.throttle is not None:
				self.tbdisconnect(self.throttle, self.block_sink2, 'A')
		except Exception as e:
			# This is okay to happen. It will not be connected
			# the very first time and we support recurrent calling
			# of this function for safety.
			print 'exception', e

		sys.stdout.flush()
		if len(self.ins) > 0:
			try:
				self.tbdisconnect(self.ins[0][1], self.block_sink, 'K1')
			except Exception as e:
				print 'exception', e, 0
			try:
				self.tbdisconnect(self.ins[0][0], self.block_sink, 'K2')
			except Exception as e:
				print 'exception', e, 0
			try:
				self.tbdisconnect(self.ins[0][0], (self.ins[0][1], 0), 'K3')
			except Exception as  e:
				print 'exception', e, 0

		for x in xrange(0, len(self.ins)):
			sys.stdout.flush()
			if x == 0:
				pass
			else:
				print '--', self.ins[x]
				# Try straight down.
				try:
					self.tbdisconnect(self.ins[x][1], self.ins[x-1][1], 'C')
					print 'straight across', x
				except Exception as e:
					print 'exception', e, x
				# Try across.
				try:
					self.tbdisconnect(self.ins[x][0], (self.ins[x][1], 0) , 'D')
					print 'across', x
				except Exception as e:
					print 'exception', e, x
				# Try straight down and across.
				try:
					self.tbdisconnect(self.ins[x][0], (self.ins[x - 1][1], 1) , 'H')
					print 'down and across', x
				except Exception as e:
					print 'exception', e, x

		# This breaks any limiter connections.
		for x in xrange(0, len(self.ins)):
			if self.ins[x][2] is not None:
				self.tbdisconnect(self.ins[x][2], self.ins[x][0], 'V')

		sys.stdout.flush()
		sys.stdout.flush()
		self.tb.unlock()
		sys.stdout.flush()

	def tbdisconnect(self, a, b, tag):
		sys.stdout.flush()
		self.tb.disconnect(a, b)

	def tbconnect(self, a, b, tag):
		sys.stdout.flush()
		self.tb.connect(a, b)

	def __connect_all(self):
		self.tb.lock()
		for x in xrange(0, len(self.ins)):
			if x == len(self.ins) - 1:
				self.ins[x][1] = None
			else:
				if self.ins[x][1] is None:
					if self.bcomplex is True:
						self.ins[x][1] = blocks.add_cc()
					else:
						self.ins[x][1] = blocks.add_ff()
					self.ins[x][1].set_min_noutput_items(8192)
		if len(self.ins) == 0:
 			self.tb.unlock()
			return True

		# Connect limiters that act like a normal block.
		for x in xrange(0, len(self.ins)):
			if self.ins[x][2] is not None:
				self.tbconnect(self.ins[x][2], self.ins[x][0], 'RXBLOCKMODER')

		# Special case #1 (single)
		if len(self.ins) == 1:
			if self.throttle is not None:
				self.tbconnect(self.throttle, self.block_sink2, 'Z2')
			self.tbconnect(self.ins[0][0], self.block_sink, 'Z1')
			self.tb.unlock()
			return True 

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
				self.tbconnect(self.ins[x][0], (self.ins[x][1], 0) , 'E' + str(x))
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

		def __disconnect(self, a, b):
			self.old_disconnect(a, b)
			sys.stderr.write('DISCONNECT %s -> %s\n' % (a, b))

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
			update_all_channels()
		
		def change_bw(dev, value):
			dev.set_bandwidth(value)
			update_all_channels()
		
		def change_sps(dev, value):
			dev.set_samp_rate(value)
			update_all_channels()

		def change_vol(value):
			pass

		def change_chan(value):
			self.set_cur_vchan(value)

		# TODO: match below in controls for default to reduce programmer bugs
		start_sps = 16000 * 4

		self.qfft.set_sps(start_sps)

		self.q_rx_cfreq = qlcdnumberadjustable.QLCDNumberAdjustable(label='RX FREQ', digits=12, signal=lambda v: change_freq(self.rx, v), xdef=146000000)
		self.q_rx_gain = qlcdnumberadjustable.QLCDNumberAdjustable(label='RX GAIN', digits=2, signal=lambda v: change_gain(self.rx, v), xdef=70)
		self.q_rx_bw = qlcdnumberadjustable.QLCDNumberAdjustable(label='RX BW', digits=9, signal=lambda v: change_bw(self.rx, v), xdef=63500)
		self.q_rx_sps = qlcdnumberadjustable.QLCDNumberAdjustable(label='RX SPS', digits=4, mul=16000, signal=lambda v: change_sps(self.rx, v), xdef=4)

		self.q_tx_cfreq = qlcdnumberadjustable.QLCDNumberAdjustable(label='TX FREQ', digits=12, xdef=146000000, signal=lambda v: change_freq(self.btx, v))
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

		self.tx = BlockMultipleAdd(self.tb, self.btx, limit=0.75, bcomplex=True)

		def __tick_tx():
			print 'ticking'
			self.tx.tick()

		self.tx_tick = qtcore4.QTimer(self)
		self.tx_tick.timeout.connect(__tick_tx)
		self.tx_tick.start(1000)

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
		self.audio_sink = LimterMultiplexer(tb=self.tb, dtype=numpy.float32, dtsize=4, maxinputs=4)
		self.tb.connect(self.audio_sink, self.audio_sink_base)

		self.audio_source = audio.source(16000)
		#self.audio_source = blocks.null_source(4)

		'''
			Configure the channels.
		'''
		self.tb.lock()
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