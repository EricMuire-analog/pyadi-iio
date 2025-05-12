# import threading
# import queue
# import time
# from openpyxl import Workbook
# from datetime import datetime
# from threading import Lock
# import sys
from time import sleep
# import matplotlib.pyplot as plt
# import numpy as np
import time
from adi import ad4080, ad9508, adf4350, one_bit_adc_dac
from ad4080_data_analysis import process_adc_raw_data

my_uri = "ip:analog.local"  # Default URI
Fsamp = 40  # Default Sampling Frequency
FiltMode = "disabled"  # Default Filter Mode
DecRate = 2  # Default Decimation Rate

my_adc = ad4080(uri=my_uri)
print("ad4080 sampling frequency: ", my_adc.sampling_frequency)
print("ad4080 reg read",  my_adc.reg_read(0x15))
print("Scale: ", my_adc.scale)
sleep(0.5)  # Needed some delays to make these not fail intermittently
my_pll = adf4350(uri=my_uri, device_name="/axi/spi@e0007000/adf4350@1")
print("pll adf4350 frequency: ", my_pll.frequency_altvolt0)
sleep(0.5)  # Needed some delays to make these not fail intermittently
my_divider = ad9508(uri=my_uri, device_name="ad9508")
print("ad9508 channel 0 frequency: ", my_divider.channel[0].frequency)
sleep(0.5)  # Needed some delays to make these not fail intermittently
my_one_bit_adc_dac = one_bit_adc_dac(uri=my_uri)
print("one bit adc dac sync n value", my_one_bit_adc_dac.gpio_sync_n)


my_acq_size = 2 ** 18  # setting how many conversions results to take
my_adc.rx_buffer_size = my_acq_size

# Disable the AD9508 outputs
my_one_bit_adc_dac.gpio_sync_n = 1
time.sleep(0.25)

adf4350_clk = 400_000_000 
# adf4350_clk = adf4350_clk * 1
print(f"ADF4350 PLL Frequency set to: {adf4350_clk}")
my_pll.frequency_altvolt0 = adf4350_clk
print("Set for: 40MSPS to 20MSPS Range")
my_divider.channel[2] = adf4350_clk / 10
my_divider.channel[3] = adf4350_clk / 1

time.sleep(0.5)
print("CNV Frequency: ", my_divider.channel[2])
print("CLK Frequency: ", my_divider.channel[3])

time.sleep(0.25)  # allow the PLL to relock
my_divider.reg_write(0x2B, 0x26)  # phase inverted here ONLY when dividing /1  in line 44, this is due to an ad9508 bug!
my_adc.reg_write(0x16, 0x51)


time.sleep(0.5)
# Renable the AD9508 outputs
my_one_bit_adc_dac.gpio_sync_n = 0

time.sleep(0.25)
# my_adc.filter_sel = "disabled"
# time.sleep(0.25)
# Performs the LVDS interface synchronization routine
my_adc.lvds_sync = "enable"
time.sleep(0.25)
my_adc.lvds_sync = "enable"
time.sleep(0.25)
# my_adc.filter_sel = FiltMode
# time.sleep(0.25)
# my_adc.sinc_dec_rate = DecRate
# time.sleep(0.25)

sleep(0.5)

data = my_adc.rx()

# ADC parameters
adc_freq = my_adc.sampling_frequency
adc_buff_n = my_acq_size
adc_bits = 20
adc_quants = 2 ** adc_bits
adc_vref = 3
adc_quant_v = adc_vref / adc_quants
test_type = 'sig_input'   # 'sig_input' 'dyn_range'
# test_type = 'dyn_range'

# Analyze spectrum and show plots
# spectrum.analyze(test_type, data, adc_bits, adc_vref, adc_freq, window='blackman')

(snr_adj, thd_calc,  f1_freq, fund_dbfs) = process_adc_raw_data(my_adc, 1, data, my_acq_size, adc_freq, 1)


# Teardown, not sure if entirely necessary, but had seen some setup errors on starting up without this
del my_pll
del my_one_bit_adc_dac
del my_divider
del my_adc
