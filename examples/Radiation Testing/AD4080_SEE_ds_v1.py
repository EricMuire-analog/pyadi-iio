import threading
import queue
import time
#from openpyxl import Workbook
from datetime import datetime
from threading import Lock
import sys
from time import sleep
import matplotlib.pyplot as plt
import numpy as np
import time
from adi import ad4080, ad9508, adf4350, one_bit_adc_dac


def bring_up_board():
    my_uri = "ip:analog.local"  # Default URI
    Fsamp = 40  # Default Sampling Frequency
    FiltMode = "disabled"  # Default Filter Mode
    DecRate = 2  # Default Decimation Rate

    print("starting")
    my_adc = ad4080(uri=my_uri)
    my_divider = ad9508(uri=my_uri, device_name="ad9508")
    my_one_bit_adc_dac = one_bit_adc_dac(uri=my_uri)
    my_pll = adf4350(uri=my_uri, device_name="/axi/spi@e0007000/adf4350@1")
    #my_adc.rx_buffer_size = 2 ** 13

    print("ad4080 sampling frequency: ", my_adc.sampling_frequency)
    print("ad9508 channel 0 frequency: ", my_divider.channel[0].frequency)
    print("pll adf4350 frequency: ", my_pll.frequency_altvolt0)
    print("one bit adc dac sync n value", my_one_bit_adc_dac.gpio_sync_n)
    print("ad4080 reg read",  my_adc.reg_read(0x15))
    print("Scale: ", my_adc.scale)

    # Calculate adf4350 clock frequency
    adf4350_clk = int(Fsamp * 10_000_000)  # Multiply by 10 million
    ## Disable the AD9508 outputs
    my_one_bit_adc_dac.gpio_sync_n = 1

    adf4350_clk = 400_000_000 
    adf4350_clk = adf4350_clk * 1
    print(f"ADF4350 PLL Frequency set to: {adf4350_clk}")
    my_pll.frequency_altvolt0 = adf4350_clk
    print("Set for: 40MSPS to 20MSPS Range")
    my_divider.channel[2] = adf4350_clk / 10
    my_divider.channel[3] = adf4350_clk / 1

    my_adc.reg_write(0x16, 0x71)

    my_divider.reg_write(0x2B, 0x26) # phase inverted here ONLY when dividing /1  in line 44, this is due to an ad9508 bug!
    my_divider.reg_write(0x1F, 0x16) # phase set here is correct for ch2
        
    my_one_bit_adc_dac.gpio_sync_n = 0

    #my_adc.filter_sel = "disabled"
    #time.sleep(0.25)
    my_adc.lvds_sync = "enable"
    time.sleep(0.25)
    #my_adc.filter_sel = FiltMode
    #time.sleep(0.25)
    #my_adc.sinc_dec_rate = DecRate
    #time.sleep(0.25)

    return my_adc

def read_registers(my_adc):
    # Read the registers of the ADC
    registers = [0x11,0x12,0x13,0x14,0x15,0x16,0x17,0x18]
    data = {}
    for reg in registers:
        data[reg] = my_adc.reg_read(reg)
    return data

if __name__ == '__main__':
    my_uri = "ip:analog.local"  # Default URI
    Fsamp = 40  # Default Sampling Frequency
    FiltMode = "disabled"  # Default Filter Mode
    DecRate = 2  # Default Decimation Rate

    print("starting")
    my_adc = bring_up_board()

    plt.clf()
    sleep(0.5)
    count = 0
    total_capture_count = 0
    start_time = time.time()
    last_capture_count = 0
    while True:
        total_capture_count += 1        
        adc_data = my_adc.rx()
        reg_data = read_registers(my_adc)
        sec_interval = 10
        elapsed_time = time.time() - start_time
        if elapsed_time > sec_interval:
            captures_last_x_sec = total_capture_count - last_capture_count
            print(f"Avg Reads in last {sec_interval} sec: {captures_last_x_sec/sec_interval}")
            last_capture_count = total_capture_count
            start_time = time.time()

    plt.plot(range(0, len(data)), data, label="channel0")
    plt.xlabel("Data Point")
    plt.ylabel("ADC counts")
    plt.legend(
        bbox_to_anchor=(0.0, 1.02, 1.0, 0.102),
        loc="lower left",
        ncol=4,
        mode="expand",
        borderaxespad=0.0,
    )

    plt.show()
    del my_adc
