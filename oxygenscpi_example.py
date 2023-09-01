# -*- coding: utf-8 -*-
"""
Created on Mon Oct  1 13:49:03 2018

@author: moberhofer
"""

import time
from pyOxygenSCPI import OxygenSCPI

DEWETRON_IP_ADDR = 'localhost'

mDevice = OxygenSCPI(ip_addr=DEWETRON_IP_ADDR)

print(f"Device Name: {mDevice.getIdn()}")
print(f"Protocol version: {mDevice.getVersion()}")

# Set Tranfer Channels to be transfered on values query. Please make sure, that
# Channels are available in Oxygen
mDevice.setTransferChannels(['REL-TIME', 'AI 1/1', 'AI 1/2', 'AI 1/3'])
#mDevice.setTransferChannels(['AI 1/I1 Sim', 'AI 1/I2 Sim', 'AI 1/I3 Sim'])
# Set Number of transfered Channels (default: 15)
mDevice.setNumberChannels()

# Choose a suitable number format (Default is ASCII)
mDevice.setNumberFormat(OxygenSCPI.NumberFormat.ASCII)
#mDevice.setNumberFormat(OxygenSCPI.NumberFormat.BINARY_INTEL)
#mDevice.setNumberFormat(OxygenSCPI.NumberFormat.BINARY_MOTOROLA)


# Capture Values
print("Requesting values...")
values = mDevice.getValues()
print(f"{'Channel':<15} {'Value':<10}")
for idx, channel in enumerate(mDevice.channelList):
    if type(values[idx]) is float:
        print(f"{channel:<15} {values[idx]:>10.2f}")
    else:
        print(f"{channel:<15} {values[idx]}")
time.sleep(1)

# Record Data File for 5 Seconds
print("Recording data...")
mDevice.storeSetFileName("Testfile 1")
mDevice.storeStart()
time.sleep(5)
mDevice.storeStop()
print("Recording stopped.")

# Set Elog channels and fetch some elog data
mDevice.setElogChannels(["AI 4/I1","AI 4/I2"])
mDevice.setElogTimestamp('ABS')
mDevice.setElogPeriod(0.01)
print("Starting Elog")
mDevice.startElog()
print("Waiting for 10 seconds...")
time.sleep(10)
print("Fetching elog Data")
data1 = mDevice.fetchElog()
data2 = mDevice.fetchElog()
mDevice.stopElog()
print("Elog stopped.")
print(f"First Elog row values fetched: {data1[0]}")
print(f"Last Elog row values fetched: {data2[-1]}")

# Alternatively Start elog with context manager and accumulating values
# for 10 seconds
print("Starting Elog with context manager")
mDevice.setElogTimestamp('ELOG')
with mDevice.elogContext():
    print("Waiting for 10 seconds...")
    time.sleep(10)
    print("Fetching Elog")
    data = mDevice.fetchElogAccumulated()
print("Elog stopped.")
print(f"Fetched Elog from timestamp {data[0][0]} to {data[-1][0]}s.")

mDevice.disconnect()
