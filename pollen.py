import json
import urllib.request
import urllib.error
import time
from datetime import datetime
from datetime import timedelta
import pdb
import threading
import pygame as pg
import logging
import os.path
import socket

'''The data is for regions within this Lat/Lon bounding box :-
South 19.1N
North 70.2N
West 312.54W
East 75.83

This covers most of Europe'''

POLLEN_URL = "http://ws1.metcheck.com/ENGINE/v9_0/AIRQUALITY/json.asp?lat=53.439&lon=-2.106"

TIMEOUT = 15
STATUS_TIMEOUT = "Timeout"
STATUS_OK = "OK"

def nullis0hook(d):
    """This is a hook for the JSON decoder, replacing null with 0."""
    for k in d.keys():
        if d[k]==None:
            d[k]=0
    return d

class PollenData:
    def __init__(self):
        self.airquality = [""]*9
        self.allergy = [""]*9
        self.pollen = [""]*9
        self.weekday = [""]*9

# pygame display must be initialized before constructing a Forecast object
class PollenHour:
    def __init__(self):
        self.data = PollenData()
        self.lock = threading.Lock()
        self.airquality = [""]*9
        self.allergy = [""]*9
        self.pollen = [""]*9
        self.weekday = [""]*9

class Pollen:
    def __init__(self):
        self.data = PollenData()
        self.lock = threading.Lock()
        self.airquality = [""]*9
        self.allergy = [""]*9
        self.pollen = [""]*9
        self.weekday = [""]*9


    def getData(self):
        """Get most recently retrieved consistent set of data."""
        self.lock.acquire()
        data = self.data
        self.lock.release()
        return data

    def update(self):
        """Update the forecast data"""
        data = PollenData()       
        try:
            req = urllib.request.Request(POLLEN_URL) 
        except (urllib.error.URLError, ValueError) as e:
            logging.warning("Error creating request object: %s", str(e))
            return    
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                raw = response.read()
                try:
                    pollen_json = json.loads(raw, object_hook=nullis0hook)
                    data.status = STATUS_OK
                    for hours in range(9):
                        data.airquality[hours] = pollen_json["metcheckData"]["forecastLocation"]["forecast"][hours]["airqualityIndex"]
                        data.allergy[hours] = pollen_json["metcheckData"]["forecastLocation"]["forecast"][hours]["allergyIndex"]
                        data.pollen[hours] = pollen_json["metcheckData"]["forecastLocation"]["forecast"][hours]["pollenIndex"]                   
                        data.weekday[hours] = pollen_json["metcheckData"]["forecastLocation"]["forecast"][hours]["weekday"]
                except (json.decoder.JSONDecodeError, KeyError, TypeError) as e:
                    logging.warning("Error parsing JSON data: %s", str(e))
        except (socket.timeout, socket.gaierror, urllib.error.URLError, json.decoder.JSONDecodeError, KeyError, TypeError) as e:
            logging.warning("Error retrieving Pollen data: %s", str(e))

        #Now make it available to outside world.
        self.lock.acquire()
        self.data = data
        self.lock.release()

