#!/bin/bash
try:
	import Tkinter as tk # for building the gui - Python 2
except ImportError:
	import tkinter as tk # for building the gui - # Python 3
from sllurp.reader import R420_EU, ARU2400 # for controlling the reader

class InventoryApp(object):
	'''Main window of the application
	'''
	def __init__(self, readerClass):
		self.root = tk.Tk()
		self.readerClass = readerClass
		self.reader = None
		self.tags = []
		
		# initially place in the middle of the screen
		sizeX, sizeY = 640, 360
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
		self.ip.set('192.168.4.2')
		tk.Label(self.conf, text='IP address').grid(row=row, column=0, sticky=tk.W)
		tk.Entry(self.conf, textvariable=self.ip).grid(row=row, column=1, sticky=tk.W)
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
		row = 2
		# tx power
		row += 1
		self.power = tk.DoubleVar()
		self.power.set(self.reader.power_table[-1])
		tk.Label(self.conf, text='Tx power [dBm]').grid(row=row, column=0, sticky=tk.W)
		tk.Scale(self.conf, from_=self.reader.power_table[0], to=self.reader.power_table[-1], resolution=0.25, variable=self.power, orient=tk.HORIZONTAL).grid(row=row, column=1, sticky=tk.W+tk.E)
		# frequency
		row += 1
		self.freq = tk.DoubleVar()
		self.freq.set(self.reader.freq_table[0])
		tk.Label(self.conf, text='Frequency [MHz]').grid(row=row, column=0, sticky=tk.W)
		tk.OptionMenu(self.conf, self.freq, *(self.reader.freq_table)).grid(row=row, column=1, sticky=tk.W+tk.E)
		# preset mode
		row += 1
		self.presetmode = tk.IntVar()
		self.presetmode.set(self.reader.mode_table[0])
		tk.Label(self.conf, text='Preset mode').grid(row=row, column=0, sticky=tk.W)
		tk.OptionMenu(self.conf, self.presetmode, *(self.reader.mode_table)).grid(row=row, column=1, sticky=tk.W+tk.E)
		if self.reader.impinj_report_selection:
			# search mode
			row += 1
			self.searchmode = tk.IntVar()
			self.searchmode.set(2)
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
		self.antennas.set('auto')
		tk.Label(self.conf, text='Antennas').grid(row=row, column=0, sticky=tk.W)
		tk.Entry(self.conf, textvariable=self.antennas).grid(row=row, column=1, sticky=tk.W)
		
		# button for inventory
		self.btnInventory = tk.Button(self.conf, text='Inventory', command=self.inventory, state=tk.DISABLED)
		self.btnInventory.grid(row=row, column=0, columnspan=2, sticky=tk.W+tk.E+tk.S)
		self.conf.rowconfigure(row, weight=1)
	
	def connect(self):
		if not self.reader:
			try:
				self.reader = self.readerClass(self.ip.get())
			except:
				pass
			else:
				self.buildSettings()
				self.btnConnect.config(state=tk.DISABLED)
				self.btnInventory.config(state=tk.NORMAL)
		else:
			self.reader.disconnect()
			self.reader = None
			self.btnConnect.config(state=tk.NORMAL)
			self.btnInventory.config(state=tk.DISABLED)
	
	def inventory(self):
		self.tagsHeader.set('')
		self.tagsDetected.delete(0, tk.END) # clear list
		if not self.reader:
			return
		
		# parse antenna ports from string
		antStr = self.antennas.get()
		antennas = (0,) if 'auto' in antStr else tuple(int(a) for a in antStr.split(','))

		# inventory with settings
		settings = {
			'powerDBm': self.power.get(), 
			'freqMHz': self.freq.get(), 
			'duration': self.duration.get(), 
			'mode': self.presetmode.get(), 
			'session': self.session.get(), 
			'population': self.population.get(), 
			'antennas': antennas}
		if self.reader.impinj_report_selection:
			settings.update({'searchmode': self.searchmode.get()})
		
		self.tags = self.reader.detectTags(**settings)
		
		self.tagsHeader.set('{} Tags ({} unique)'.format(len(self.tags), len(self.reader.uniqueTags(self.tags))))
		# insert found tags
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
	
	def selectTag(self, event):
		if self.reader:
			index = self.tagsDetected.curselection()[0]
			tag = self.tags[index]
			# show selected tag infos
			infos = ''
			for key, val in tag.items():
				infos += '{}: {}\n'.format(key, val)
			self.tagInfo.set(infos)

if __name__ == '__main__':
	InventoryApp(R420_EU)