.. image:: http://img.shields.io/pypi/v/sllurp.svg
    :target: https://pypi.python.org/pypi/sllurp

.. image:: https://travis-ci.org/ransford/sllurp.svg?branch=master
    :target: https://travis-ci.org/ransford/sllurp

sllurp is a Python library to interface with RFID readers.  It is a pure-Python
implementation of the Low Level Reader Protocol (LLRP).

These readers are known to work well with sllurp, but it should be adaptable
with not much effort to other LLRP-compatible readers:

- Impinj Speedway (R1000)
- Impinj Speedway Revolution (R220, R420)
- Impinj Speedway xPortal
- Motorola MC9190-Z (handheld)

File an issue on GitHub_ if you would like help getting another kind of reader
to work.

sllurp is distributed under version 3 of the GNU General Public License.  See
``LICENSE.txt`` for details.

.. _GitHub: https://github.com/ransford/sllurp/


Branch modifications
--------------------

This branch modifies the package heaviliy to make it suitable for fast re-configurations of the reader, i.e. connecting, changing a rospec parameter, inventoring, disconnecting.
As the twisted socket only allows one connection after import, we had to fake its API and implement an own transport class using the standard socket of python.
This is very hacky and is not intended for an actual application or framework.
There is a new module named "reader" where this hack is implemented for the most part.
We also had to modify the "llrp", "llrp_proto" and "llrp_decoder" modules to handle impinj specific extensions we need.
Again, very hacky implemented right now, as the package was not designed to handle custom extensions.

The longterm aim for this branch is to get rid of twisted (and probably the other third-party packages) entirely and to simplify the package code to concentrate on inventoring tags on demand.

Quick Start
-----------

.. code:: python

	from sllurp.reader import R420_EU
	
	reader = R420_EU('192.168.4.2')
	
	freqs = reader.freqTable
	powers = reader.powerTable
	
	tags = reader.detectTags(powerDBm=powers[-1], freqMHz=freqs[0], 
		mode=1002, session=2, population=1, duration=0.5, 
		impinj_searchmode=2)
	
	for iTag, tag in enumerate(tags):
		print('\n---- Tag {} ----'.format(iTag+1))
		for k, v in tag.items():
			print('{}: {}'.format(k, v))

Logging
-------

.. code:: python
	
    import logging
	
	logging.basicConfig(filename='llrp.log', level=logging.DEBUG)

Handy Reader Commands
---------------------

To see what inventory settings an Impinj reader is currently using (i.e., to
fetch the current ROSpec), ssh to the reader and

::

    > show rfid llrp rospec 0

The "nuclear option" for resetting a reader is:

::

    > reboot

If You Find a Bug
-----------------

Start an issue on GitHub_!

Bug reports are most useful when they're accompanied by verbose error messages.
Turn sllurp's log level up to DEBUG, which you can do by specifying the `-d`
command-line option to ``sllurp``.  You can log to a logfile with the ``-l
[filename]`` option.  Or simply put this at the beginning of your own code:

.. code:: python

  import logger
  sllurp_logger = logging.getLogger('sllurp')
  sllurp_logger.setLevel(logging.DEBUG)

.. _GitHub: https://github.com/ransford/sllurp/

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
