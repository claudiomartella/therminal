#!/usr/bin/env python

import cwiid, sys, time, math, threading, random 
import alsaseq, alsamidi
import matplotlib
from optparse import OptionParser
matplotlib.use('GTK')
import matplotlib.pylab as plt

DrumMote= "E0:E7:51:F9:61:BB"
SequMote= "00:1F:32:94:F3:A0"

class Point():
	def __init__(self, x=0, y=0):
		self.x = x
		self.y = y
	
	def setValues(self, x, y):
		self.x = x
		self.y = y

	def getValues(self):
		return (self.x, self.y)

class PointsDrawer(threading.Thread):
	def __init__(self, lock, points):
		threading.Thread.__init__(self)
		self.stop = threading.Event()
		plt.ion()
		
		self.points = points
		self.lock = lock
		self.fig = plt.figure()
		self.ax  = self.fig.add_subplot(111)
		self.data, = self.ax.plot([0, 0], [0, 0], 'o')
		self.ax.axis([0, 1024, 0, 850])
		self.sleepDelay = 0.03

	def run(self):
		xdata = []
		ydata = []
		while True:
			with self.lock:
				xdata = [ cwiid.IR_X_MAX-point.getValues()[0] for point in self.points ]
				ydata = [ point.getValues()[1] for point in self.points ]
			
			self.data.set_xdata(xdata)
			self.data.set_ydata(ydata)
			self.fig.canvas.draw()

			time.sleep(self.sleepDelay)

class MIDISequencer(threading.Thread):
        def __init__(self, lock, volumePoint, notePoint, channel):
                threading.Thread.__init__(self)
                self.stop = threading.Event()
                self.volumePoint = volumePoint
                self.notePoint   = notePoint
		self.channel     = channel
                self.lock        = lock
		self.sleepDelay   = 0.03
                alsaseq.client("therminal", 0, 1, False)
		alsaseq.start()

	def create_chord(self, action, channel, note, volume):
		chord = []	
		
		# root note		
		chord.append(action(channel, note, volume))
		# fifth note
		#chord.append(action(channel, note+7, volume))
		
		return chord

        def run(self):
		last = (0, 0)
                while True:
                        with self.lock:
                                (x1, y1) = self.volumePoint.getValues()
				(x2, y2) = self.notePoint.getValues()
                        
			volume = self._fromWIItoMIDI(127, 0, cwiid.IR_Y_MAX, 100, int(y1))
                        note   = self._fromWIItoMIDI(110, 40, cwiid.IR_X_MAX, 0, int(x1))
                        
			if volume > 0:
				lastnote, lastvolume = last
				if lastnote != note or lastvolume != volume:
					for chordnote in self.create_chord(alsamidi.noteoffevent, self.channel, lastnote, lastvolume):
						alsaseq.output(chordnote)
					#time.sleep(0.03)
					for chordnote in self.create_chord(alsamidi.noteonevent, self.channel, int(note), int(volume)):
						alsaseq.output(chordnote)
					#print "sending note %d at volume %d on channel %d" % (note, volume, self.channel)
			else:
				lastnote, lastvolume = last
				if lastvolume != 0:
					for chord in self.create_chord(alsamidi.noteoffevent, self.channel, lastnote, lastvolume):
						alsaseq.output(chord)
					#print "offing the note"
			
			last = (note, volume)

			time.sleep(self.sleepDelay)

        def _fromWIItoMIDI(self, beta, alpha, b, a, x):
                return round(x*((beta-alpha)/float(b-a))-((beta-alpha)/float(b-a))+alpha)



class DrumSequencer(threading.Thread):
	def __init__(self, lock, pointA, pointB, channel):
		threading.Thread.__init__(self)
		self.stop = threading.Event()
		self.pointA     = pointA
		self.pointB     = pointB
		self.lock       = lock
		self.channel	= channel
		self.sleepDelay = 0.03
		
		alsaseq.client("druminal", 0, 1, False)
		alsaseq.start()

	def run(self):
		p1=False
		p2=False
		
		lastx1 = lastx2 = 0
		while True:
			with self.lock:
				(x1, y1) = self.pointA.getValues()
				(x2, y2) = self.pointB.getValues()
			if y1 == 0 and p1 == True:
				p1=False
				#note = self._fromWIItoMIDI(52, 36, cwiid.IR_X_MAX, 0, int(lastx1))
				note = random.randint(1, 100) % 16 + 36
				alsaseq.output(alsamidi.noteonevent(self.channel, int(note), 126))					
				print note
                                #print "1: sending %d" % (int(note))
			
			elif y1 != 0:
				p1=True
			else:
				pass

			if y2 == 0 and p2 == True:
				p2=False
				#note = self._fromWIItoMIDI(52, 36, cwiid.IR_X_MAX, 0, int(lastx2))
                                note = random.randint(1, 100) % 16 + 36
				alsaseq.output(alsamidi.noteonevent(self.channel, int(note), 126))
                                #print "2: sending %d" % (int(note))

			elif y2 != 0:
				p2=True
			else:
				 pass
                        lastx1 = x1
                        lastx2 = x2

			time.sleep(self.sleepDelay)	


	def _fromWIItoMIDI(self, beta, alpha, b, a, x):
                return round(x*((beta-alpha)/float(b-a))-((beta-alpha)/float(b-a))+alpha)

class WiiListener(threading.Thread):
	def __init__(self, lock, point1, point2, address):
                threading.Thread.__init__(self)
                self.stop = threading.Event()
		self.lock    = lock
		self.point1  = point1
		self.point2  = point2
		self.wiimote = None
		self.address = address

	def run(self):
		try:
			self.wiimote = cwiid.Wiimote(self.address)
		except RuntimeError:
			sys.exit(-1)
		self.wiimote.mesg_callback = self._callback
		rpt_mode = 0
		rpt_mode ^= cwiid.RPT_IR
		self.wiimote.rpt_mode = rpt_mode
		self.wiimote.enable(cwiid.FLAG_MESG_IFC)
	
		exit = False
		while not exit:
			a = sys.stdin.read(1)
			if a == 'x':
				exit = False	
		
		self.wiimote.close()

	def _callback(self, mesg_list, time):
		x1 = x2 = y1 = y2 = 0
        	#print "time: %f" % time
		for mesg in mesg_list:
                	# let's ignore non IR messages (they should not arrive anyway...)
                	if mesg[0] != cwiid.MESG_IR:
                        	print "non-IR message delivered!"
                        	pass
                	# multiple sources of IR DATA
                	sources = mesg[1]
                	# volume        
                	if sources[0]:
                        	(x1, y1) = sources[0]['pos']
                        	#print "(%d, %d) " % (x1, y1)
                	# freq
                	if sources[1]:
                        	(x2, y2) = sources[1]['pos']
                        	#print "(%d, %d) " % (x2, y2)
			with self.lock:
				self.point1.setValues(x1, y1)
				self.point2.setValues(x2, y2)


if __name__=="__main__":
	
	usage  ="usage: %prog [options] arg"
	parser = OptionParser(usage)
	parser.add_option("-i", "--instrument", dest="instrument", 
			help="instrument to play [drums|sequencer]")
	parser.add_option("-a", "--address", dest="address",
			help="wiimote's address")
	parser.add_option("-c", "--channel", dest="channel",
			help="midi channel")
	(options, args) = parser.parse_args()

        pointsLock  = threading.Lock()
        P1 = Point()
        P2 = Point()
	if options.channel != None:
		ch = int(options.channel)
	else:
		parser.error("should pass channel number")
	if options.instrument == "drums":
		instrument = DrumSequencer(pointsLock, P1, P2, ch)
	elif options.instrument == "sequencer":
		instrument = MIDISequencer(pointsLock, P1, P2, ch)
	elif options.instrument == None:
		parser.error("should pass instrument name")
	else:
		parser.error("unknown instrument")

	if options.address == None:
		parser.error("should pass the wiimote address")
	
        print "Welcome to Therminal, please press 1+2 to pair your device..."

	drawer      = PointsDrawer(pointsLock, [P1, P2])
	wiilistener = WiiListener(pointsLock, P1, P2, options.address)
	drawer.start()
	instrument.start()	
	wiilistener.start()
	wiilistener.join()

	print "Exiting..."
	sys.exit(0)
