sllurp is a Python library to interface with RFID readers.
It is a pure-Python implementation of the Low Level Reader Protocol (LLRP).

These readers are known to work well with sllurp, but it should be adaptable
with not much effort to other LLRP-compatible readers:

- Impinj Speedway (R1000)
- Impinj Speedway Revolution (R220, R420)
- Impinj Speedway xPortal
- Motorola MC9190-Z (handheld)
- Kathrein ARU2400
- Zebra FX9600

File an issue on GitHub_ if you would like help getting another kind of reader to work.

sllurp is distributed under version 3 of the GNU General Public License.  See
``LICENSE.txt`` for details.

.. _GitHub: https://github.com/ransford/sllurp/


Branch modifications
--------------------

This branch modifies the package heaviliy to make it suitable for fast re-configurations of the reader, 
i.e. connecting, changing a rospec parameter, inventoring, changing a rospec parameter, inventoring, ..., disconnecting.


As the twisted socket only allows one connection after import, we had to implement an own transport class using the standard socket of python.
There is a new module reader_ where specific reader classes can inherit from the LLRPClient.
We also modified the llrp_, llrp_proto_ and llrp_decoder_ modules to handle impinj specific extensions we need.
Also, llrp_ is now completely rewritten to be state-less and does not depend on twisted.
That way, the code is much cleaner and there is no hassle with chaining deferreds.

.. _reader: sllurp/reader.py
.. _llrp: sllurp/llrp.py
.. _llrp_proto: sllurp/llrp_proto.py
.. _llrp_decoder: sllurp/llrp_decoder.py

Quick Start
-----------

.. code:: python

	from sllurp.reader import R420
	
	reader = R420('192.168.4.2')
	
	freqs = reader.freq_table
	powers = reader.power_table
	
	tags = reader.detectTags(powerDBm=powers[-1], freqMHz=freqs[0], 
		mode=1002, session=2, population=1, duration=0.5, searchmode=2)
	
	for tag in tags:
		print(tag)

Tag access
-----------

Example code for changing Tags EPC

.. code:: python

	from sllurp.reader import R420
	#import logging
	#logging.basicConfig(filename='log.txt', level=logging.DEBUG)

	reader = R420('192.168.4.2') # connect to reader

	# setup access spec
	epcLen = 12 # total number of bytes
	epcRawStart = b'\x12\x34\x56\x78' # let the raw EPC URI start with these bytes
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

Logging
-------

.. code:: python
	
    import logging
	
	logging.basicConfig(filename='llrp.log', level=logging.DEBUG)

GUI
---

Currently, the GUI supports only the classes defined in reader_.
You have to change the class in the last line of the app_.

.. _reader: sllurp/reader.py
.. _app: inventory_app.py

Known Issues
------------

Reader mode selection is confusing_, not least because the LLRP specification
traditionally conflated ``ModeIndex`` and ``ModeIdentifier``.  If you're using
``sllurp inventory``, you probably want to use ``--mode-identifier N`` instead
of ``-mode-index``.  Check your reader's manual to see what mode identifiers it
supports via the ``C1G2RFControl`` parameter, or run ``sllurp --debug
inventory`` against a reader to see a dump of the supported modes in the
capabilities description.

.. _confusing: https://github.com/ransford/sllurp/issues/63#issuecomment-309233937

Contributing
------------

Want to contribute?  Here are some areas that need improvement:

- Reduce redundancy in the ``encode_*`` and ``decode_*`` functions in
  ``llrp_proto.py``.
- Support the AccessSpec primitive (basis for tag read and write).
- Write tests for common encoding and decoding tasks.
- Make ``get_reader_config`` use the ``fabric`` library to connect to readers
  via SSH.
- Generalize LLRP support beyond Impinj readers.  Remove Impinj-specific
  assumptions.

Authors
-------

Much of the code in sllurp is by `Ben Ransford`_, although it began its life in
August 2013 as a fork of LLRPyC_.  Many fine citizens of GitHub have
contributed code to sllurp since the fork.

.. _Ben Ransford: https://ben.ransford.org/
.. _LLRPyC: https://sourceforge.net/projects/llrpyc/
