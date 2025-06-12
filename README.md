# DEWETRON pyOxygenSCPI

pyOxygenSCPI is a Python wrapper for SCPI communication with Dewetron Oxygen


# Installation

## Manual

1. Clone GIT repository \
`git clone https://github.com/DEWETRON/pyOxygenSCPI.git`

2. Change to directory \
`cd pyOxygenSCPI`

3. Install \
`python3 setup.py install`

## Using pip
```bash
python3 -m pip install git+https://github.com/DEWETRON/pyOxygenSCPI.git
```

# Documentation
## Quick Start
This quick demo shows how to connect to an Oxygen instance on the local system and displays its channel list:
```python
from pyOxygenSCPI import OxygenSCPI

mDevice = OxygenSCPI(ip_addr='localhost', tcp_port=10001)
channel_list = mDevice.getChannelList()

print("Available channels:")
for ch_id, ch_name in channel_list:
    print(f"  {ch_name:20} (id = {ch_id})")
```

You can find more examples in the [examples](examples) folder.

## OXYGEN SCPI Command Reference
You can find the SCPI command reference here: https://docs.dewetron.cloud/doc/scpi/

# About

**For technical questions please contact:**

Michael Oberhofer 

michael.oberhofer@dewetron.com

Gunther Laure

gunther.laure@dewetron.com




# License
MIT License

Copyright (c) 2021 DEWETRON

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
LICENSE (END)
