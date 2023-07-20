from datetime import date, datetime, timezone
import logging
import threading
import copy
import pickle
import codecs
import EventDB
import EQEventGatherer

now = datetime.now()

# Colors for display
BLACK  = (0, 0, 0)
WHITE  = (255, 255, 255)
RED    = (255, 0, 0)
YELLOW = (255, 255, 0)
ORANGE = (255, 215, 0)
BLUE = (173, 216, 230)

# Converted EQMap into a class.
class EQMap:
    def __init__(self, dispMgr):
        self.displayManager = dispMgr
        self.blinkToggle = False
        # Create instance of database
        self.eventDB = EventDB.EventDB()
        self.cqID = ""
        self.cqLon = 0.0
        self.cqLat = 0.0
        self.cqEv = ""       # *** Earthquake Type ***
        self.cqMag = 0.0  # mag of earthquake
        self.cqMag1 = 0.0 # max mag today
        self.cqMag2 = 0.0 # max mag this year
        self.cqDepth = 0.0
        self.cqTime = datetime.now()  # time of earthquake
        self.cqTime1 = datetime.now() # time of max earthquake (h,m,s)
        self.cqTime2 = datetime.now(timezone.utc) # time of max earthquake this year (d,m,y)        
        self.cqLocation = " " # location of earthquake
        self.cqLocation1 = " " # location of max
        self.cqLocation2 = "" # location of max this year  
        self.lock = threading.Lock()

        # Check if databases exist, if not, create them
        try:
            with open('score.dat', 'rb') as file:
                self.cqMag2 = pickle.load(file)  
        except (FileNotFoundError, EOFError) as e:
            logging.error(f"An error occurred while loading 'score.dat': {e}")
            self.cqMag2 = 0.0

        try:
            with open('score1.dat', 'rb') as file:
                self.cqLocation2 = pickle.load(file)            
        except (FileNotFoundError, EOFError) as e:
            logging.error(f"An error occurred while loading 'score1.dat': {e}")
            self.cqLocation2 = ""

        try:
            with open('score2.dat', 'rb') as file:
                self.cqTime2 = pickle.load(file)
        except (FileNotFoundError, EOFError) as e:
            logging.error(f"An error occurred while loading 'score2.dat': {e}")
            self.cqTime2 = datetime.now(timezone.utc)

    def repaintMap(self):
        # This data is shared between threads. Protect it with a lock.
        self.lock.acquire()
        cqLon = self.cqLon
        cqLat = self.cqLat
        cqEv = self.cqEv          # *** Earthquake Type ***
        cqMag = self.cqMag
        cqMag1 = self.cqMag1
        cqMag2 = self.cqMag2
        cqDepth = self.cqDepth
        cqTime = self.cqTime
        cqTime1 = self.cqTime1
        cqTime2 = self.cqTime2  
        cqLocation = self.cqLocation
        cqLocation1 = self.cqLocation1
        cqLocation2 = self.cqLocation2
        eventDB = copy.deepcopy(self.eventDB)
        self.lock.release()
        self.displayManager.displayMap()

        # Display Max event
        if self.cqMag > self.cqMag1:
            self.cqMag1 = self.cqMag
            self.cqLocation1 = self.cqLocation 
            self.cqTime1 = self.cqTime
            # Display Max event This Year
            if self.cqMag > self.cqMag2:
                cqMag2 = cqMag
                cqLocation2 = cqLocation
                cqTime2  = cqTime
                with open('score.dat', 'wb') as file:
                    pickle.dump(self.cqMag2, file) # Add Maximum Earthquake this year to database
                with open('score1.dat', 'wb') as file1:
                    pickle.dump(self.cqLocation2, file1) # Add Maximum Earthquake Location this year to database
                with open('score2.dat', 'wb') as file2:
                    pickle.dump(self.cqTime2, file2) # Add Maximum Earthquake Time this year to database 

        # Check if the year has changed       
        if self.cqTime.year != now.year:
            self.cqLocation2 = self.cqLocation
            self.cqMag2 = self.cqMag
            self.cqTime2 = self.cqTime
            pickle.dump(score2, file2) # Add Maximum Earthquake Time this year to database
            with open('score.dat', 'wb') as file:
                pickle.dump(self.cqMag2, file) # Add Maximum Earthquake this year to database
            with open('score1.dat', 'wb') as file1:
                pickle.dump(self.cqLocation2, file1) # Add Maximum Earthquake Location this year to database
            with open('score2.dat', 'wb') as file2:
                pickle.dump(self.cqTime2, file2) # Add Maximum Earthquake Time this year to database 
            

        self.displayManager.displayMax(cqMag1, cqLocation1, cqMag2, cqLocation2)

        # Display number of EQ events
        self.displayManager.displayNumberOfEvents(eventDB.numberOfEvents())

        # Display EQ location
        self.displayManager.displayLocation(cqLocation, cqMag)

        # Display EQ Type
        self.displayManager.displayEv(cqEv)   #  *** Earthquake type ***

        # Display EQ magnitude
        self.displayManager.displayMagnitude(cqMag)    

        # Display EQ depth
        self.displayManager.displayDepth(cqDepth)

        # Display EQ data on display
        self.displayManager.displayEarthquakeTime(cqTime.strftime("%d-%m-%Y %H:%M:%S")) #time and date of earthquake
        self.displayManager.displayEarthquakeTime1(cqTime1.strftime("%-H:%-M:%p"))      #time of max today
        self.displayManager.displayEarthquakeTime2(cqTime2.strftime("%d-%m-%Y"))        #date of max this year

        # Display all of the EQ events in the DB
        count = eventDB.numberOfEvents()
        for i in range(count):
            id, lon, lat,  Ev, mag, timestamp = eventDB.getEvent(i)
            # Color depends upon magnitude
            color = self.displayManager.colorFromMag(mag)
            self.displayManager.mapEarthquake(lon, lat, mag, color)

        # We handle blinking here. repaintMap is called continuously. Any painting has to be done in this method.
        # self.blinkToggle gets toggled in the every500ms method
        if self.blinkToggle:
            color = self.displayManager.colorFromMag(cqMag)
        else:
            color = BLACK
        self.displayManager.mapEarthquake(cqLon, cqLat, cqMag, color) #("Repainting EQ circle: {} {} {}".format(cqLon, cqLat, cqMag))
        self.displayManager.animEQeventTick()

        # Update databases if values have changed
        if cqMag2 != self.cqMag2:
            self.cqMag2 = cqMag2
            with open('score.dat', 'wb') as file:
                pickle.dump(self.cqMag2, file)

        if cqLocation2 != self.cqLocation2:
            self.cqLocation2 = cqLocation2
            with open('score1.dat', 'wb') as file:
                pickle.dump(self.cqLocation2, file)

        if cqTime2 != self.cqTime2:
            self.cqTime2 = cqTime2
            with open('score2.dat', 'wb') as file:
                pickle.dump(self.cqTime2, file)

    def midnightReset(self):
        now = datetime.now()
#        if now.hour == 21 and now.minute == 0 and now.second == 0:
        self.lock.acquire()
        self.eventDB.clear()
        self.lock.release()
        self.cqID = ""
        self.cqLocation = ""
        self.location1 = ""
        self.cqLon = 0.0
        self.cqLat = 0.0
        self.cqearthquakeTime = ""
        self.cqEv = "9PM Reset"   # ***reset at 9pm ***
        self.cqMag = 0.0
        self.cqDepth = 0.0
        self.cqTime = datetime.now()
        self.cqMag1 = 0.0
        self.cqLocation1 = ""
        logging.info("9pm reset.") #clear map data at midnight as this is when I go to bed
        
    def earthquakeEvent(self, cqID, cqLocation, cqLon, cqLat, cqEv, cqMag, cqDepth, cqTime):      #  *** Earthquake Type ***
        newEvent = False
        # The data below is shared between threads. Protect it with a lock.
        self.lock.acquire()
        self.cqID = cqID
        self.cqLocation = cqLocation
        self.cqLon = cqLon
        self.cqLat = cqLat
        self.cqEv = cqEv         # *** Earthquake Type ***   
        self.cqMag = cqMag
        self.cqDepth = cqDepth
        self.cqTime = cqTime
        if self.eventDB.addUpdateEvent(self.cqID, self.cqLon, self.cqLat, self.cqEv, self.cqMag, self.cqTime, update=False) == 0:       # *** Eerthquake Type ***
            logging.info("Loc: {} Lon: {} Lat: {} Ev: {} Mag: {} Depth: {} Time: {}".format(
                self.cqLocation, self.cqLon, self.cqLat, self.cqEv, self.cqMag, self.cqDepth, self.cqTime.strftime("%H:%M:%S")))        # *** Eerthquake Type ***
        self.lock.release()

        # Trigger animation
        if newEvent:
            self.displayManager.startAnimEQevent(self.cqLocation)

    def every500ms(self):
        self.blinkToggle = not self.blinkToggle
