# SLLURP

sllurp is a Python library to interface with RFID readers.
It is a pure-Python implementation of the Low Level Reader Protocol (LLRP).

These readers are known to work well with sllurp, but it should be adaptable
with not much effort to other LLRP-compatible readers:

- Impinj Speedway (R1000)
- Impinj Speedway Revolution (R220, R420, R700)
- Impinj Speedway xPortal
- Motorola MC9190-Z (handheld)
- Kathrein ARU2400
- Zebra FX9600

## Branch modifications

This repository was forked from https://github.com/ransford/sllurp/ and a new branch "measurements" added, which modifies the package heaviliy to make it suitable for fast re-configurations of the reader, 
i.e. connecting, changing a rospec parameter, inventoring, changing a rospec parameter, inventoring, ..., disconnecting.

As the twisted socket only allows one connection after import, we had to implement an own transport class using the standard socket of python.
There is a new module [reader.py](sllurp/reader.py) where specific reader classes can inherit from the LLRPClient.
We also modified the [llrp.py](sllurp/llrp.py), [llrp_proto.py](sllurp/llrp_proto.py) and [llrp_decoder.py](sllurp/llrp_decoder.py) modules to handle impinj specific extensions we need.
Also, llrp.py is now completely rewritten to be state-less and does not depend on twisted.
That way, the code is much cleaner and there is no hassle with chaining deferreds.

## Quick Start

```python
from sllurp.reader import R420

reader = R420('192.168.4.2')

freqs = reader.freq_table
powers = reader.power_table

tags = reader.detectTags(powerDBm=powers[-1], freqMHz=freqs[0], 
	mode=1002, session=2, population=1, duration=0.5, searchmode=2)

for tag in tags:
	print(tag)
```

## Tag access

Example code for changing Tags EPC

```python
from sllurp.reader import R420
#import logging
#logging.basicConfig(filename='log.txt', level=logging.DEBUG)

reader = R420('192.168.4.2') # connect to reader

# setup access spec
epcLen = 12 # total number of bytes
epcRawStart = b'myTag' # let the raw EPC URI start with these bytes
epcRawUri = epcRawStart+b'\x00'*(epcLen-len(epcRawStart)) # fill up with zeros
# note: 1 Word = 2 Bytes
writeSpecParam = {
	'OpSpecID': 0,
	'MB': 1,
	'WordPtr': 2,
	'AccessPassword': 0,
	'WriteDataWordCount': len(epcRawUri)//2,
	'WriteData': epcRawUri,
}
reader.startAccess(writeWords=writeSpecParam, opCount=0) # set opCount to 1 to stop after 1 write operation
# Actually adds and enables an access spec.
# It is executed with the next inventory round (reader.detectTags())

'''
readSpecParam = {
	'OpSpecID': 0,
	'MB': 1,
	'WordPtr': 0,
	'AccessPassword': 0,
	'WordCount': 8
}
reader.startAccess(readWords=readSpecParam)
'''

print('Before changing:')
tags = reader.detectTags(powerDBm=16, antennas=(1,)) # remove antennas argument or set to (0,) to use all antenna ports
for tag in tags:
	print(tag)
# At this point, the access spec is deleted

# Normal inventory
print('After changing:')
tags = reader.detectTags(powerDBm=16, antennas=(1,))
for tag in tags:
	print(tag)
```

## Logging

```python
import logging

logging.basicConfig(level=logging.INFO)
logging.basicConfig(filename='llrp.log', level=logging.DEBUG)
```

## GUI

There is a basic GUI written in tkinter (which may be installed separatley depending on the Python version). Currently, it supports only the classes defined in [reader.py](sllurp/reader.py)

```python
from sllurp.gui import InventoryApp
app = InventoryApp() # start the GUI
```

The GUI can also be started with `python -m sllurp.gui`
