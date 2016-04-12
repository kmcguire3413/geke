from PyQt4 import QtCore as qtcore4
from PyQt4 import QtGui as qtgui4
import PyQt4 as pyqt4

import math

class ChanOverview(qtgui4.QWidget):
	class Chan:
		pass

	def __init__(self, chancnt, w, h):
		qtgui4.QWidget.__init__(self)

		self.resize(w, h)

		self.chans = []

		bdim = math.ceil(math.sqrt(float(chancnt)))
		bw = float(w) / bdim
		bh = float(h) / bdim		

		for iy in xrange(0, int(bdim)):
			for ix in xrange(0, int(bdim)):
				iz = ix + iy * int(bdim)
				if iz >= chancnt:
					break
				cont = ChanOverview.Chan()
				self.chans.append(cont)
				cont.w = bw
				cont.h = bh
				cont.x = float(ix * bw)
				cont.y = float(iy * bh)
				cont.active = False
				cont.volume = 0.0
				cont.audio = 0.0
				cont.chan_num = iz

	def paintEvent(self, event):
		print 'telling cont(s) to repaint!!'
		qp = qtgui4.QPainter(self)
		for c in self.chans:
			self.chanPaint(
				c, qp, c.x, c.y, c.w, c.h
			)
		qp.end()

	def chanPaint(self, c, qp, x, y, w, h):
		print 'cont painting!!', x, y, w, h
		rect = qtcore4.QRectF
		color = qtgui4.QColor()
		color.setRgb(200, 200, 200)
		qp.fillRect(
			rect(
				x + 0.0, 
				y + h, 
				w * 0.5, 
				float(c.volume) / 100.0 * -h), color)
		qp.fillRect(
			rect(
				x + w * 0.5, 
				y + h,
				w * 0.5, 
				float(c.audio) / 100.0 * -h), 
		color)

		color.setRgb(60, 60, 60)
		brush = qtgui4.QPen(color)
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
		print 'repaint!!! now!!'

	# Color the right bar for current audio level at 0.0 to 1.0
	def set_chan_audio_level(self, ndx, level):
		self.chans[ndx].audio = float(level)
		self.update()

	# Color current yellowish.
	def set_chan_current(self, ndx):
		self.cur_chan = int(ndx)
		self.update()