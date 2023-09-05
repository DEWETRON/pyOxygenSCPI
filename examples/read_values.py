"""
Determinine all available channels and return values of the first two channels
"""

import time
from pyOxygenSCPI import OxygenSCPI

DEWETRON_IP_ADDR = 'localhost'
DEWETRON_PORT = 10001

mDevice = OxygenSCPI(ip_addr=DEWETRON_IP_ADDR, tcp_port=DEWETRON_PORT)

print("Available channels:")
channel_list = mDevice.getChannelList()
for ch_id, ch_name in channel_list:
    print(f"  {ch_name:20} (id = {ch_id})")

# Select the first two channels
selection = [ch_name for _, ch_name in channel_list[0:2]]
mDevice.setTransferChannels(selection, includeAbsTime=True)

# Requesting values
print(f'{selection[0]:20} {selection[1]:>15} {selection[2]:>15}')
for n in range(4):
    values = mDevice.getValues()
    timestamp = values[0].strftime("%Y-%m-%d %H:%M:%S")
    print(f'{timestamp:20} {values[1]:>15.2} {values[2]:>15.2}')
    time.sleep(1)
