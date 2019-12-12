sllurp is a Python library to interface with RFID readers.
It is a pure-Python implementation of the Low Level Reader Protocol (LLRP).

These readers are known to work well with sllurp, but it should be adaptable
with not much effort to other LLRP-compatible readers:

- Impinj Speedway (R1000)
- Impinj Speedway Revolution (R220, R420)
- Impinj Speedway xPortal
- Motorola MC9190-Z (handheld)
- Kathrein ARU2400

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

Currently, only inventoring is implemented (scrapped the access methods).

.. _reader: sllurp/reader.py
.. _llrp: sllurp/llrp.py
.. _llrp_proto: sllurp/llrp_proto.py
.. _llrp_decoder: sllurp/llrp_decoder.py

Quick Start
-----------

.. code:: python

	from sllurp.reader import R420_EU
	
	reader = R420_EU('192.168.4.2')
	
	freqs = reader.freq_table
	powers = reader.power_table
	
	tags = reader.detectTags(powerDBm=powers[-1], freqMHz=freqs[0], 
		mode=1002, session=2, population=1, duration=0.5, searchmode=2)
	
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
