#!/bin/bash
import Tkinter as tk # for building the gui
from sllurp.reader import R420_EU # for controlling the reader

class InventoryApp(object):
	'''Main window of the application
	'''
	def __init__(self):
		self.root = tk.Tk()
		self.reader = None
		self.tags = []
		
		# initially place in the middle of the screen
		sizeX, sizeY = 640, 360
		screenX, screenY = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
		self.root.geometry('{}x{}+{}+{}'.format(sizeX, sizeY, 
			int(screenX/2-sizeX/2), int(screenY/2-sizeY/2)))
		self.root.title('Tag inventory')
		
		headFont = ('Arial', 18)
		
		# make reader settings panel
		settings = tk.Frame(self.root)
		settings.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
		# header
		tk.Label(settings, text='Reader settings', font=headFont).grid(row=0, column=0, columnspan=2)
		# ip
		self.ip = tk.StringVar()
		self.ip.set('192.168.4.2')
		tk.Label(settings, text='IP address').grid(row=1, column=0, sticky=tk.W)
		tk.Entry(settings, textvariable=self.ip).grid(row=1, column=1, sticky=tk.W)
		# tx power
		self.power = tk.DoubleVar()
		self.power.set(31.50)
		tk.Label(settings, text='Tx power [dBm]').grid(row=2, column=0, sticky=tk.W)
		tk.Scale(settings, from_=10.00, to=31.50, resolution=0.25, variable=self.power, orient=tk.HORIZONTAL).grid(row=2, column=1, sticky=tk.W+tk.E)
		# frequency
		self.freq = tk.DoubleVar()
		self.freq.set(865.7)
		tk.Label(settings, text='Frequency [MHz]').grid(row=3, column=0, sticky=tk.W)
		tk.OptionMenu(settings, self.freq, 865.7, 866.3, 866.9, 867.5).grid(row=3, column=1, sticky=tk.W+tk.E)
		# preset mode
		self.presetmode = tk.IntVar()
		self.presetmode.set(3)
		tk.Label(settings, text='Preset mode').grid(row=4, column=0, sticky=tk.W)
		tk.OptionMenu(settings, self.presetmode, 0, 1, 2, 3, 5, 1000, 1002).grid(row=4, column=1, sticky=tk.W+tk.E)
		# search mode
		self.searchmode = tk.IntVar()
		self.searchmode.set(3)
		tk.Label(settings, text='Search mode').grid(row=5, column=0, sticky=tk.W)
		tk.OptionMenu(settings, self.searchmode, 0, 1, 2, 3).grid(row=5, column=1, sticky=tk.W+tk.E)
		# session
		self.session = tk.IntVar()
		self.session.set(1)
		tk.Label(settings, text='Session').grid(row=6, column=0, sticky=tk.W)
		tk.OptionMenu(settings, self.session, 1, 2).grid(row=6, column=1, sticky=tk.W+tk.E)
		# tag population
		self.population = tk.IntVar()
		self.population.set(10)
		tk.Label(settings, text='Tag population').grid(row=7, column=0, sticky=tk.W)
		tk.Entry(settings, textvariable=self.population).grid(row=7, column=1, sticky=tk.W)
		# inventory duration
		self.duration = tk.DoubleVar()
		self.duration.set(1.0)
		tk.Label(settings, text='Inventory duration [s]').grid(row=8, column=0, sticky=tk.W)
		tk.Entry(settings, textvariable=self.duration).grid(row=8, column=1, sticky=tk.W)
		# buttons for connect and inventory
		self.btnConnect = tk.Button(settings, text='Connect reader', command=self.connect)
		self.btnConnect.grid(row=9, column=0, sticky=tk.W+tk.E+tk.S)
		settings.rowconfigure(9, weight=1)
		self.btnInventory = tk.Button(settings, text='Inventory', command=self.inventory, state=tk.DISABLED)
		self.btnInventory.grid(row=9, column=1, sticky=tk.W+tk.E+tk.S)
		settings.rowconfigure(9, weight=1)
		
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
	
	def connect(self):
		if not self.reader:
			try:
				self.reader = R420_EU(self.ip.get())
				self.btnConnect.config(state=tk.DISABLED)
				self.btnInventory.config(state=tk.NORMAL)
			except:
				pass
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
		# inventory with settings
		self.tags = self.reader.detectTags(
			powerDBm=self.power.get(), 
			freqMHz=self.freq.get(), 
			duration=self.duration.get(), 
			mode=self.presetmode.get(), 
			session=self.session.get(), 
			searchmode=self.searchmode.get(), 
			population=self.population.get())
		# get number of tags
		def uniqueTags(trp):
			epcs = []
			for tag in trp:
				epc = tag['EPC-96']
				if epc not in epcs:
					epcs.append(epc)
			return epcs
		
		self.tagsHeader.set('{} Tags ({} unique)'.format(len(self.tags), len(uniqueTags(self.tags))))
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
			sigRange = range(-80, -40, 10)
			# get last 3 digits of Tag ID
			epc = tag.get('EPC-96', '0000')
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
	InventoryApp()