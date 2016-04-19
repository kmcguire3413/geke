from gnuradio import gr
from gnuradio import blocks, analog, filter, qtgui, audio, fft
import scipy, pylab
import numpy
import time
import sip
import struct
import math
import random
import types
import cProfile

from PyQt4 import QtCore as qtcore4
from PyQt4 import QtGui as qtgui4
import PyQt4 as pyqt4

from scipy import fftpack
import gnuradio.uhd as uhd
import sys
import qdarkstyle

import geke

import lib.yaesu.main as yaesu_main

class nothing_c(gr.sync_block):
	def __init__(self):
		gr.sync_block.__init__(self, name='nothing_c', in_sig=[], out_sig=[numpy.complex64])

	def work(self, input_items, output_items):
		return 0

def dbgwbgc(w):
	r = int(random.random() * 255.0)
	g = int(random.random() * 255.0)
	b = int(random.random() * 255.0)

	w.setStyleSheet('background-color: rgb(%s, %s, %s);' % (r, g, b))	

def debug_widgets_bgcolor(w):
	r = int(random.random() * 255.0)
	g = int(random.random() * 255.0)
	b = int(random.random() * 255.0)
	try:
		#pal = qtgui4.QPalette()
		#pal.setColor(w.backgroundRole(), qtgui4.QColor(r, g, b))
		#w.setPalette(pal)
		#w.setAutoFillBackground(True)
		#w.repaint()
		dbgwbgc(w)
	except Exception as e:
		print e
	for c in w.children():
		debug_widgets_bgcolor(c)


class QMainWindow(qtgui4.QWidget):
	def __init__(self):
		qtgui4.QWidget.__init__(self)
		self.layout = qtgui4.QVBoxLayout()

		self.rfront = yaesu_main.YaesuBC()
		self.rfront.setParent(self)

qapp = qtgui4.QApplication(sys.argv)
qapp.setAttribute(10, True)
#qapp.setStyleSheet(qdarkstyle.load_stylesheet(pyside=False))
qapp.setStyle(qtgui4.QStyleFactory.create("Fusion"))
darkPalette = qtgui4.QPalette()
darkPalette.setColor(qtgui4.QPalette.Window, qtgui4.QColor(5, 5, 5))
darkPalette.setColor(qtgui4.QPalette.WindowText, qtgui4.QColor(200, 200, 200))
darkPalette.setColor(qtgui4.QPalette.Base, qtgui4.QColor(25,25,25))
darkPalette.setColor(qtgui4.QPalette.AlternateBase, qtgui4.QColor(53,53,53))
darkPalette.setColor(qtgui4.QPalette.ToolTipBase, qtgui4.QColor(200, 200, 200))
darkPalette.setColor(qtgui4.QPalette.ToolTipText, qtgui4.QColor(200, 200, 200))
darkPalette.setColor(qtgui4.QPalette.Text, qtgui4.QColor(200, 200, 200))
darkPalette.setColor(qtgui4.QPalette.Button, qtgui4.QColor(53,53,53))
darkPalette.setColor(qtgui4.QPalette.ButtonText, qtgui4.QColor(200, 200, 200))
darkPalette.setColor(qtgui4.QPalette.BrightText, qtgui4.QColor(200, 0, 0))
darkPalette.setColor(qtgui4.QPalette.Link, qtgui4.QColor(42, 130, 218))
darkPalette.setColor(qtgui4.QPalette.Highlight, qtgui4.QColor(42, 130, 218))
darkPalette.setColor(qtgui4.QPalette.HighlightedText, qtgui4.QColor(0, 0, 0))
qapp.setPalette(darkPalette);
qapp.setStyleSheet("QWidget { background-color: #050505; } QToolTip { color: #ffffff; background-color: #2a82da; border: 1px solid white; }");

qwin = QMainWindow()
qwin.show() #FullScreen()
qapp.exec_()
