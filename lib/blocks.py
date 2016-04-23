from PyQt4 import QtCore as qtcore4
from PyQt4 import QtGui as qtgui4
import PyQt4 as pyqt4

from gnuradio import gr
from gnuradio import blocks, analog, filter, qtgui, audio, fft

import geke

import types
import math
import numpy
import cmath
import time
import sys
import threading

class RepeatLimitAndRot(gr.interp_block):
	"""
	"""
	def __init__(self, repeat, rot_limit, theta_inc):
		gr.interp_block.__init__(self, 
			'RepeatLimitAndSpin', 
			in_sig = [numpy.dtype(numpy.float32)], 
			out_sig = [numpy.dtype(numpy.complex64)],
			interp=int(repeat)
		)
		self.rot_limit = rot_limit
		self.theta_inc = theta_inc
		self.repeat = repeat
		self.last_theta = 0.0
		self.last_mag = 0.0

	def set_theta_inc(self, theta_inc):
		self.theta_inc = theta_inc

	def set_rot_limit(self, rot_limit):
		self.rot_limit = rot_limit

	def work(self, input_items, output_items):
		inp = input_items[0]
		oup = output_items[0]

		inp = numpy.repeat(inp, self.repeat)
		inp = numpy.vectorize(complex)(inp, [0])
		
		(self.last_theta, self.last_mag) = geke.spin_and_limit(self.rot_limit, self.theta_inc, self.last_theta, self.last_mag, inp)
		oup[:] = inp
		return len(oup)


