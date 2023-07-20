import threading
import logging
from datetime import timedelta
from datetime import datetime
import pysmartweatherudp as pswu
import copy

STATUS_OK = "OK"

class SkyDeviceData:
     def __init__(self):
        self.raw=""
        self.timestamp = ""
        self.wind_speed_rapid = 0
        self.wind_bearing_rapid = 0
        self.pressure = 0
        self.temperature = 0
        self.temphigh=-10
        self.templow=30        
        self.humidity = 0
        self.lightning_count = 0
        self.lightning_distance = 0
        self.lightning_time = 946684801
        self.airbattery = 0
        self.dewpoint = 0
        self.heat_index = 0
        self.illuminance = 0
        self.uv = 0
        self.precipitation_rate = 0
        self.wind_speed = 0
        self.wind_bearing = 0
        self.wind_lull = 0
        self.wind_gust = 0
        self.highgust = 0
        self.skybattery = 0
        self.solar_radiation = 0
        self.wind_direction = 0
        self.wind_chill = 0
        self.feels_like = 999
        self.sensor_status = 0 
        self.radio_stats = 0
        self.dirs = ""
        self.status = STATUS_OK     
       
        '''  self.status = 0   '''
 
#The Sky class retrieves the sky device data from weatherflow.com and extracts relevant data.
class SkyDevice:
    def __init__(self):
        self.data = SkyDeviceData()
        self.lock = threading.Lock()        
        self.updateTime = datetime.now()
        self.templow=30
        self.temphigh=-10          
        self.receiver = pswu.SWReceiver() #Note: we're using metric units here and convert where needed in receiverCallback below.
        self.receiver.registerCallback(self.makeClosure())
        self.receiver.start() #Start the thread.

    def stop(self):
        #Shut down the receiver thread.
        self.receiver.stop()

    def makeClosure(self):
        #This function is an adapter that turns a free function call into an object method call,
        #so we can plug it into the receiver registerCallback() method.

        def closure(ds):
            self.receiverCallback(ds)

        return closure

    def receiverCallback(self, ds):
        #New data has been received over UDP. Store it into the SkyDeviceData object

        self.lock.acquire()   
        data = copy.deepcopy(self.data)
        self.lock.release()

        #logging.info("SkyDevice receiverCallback")
        #logging.info(ds.type)

        if ds.type == 'evt_strike':
            data.lightning_time = ds.strikeEpoch
            data.lightning_distance = round(ds.strikeDistance*0.621371192,1) #km to miles
        elif ds.type == 'device_status':
            logging.info("device_status received")
            data.timestamp = ds.timestamp
            data.sensor_status = ds.sensor_status
            data.radio_stats = ds.radio_stats
        elif ds.type == 'st':
            data.timestamp = ds.timestamp
            data.illuminance = ds.illuminance
            data.uv = ds.uv
            data.precipitation_rate = ds.precipitation_rate
            data.wind_speed = ds.wind_speed*2.2369362921 #Convert mps to mph 
            data.wind_bearing = ds.wind_bearing
            if ds.wind_bearing <= 180:
                data.wind_bearing = ds.wind_bearing + 180
            else:
                data.wind_bearing = ds.wind_bearing - 180    
#            logging.info("wind speed: {}".format(data.wind_speed))                  
            data.wind_lull = ds.wind_lull*2.2369362921 #Convert mps to mph 
            data.wind_gust = ds.wind_gust*2.2369362921 #Convert mps to mph             
            if data.wind_gust > data.highgust:
                data.highgust = data.wind_gust 
            else: 
                data.highgust = data.highgust  
            data.skybattery = ds.skybattery
            data.solar_radiation = ds.solar_radiation
            data.wind_direction = ds.wind_direction
            data.pressure = ds.pressure
            data.temperature = ds.temperature
            self.lock.acquire()                 
            if data.temperature  < self.templow:
                self.templow = data.temperature 
            if data.temperature  > self.temphigh:
                self.temphigh = data.temperature 
            data.templow = self.templow
            data.temphigh = self.temphigh   
            self.lock.release()     
            data.humidity = ds.humidity
            data.lightning_count = ds.lightning_count
            data.airbattery = ds.airbattery
            data.dewpoint = ds.dewpoint
            data.heat_index = ds.heat_index
            data.wind_chill = ds.wind_chill
            data.feels_like = ds.feels_like
        elif ds.type == 'rapid_wind':
            data.timestamp = ds.timestamp
            data.wind_speed_rapid = ds.wind_speed_rapid*2.23694 #Convert mps to mph
            if ds.wind_bearing_rapid <= 180:
                data.wind_bearing_rapid = ds.wind_bearing_rapid + 180
            else:
                data.wind_bearing_rapid = ds.wind_bearing_rapid - 180   
#                logging.info("wind speed rapid: {}".format(data.wind_speed_rapid))

                #dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
                #ix = round(data.wind_bearing_rapid / (360. / len(dirs)))
                #return dirs[ix % len(dirs)]
                #data.dirs = dirs[ix % len(dirs)]


        self.lock.acquire()
        self.data = data
        self.lock.release()

    def getData(self):
        """Get most recently retrieved consistent set of data."""
        self.lock.acquire()
        data = self.data
        self.lock.release()
        return data
        
    def midnightReset(self):
        """Reset any values that require resetting at midnight"""
        self.lock.acquire()
        self.temphigh=-10
        self.templow=30
        self.highgust=0
        self.lock.release()        

    def update(self):
        """Update the sky device data"""
        pass #Nothing to do here in the UDP variant of the sky module.