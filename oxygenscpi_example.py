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
mDevice.setTransferChannels(['AI 1/1', 'AI 1/2', 'AI 1/3'])
#mDevice.setTransferChannels(['AI 1/I1 Sim', 'AI 1/I2 Sim', 'AI 1/I3 Sim'])
# Set Number of transfered Channels (default: 15)
mDevice.setNumberChannels()

# Capture Values
print("Requesting values...")
values = mDevice.getValues()
print(f"{'Channel':<15} {'Value':<10}")
for idx, channel in enumerate(mDevice.channelList):
    print(f"{channel:<15} {values[idx]:>10.3f}")
time.sleep(1)

# Record Data File for 5 Seconds
print("Recording data...")
mDevice.storeSetFileName("Testfile 1")
mDevice.storeStart()
time.sleep(5)
mDevice.storeStop()
print("Recording stopped.")

mDevice.disconnect()
