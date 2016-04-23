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

class Debug(gr.sync_block):
	def __init__(self, xtype, tag=None):
		gr.sync_block.__init__(self, 'PyDebug', in_sig=[xtype], out_sig=[])
		self.last = time.time()
		self.xtype = xtype
		self.tag = tag

	def work(self, input_items, output_items):
		if time.time() - self.last > 3:
			self.last = time.time()
			if self.tag is None:
				tag = '%s' % self
			else:
				tag = self.tag
			v = '(%s,%s)' % (input_items[0].real[0], input_items[0].imag[0])
			print 'debug[%s:%s]:%s' % (tag, self.xtype, v)
		return len(input_items[0])