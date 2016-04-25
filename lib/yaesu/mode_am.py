from PyQt4 import QtCore as qtcore4
from PyQt4 import QtGui as qtgui4
import PyQt4 as pyqt4

import numpy
import math

from gnuradio import gr
from gnuradio import blocks, analog, filter, qtgui, audio, fft

import lib.debug as debug
import lib.qlcdnumberadjustable as qlcdnumberadjustable
import lib.yaesu.modeshell as modeshell
import lib.blocks as gblocks

ModeShell = modeshell.ModeShell

class AM(ModeShell):
	def __init__(self, tb, rx, tx, audio, audio_in, chanover, beeper):
		uicfg = {
			'txpwrpri': self.make_cfg_lcdnum(3, False, 0, 'TX PWR PRI'),
			'volpwrpri': self.make_cfg_lcdnum(3, False, 0, 'VOL PWR PRI'),
			'freq': self.make_cfg_lcdnum(12, False, 146415000, 'ABS FREQ HZ'),
			'tx_audio_mul': self.make_cfg_lcdnum(4, False, 6, 'TX INPUT LINEAR AMP'),
			'tx_filter_gain': self.make_cfg_lcdnum(4, False, 1, 'TX FILTER GAIN'),
			'ssb_shifter_freq': self.make_cfg_lcdnum(7, True, 0, 'SSB SHIFT HZ'),
			'cutoff_freq': self.make_cfg_lcdnum(7, False, 2900, 'BW HZ'),
			'cutoff_width': self.make_cfg_lcdnum(4, False, 100, 'BW EDGE HZ'),
			'qtx_sq': self.make_cfg_lcdnum(4, False, 100, 'TX SQ'),
			'rx_filter_gain': self.make_cfg_lcdnum(4, False, 10, 'RX FILTER GAIN'),
			'rx_output_gain': self.make_cfg_lcdnum(4, False, 0, 'RX OUTPUT LOG AMP'),
			'qrx_sq': self.make_cfg_lcdnum(4, False, 0, 'RX SQ'),
		}
		ModeShell.__init__(self, uicfg, tb, rx, tx, audio, audio_in, chanover, beeper)

	def update(self, rxcenter, txcenter, rxsps, txsps, fast=False):
		ModeShell.update(self, rxcenter, txcenter, rxsps, txsps, fast=fast)
		"""
		Updates the module by its parameters. Supports a full reconfiguration
		and a fast reconfiguration for only simple changes such as volume, squelch,
		frequency, and audiosps which can be changed without much computational expense.
		"""
		rxsps = float(rxsps)
		self.rxsps = rxsps
		txsps = float(txsps)
		self.txsps = txsps

		pre = [
			'tx_vol', 'tx_sq', 'tx_cnst_src', 'tx_ftc', 'tx_ssb_shifter_mul',
			'tx_ssb_shifter', 'tx_lpf', 'tx_if0', 'tx_if0_mul', 'rx_if0', 'rx_if0_mul',
			'rx_lpf', 'rx_cms', 'rx_vol', 'sqblock'
		]
		for q in pre:
			setattr(self, q, None)		

		freq = self.freq.get_value()
		tx_audio_mul = self.tx_audio_mul.get_value()
		tx_ssb_shifter_freq = self.ssb_shifter_freq.get_value()
		tx_cutoff_freq = self.cutoff_freq.get_value()
		tx_filter_gain = self.tx_filter_gain.get_value()
		tx_cutoff_width = self.cutoff_width.get_value()
		tx_sqval = self.qtx_sq.get_value()

		rx_output_gain = self.rx_output_gain.get_value()
		rx_cutoff_freq = self.cutoff_freq.get_value()
		rx_filter_gain = self.rx_filter_gain.get_value()
		rx_cutoff_width = self.cutoff_width.get_value()
		rx_sqval = self.qrx_sq.get_value()

		print 'rx_cutoff_freq:%s' % rx_cutoff_freq

		tx_loc_freq = freq - txcenter
		rx_loc_freq = freq - rxcenter

		print '@@@@@@@@@@ KEY CHANGED WAS %s' % self.key_changed

		if self.key_changed == 'txpwrpri':
			print '$$$$ RETURNING'
			return

		if self.key_changed == 'qtx_sq' and self.tx_sq is not None:
			self.tx_sq.set_threshold(tx_sqval / 100.0)
			return

		if self.key_changed == 'qrx_sq' and self.sqblock is not None:
			self.sqblock_sq.set_threshold(rx_sqval / 100.0)
			return

		if self.key_changed == 'freq':
			freq = self.freq.get_value()
			tx_loc_freq = freq - txcenter
			rx_loc_freq = freq - rxcenter
			if abs(tx_loc_freq) < txsps * 0.7 and self.tx_vol is not None:
				self.rxtxstatus.set_tx_status(True)
				self.tx_if0_mul.set_phase_inc(tx_loc_freq / txsps * math.pi * 2.0)
			if abs(rx_loc_freq) < txsps * 0.7 and self.rx_if0 is not None:
				self.rxtxstatus.set_rx_status(True)
				self.rx_if0_mul.set_phase_inc(rx_loc_freq / txsps * math.pi * 2.0)
			if self.rx_if0 is not None and self.tx_vol is not None:
				return

		if self.key_changed == 'ssb_shifter_freq' and self.tx_ssb_shifter is not None:
			self.tx_ssb_shifter_mul.set_phase_inc	(tx_ssb_shifter_freq / 16000.0 * math.pi * 2.0)
			return

		if self.key_changed == 'cutoff_freq' or self.key_changed == 'cutoff_width':
			if self.tx_lpf:
				self.tx_lpf.set_taps(filter.firdes.low_pass(int(tx_filter_gain), txsps, tx_cutoff_freq, tx_cutoff_width, filter.firdes.WIN_BLACKMAN, 6.76))
			if self.rx_lpf:
				self.rx_lpf.set_taps(filter.firdes.low_pass(int(rx_filter_gain), rxsps, rx_cutoff_freq, rx_cutoff_width, filter.firdes.WIN_BLACKMAN, 6.76))
			return

		if self.key_changed == 'tx_filter_gain' and self.tx_lpf is not None:
			self.tx_lpf.set_taps(filter.firdes.low_pass(int(tx_filter_gain), txsps, tx_cutoff_freq, tx_cutoff_width, filter.firdes.WIN_BLACKMAN, 6.76))
			return

		if self.key_changed == 'rx_filter_gain' and self.rx_lpf is not None:
			self.rx_lpf.set_taps(filter.firdes.low_pass(int(rx_filter_gain), rxsps, rx_cutoff_freq, rx_cutoff_width, filter.firdes.WIN_BLACKMAN, 6.76))
			return

		# Turn it off to disconnect them before the variable contents
		# below are replaced.
		was_active = self.active
		self.off()

		if abs(tx_loc_freq) > txsps * 0.75:
			self.tx_vol = None
			self.rxtxstatus.set_tx_status(False)
		else:
			self.tx_vol = blocks.multiply_const_ff(tx_audio_mul)
			self.tx_sq = analog.standard_squelch(audio_rate=16000)
			self.tx_sq.set_threshold(tx_sqval / 100.0)
			self.tx_cnst_src = analog.sig_source_f(int(16000), analog.GR_CONST_WAVE, 0, 0, 0)
			self.tx_ftc = blocks.float_to_complex()

			self.tx_ssb_shifter_mul = blocks.rotator_cc()
			self.tx_ssb_shifter_mul.set_phase_inc(tx_ssb_shifter_freq / 16000.0 * math.pi * 2.0)

			self.tx_lpf = filter.interp_fir_filter_ccf(int(txsps / 16000), filter.firdes.low_pass(int(tx_filter_gain), txsps, tx_cutoff_freq, tx_cutoff_width, filter.firdes.WIN_BLACKMAN, 6.76))

			self.tx_if0_mul = blocks.rotator_cc()
			self.tx_if0_mul.set_phase_inc(tx_loc_freq / txsps * math.pi * 2.0)
			# Late failure is okay. Better false negative than RX is OFF.
			self.rxtxstatus.set_tx_status(True)

		if abs(rx_loc_freq) > rxsps * 0.75:
			self.rx_if0 = None
			self.rxtxstatus.set_rx_status(False)
		else:
			# Early failure is okay. Better false positive that TX is ON.
			self.rxtxstatus.set_rx_status(True)
			self.rx_if0_mul = blocks.rotator_cc()
			self.rx_if0_mul.set_phase_inc(-rx_loc_freq / rxsps * math.pi * 2.0)
			self.rx_lpf = filter.fir_filter_ccf(int(rxsps / 16000), filter.firdes.low_pass(int(rx_filter_gain), int(rxsps), rx_cutoff_freq, rx_cutoff_width, filter.firdes.WIN_HAMMING, 6.76))
			self.rx_cms = blocks.complex_to_mag_squared()
			self.rx_vol = blocks.multiply_const_ff(10.0 ** (rx_output_gain / 10.0))

			self.sqblock = analog.standard_squelch(16000)
			self.sqblock.set_threshold(float(rx_sqval) / 100.0)

			self.rx_sigstr = gblocks.SignalStrengthCalculator(numpy.float32)
			self.chanover.set_audio_strength_query_func(self.rx_sigstr.get_value)

		if was_active:
			self.on()
		else:
			self.off()

	def on(self):
		ModeShell.on(self)
		self.tb.lock()
		if self.tx_vol is not None:
			print '@@@@@ connecting tx blocks;'
			#self.tx_tmp = blocks.null_source(4)
			#self.connect(self.tx_tmp, self.tx_vol, (self.tx_ftc, 0))
			
			self.connect(self.audio_rx, self.tx_vol, (self.tx_ftc, 0))
			self.connect(self.tx_cnst_src, (self.tx_ftc, 1))
			
			self.connect(self.tx_ftc, self.tx_ssb_shifter_mul, self.tx_lpf, self.tx_if0_mul)			
			#self.connect(self.tx_if0_mul, debug.Debug(xtype=numpy.dtype(numpy.complex64), tag='FROM TX LAST BLOCK'))
			
			self.tx_disconnect_node = self.tx.connect(
				txblock=self.tx_if0_mul,
				pwrprimon=self.txpwrpri
			)
		if self.rx_if0_mul is not None:
			self.connect(self.rx, self.rx_if0_mul, self.rx_lpf, self.rx_cms, self.rx_vol)
			self.connect(self.rx, debug.Debug(xtype=numpy.dtype(numpy.complex64), tag='FROM RX FIRST BLOCK'))
			self.connect(self.rx_cms, self.rx_sigstr)
			self.audio_disconnect_node = self.audio_tx.connect(
				txblock=self.rx_vol,
				pwrprimon=self.volpwrpri
			)
		self.tb.unlock()
		self.chanover.change_active(True)

	def off(self):
		ModeShell.off(self)
		self.tb.lock()
		self.disconnect_all()
		if self.tx_disconnect_node is not None:
			self.tx_disconnect_node.disconnect()
			self.tx_disconnect_node = None
		if self.audio_disconnect_node is not None:
			self.audio_disconnect_node.disconnect()
			self.audio_disconnect_node = None
		self.chanover.change_active(False)
		self.tb.unlock()




