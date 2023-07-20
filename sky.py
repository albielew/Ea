import json
import urllib.request
import urllib.error
import threading
import socket
import logging
from datetime import timedelta
from datetime import datetime

SKY_DEVICE_URL = "https://swd.weatherflow.com/swd/rest/observations/?device_id=130583&api_key=20c70eae-e62f-4d3b-b3a4-8586e90f3ac8"
TIMEOUT = 15
STATUS_TIMEOUT = "Timeout"
STATUS_OK = "OK"

def nullis0hook(d):
    """This is a hook for the JSON decoder, replacing null with 0."""
    for k in d.keys():
        if d[k]==None:
            d[k]=0
    return d

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
        self.lightning_time = 0
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
        self.skybattery = 0
        self.solar_radiation = 0
        self.wind_direction = 0
        self.wind_chill = 0
        self.feels_like = 0  
        self.sensor_status = 0
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

    def stop(self):
        pass #stub for api compatibility
        
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
        self.lock.release()        

    def update(self):
        """Update the sky device data"""
        data = SkyDeviceData()

        try:
            req = urllib.request.Request(SKY_DEVICE_URL)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                data.raw = response.read()
                sky_json = json.loads(data.raw, object_hook=nullis0hook)
                data.timestamp = sky_json["obs"][0][0]        
                data.wind_speed_rapid = sky_json["obs"][0][2]*2.23694 #Convert mps to mph
                data.wind_gust = sky_json["obs"][0][3]*2.23694 #Convert mps to mph                  
                data.wind_bearing_rapid = sky_json["obs"][0][4]
                self.lock.acquire()                
                if data.wind_bearing_rapid <= 180:
                    data.wind_bearing_rapid = data.wind_bearing_rapid + 180
                else:
                    data.wind_bearing_rapid = data.wind_bearing_rapid - 180
                self.lock.release()                   
                data.pressure = sky_json["obs"][0][6]
                data.temperature = sky_json["obs"][0][7]
                self.lock.acquire()                 
                if data.temperature  < self.templow:
                    self.templow = data.temperature 
                if data.temperature  > self.temphigh:
                    self.temphigh = data.temperature 
                data.templow = self.templow
                data.temphigh = self.temphigh   
                self.lock.release()                     
                data.humidity = sky_json["obs"][0][8]
                data.illuminance = sky_json["obs"][0][9]
                data.uv = sky_json["obs"][0][10]
                data.solar_radiation = sky_json["obs"][0][11]
                data.precipitation_rate = sky_json["obs"][0][12]
                data.lightning_distance = sky_json["obs"][0][14]
                data.lightning_count = sky_json["obs"][0][15]
                data.skybattery = sky_json["obs"][0][16]

        except (socket.timeout, socket.gaierror, urllib.error.URLError, json.decoder.JSONDecodeError, KeyError, TypeError):
            logging.warning("Error retrieving sky device data")

            #declare timeout only after timeout period
            if datetime.now() - self.updateTime > timedelta(seconds=TIMEOUT):
                data.status = STATUS_TIMEOUT
            else: #If timeout period has not elapsed yet, use previous data
                logging.info("Not timing out yet.")
                data = self.data

        self.lock.acquire()
        self.data = data
        self.lock.release()