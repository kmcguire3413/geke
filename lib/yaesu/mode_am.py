from PyQt4 import QtCore as qtcore4
from PyQt4 import QtGui as qtgui4
import PyQt4 as pyqt4

from gnuradio import gr
from gnuradio import blocks, analog, filter, qtgui, audio, fft

import lib.qlcdnumberadjustable as qlcdnumberadjustable
import lib.yaesu.modeshell as modeshell

ModeShell = modeshell.ModeShell

class AM(ModeShell):
	def __init__(self, tb, rx, tx, audio, audio_in, chanover):
		uicfg = {
			'txpwrpri': self.make_cfg_lcdnum(3, False, 0, 'TX PWR PRI ALLOC'),
			'freq': self.make_cfg_lcdnum(12, False, 90005000, 'ABS FREQ HZ'),
			'tx_audio_mul': self.make_cfg_lcdnum(4, False, 6, 'TX INPUT LINEAR AMP'),
			'tx_filter_gain': self.make_cfg_lcdnum(4, False, 430, 'TX FILTER GAIN'),
			'ssb_shifter_freq': self.make_cfg_lcdnum(7, True, 11000, 'SSB SHIFT HZ'),
			'cutoff_freq': self.make_cfg_lcdnum(7, False, 1300, 'BW HZ'),
			'cutoff_width': self.make_cfg_lcdnum(4, False, 100, 'BW EDGE HZ'),
			'qtx_sq': self.make_cfg_lcdnum(4, False, 100, 'TX SQ'),
			'rx_filter_gain': self.make_cfg_lcdnum(4, False, 0, 'RX FILTER GAIN'),
			'rx_output_gain': self.make_cfg_lcdnum(4, False, 20, 'RX OUTPUT LOG AMP'),
			'qrx_sq': self.make_cfg_lcdnum(4, False, 0, 'RX SQ'),
		}
		ModeShell.__init__(self, uicfg, tb, rx, tx, audio, audio_in, chanover)

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

		# Turn it off to disconnect them before the variable contents
		# below are replaced.
		was_active = self.active
		self.off()

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

		tx_loc_freq = freq - txcenter
		rx_loc_freq = freq - rxcenter

		print 'tx_loc_freq:%s rx_loc_freq:%s' % (tx_loc_freq, rx_loc_freq)

		if abs(tx_loc_freq) > txsps * 0.75:
			self.tx_vol = None
		else:
			self.tx_vol = blocks.multiply_const_ff(tx_audio_mul)
			self.tx_sq = analog.standard_squelch(audio_rate=16000)
			self.tx_sq.set_threshold(tx_sqval / 10.0)
			self.tx_cnst_src = analog.sig_source_f(0, analog.GR_CONST_WAVE, 0, 0, 0)
			self.tx_ftc = blocks.float_to_complex(1)
			self.tx_ssb_shifter_mul = blocks.multiply_vcc(1)
			self.tx_ssb_shifter = analog.sig_source_c(txsps, analog.GR_COS_WAVE, tx_ssb_shifter_freq, 0.1, 0)
			self.tx_lpf = filter.interp_fir_filter_ccf(int(txsps / 16000), filter.firdes.low_pass(int(tx_filter_gain), txsps, tx_cutoff_freq, tx_cutoff_width, filter.firdes.WIN_BLACKMAN, 6.76))
			self.tx_if0 = analog.sig_source_c(txsps, analog.GR_COS_WAVE, tx_loc_freq, 0.1, 0)		
			self.tx_if0_mul = blocks.multiply_vcc(1)

		if abs(rx_loc_freq) > rxsps * 0.75:
			self.rx_if0 = None
		else:
			self.rx_if0 = analog.sig_source_c(rxsps, analog.GR_COS_WAVE, -rx_loc_freq, 0.1, 0)
			self.rx_if0_mul = blocks.multiply_vcc(1)
			self.rx_lpf = filter.fir_filter_ccf(int(rxsps / 16000), filter.firdes.low_pass(int(rx_filter_gain), int(rxsps), rx_cutoff_freq, rx_cutoff_width, filter.firdes.WIN_HAMMING, 6.76))
			self.rx_cms = blocks.complex_to_mag_squared()
			self.rx_vol = blocks.multiply_const_ff(10.0 ** (rx_output_gain / 10.0))
			self.sqblock = analog.standard_squelch(16000)
			self.sqblock.set_threshold(float(rx_sqval) / 100.0)

		if was_active:
			self.on()
		else:
			self.off()

	def on(self):
		ModeShell.on(self)
		self.tb.lock()
		if self.tx_vol is not None:
			self.connect(self.audio_rx, self.tx_vol, self.tx_sq, (self.tx_ftc, 0))
			self.connect(self.tx_ftc, self.tx_ssb_shifter_mul, self.tx_lpf, (self.tx_if0_mul, 0))
			self.connect(self.tx_if0, (self.tx_if0_mul, 1))
			self.connect(self.tx_cnst_src, (self.tx_ftc, 1))
			self.tx_disconnect_node = self.tx.connect(txblock=self.tx_if0_mul, pwrprimon=self.txpwrpri)
		if self.rx_if0 is not None:
			self.connect(self.rx, (self.rx_if0_mul, 0))
			self.connect(self.rx_if0, (self.rx_if0_mul, 1))
			self.connect(self.rx_if0_mul, self.rx_lpf, self.rx_cms, self.rx_vol)
			self.audio_disconnect_node = self.audio_tx.connect(self.rx_vol)
		print 'about to unlock'
		self.tb.unlock()
		print 'unlocking'
		self.chanover.change_active(True)
		print 'ON'

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
		print 'OFF'
