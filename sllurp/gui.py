try:
	import Tkinter as tk # for building the gui - Python 2
	import tkFileDialog # for opening a file with filedialog
except ImportError:
	import tkinter as tk # for building the gui - # Python 3
	import tkinter.filedialog as tkFileDialog

import json # for saving capabilities as JSON file
from .reader import Reader, R420, ARU2400, FX9600 # for controlling readers


readerClasses = {
	'Generic': Reader, 
	'R420': R420, 
	'ARU2400': ARU2400, 
	'FX9600': FX9600
}


class InventoryApp(object):
	'''Main window of the application
	'''
	def __init__(self):
		self.root = tk.Tk()
		self.reader = None
		self.tags = []
		self.trackedTags = []
		
		# initially place in the middle of the screen
		sizeX, sizeY = 800, 550
		screenX, screenY = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
		self.root.geometry('{}x{}+{}+{}'.format(sizeX, sizeY, 
			int(screenX/2-sizeX/2), int(screenY/2-sizeY/2)))
		self.root.title('Tag inventory')
		
		headFont = ('Arial', 18)
		
		# make reader config panel
		self.conf = tk.Frame(self.root)
		self.conf.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
		# header
		row = 0
		tk.Label(self.conf, text='Reader settings', font=headFont).grid(row=row, column=0, columnspan=2)
		# ip
		row += 1
		self.ip = tk.StringVar()
		self.ip.set('192.168.5.2')
		tk.Label(self.conf, text='IP address').grid(row=row, column=0, sticky=tk.W)
		tk.Entry(self.conf, textvariable=self.ip).grid(row=row, column=1, sticky=tk.W)
		# reader model
		row += 1
		self.model = tk.StringVar()
		self.model.set('Generic')
		tk.Label(self.conf, text='Reader model').grid(row=row, column=0, sticky=tk.W)
		tk.OptionMenu(self.conf, self.model, *(readerClasses.keys())).grid(row=row, column=1, sticky=tk.W+tk.E)
		#  button for connect
		row += 1
		self.btnConnect = tk.Button(self.conf, text='Connect reader', command=self.connect)
		self.btnConnect.grid(row=row, column=0, columnspan=2, sticky=tk.W+tk.E)
		
		# make the found tags list
		taglist = tk.Frame(self.root)
		taglist.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
		# header
		self.tagsHeader = tk.StringVar()
		self.tagsHeader.set('Tags detected')
		tk.Label(taglist, textvariable=self.tagsHeader, font=headFont).pack()
		# list containing detected tags
		scrollbar = tk.Scrollbar(taglist, orient=tk.VERTICAL)
		self.tagsDetected = tk.Listbox(taglist, yscrollcommand=scrollbar.set, selectmode=tk.SINGLE)
		scrollbar.config(command=self.tagsDetected.yview)
		scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
		self.tagsDetected.pack(fill=tk.BOTH, expand=True)
		self.tagsDetected.bind('<ButtonRelease-1>', self.selectTag)
		# buttons for filtering tags
		tk.Button(taglist, text='Track tags', command=self.trackTags).pack(fill=tk.X)
		tk.Button(taglist, text='Clear tracked', command=self.clearTrackedTags).pack(fill=tk.X)
		
		# make the selected tags info panel
		taginfo = tk.Frame(self.root)
		taginfo.pack(side=tk.LEFT, fill=tk.Y, expand=True, padx=5, pady=5)
		# header
		tk.Label(taginfo, text='Tag info', font=headFont).pack()
		# tag info string
		self.tagInfo = tk.StringVar()
		tk.Label(taginfo, textvariable=self.tagInfo, anchor=tk.W, justify=tk.LEFT).pack()
		
		# start working
		self.root.mainloop()
	
	def buildSettings(self):
		row = 3
		
		# tx power
		pows = self.reader.power_table
		row += 1
		self.power = tk.DoubleVar()
		self.power.set(pows[-1])
		tk.Label(self.conf, text='Tx power [dBm]').grid(row=row, column=0, sticky=tk.W)
		tk.Scale(self.conf, from_=pows[0], to=pows[-1], resolution=pows[1]-pows[0], variable=self.power, orient=tk.HORIZONTAL).grid(row=row, column=1, sticky=tk.W+tk.E)
		
		# frequency
		row += 1
		self.freq = tk.DoubleVar()
		self.freq.set(self.reader.freq_table[0])
		tk.Label(self.conf, text='Frequency [MHz]').grid(row=row, column=0, sticky=tk.W)
		tk.OptionMenu(self.conf, self.freq, *(self.reader.freq_table)).grid(row=row, column=1, sticky=tk.W+tk.E)
		
		# preset mode
		row += 1
		modeID = self.reader.mode_table[0]
		self.presetmode = tk.IntVar()
		self.presetmode.set(modeID)
		tk.Label(self.conf, text='Preset mode').grid(row=row, column=0, sticky=tk.W)
		tk.OptionMenu(self.conf, self.presetmode, *(self.reader.mode_table), command=self.displayModeInfos).grid(row=row, column=1, sticky=tk.W+tk.E)
		
		# preset mode infos
		row += 1
		self.modeInfo = tk.StringVar()
		self.displayModeInfos(modeID)
		tk.Label(self.conf, textvariable=self.modeInfo, anchor=tk.W, justify=tk.LEFT).grid(row=row, column=1, sticky=tk.W+tk.E)
		
		# search mode
		if isinstance(self.reader, R420):
			row += 1
			self.searchmode = tk.IntVar()
			self.searchmode.set(0)
			tk.Label(self.conf, text='Search mode').grid(row=row, column=0, sticky=tk.W)
			tk.OptionMenu(self.conf, self.searchmode, 0, 1, 2, 3).grid(row=row, column=1, sticky=tk.W+tk.E)
		
		# session
		row += 1
		self.session = tk.IntVar()
		self.session.set(1)
		tk.Label(self.conf, text='Session').grid(row=row, column=0, sticky=tk.W)
		tk.OptionMenu(self.conf, self.session, 0, 1, 2, 3).grid(row=row, column=1, sticky=tk.W+tk.E)
		
		# tag population
		row += 1
		self.population = tk.IntVar()
		self.population.set(4)
		tk.Label(self.conf, text='Tag population').grid(row=row, column=0, sticky=tk.W)
		tk.Entry(self.conf, textvariable=self.population).grid(row=row, column=1, sticky=tk.W)
		
		# inventory duration
		row += 1
		self.duration = tk.DoubleVar()
		self.duration.set(1.0)
		tk.Label(self.conf, text='Inventory duration [s]').grid(row=row, column=0, sticky=tk.W)
		tk.Entry(self.conf, textvariable=self.duration).grid(row=row, column=1, sticky=tk.W)
		
		# antennas
		row += 1
		self.antennas = tk.StringVar()
		self.antennas.set('all')
		tk.Label(self.conf, text='Antennas').grid(row=row, column=0, sticky=tk.W)
		tk.Entry(self.conf, textvariable=self.antennas).grid(row=row, column=1, sticky=tk.W)
		
		# button for single inventory
		row += 1
		tk.Button(self.conf, text='Single inventory', command=self.singleInventory).grid(row=row, column=0, columnspan=2, sticky=tk.W+tk.E+tk.S)

		# button for live inventory
		row += 1
		self.liveStateTxt = tk.StringVar()
		self.liveStateTxt.set('Live inventory')
		tk.Button(self.conf, textvariable=self.liveStateTxt, command=self.liveInventory).grid(row=row, column=0, columnspan=2, sticky=tk.W+tk.E+tk.S)
		
		# button for saving capabilities
		row += 1
		tk.Button(self.conf, text='Save capabilities', command=self.saveCapabilities).grid(row=row, column=0, columnspan=2, sticky=tk.W+tk.E+tk.S)
		self.conf.rowconfigure(row, weight=1)
	
	def displayModeInfos(self, modeID):
		'''
		Displays mode infos in the self.modeInfo label

		:param modeID: preset mode identifier
		'''
		if not self.reader:
			return
		
		# get mode infos
		modes = self.reader.capabilities['RegulatoryCapabilities']['UHFBandCapabilities']['UHFRFModeTable']
		modeInfos = next(v for v in modes.values() if v['ModeIdentifier'] == modeID)

		# convert to understandable data
		infos = ''
		
		# C: EPC HAG T&C conformance flag
		# skip, as not interesting
		
		# M: Spectral mask indicator
		ms = {
			0: 'unknown', 
			1: 'single reader', 
			2: 'multi reader', 
			3: 'dense reader'
		}
		m = ms[modeInfos['M']]
		infos += 'Spectral mask: {}\n'.format(m)
		
		# PIE: 1000 times the data1 to data0 symbol length ratio (1.5...2.0)
		pie = modeInfos['PIE']
		infos += 'PIE ratio: {}\n'.format(pie/1000)

		# Min/Step/Max Tari: tari time in ns (duration of data0 symbol)
		minTari, stepTari, maxTari = modeInfos['MinTari'], modeInfos['StepTari'], modeInfos['MaxTari']
		infos += 'Tari: '
		if maxTari != minTari:
			infos += '{}...{} ({} step) us\n'.format(minTari/1000, maxTari/1000, stepTari/1000)
		else:
			infos += '{} us\n'.format(minTari/1000)
		
		# R: DR-value. Together with BDR, defines TRcal (TRcal = DR/BDR)
		# skip, as not interesting

		# BDR: Backscatter data rate (bps), i.e. tag frequency divided by modulation factor
		blf = modeInfos['BDR']
		infos += 'Tag data rate: {} bps\n'.format(blf/1000)

		# Mod: Modulation/Encoding
		mods = {
			0: 'FM0', 
			1: 'Miller2', 
			2: 'Miller4', 
			3: 'Miller8'
		}
		mod = mods[modeInfos['Mod']]
		infos += 'Tag modulation: {}'.format(mod)

		# put in label
		self.modeInfo.set(infos)

	
	def connect(self):
		if not self.reader:
			try:
				self.readerClass = readerClasses[self.model.get()]
				self.reader = self.readerClass(self.ip.get())
			except:
				pass
			else:
				self.buildSettings()
				self.btnConnect.config(state=tk.DISABLED)
	
	def getSettings(self):
		# parse antenna ports from string
		antStr = self.antennas.get()
		antennas = (0,) if 'all' in antStr else tuple(int(a) for a in antStr.split(','))

		# inventory with settings
		settings = {
			'powerDBm': self.power.get(), 
			'freqMHz': self.freq.get(), 
			'mode': self.presetmode.get(), 
			'duration': self.duration.get(), 
			'session': self.session.get(), 
			'population': self.population.get(), 
			'antennas': antennas
		}
		if isinstance(self.reader, R420):
			settings.update({'searchmode': self.searchmode.get()})
		
		return settings
	
	def singleInventory(self):
		if not self.reader:
			return
		
		settings = self.getSettings()
		self.tags = self.reader.detectTags(**settings)
		self.listTags()
	
	def liveInventory(self):
		if not self.reader:
			return
		
		if self.liveStateTxt.get() == 'Live inventory':
			# start live inventory
			settings = self.getSettings()
			settings['timeInterval'] = settings.pop('duration')
			settings['tagInterval'] = None
			self.reader.startLiveReports(self.collectTags, **settings)
			self.liveStateTxt.set('Stop inventory')
		else:
			# stop live inventory
			self.reader._liveStop.set()
			self.liveStateTxt.set('Live inventory')
	
	def collectTags(self, tagreport):
		# list detected tags
		self.tags = tagreport
		self.listTags()

	def listTags(self):
		# clear tag list
		self.tagsHeader.set('') # clear summary
		self.tagInfo.set('') # clear selected tag infos
		self.tagsDetected.delete(0, tk.END) # clear list

		if not (self.reader and self.tags):
			return
		
		# insert found tags in list
		self.tagsHeader.set('{} Tags ({} unique)'.format(len(self.tags), len(self.reader.uniqueTags(self.tags))))
		for tag in self.tags:
			rssi = tag.get('RSSI', tag.get('PeakRSSI'))
			# make indicator for RSSI
			if rssi >= -40:
				stars = '*****'
			elif rssi >= -50:
				stars = '****'
			elif rssi >= -60:
				stars = '***'
			elif rssi >= -70:
				stars = '**'
			else:
				stars = '*'
			# get last 3 digits of Tag ID
			epc = self.reader.getEPC(tag)
			id = int(epc[-2:], 16)
			# insert line with EPC, ID and RSSI
			self.tagsDetected.insert(tk.END, '{} (...{}) | {}'.format(epc, id, stars))
	
	def trackTags(self):
		if self.reader:
			self.reader.includeEPCs = [self.reader.getEPC(tag) for tag in self.tags]
	
	def clearTrackedTags(self):
		if self.reader:
			self.reader.includeEPCs = []
	
	def selectTag(self, event):
		if self.tags:
			index = self.tagsDetected.curselection()[0]
			tag = self.tags[index]
			# show selected tag infos
			infos = ''
			for key, val in tag.items():
				infos += '{}: {}\n'.format(key, val)
			self.tagInfo.set(infos)
	
	def saveCapabilities(self):
		filepath = tkFileDialog.asksaveasfilename(
			filetypes=[('JSON', '.json'), ('All files', '*')], 
			defaultextension='.json', 
			initialfile='capabilities.json'
		)
		if filepath and self.reader: # not canceled
			with open(filepath, 'w') as file:
				file.write(json.dumps(self.reader.capabilities, indent=4))

if __name__ == '__main__':
	InventoryApp()