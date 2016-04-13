from PyQt4 import QtCore as qtcore4
from PyQt4 import QtGui as qtgui4
import PyQt4 as pyqt4

from gnuradio import gr
from gnuradio import blocks, analog, filter, qtgui, audio, fft

import lib.qlcdnumberadjustable as qlcdnumberadjustable

import geke

import numpy
import math

class QFastFFT(qtgui4.QWidget):
	class CenterMeta:
		pass

	def __init__(self, tb, fftlen=1024, parent=None):
		qtgui4.QImage.__init__(self, parent)

		self.fftsize = None
		#self.ylength = 1024.0
		self.fftlen = None		
		self.tb = tb
		self.queue = []
		self.src_blk = None

		self.paint_timer = qtcore4.QTimer(self)
		self.paint_timer.timeout.connect(self.__paintTick)
		self.paint_timer.start(1000 // 7)

		# Used to auto-adjust scale over multiple iterations.
		self.avg = (0.0, 1.0)
		self.ly = 0
		self.fft = None

		def __change_fftsize(pow2size):
			fftsize = 2 ** pow2size
			self.change(fftsize, self.fftlen)

		self.fftsize_pow2_select = qlcdnumberadjustable.QLCDNumberAdjustable(
			label='FFT Size', 
			digits = 2,
			xdef = 4,
			max = 16,
			signal = __change_fftsize
		)

		self.fftsize_pow2_select.setParent(self)
		self.fftsize_pow2_select.move(0, 0)
		self.fftsize_pow2_select.resize(100, 25)

		self.drawtop = 25

		self.centers = {}

	def get_center_meta(self, id):
		if self.centers.get(id, None) is None:
			meta = QFastFFT.CenterMeta()
			self.centers[id] = meta
			meta.freq = 0.0
			meta.width = 10.0
			meta.active = False

		return self.centers[id]

	def set_center_width(self, ndx, width_hz):
		meta = self.get_center_meta(ndx)
		meta.width = width_hz
		self.update()

	def set_center_freq(self, ndx, center_freq):
		meta = self.get_center_meta(ndx)
		meta.freq = center_freq
		self.update()
		print 'qfastfft center freq set to %s for id %s' % (center_freq, ndx)

	def set_center_active(self, ndx, active):
		meta = self.get_center_meta(ndx)
		meta.active = active
		self.update()

	def set_sps(self, sps):
		self.sps = sps

	def change(self, fftsize, fftlen):
		fftlen = 1024 * 5
		# TODO: change without clearing the buffer
		self.bmpbuf = bytearray('\x00\x00\x00\x00' * (fftsize * fftlen))

		self.img = qtgui4.QImage(self.bmpbuf, fftsize, fftlen, fftsize * 4, qtgui4.QImage.Format_RGB32)

		self.fftsize = fftsize
		self.fftlen = fftlen

		if self.src_blk is None:
			return

		self.tb.lock()
		if self.fft is not None:
			try:
				self.tb.disconnect(self.src_blk, self.fft)
			except:
				pass
			try:
				self.tb.disconnect(self.fft, slf.stv0)
			except:
				pass
			try:
				self.tb.disconnect(self.stv0, self.ctm)
			except:
				pass

		fft_filter = []
		for x in xrange(0, fftsize):
			fft_filter.append(math.sin(float(x) / float(fftsize) * math.pi))

		self.fft = fft.fft_vcc(fftsize, True, fft_filter, True, 4)
		self.stv0 = blocks.stream_to_vector(8, fftsize)
		self.ctm = blocks.complex_to_mag_squared(fftsize)
		self.reader = PyBlockHandler(fftsize=fftsize, blockcnt=1)
		self.reader.setVecHandler(self.__vec_handler)
		self.keep = blocks.keep_m_in_n(8, self.fftsize, self.fftsize * 2, 0)

		self.tb.connect(self.src_blk, self.keep, self.stv0, self.fft, self.ctm, self.reader)

		self.tb.unlock()

	def set_src_blk(self, blk):
		"""
		Set the GR source block to receive samples from. This relieves the source
		block or external logic from having to reconnect on changes to the blocks
		if needed.
		"""
		self.src_blk = blk

	def __vec_handler(self, vecs):
		for x in xrange(0, len(vecs)):
			self.queue.append(vecs[x])

	def __paintTick(self):
		self.update()

	def paintEvent(self, event):
		qp = qtgui4.QPainter(self)
		self.fast_paint_no_scroll(event, qp)
		#self.slow_paint_scroll(event)
		self.queue = []

		font = qtgui4.QFont()		

		for k in self.centers:
			meta = self.centers[k]

			pixperhz = float(self.width()) / float(self.sps)

			color = qtgui4.QColor()

			if meta.active:
				color.setRgbF(1.0, 0.0, 0.0, 1.0)
			else:
				color.setRgbF(1.0, 0.0, 0.0, 0.5)

			if meta.freq < 0.0:
				sign = -1.0
			else:
				sign = 1.0

			x = pixperhz * meta.freq + self.width() * 0.5 + sign * meta.width * pixperhz * 0.5

			fs = 10.0
			font.setPixelSize(fs)
			qp.setFont(font)			

			qp.drawRect(
				qtcore4.QRectF(
					x,
					self.drawtop,
					pixperhz * meta.width,
					self.height()
				)
			)

			qp.drawText(x + 1, self.drawtop, fs, 30, 0, '%s' % k)

		qp.end()


	def slow_paint_scroll(self, event):
		qpainter = qtgui4.QPainter(self)

		if self.width() < self.fftsize:
			vwidth = float(self.width())
		else:
			vwidth = float(self.fftsize)

		if self.height() < self.fftlen:
			vheight = float(self.height())
		else:
			vheight = float(self.fftlen)
		
		self.last_th = float(self.ly) / self.fftsize
		for z in xrange(0, len(self.queue)):
			vec = self.queue[z]
			self.avg = geke.system(self, vec, self.fftsize, self.avg, self.bmpbuf, vwidth)

		yw = float(self.height()) / float(self.fftlen)

		th = float(self.ly) / self.fftsize

		if self.last_th == th:
			self.last_th = th - 1

		if self.last_th > th:
			# The wraparound of the buffer causes this inversion which
			# we handle below by disjointing the split of both the source
			# and destination images into three pieces that can be swapped
			# around.
			invert = True
			lth = th
			cth = self.last_th
		else:
			invert = False
			lth = self.last_th
			cth = th

		tsrc = qtcore4.QRectF(0, 0, vwidth, lth)
		msrc = qtcore4.QRectF(0, lth, vwidth, cth - lth)
		esrc = qtcore4.QRectF(0, cth, vwidth, float(self.fftlen) - cth)

		swidth = float(self.width())

		def dbg(a, b, c):
			qpainter.drawImage(a, b, c)

		if not invert:
			ch = 0.0
			dbg(qtcore4.QRectF(0, ch, swidth, esrc.height() * yw), self.img, esrc)
			ch += float(esrc.height()) * yw
			dbg(qtcore4.QRectF(0, ch, swidth, tsrc.height() * yw), self.img, tsrc)
			ch += float(tsrc.height()) * yw
			dbg(qtcore4.QRectF(0, ch, swidth, msrc.height() * yw), self.img, msrc)
		else:
			ch = 0.0
			dbg(qtcore4.QRectF(0, ch, swidth, msrc.height() * yw), self.img, msrc)
			ch += float(msrc.height()) * yw
			dbg(qtcore4.QRectF(0, ch, swidth, esrc.height() * yw), self.img, esrc)
			ch += float(esrc.height()) * yw
			dbg(qtcore4.QRectF(0, ch, swidth, tsrc.height() * yw), self.img, tsrc)

		qpainter.end()

		'''
		qpainter.drawImage(
			qtcore4.QRectF(self.width() / 2, self.height() / 2, self.width() / 2, self.height() / 2),
			self.img,
			qtcore4.QRectF(0, 0, self.fftsize / 2.1, self.fftlen / 2.3)
		)
		'''

	def fast_paint_no_scroll(self, event, qpainter):

		if self.width() < self.fftsize:
			vwidth = float(self.width())
		else:
			vwidth = float(self.fftsize)

		for z in xrange(0, len(self.queue)):
			vec = self.queue[z]
			self.avg = geke.system(self, vec, self.fftsize, self.avg, self.bmpbuf, vwidth)

		qpainter.drawImage(
			qtcore4.QRectF(0, self.drawtop + 25.0, self.width(), self.height() - (self.drawtop + 25.0)),
			self.img,
			qtcore4.QRectF(0, 0, self.fftsize, self.fftlen)
		)

		#print 'done painting'

	def blk(self):
		return self.reader

class PyBlockHandler(gr.sync_block):
	def __init__(self, fftsize, blockcnt):
		gr.sync_block.__init__(self, name= "PyBlockHandler", in_sig = [numpy.dtype((numpy.float32, fftsize * blockcnt))], out_sig = [])
		self.vechandler = None

	def setVecHandler(self, vechandler):
		self.vechandler = vechandler

	def work(self, input_items, output_items):
		ia = input_items[0]
		self.vechandler(ia)
		return len(ia)
