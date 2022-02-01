from __future__ import print_function
from collections import defaultdict
import logging
import pprint
import struct
from .llrp_proto import LLRPROSpec, LLRPError, Message_struct, \
	Message_Type2Name, Capability_Name2Type, AirProtocol, \
	llrp_data2xml, LLRPMessageDict, ReaderConfigurationError, EXT_TYPE
from binascii import hexlify
from .util import BITMASK
import socket # for connecting to the reader via TCP/IP

LLRP_PORT = 5084

logger = logging.getLogger(__name__)

class LLRPMessage(object):
	hdr_fmt = '!HI'
	hdr_len = struct.calcsize(hdr_fmt)  # == 6 bytes
	full_hdr_fmt = hdr_fmt + 'I'
	full_hdr_len = struct.calcsize(full_hdr_fmt)  # == 10 bytes

	def __init__(self, msgdict={}, msgbytes=b''):
		if not (msgdict or msgbytes):
			raise LLRPError(
				'Provide either a message dict or a sequence of bytes.')
		self.msgdict = msgdict
		self.msgbytes = msgbytes
		if msgdict:
			self.msgdict = LLRPMessageDict(msgdict)
			if not msgbytes:
				self.serialize()
		if msgbytes:
			self.msgbytes = msgbytes
			if not msgdict:
				self.deserialize()

	def serialize(self):
		'''Turns the msg dictionary into a sequence of bytes'''
		if not self.msgdict:
			raise LLRPError('No message dict to serialize.')
		name = list(self.msgdict.keys())[0]
		logger.debug('serializing %s command', name)
		ver = self.msgdict[name]['Ver'] & BITMASK(3)
		msgtype = self.msgdict[name]['Type'] & BITMASK(10)
		msgid = self.msgdict[name]['ID']
		try:
			encoder = Message_struct[name]['encode']
		except KeyError:
			raise LLRPError('Cannot find encoder for message type '
							'{}'.format(name))
		data = encoder(self.msgdict[name])
		self.msgbytes = struct.pack(self.full_hdr_fmt,
									(ver << 10) | msgtype,
									len(data) + self.full_hdr_len,
									msgid) + data
		logger.debug('serialized bytes: %s', hexlify(self.msgbytes))
		logger.debug('done serializing %s command', name)

	def deserialize(self):
		'''Turns a sequence of bytes into a message dictionary.'''
		if not self.msgbytes:
			raise LLRPError('No message bytes to deserialize.')
		data = self.msgbytes
		msgtype, length, msgid = struct.unpack(self.full_hdr_fmt,
											   data[:self.full_hdr_len])
		ver = (msgtype >> 10) & BITMASK(3)
		msgtype = msgtype & BITMASK(10)
		try:
			if msgtype == EXT_TYPE:
				# patch for impinj extensions
				cust_fmt = '!IB'
				cust_fmt_len = struct.calcsize(cust_fmt)
				vendor, subtype = struct.unpack(cust_fmt, 
					data[self.full_hdr_len:self.full_hdr_len+cust_fmt_len])
				name = Message_Type2Name[(msgtype, subtype)]
			else:
				name = Message_Type2Name[msgtype]
			logger.debug('deserializing %s command', name)
			decoder = Message_struct[name]['decode']
		except KeyError:
			raise LLRPError('Cannot find decoder for message type '
							'{}'.format(msgtype))
		body = data[self.full_hdr_len:length]
		try:
			self.msgdict = {
				name: dict(decoder(body))
			}
			self.msgdict[name]['Ver'] = ver
			self.msgdict[name]['Type'] = msgtype
			self.msgdict[name]['ID'] = msgid
			logger.debug('done deserializing %s command', name)
		except LLRPError:
			logger.exception('Problem with %s message format', name)
			return ''
		return ''

	def isSuccess(self):
		if not self.msgdict:
			return False
		msgName = self.getName()
		md = self.msgdict[msgName]

		try:
			if msgName == 'READER_EVENT_NOTIFICATION':
				ev = md['ReaderEventNotificationData']
				if 'ConnectionAttemptEvent' in ev:
					return ev['ConnectionAttemptEvent']['Status'] == 'Success'
				elif 'AntennaEvent' in ev:
					return ev['AntennaEvent']['EventType'] == 'Connected'
			elif 'LLRPStatus' in md:
				return md['LLRPStatus']['StatusCode'] == 'Success'
		except KeyError:
			logger.exception('failed to parse status from %s', msgName)
			return False
		
		# nothing to complain apparently
		return True

	def getName(self):
		if not self.msgdict:
			return ''
		return list(self.msgdict.keys())[0]

	def __repr__(self):
		try:
			ret = llrp_data2xml(self.msgdict)
		except TypeError as te:
			logger.exception(te)
			ret = ''
		return ret


class Transport:
	'''TCP socket interface'''
	def __init__(self):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.isConnected = False
	
	def connect(self, ip, port):
		self.sock.connect((ip, port))
		self.isConnected = True
	
	def write(self, msg):
		self.sock.sendall(msg)
	
	def read(self, timeout=None):
		self.sock.settimeout(timeout)
		return self.sock.recv(4096)
	
	def disconnect(self):
		self.sock.close()
		self.isConnected = False
		
class LLRPClient(object):
	
	def __init__(self, ip, antennas=(0,), power=0, channel=1, 
				report_interval=0.1, report_every_n_tags=None, report_timeout=10.,
				report_selection={}, mode_index=None, mode_identifier=None, tari=None, 
				session=2, population=1, freq_hop_table_id=0):
		# settings
		self.ip = ip # reader ip address
		
		self.antennas = antennas # list or tuple of antenna indices to use
		self.power = power # transmit power index based on the power_table
		self.channel = channel # frequency channel index
		self.hopTableID = freq_hop_table_id # frequency hop table id
		
		self.report_interval = report_interval # report after duration in sec, OR...
		self.report_every_n_tags = report_every_n_tags # report every n tags
		self.report_timeout = report_timeout # in case every n tags don't respond
		
		self.population = population # estimated tag population
		self.session = session # 0...3 for inventoring same tag(s) with different readers
		self.mode_index = mode_index # mode table index, OR...
		self.mode_identifier = mode_identifier # mode name in table
		self.tari = tari # is ignored on impinj readers / set through mode
		
		self.report_selection = report_selection # what to report
		
		# instance properties
		self.transport = Transport()
		self.capabilities = {}
		self.power_table = []
		self.power_idx_table = []
		self.freq_table = []
		self.mode_table = []
		self.reader_mode = None
		
		self.expectingRemainingBytes = 0
		self.partialData = ''
		
		self.lastReceivedMsg = None
		
		self.msgCallbacks = defaultdict(list)
	
	def reportTimeout(self):
		''':returns: timeout for tag reports'''
		return self.report_timeout+1 if self.report_every_n_tags else max(5., (self.report_interval or 1.)+1.)
	
	def startConnection(self):
		# connect
		self.transport.connect(self.ip, LLRP_PORT)
		# await connection message from reader
		try:
			self.readLLRPMessage('READER_EVENT_NOTIFICATION')
		except LLRPError:
			# when the region is not set, we cannot access the reader
			# to set the region, ssh root@<ip>, pw: "impinj" >show system region >config system region <region id>
			self.disconnect()
			raise
		except TimeoutError:
			pass # reader does not notify
		
		# get reader capabilities
		self.getCapabilities()
	
	def disconnect(self):
		self.transport.disconnect()
	
	def __del__(self):
		# close connection
		try:
			self.stopPolitely()
			self.disconnect()
		except:
			pass
	
	def addMsgCallback(self, msg, cb):
		'''Adds a function callback which is called for a 
		specified message from the reader.
		The function gets called with the message dictionary as argument.'''
		self.msgCallbacks[msg].append(cb)
	
	def removeMsgCallback(self, msg, cb):
		'''Removes a function callback added in "addMsgCallback"'''
		self.msgCallbacks[msg].remove(cb)
	
	def parseCapabilities(self, capdict):
		'''Parse a capabilities dictionary and adjust instance settings.
		Sets the following instance variables:
		- self.antennas (list of antenna numbers, e.g., [1] or [1, 2])
		- self.power_table (list of dBm values)
		- self.reader_mode (dictionary of mode settings, e.g., Tari)
		'''
		logger.debug('Checking parameters against reader capabilities')
		# check requested antenna set
		gdc = capdict['GeneralDeviceCapabilities']
		max_ant = gdc['MaxNumberOfAntennaSupported']
		if max(self.antennas) > max_ant:
			self.antennas = tuple(range(1, max_ant + 1))
			logger.info('Wrong antennas specified. Setting to max supported antennas')
		
		# parse available transmit power entries, set self.power
		bandcap = capdict['RegulatoryCapabilities']['UHFBandCapabilities']
		self.parsePowerTable(bandcap)
		logger.debug('power_table: %s', self.power_table)
		# check for valid power index
		maxPowerIdx = max(self.power_idx_table)
		if self.power > maxPowerIdx or self.power < 0:
			self.power = maxPowerIdx
			logger.info('Wrong power index %d specified. Setting to max power', self.power)
		
		# parse available frequencies
		self.freq_table = self.parseFreqTable(bandcap)
		
		# parse modes
		regcap = capdict['RegulatoryCapabilities']
		modes = regcap['UHFBandCapabilities']['UHFRFModeTable']
		self.mode_table = [v['ModeIdentifier'] for v in modes.values()]
		# select a mode by matching available modes to requested parameters:
		# favor mode_identifier over mode_index
		if self.mode_identifier is not None:
			mode_matches = [v for v in modes.values() 
				if v['ModeIdentifier'] == self.mode_identifier]
			if not mode_matches:
				raise ReaderConfigurationError('Invalid mode_identifier {}. '
					'Modes available: {}'.format(self.mode_identifier, self.mode_table))
			else:
				self.reader_mode = mode_matches[0]
			
		elif self.mode_index is not None:
			mode_list = [modes[k] for k in sorted(modes.keys())]
			try:
				self.reader_mode = mode_list[self.mode_index]
			except IndexError:
				raise ReaderConfigurationError('Invalid mode_index')
			
		else:
			logger.info('Using default mode (index 0)')
			self.reader_mode = list(modes.values())[0]

		logger.debug('using reader mode: %s', self.reader_mode)

		# check if Impinj reader
		self.vendor = capdict['GeneralDeviceCapabilities']['DeviceManufacturerName']
	
	def getCapabilities(self):
		'''Requests reader capabilities and parses them to 
		set reader mode, tari and tx power table.'''
		self.send_GET_READER_CAPABILITIES()
		self.capabilities = self.readLLRPMessage('GET_READER_CAPABILITIES_RESPONSE')
		logger.debug('Capabilities: %s', pprint.pformat(self.capabilities))
		try:
			self.parseCapabilities(self.capabilities)
		except ReaderConfigurationError as err:
			logger.exception('Capabilities mismatch')
			raise err
	
	def getROSpec(self, *args, **kwargs):
		logger.debug('Creating ROSpec')
		self.parseCapabilities(self.capabilities) # check if parameters are valid
		# create an ROSpec to define the reader's inventorying behavior
		rospec = LLRPROSpec(1, *args, **kwargs)
		logger.debug('ROSpec: %s', rospec)
		return rospec
	
	def startInventory(self):
		'''Add a ROSpec to the reader and enable it.'''
		rospec = self.getROSpec(
			antennas=self.antennas, 
			power=self.power, 
			channel=self.channel, 
			report_interval=self.report_interval, 
			report_every_n_tags=self.report_every_n_tags, 
			report_timeout=self.report_timeout,
			report_selection=self.report_selection, 
			mode_index=self.mode_index or self.reader_mode['ModeIdentifier'],
			tari=self.tari or self.reader_mode['MaxTari'],
			session=self.session,
			population=self.population,
			hopTableID=self.hopTableID
		)['ROSpec']
		logger.info('starting inventory')
		# add rospec
		self.send_ADD_ROSPEC(rospec)
		self.readLLRPMessage('ADD_ROSPEC_RESPONSE')
		# enable rospec
		self.send_ENABLE_ROSPEC(rospec['ROSpecID'])
		self.readLLRPMessage('ENABLE_ROSPEC_RESPONSE')
	
	def stopPolitely(self):
		'''Delete all active AccessSpecs and ROSpecs.'''
		logger.info('stopping politely')
		# delete all accessspecs
		self.send_DELETE_ACCESSSPEC()
		self.readLLRPMessage('DELETE_ACCESSSPEC_RESPONSE')
		# delete all rospecs
		self.send_DELETE_ROSPEC()
		self.readLLRPMessage('DELETE_ROSPEC_RESPONSE')
	
	def startAccess(self, readWords=None, writeWords=None, target=None,
					opCount=1, accessSpecID=1, param=None,
					*args):
		m = Message_struct['AccessSpec']
		if not target:
			target = {
				'MB': 0,
				'Pointer': 0,
				'MaskBitCount': 0,
				'TagMask': b'',
				'DataBitCount': 0,
				'TagData': b''
			}

		opSpecParam = {
			'OpSpecID': 0,
			'AccessPassword': 0,
		}

		if readWords:
			opSpecParam['MB'] = readWords['MB']
			opSpecParam['WordPtr'] = readWords['WordPtr']
			opSpecParam['WordCount'] = readWords['WordCount']
			if 'OpSpecID' in readWords:
				opSpecParam['OpSpecID'] = readWords['OpSpecID']
			if 'AccessPassword' in readWords:
				opSpecParam['AccessPassword'] = readWords['AccessPassword']

		elif writeWords:
			opSpecParam['MB'] = writeWords['MB']
			opSpecParam['WordPtr'] = writeWords['WordPtr']
			opSpecParam['WriteDataWordCount'] = \
				writeWords['WriteDataWordCount']
			opSpecParam['WriteData'] = writeWords['WriteData']
			if 'OpSpecID' in writeWords:
				opSpecParam['OpSpecID'] = writeWords['OpSpecID']
			if 'AccessPassword' in writeWords:
				opSpecParam['AccessPassword'] = writeWords['AccessPassword']

		elif param:
			# special parameters like C1G2Lock
			opSpecParam = param

		else:
			raise LLRPError('startAccess requires readWords or writeWords.')

		accessStopParam = {
			'AccessSpecStopTriggerType': 1 if opCount > 0 else 0,
			'OperationCountValue': opCount,
		}

		accessSpec = {
			'Type': m['type'],
			'AccessSpecID': accessSpecID,
			'AntennaID': 0,  # all antennas
			'ProtocolID': AirProtocol['EPCGlobalClass1Gen2'],
			'C': False,  # disabled by default
			'ROSpecID': 0,  # all ROSpecs
			'AccessSpecStopTrigger': accessStopParam,
			'AccessCommand': {
				'TagSpecParameter': {
					'C1G2TargetTag': {  # XXX correct values?
						'MB': target['MB'],
						'M': 1,
						'Pointer': target['Pointer'],
						'MaskBitCount': target['MaskBitCount'],
						'TagMask': target['TagMask'],
						'DataBitCount': target['DataBitCount'],
						'TagData': target['TagData']
					}
				},
				'OpSpecParameter': opSpecParam,
			},
			'AccessReportSpec': {
				'AccessReportTrigger': 1  # report at end of access
			}
		}
		logger.debug('AccessSpec: %s', accessSpec)

		# add spec
		self.send_ADD_ACCESSSPEC(accessSpec)
		self.readLLRPMessage('ADD_ACCESSSPEC_RESPONSE')
		# enable it
		self.send_ENABLE_ACCESSSPEC(accessSpec['AccessSpecID'])
		self.readLLRPMessage('ENABLE_ACCESSSPEC_RESPONSE')
	
	def handleMessage(self, lmsg):
		'''Checks a LLRP message for common issues.'''
		self.lastReceivedMsg = lmsg
		logger.debug('LLRPMessage received: %s', lmsg)
		msgName = lmsg.getName()
		if not msgName:
			logger.warning('Cannot handle unknown LLRP message')
			return
		msgDict = lmsg.msgdict[msgName]
		
		# check errors in the message
		if not lmsg.isSuccess():
			if 'LLRPStatus' in msgDict:
				status = msgDict['LLRPStatus']['StatusCode']
				err = msgDict['LLRPStatus']['ErrorDescription']
				logger.fatal('Error %s in %s: %s', status, msgName, err)
			raise LLRPError('Message %s was not successful. See log for details.', msgName)
		
		# keepalives can occur at any time
		if msgName == 'KEEPALIVE':
			self.send_KEEPALIVE_ACK()
		
		# call registered callback functions
		for fn in self.msgCallbacks[msgName]:
			fn(msgDict)
		
	def rawDataReceived(self, data):
		'''Receives binary data from the reader. In normal cases, we can parse 
		the message according to the protocoll and return it as a dictionary.'''
		logger.debug('got %d bytes from reader: %s', len(data), hexlify(data))
		
		if self.expectingRemainingBytes:
			if len(data) >= self.expectingRemainingBytes:
				data = self.partialData + data
				self.partialData = ''
				self.expectingRemainingBytes -= len(data)
			else:
				# still not enough; wait until next time
				self.partialData += data
				self.expectingRemainingBytes -= len(data)
				return
			
		while data:
			# parse the message header to grab its length
			if len(data) >= LLRPMessage.full_hdr_len:
				msg_type, msg_len, message_id = struct.unpack(
					LLRPMessage.full_hdr_fmt, data[:LLRPMessage.full_hdr_len])
			else:
				logger.warning('Too few bytes (%d) to unpack message header', len(data))
				self.partialData = data
				self.expectingRemainingBytes = LLRPMessage.full_hdr_len - len(data)
				break
			
			logger.debug('expect %d bytes (have %d)', msg_len, len(data))
			
			if len(data) < msg_len:
				# got too few bytes
				self.partialData = data
				self.expectingRemainingBytes = msg_len - len(data)
				logger.debug('Too few bytes (%d) received to unpack message at once. '
					'(%d) remaining bytes', len(data), self.expectingRemainingBytes)
				break
			else:
				# got at least the right number of bytes
				self.expectingRemainingBytes = 0
				lmsg = LLRPMessage(msgbytes=data[:msg_len])
				self.handleMessage(lmsg)
				data = data[msg_len:]
	
	def send_KEEPALIVE_ACK(self):
		self.sendLLRPMessage(LLRPMessage(msgdict={
			'KEEPALIVE_ACK': {
				'Ver':  1,
				'Type': 72,
				'ID':   0,
			}}))
	
	def send_GET_READER_CAPABILITIES(self):
		self.sendLLRPMessage(LLRPMessage(msgdict={
			'GET_READER_CAPABILITIES': {
				'Ver':  1,
				'Type': 1,
				'ID':   0,
				'RequestedData': Capability_Name2Type['All']
			}}))
	
	def send_ADD_ROSPEC(self, roSpec):
		self.sendLLRPMessage(LLRPMessage(msgdict={
			'ADD_ROSPEC': {
				'Ver':  1,
				'Type': 20,
				'ID':   0,
				'ROSpecID': roSpec['ROSpecID'],
				'ROSpec': roSpec,
			}}))
	
	def send_ENABLE_ROSPEC(self, roSpecID):
		self.sendLLRPMessage(LLRPMessage(msgdict={
			'ENABLE_ROSPEC': {
				'Ver':  1,
				'Type': 24,
				'ID':   0,
				'ROSpecID': roSpecID
			}}))
	
	def send_DELETE_ROSPEC(self, roSpecID=0):
		# when ID is 0, deletes all ROSpecs
		self.sendLLRPMessage(LLRPMessage(msgdict={
			'DELETE_ROSPEC': {
				'Ver':  1,
				'Type': 21,
				'ID':   0,
				'ROSpecID': roSpecID
			}}))
	
	def send_ADD_ACCESSSPEC(self, accessSpec):
		self.sendLLRPMessage(LLRPMessage(msgdict={
			'ADD_ACCESSSPEC': {
				'Ver':  1,
				'Type': 40,
				'ID':   0,
				'AccessSpec': accessSpec,
			}}))

	def send_ENABLE_ACCESSSPEC(self, accessSpecID):
		self.sendLLRPMessage(LLRPMessage(msgdict={
			'ENABLE_ACCESSSPEC': {
				'Ver':  1,
				'Type': 42,
				'ID':   0,
				'AccessSpecID': accessSpecID,
			}}))
	
	def send_DISABLE_ACCESSSPEC(self, accessSpecID=1):
		self.sendLLRPMessage(LLRPMessage(msgdict={
			'DISABLE_ACCESSSPEC': {
				'Ver':  1,
				'Type': 43,
				'ID':   0,
				'AccessSpecID': accessSpecID,
			}}))
	
	def send_DELETE_ACCESSSPEC(self, accessSpecID=0):
		# when ID is 0, deletes all access specs
		self.sendLLRPMessage(LLRPMessage(msgdict={
			'DELETE_ACCESSSPEC': {
				'Ver': 1,
				'Type': 41,
				'ID': 0,
				'AccessSpecID': accessSpecID
			}}))
	
	def parsePowerTable(self, uhfbandcap):
		'''Parse the transmit power table.
		:param uhfbandcap: Capability dictionary from
			self.capabilities['RegulatoryCapabilities']['UHFBandCapabilities']
		'''
		self.power_table = []
		self.power_idx_table = []
		for k, v in uhfbandcap.items():
			if k.startswith('TransmitPowerLevelTableEntry'):
				self.power_table.append(int(v['TransmitPowerValue'])/100.)
				self.power_idx_table.append(int(v['Index']))
		
		self.power_table.sort()
		self.power_idx_table.sort()
	
	def parseFreqTable(self, uhfbandcap):
		'''Parse the frequency table.
		:param uhfbandcap: Capability dictionary from
			self.capabilities['RegulatoryCapabilities']['UHFBandCapabilities']
		:returns: list of frequencies in MHz
		'''
		freqInfos = uhfbandcap.get('FrequencyInformation')
		if freqInfos:
			# checks the frequency informations
			def freqTableValuesMHz(freqTable):
				''':returns: frequency values in MHz'''
				freqs = [int(v)/1000. for k, v in freqTable.items() if k.startswith('Frequency')]
				freqs.sort()
				return freqs
			
			# frequency hopping region?
			hopping = freqInfos.get('Hopping')
			if hopping:
				freqHopTables = [v for k, v in freqInfos.items() if k.startswith('FrequencyHopTable')]
				if freqHopTables:
					# select frequency hop table based on specified id
					freqHopIDTables = list(filter(lambda t: t['HopTableId'] == self.hopTableID, freqHopTables))
					if freqHopIDTables:
						freqHopTable = freqHopIDTables[0]
					else:
						freqHopTable = freqHopTables[0]
						logger.warning('No hop table with id {} found. '
							'Using table {}'.format(self.hopTableID, freqHopTable))
						self.hopTableID = freqHopTable['HopTableId']

					return freqTableValuesMHz(freqHopTable)
			else:
				# fixed frequency list
				fixedFreqTable = freqInfos.get('FixedFrequencyTable')
				if fixedFreqTable:
					return freqTableValuesMHz(fixedFreqTable)
		
		logger.warning('No fixed or hop frequency table in capabilities')
		return []
	
	def sendLLRPMessage(self, llrp_msg):
		self.transport.write(llrp_msg.msgbytes)
	
	def readLLRPMessage(self, msgName=None):
		'''Reads incoming data from the reader until a specified message.'''
		self.lastReceivedMsg = {}
		
		# receive data
		self.rawDataReceived(self.transport.read(self.reportTimeout()))
		while self.expectingRemainingBytes:
			self.rawDataReceived(self.transport.read(self.reportTimeout()))
		if not hasattr(self.lastReceivedMsg, 'getName'):
			raise LLRPError('Could not decode llrp message from reader')
		
		if msgName:
			# wait until expected message received
			while self.lastReceivedMsg.getName() != msgName:
				self.rawDataReceived(self.transport.read(self.reportTimeout()))
		else:
			msgName = self.lastReceivedMsg.getName()
		return self.lastReceivedMsg.msgdict[msgName]