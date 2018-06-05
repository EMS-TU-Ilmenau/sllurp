from .llrp import LLRPClient # low level reader protocoll
import numpy as np # for building tx power table and searching in tables
import threading # for making live tag reports non-blocking

'''
Classes for specific reader implementations
'''

'''search for a value in an array and return index for best match'''
nearestIndex = lambda a, v: (np.abs(np.asarray(a)-v)).argmin()

class R420_EU(LLRPClient):
	def __init__(self, ip='192.168.4.2', includeEPCs=[], excludeEPCs=[], *args, **kwargs):
		''':param ip: IP address of the reader
		:param includeEPCs: string or list of strings containing EPCs to look for during inventory.
			Other tags will not be reported when used.
		:param excludeEPCs: string or list of strings containing EPCs to ignore during inventory.
			Tags with these EPCs will not be reported when used.
		'''
		# epc filters
		self.includeEPCs = includeEPCs
		self.excludeEPCs = excludeEPCs
		
		# hard codes frequency channels for ETSI EN 302-208 v1.4.1
		# getting actual frequency table (from device config) is not implemented in sllurp
		self.freq_table = [865.7, 866.3, 866.9, 867.5]
		
		# init common llrp stuff
		LLRPClient.__init__(self, ip, *args, **kwargs)
		
		# select what data we want to get from the reader
		self.report_selection = {
			'EnableROSpecID': False,
			'EnableSpecIndex': False,
			'EnableInventoryParameterSpecID': False,
			'EnableAntennaID': True,
			'EnableChannelIndex': True,
			'EnablePeakRRSI': True,
			'EnableFirstSeenTimestamp': True,
			'EnableLastSeenTimestamp': True,
			'EnableTagSeenCount': True,
			'EnableAccessSpecID': False}
		self.impinj_report_selection = {
			'ImpinjEnablePeakRSSI': True,
			'ImpinjEnableRFPhaseAngle': True}
		
		# connect to reader
		self.startConnection()
		self.enableImpinjFeatures()
		print('Connected to reader')
	
	def getPowerIndex(self, powDBm):
		'''search nearest matching power in table
		:param powDBm: power in dBm
		:returns: table index'''
		return nearestIndex(self.power_table, powDBm)+1
	
	def getChannelIndex(self, freqMHz):
		'''search nearest matching channel in table
		:param freqMHz: frequency in MHz
		:returns: table index'''
		return nearestIndex(self.freq_table, freqMHz)+1
	
	def filterTags(self, trp):
		'''Filters tags based on the EPC filters specified on construction
		:param trp: tagreport
		:returns: filtered tagreport'''
		if self.includeEPCs:
			# include tags in filter
			return [tag for tag in trp if self.getEPC(tag) in self.includeEPCs]
		elif self.excludeEPCs:
			# exclude tags in filter
			return [tag for tag in trp if self.getEPC(tag) not in self.excludeEPCs]
		else:
			# nothing to filter
			return trp
	
	def detectTags(self, powerDBm=31.5, freqMHz=866.9, duration=0.5, mode=1002, session=2, searchmode=0, population=1, rounds=1):
		'''starts the readers inventoring process and return the found tags.
		
		:param duration: gives the reader that much time in seconds to find tags
		:param powerDBm: tx power in dBm. 
			Valid values are 10...31.5 in 0.25 steps
		:param freqMHz: frequency band in MHz. 
			Valid values for EU are 865.7, 866.3, 866.9, 867.5
		:param mode: preset mode identifier which defines tari, miller, etc. 
			Valid values are 1002, 1000, 5, 3, 2, 1, 0
		:param session: depending on the searchmode has different behaviour.
		:param searchmode: impinj specific muting mode
			Valid values are 0 (not enabled), 1, 2, 3
		:param population: number of tags estimated in the readers scope
		:param rounds: number of tag reports until stopping inventoring
		:returns: list of detected tags with their meta informations
		'''
		# update settings
		self.report_interval = duration
		self.power = self.getPowerIndex(powerDBm)
		self.channel = self.getChannelIndex(freqMHz)
		self.mode_identifier = mode
		self.impinj_searchmode = searchmode
		self.session = session
		self.population = population
		# check settings against capabilities
		self.parseCapabilities(self.capabilities)
		
		# prepare inventory
		self.rounds = rounds
		self.round = 0
		self.detectedTags = []
		# we want to get informed when tags are reported
		self.addMsgCallback('RO_ACCESS_REPORT', self.foundTags)
		
		# start inventory
		self.startInventory()
		# wait for tagreport(s)
		while self.round < rounds:
			self.readLLRPMessage('RO_ACCESS_REPORT')
		
		# don't need more reports
		self.removeMsgCallback('RO_ACCESS_REPORT', self.foundTags)
		# stop inventoring
		self.stopPolitely()
		
		# return results
		if rounds == 1:
			return self.detectedTags[0]
		else:
			return self.detectedTags
	
	def foundTags(self, msgdict):
		'''report about found tags'''
		tags = msgdict['TagReportData'] or []
		tags = self.filterTags(tags) # filter tags
		self.detectedTags.append(tags) # save tag list
		print('{} unique tags detected'.format(len(self.uniqueTags(tags))))
		self.round += 1
	
	def startLiveReports(self, reportCallback, powerDBm=31.5, freqMHz=866.9, duration=1.0, mode=1002, session=2, searchmode=0, population=1):
		'''starts the readers inventoring process and 
		reports tagreports periodically through a callback function.
		
		:param reportCallback: call back function which is called every 
			"duration" seconds with the tagreport as argument
		the other parameters are the same as in "detectTags"
		'''
		# update settings
		self.report_interval = duration
		self.power = self.getPowerIndex(powerDBm)
		self.channel = self.getChannelIndex(freqMHz)
		self.mode_identifier = mode
		self.impinj_searchmode = searchmode
		self.session = session
		self.population = population
		# check settings against capabilities
		self.parseCapabilities(self.capabilities)
		
		# we want to get informed when tags are reported
		self._liveReport = reportCallback
		self.addMsgCallback('RO_ACCESS_REPORT', self._foundTagsLive)
		
		# continue non-blocking
		self._liveStop = threading.Event()
		self._liveThread = threading.Thread(target=self._liveInventory, args=(self._liveStop,))
		self._liveThread.start()
	
	def stopLiveReports(self):
		'''stops the live inventoring'''
		try:
			self._liveStop.set()
		except:
			pass
	
	def _liveInventory(self, stopper):
		'''non-blocking inventory'''
		# start inventory
		self.startInventory()
		
		# read all tag report messages until user stops
		while not stopper.is_set():
			self.readLLRPMessage('RO_ACCESS_REPORT')
		
		# don't need more reports
		self.removeMsgCallback('RO_ACCESS_REPORT', self._foundTagsLive)
		# stop inventoring
		self.stopPolitely()		
	
	def _foundTagsLive(self, msgdict):
		tags = msgdict['TagReportData'] or []
		tags = self.filterTags(tags) # filter tags
		self._liveReport(tags)
	
	def getEPC(tag):
		''':param tag: single tag dictionary of a tagreport
		:returns: EPC string'''
		epc = tag['EPC-96'] if 'EPC-96' in tag else tag['EPCData']['EPC']
		return str(epc)
	
	def uniqueTags(self, tags):
		'''gets unique tags of a tagreport
		:param tags: array containing dictionary of tag meta infos
		:returns: list of unique EPC strings'''
		epcs = []
		for tag in tags:
			epc = self.getEPC(tag)
			if epc not in epcs:
				epcs.append(epc)
		
		return epcs
