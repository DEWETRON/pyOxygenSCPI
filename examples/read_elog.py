"""
Determinine all available channels and return values of the first two channels via ELOG

The ELOG subsystem allows the SCPI user to retrieve synchronized access to multiple channels
via statistics calculations. First, the subsystem needs to be configured. Possible parameters
are a channel list, aggregation calculations, aggregation duration as well as result formats
and timestamp formats. After configuration, the user can start the computations and fetch all
values. By continuously requesting data records, gap-less readout is possible. Data is kept
available inside Oxygen for at least 20 seconds before fetching of old samples is no longer
possible.
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
mDevice.setElogChannels(selection)
mDevice.setElogTimestamp('REL')
mDevice.setElogCalculations(['RMS', 'MIN'])
mDevice.setElogPeriod(0.1)
print(f'{"Time":5} {selection[0]:>11} RMS {selection[0]:>11} MIN {selection[1]:>11} RMS {selection[1]:>11} MIN')
with mDevice.elogContext():
    for n in range(4):
        time.sleep(1)
        data = mDevice.fetchElog(raw_string=False)
        if data:
            for values in data:
                print(f'{values[0]:5} {values[1]:>15.3} {values[2]:>15.3} {values[3]:>15.3} {values[4]:>15.3}')
