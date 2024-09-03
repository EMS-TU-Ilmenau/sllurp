import struct
import logging
from . import llrp_proto
from .util import BITMASK

logger = logging.getLogger(__name__)

EXT_TYPE = 1023 # extension type
IPJ_VEND = 25882 # Impinj vendor id
MOTO_VEND = 161 # Motorola/Zebra vendor id

tve_header = '!B'
tve_header_len = struct.calcsize(tve_header)

tve_param_formats = {
	# param type: (param name, struct format)
	1: ('AntennaID', '!H'),
	2: ('FirstSeenTimestampUTC', '!Q'),
	3: ('FirstSeenTimestampUptime', '!Q'),
	4: ('LastSeenTimestampUTC', '!Q'),
	5: ('LastSeenTimestampUptime', '!Q'),
	6: ('PeakRSSI', '!b'),
	7: ('ChannelIndex', '!H'),
	8: ('TagSeenCount', '!H'),
	9: ('ROSpecID', '!I'),
	10: ('InventoryParameterSpecID', '!H'),
	14: ('SpecIndex', '!H'),
	15: ('ClientRequestOpSpecResult', '!H'),
	16: ('AccessSpecID', '!I')
}

impinj_param_formats = {
	# param subtype: (param name, struct format, recalculation function)
	56: ('PhaseAngle', '!H', lambda x: x*360.0/4096),
	57: ('RSSI', '!h', lambda x: x/100.0)
}

moto_param_formats = {
	# param subtype: (param name, struct format, recalculation function)
	709: ('TagPhase', '!h', lambda x: x*180.0/0x8000)
}

ext_param_formats = {
	IPJ_VEND: impinj_param_formats, 
	MOTO_VEND: moto_param_formats
}

def decode_tve_parameter(data):
	'''
	Generic byte decoding function for tve parameters.
	
	Given an array of bytes, tries to interpret a tve parameter from the
	beginning of the array.  Returns the decoded data and the number of bytes
	it read
	'''
	# decode the TVE field's header (1 bit "reserved" + 7-bit type)
	(msgtype,) = struct.unpack(tve_header, data[:tve_header_len])
	if not msgtype & 0b10000000:
		return None, 0
	
	msgtype = msgtype & 0x7f
	
	par = tve_param_formats.get(msgtype)
	if par:
		param_name = par[0]
		param_fmt = par[1]
		logger.debug('found %s (type=%s)', param_name, msgtype)
	else:
		logger.warning('Unknown parameter subtype %d', msgtype)
		return None, 0
	
	# decode the body
	nbytes = struct.calcsize(param_fmt)
	end = tve_header_len + nbytes
	try:
		(unpacked,) = struct.unpack(param_fmt, data[tve_header_len:end])
		return {param_name: unpacked}, end
	except struct.error:
		logger.warning('Could not decode %s', param_name)
		return None, 0

def decode_ext_parameter(data):
	'''
	Generic byte decoding function for extension parameters.
	
	Given an array of bytes, tries to interpret an parameter from the
	beginning of the array.  Returns the decoded data and the number of bytes
	it read
	'''
	header = '!HHII'
	header_len = struct.calcsize(header)
	if len(data) <= header_len:
		# seems not to be the right data to decode
		return None, 0
	
	# decode the field's header
	head, _, vendor, msgtype = struct.unpack(header, data[:header_len])
	type = head & BITMASK(10)
	if type != EXT_TYPE:
		return None, 0
	
	param_formats = ext_param_formats.get(vendor)
	if not param_formats:
		logger.warning('Unknown vendor ID %d', vendor)
		return None, 0

	par = param_formats.get(msgtype)
	if par:
		param_name = par[0]
		param_fmt = par[1]
		param_calc = par[2]
		logger.debug('found %s (type=%s)', param_name, msgtype)
	else:
		logger.warning('Unknown parameter subtype %d', msgtype)
		return None, 0
	
	# decode the body
	nbytes = struct.calcsize(param_fmt)
	end = header_len + nbytes
	try:
		(unpacked,) = struct.unpack(param_fmt, data[header_len:end])
		return {param_name: param_calc(unpacked)}, end
	except struct.error:
		logger.warning('Could not decode %s', param_name)
		return None, 0