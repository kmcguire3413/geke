from PyQt4 import QtCore as qtcore4
from PyQt4 import QtGui as qtgui4
import PyQt4 as pyqt4

import math

class ChanOverview(qtgui4.QWidget):
	class Chan:
		pass

	def __init__(self, chancnt):
		qtgui4.QWidget.__init__(self)

		self.chans = []

		self.chancnt = chancnt
		self.cur_chan = None
		
		for x in xrange(0, chancnt):
			cont = ChanOverview.Chan()
			cont.chan_num = x
			cont.active = False
			cont.squelch = 0.0
			cont.volume = 0.0
			cont.audio = 0.0			
			self.chans.append(cont)

	def compute_dim(self):
		bdim = math.ceil(math.sqrt(float(self.chancnt)))
		w = self.width()
		h = self.height()
		bw = float(w) / bdim
		bh = float(h) / bdim		

		for iy in xrange(0, int(bdim)):
			for ix in xrange(0, int(bdim)):
				iz = ix + iy * int(bdim)
				if iz >= self.chancnt:
					break
				cont = self.chans[iz]
				cont.w = bw
				cont.h = bh
				cont.x = float(ix * bw)
				cont.y = float(iy * bh)

	def paintEvent(self, event):
		self.compute_dim()
		qp = qtgui4.QPainter(self)
		for c in self.chans:
			self.chanPaint(
				c, qp, c.x, c.y, c.w, c.h
			)
		qp.end()

	def chanPaint(self, c, qp, x, y, w, h):
		rect = qtcore4.QRectF
		color = qtgui4.QColor()

		if c.active:
			rm = 0.5
			gm = 1.0
			bm = 0.5
		else:
			rm = 0.5
			gm = 0.5
			bm = 0.5

		if self.cur_chan == c.chan_num:
			rm = 1.0

		def getcolor(r, g, b):
			return qtgui4.QColor(float(r) * rm, float(g) * gm, float(b) * bm)

		color = getcolor(130, 230, 130)
		qp.fillRect(
			rect(
				x + 0.0, 
				y + h, 
				w * 0.33, 
				float(c.volume) / 100.0 * -h), color)
		color = getcolor(170, 170, 170)
		qp.fillRect(
			rect(
				x + w * 0.5, 
				y + h,
				w * 0.33, 
				float(c.audio) / 100.0 * -h),
		color)
		color = getcolor(130, 230, 130)
		qp.fillRect(
			rect(
				x + w * 0.5, 
				y + h,
				w * 0.33, 
				float(c.squelch) / 100.0 * -h),
		color)

		color = getcolor(60, 60, 60)
		brush = qtgui4.QPen(color)
		font = qtgui4.QFont()
		font.setPixelSize(8)
		qp.setFont(font)
		qp.setPen(brush)
		qp.drawText(x, y, w * 0.5, h * 0.2, 0, '(%s)' % c.chan_num)
		qp.drawText(x, y + h * 0.2, w * 0.5, h * 0.2, 0, '%s' % c.volume)
		qp.drawText(x + w * 0.5, y + h * 0.2, w * 0.5, h * 0.2, 0, '%s' % c.audio)

	def give_size(self, w, h):
		self.setMaximumSize(w, h)
		self.setMinimumSize(w, h)
		self.resize(w, h)

	# Color greenish or redish.
	def set_chan_active(self, ndx, active):
		if active:
			self.chans[ndx].active = True
		else:
			self.chans[ndx].active = False
		self.update()

	# Color the left bar for volume intensity at 0.0 to 1.0
	def set_chan_volume(self, ndx, volume):
		self.chans[ndx].volume = float(volume)
		self.update()

	def set_chan_squelch(self, ndx, squelch):
		self.chans[ndx].squelch = float(squelch)
		self.update()

	# Color the right bar for current audio level at 0.0 to 1.0
	def set_chan_audio_level(self, ndx, level):
		self.chans[ndx].audio = float(level)
		self.update()

	# Color current yellowish.
	def set_chan_current(self, ndx):
		self.cur_chan = int(ndx)
		self.update()