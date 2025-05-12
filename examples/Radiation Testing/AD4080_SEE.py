import threading
from threading import Lock
import queue
import time
from openpyxl import Workbook
from datetime import datetime
import sys
from time import sleep
import matplotlib.pyplot as plt
import numpy as np
import time
from adi import ad4080, ad9508, adf4350, one_bit_adc_dac
from ad4080_data_analysis import process_adc_raw_data, get_adc_data

total_capture_count = 0
capture_count_lock = Lock()

def save_workbook_async(workbook, filename):
    def save():
        workbook.save(filename)
    threading.Thread(target=save).start()

def read_registers(my_adc):
    # Read the registers of the ADC
    registers = [0x11,0x12,0x13,0x14,0x15,0x16,0x17,0x18]
    data = {}
    for reg in registers:
        data[reg] = my_adc.reg_read(reg)
    return data

def startup():
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

    return my_adc, my_acq_size

def data_reader(my_adc, my_acq_size, data_queue, stop_event, run_type):
    """
    Reads data continuously and stores it in a queue.
    Tracks the number of register reads and data captures.
    Logs the counts every 10 seconds.
    """
    global total_capture_count
    last_capture_count = 0
    start_time = time.time()

    while not stop_event.is_set():
        # Read registers
        registers = read_registers(my_adc)
        data_queue.put(registers)

        # Capture data
        if run_type == '1':
            captured_data =  get_adc_data(my_adc.rx(),my_acq_size)
            with capture_count_lock:
                total_capture_count += 1
            data_queue.put(captured_data[0])

        # Log performance every sec_interval seconds
        sec_interval = 10
        if time.time() - start_time >= sec_interval:
            # Calculate the counts for the last sec_interval seconds
            captures_last_x_sec = total_capture_count - last_capture_count

            # Log the counts
            print(f"Avg Reads in last {sec_interval} sec: {captures_last_x_sec/sec_interval}")

            # Update the last counts and reset the timer
            last_capture_count = total_capture_count
            start_time = time.time()

        if data_queue.qsize() > 900:  # Log a warning if the queue is almost full
            print(f"Data queue is nearing capacity! Size is {data_queue.qsize()}")

        time.sleep(0.001)  # Adjust sleep interval as needed

def data_logger(data_queue, stop_event, run_number):
    """
    Logs data from the queue into an Excel file with timestamps.
    """
    # Create an Excel workbook and sheets
    workbook = Workbook()
    register_sheet = workbook.active
    register_sheet.title = "Register Reads"
    capture_sheet = workbook.create_sheet(title="Capture Data")

    # Add headers to the sheets
    register_sheet.append(["Timestamp", "Register Data"])
    capture_sheet.append(["Timestamp", "Capture Data"])

    buffer = []
    buffer_size = 100  # Adjust buffer size as needed

    while not stop_event.is_set() or not data_queue.empty():
        try:
            # Retrieve data from the queue
            data = data_queue.get(timeout=0.1)
            buffer.append(data)
            reg_col = 1
            cap_col = 1
            # Process or log data in batches
            # Save the workbook less frequently
            if len(buffer) >= buffer_size:
                for item in buffer:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                    if isinstance(item, list):  # Register data
                        register_sheet.cell(row=1, column=reg_col, value=timestamp)  # Timestamp in row 1
                        for row_idx, value in enumerate(item, start=2):  # Write data vertically
                            register_sheet.cell(row=row_idx, column=reg_col, value=value)
                        reg_col += 1
                    else:  # Capture data
                        capture_sheet.cell(row=1, column=cap_col, value=timestamp)  # Timestamp in row 1
                        for row_idx, value in enumerate(item.tolist(), start=2):  # Write data vertically
                            capture_sheet.cell(row=row_idx, column=cap_col, value=value)
                        cap_col += 1
                buffer.clear()

                # Save the workbook every x amount of entries instead of every batch
                if total_capture_count % 5000 == 0:
                    print("Saving workbook...")
                    save_workbook_async(workbook, f"Run_{run_number}_data_log.xlsx")
                    print("Workbook saved")
        except queue.Empty:
            continue

    # Final save when the logger stops
    save_workbook_async(workbook, f"Run_{run_number}_data_log.xlsx")

if __name__ == '__main__':
    run_number = input('Enter the run number: ')
    run_type = input('Enter the run type (1: Reg & ADC Data, anything else: just reg): ')
    print("Starting Barracuda Device Startup Script")
    my_adc, my_acq_size = startup()

    data_queue = queue.Queue(maxsize=1000)
    stop_event = threading.Event()

    reader_thread = threading.Thread(target = data_reader, args=(my_adc, my_acq_size, data_queue, stop_event, run_type))
    logger_thread = threading.Thread(target = data_logger, args=(data_queue, stop_event, run_number))

    reader_thread.start()
    logger_thread.start()

    try:
        while True:
            time.sleep(1)  # Main thread can perform other tasks
    except KeyboardInterrupt:
        print("Stopping threads...")
        stop_event.set()
        reader_thread.join()
        logger_thread.join()
        del my_adc
        print("Threads stopped.")
