from .llrp import LLRPClient # low level reader protocoll
import threading # for making live tag reports non-blocking

'''
Classes for specific reader implementations
'''

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
		
		# init common llrp stuff
		LLRPClient.__init__(self, ip, *args, **kwargs)
		
		# backup frequency table
		self.freq_table = [865.7, 866.3, 866.9, 867.5]
		
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
		print('Connected to reader')
	
	def nearestIndex(self, arr, val):
		'''
		Searches for a value in an array and return index for best match
		:param arr: array with values (int / float)
		:param val: int or float value to search for in the array
		:returns: index for best match of value in array
		'''
		smallestDiff = 2**64-1
		iMatch = 0
		for iArr, vArr in enumerate(arr):
			# compare array value and val
			diff = abs(vArr-val)
			if diff < smallestDiff:
				# found smaller difference, so remember
				iMatch = iArr
				smallestDiff = diff

		return iMatch
	
	def getPowerIndex(self, powDBm):
		'''search nearest matching power in table
		:param powDBm: power in dBm
		:returns: table index'''
		return self.nearestIndex(self.power_table, powDBm)+1
	
	def getChannelIndex(self, freqMHz):
		'''search nearest matching channel in table
		:param freqMHz: frequency in MHz
		:returns: table index'''
		return self.nearestIndex(self.freq_table, freqMHz)+1
	
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
	
	def detectTags(self, powerDBm=31.5, freqMHz=866.9, duration=0.5, mode=1002, session=2, searchmode=0, population=1, antennas=(0,), rounds=1):
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
		:antennas: tuple of antenna ports to use for inventory.
			Set to (0,) to scan automatically over all
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
		self.antennas = antennas
		
		# prepare inventory
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
	
	def startLiveReports(self, reportCallback, powerDBm=31.5, freqMHz=866.9, duration=1.0, mode=1002, session=2, searchmode=0, population=1, antennas=(0,)):
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
		self.antennas = antennas
		
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
			self._liveThread.join()
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
	
	def getEPC(self, tag):
		''':param tag: single tag dictionary of a tagreport
		:returns: EPC string'''
		epc = tag['EPC-96'] if 'EPC-96' in tag else tag['EPCData']['EPC']
		return epc.decode()
	
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


class ARU2400(R420_EU):
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
		
		# connect to reader
		self.startConnection()
		print('Connected to reader')
	
	def detectTags(self, powerDBm=27., freqMHz=866.9, duration=0.5, mode=12, session=2, population=1, antennas=(0,)):
		'''starts the readers inventoring process and return the found tags.
		
		:param duration: gives the reader that much time in seconds to find tags
		:param powerDBm: tx power in dBm. 
			Valid values are 10...31.5 in 0.25 steps
		:param freqMHz: frequency band in MHz. 
			Valid values for EU are 865.7, 866.3, 866.9, 867.5
		:param mode: preset mode identifier which defines tari, miller, etc. 
			Valid values are 1002, 1000, 5, 3, 2, 1, 0
		:param session: controls tag muting behaviour
		:param population: number of tags estimated in the readers scope
		:antennas: tuple of antenna ports to use for inventory.
			Set to (0,) to scan automatically over all
		:returns: list of detected tags with their meta informations
		'''
		# Kathrein does not report multiple tags in one tagreport, so typical interval report is not possible
		# update settings
		self.report_interval = None
		self.report_every_n_tags = 10 # report every n tags
		self.report_timeout = duration # in case every n tags don't respond
		self.power = self.getPowerIndex(powerDBm)
		self.channel = self.getChannelIndex(freqMHz)
		self.mode_identifier = mode
		self.session = session
		self.population = population
		self.antennas = antennas
		
		# prepare inventory
		self.round = 0
		self.detectedTags = []
		# we want to get informed when tags are reported
		self.addMsgCallback('RO_ACCESS_REPORT', self.foundTags)
		
		# start inventory
		self.startInventory()
		# wait for tagreport(s)
		nAnts = self.capabilities['GeneralDeviceCapabilities']['MaxNumberOfAntennaSupported']
		while self.round < population*nAnts:
			try:
				self.readLLRPMessage('RO_ACCESS_REPORT')
			except:
				# Kathrein does not respond with an empty RO_ACCESS_REPORT
				break
		
		# don't need more reports
		self.removeMsgCallback('RO_ACCESS_REPORT', self.foundTags)
		# stop inventoring
		self.stopPolitely()
		
		# return results
		print('{} unique tags detected'.format(len(self.uniqueTags(self.detectedTags))))
		return self.detectedTags
		
	def foundTags(self, msgdict):
		'''report about found tags'''
		tags = msgdict['TagReportData'] or []
		tags = self.filterTags(tags) # filter tags
		# faking duration-based inventory (like R420) by updating existing tagreports if necessary
		for newTag in tags:
			newEPC = self.getEPC(newTag)
			newPort = newTag['AntennaID']
			alreadySeen = False
			for oldTag in self.detectedTags:
				oldEPC = self.getEPC(oldTag)
				oldPort = oldTag['AntennaID']
				if oldEPC == newEPC and oldPort == newPort:
					oldTag['TagSeenCount'] += 1
					oldTag['PeakRSSI'] = max(oldTag['PeakRSSI'], newTag['PeakRSSI'])
					oldTag['LastSeenTimestampUptime'] = max(oldTag['LastSeenTimestampUptime'], newTag['LastSeenTimestampUptime'])
					alreadySeen = True
					break
			if not alreadySeen:
				self.detectedTags.append(newTag)
		
		self.round += 1
