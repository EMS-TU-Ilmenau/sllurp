#!/bin/bash
import llrp # low level reader protocoll
import socket # for connecting to the reader via TCP/IP
import numpy as np # for building tx power table and searching in tables

'''
Classes for specific reader implementations
'''

'''search for a value in an array and return index for best match'''
nearestIndex = lambda a, v: (np.abs(np.asarray(a)-v)).argmin()

class FakeFactory:
	'''interface to fake llrp client factory'''
	def __init__(self):
		self.protocols = []

class FakeTransport:
	'''interface to fake twisted'''
	def __init__(self):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	
	def connect(self, ip, port):
		self.sock.connect((ip, port))
	
	def write(self, msg):
		self.sock.sendall(msg)
	
	def read(self):
		return self.sock.recv(4096)
	
	def loseConnection(self):
		pass

class R420_EU:
	def __init__(self, ip='192.168.4.2'):
		self.ip = ip
		self.detectedTags = []
		self.inventoryFinished = False
		
		# hard coded tx powers for the R420
		# could also get the values using sllurp tx_power_table (from device capabilities)
		self.powerTable = list(np.arange(10, 31.75, 0.25))
		
		# hard codes frequency channels for ETSI EN 302-208 v1.4.1
		# getting actual frequency table (from device config) is not implemented in sllurp
		self.freqTable = [865.7, 866.3, 866.9, 867.5]
		
		# note: the actual tables start indices are 1, not 0 as here
		
	def detectTags(self, duration=0.5, powerDBm=31.5, freqMHz=866.9, mode=1002, session=2, population=4, **kwargs):
		'''starts the readers inventoring process and return the found tags.
		note that the reader is very high-level, so there is not much control over it.
		:param duration: gives the reader that much time in seconds to find tags
		:param powerDBm: tx power in dBm. Valid values are 10...31.5 in 0.25 steps
		:param freqMHz: frequency band in MHz. Valid values for EU are 865.7, 866.3, 866.9, 867.5
		:param mode: preset mode identifier which defines tari, miller, etc. Valid values are 1002, 1000, 5, 3, 2, 1, 0
		:param session: defines the search routine and tag respond. Valid values are 1 (mute tags for a while), 2 (respond to every query)
		:param population: number of tags estimated in the readers scope
		:returns: list of detected tags with their meta informations
		'''
		# setup the reader via a LLRP client
		'''
		notes:
		- tx_power is an index for the tx_power_list, 0 means max power.
		- tag reports can be triggered using the duration (period in s) or report_every_n_tags (the other must be None).
		- mode_identifier set/overrides modulation. When set to None, it is choosen by the modulation.
		See Impinj_Octance_LLRP.pdf, p.19 for the mode id definitions.
		For available modulations, see Modulation_Name2Type in llrp_proto.py 
		- tari is ignored (see Impinj_Octance_LLRP.pdf, p.18).
		- per default, reader chooses searchmode (impinj specific feature) based on session.
		See http://www.brettgreen.com/llrpsource/Documents/InventorySearchMode.pdf.
		Basically, session 1 is good for inventoring as they are silenced a few seconds. 
		Session 2 is good to testing as tags respond to every request.
		- I patched llrp.py and llrp_proto.py to set channel index (frequency) in ROSpec.
		- sllurp does NOT support device configuration (similar to device capabilities).
		See chapter 12 of llrp standard. It would take too much time to implement.
		'''
		proto = llrp.LLRPClient(
			factory=FakeFactory(),
			start_inventory=True,
			reset_on_connect=False,
			duration=duration,
			report_every_n_tags=None,
			antennas=(0,),
			tx_power=self.getPowerIndex(powerDBm),
			channel=self.getChannelIndex(freqMHz),
			mode_identifier=mode,
			modulation='M4',
			tari=6250,
			session=session,
			tag_population=population,
			tag_content_selector={
				'EnableROSpecID': False,
				'EnableSpecIndex': False,
				'EnableInventoryParameterSpecID': False,
				'EnableAntennaID': True,
				'EnableChannelIndex': True,
				'EnablePeakRRSI': True,
				'EnableFirstSeenTimestamp': True,
				'EnableLastSeenTimestamp': True,
				'EnableTagSeenCount': True,
				'EnableAccessSpecID': False}, 
			impinj_content_selector={
				'ImpinjEnablePeakRSSI': True,
				'ImpinjEnableRFPhaseAngle': True}, 
			**kwargs)
		
		# setting up callbacks
		proto.addStateCallback(llrp.LLRPClient.STATE_CONNECTED, self._connected)
		proto.addStateCallback(llrp.LLRPClient.STATE_INVENTORYING, self._inventory)
		proto.addMessageCallback('RO_ACCESS_REPORT', self._foundTags)
		
		# start connection to reader
		transport = FakeTransport()
		proto.transport = transport
		transport.connect(self.ip, llrp.LLRP_PORT)
		
		# parse data while inventoring
		self.inventoryFinished = False
		while self.inventoryFinished == False:
			proto.rawDataReceived(transport.read())
		
		#print('Closing connection')
		proto.stopPolitely(disconnect=True)
		# empirically found out that this properly disconnects reader 
		# so that the power consumption goes low
		proto.rawDataReceived(transport.read())
		proto.rawDataReceived(transport.read())
		transport.sock.close()
		
		# return found tags
		return self.detectedTags
	
	def _connected(self, proto):
		'''connected to reader with llrp protocoll interface
		:param proto: llrp protocoll interface'''
		#print('Connected to reader')
		# print some informations about the reader
		'''
		print(proto.capabilities) # contains all reader capabilities like tx power table and modes
		print('ROspec:\n{}\n'.format(proto.getROSpec())) # current reader operation specs
		'''
	
	def _inventory(self, proto):
		'''inventoring has started
		:param proto: llrp protocoll interface'''
		print('Inventoring...')
		self.detectedTags = []
		self.inventoryFinished = False
	
	def _foundTags(self, tagReport):
		'''report about found tags'''
		if self.inventoryFinished:
			# already found tags
			return
		tags = tagReport.msgdict['RO_ACCESS_REPORT']['TagReportData']
		if tags:
			#self.reportTags(tags) # print tag infos (RSSI, timestamp, ...)
			self.detectedTags = tags # save tag list
		print('{} tags detected'.format(len(self.detectedTags)))
		self.inventoryFinished = True
	
	def getPowerIndex(self, powDBm):
		'''search nearest matching power in table
		:param powDBm: power in dBm
		:returns: table index'''
		return nearestIndex(self.powerTable, powDBm)+1
	
	def getChannelIndex(self, freqMHz):
		'''search nearest matching channel in table
		:param freqMHz: frequency in MHz
		:returns: table index'''
		return nearestIndex(self.freqTable, freqMHz)+1
	
	def reportTags(self, tags):
		'''prints out informations about tags found
		:param tags: array containing dictionary of tag meta infos'''
		print('\n\tReport for {} tags:\n'.format(len(tags)))
		# cycle through tags and list their stats (enabled by tag_content_selector)
		for tag in tags:
			for k, v in tag.items():
				print('{}: {}'.format(k, v))
			print('')
