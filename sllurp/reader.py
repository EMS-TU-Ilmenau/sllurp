#!/bin/bash
import llrp # low level reader protocoll
import numpy as np # for building tx power table and searching in tables

'''
Classes for specific reader implementations
'''

'''search for a value in an array and return index for best match'''
nearestIndex = lambda a, v: (np.abs(np.asarray(a)-v)).argmin()

class R420_EU(llrp.LLRPClient):
	def __init__(self, ip='192.168.4.2', *args, **kwargs):
		self.detectedTags = []
		self.round = 0
		self.rounds = 1
		# hard codes frequency channels for ETSI EN 302-208 v1.4.1
		# getting actual frequency table (from device config) is not implemented in sllurp
		self.freq_table = [865.7, 866.3, 866.9, 867.5]
		
		# init common llrp stuff
		super(R420_EU, self).__init__(ip, *args, **kwargs)
		
		# we want to get informed when tags are reported
		self.addMsgCallback('RO_ACCESS_REPORT', self.foundTags)
		
		# connect to reader
		self.startConnection()
		self.enableImpinjFeatures()
		print('Connected to reader')
		
	def detectTags(self, powerDBm=31.5, freqMHz=866.9, duration=0.5, mode=1002, session=2, searchmode=0, population=1, rounds=1, **kwargs):
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
		
		# check settings against capabilities
		self.parseCapabilities(self.capabilities)
		
		# prepare inventory
		self.rounds = rounds
		self.round = 0
		self.detectedTags = []
		# start inventory
		self.startInventory()
		# wait for tagreport(s)
		while self.round < rounds:
			self.readLLRPMessage('RO_ACCESS_REPORT')
		# stop
		self.stopPolitely()
		
		# return results
		if rounds == 1:
			return self.detectedTags[0]
		else:
			return self.detectedTags
	
	def foundTags(self, msgdict):
		'''report about found tags'''
		if self.round >= self.rounds:
			return
		tags = msgdict['TagReportData'] or []
		self.detectedTags.append(tags) # save tag list
		print('{} tags detected'.format(len(tags)))
		self.round += 1
	
	def getPowerIndex(self, powDBm):
		'''search nearest matching power in table
		:param powDBm: power in dBm
		:returns: table index'''
		return nearestIndex(self.power_table, powDBm)
	
	def getChannelIndex(self, freqMHz):
		'''search nearest matching channel in table
		:param freqMHz: frequency in MHz
		:returns: table index'''
		return nearestIndex(self.freq_table, freqMHz)+1
	
	def reportTags(self, tags):
		'''prints out informations about tags found
		:param tags: array containing dictionary of tag meta infos'''
		print('\n\tReport for {} tags:\n'.format(len(tags)))
		# cycle through tags and list their stats (enabled by tag_content_selector)
		for tag in tags:
			for k, v in tag.items():
				print('{}: {}'.format(k, v))
			print('')
