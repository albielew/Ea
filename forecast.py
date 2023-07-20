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
import pickle

FORECAST_URL = "https://swd.weatherflow.com/swd/rest/better_forecast?api_key=20c70eae-e62f-4d3b-b3a4-8586e90f3ac8&station_id=44303&lat=53.440&lon=-2.105"
TIMEOUT = 15
STATUS_TIMEOUT = "Timeout"
STATUS_OK = "OK"

def nullis0hook(d):
    """This is a hook for the JSON decoder, replacing null with 0."""
    for k in d.keys():
        if d[k] is None:
            d[k] = 0
    return d

class ForecastData:
    def __init__(self):
        self.status = ""
        self.conditions = ""
        self.iconnow = "--"
        self.updateTime = ""    
        self.tempnow = 0
        self.templow = 30
        self.temphigh = -10
        self.updateTime = datetime.now()
        self.year = 0
        self.previous_day = None
        self.previous_year = self.updateTime.year
        self.sea_level_pressure = 0
        self.station_pressure = 0
        self.pressure_trend = ""
        self.relative_humidity = 0
        self.wind_avg = 0
        self.wind_direction_cardinal = ""
        self.angle = 0
        self.wind_gust = 0
        self.highgust = 0
        self.brightness = 0
        self.solar_radiation = 0
        self.uv = 0
        self.feels_like = 0
        self.dew_point = 0
        self.wet_bulb_temperature = "" 
        self.delta_t = 0
        self.air_density = 0
        self.lightning_strike_last_distance = "0"
        self.lightning1 = ""
        self.lightning_strike_last_epoch = 0
        self.precip_accum_local_yesterday = 0
        self.precip_accum_local_day = 0
        self.condday = [""]*6
        self.icon = [""]*6
        self.iconday_filename = [os.path.join("images",os.path.join("forecast_icons","--_"))]*6
        self.iconday = [pg.image.load(os.path.join("images",os.path.join("forecast_icons","--_1.bmp"))).convert()]*6
        self.thighday = [0]*6
        self.tlowday = [0]*6
        self.sunriseday = [""]*6        
        self.sunsetday = [""]*6          
        self.precprday = [0]*6
        self.precpiconday = [""]*6
        self.preciptypeday = [""]*6
        self.wind_avghour = [""]*13
        self.conditionshour = [""]*13
        self.iconhour = [""]*13
        self.precipprhour = [""]*13
        self.preciptypehour = [""]*13
        self.feelslikehour = [0]*13
        self.airtemphour = [0]*13 
        self.wind_direction_cardinalhour = [""]*13 
        self.sea_level_pressurehour = [0]*13    
        self.forecast_icon_filename = os.path.join("images",os.path.join("weather_icons","--_.bmp"))
        self.forecast_icon = pg.image.load(self.forecast_icon_filename).convert()
        self.kia = None
        kia_filename = os.path.join("images", os.path.join("weather_icons", "kia.bmp"))
        if os.path.exists(kia_filename):
            self.kia = pg.image.load(kia_filename).convert()
        else:
            logging.warning("Weather icon file {} not found.".format(kia_filename))
        self.map1 = pg.image.load(os.path.join("images",os.path.join("new.bmp"))).convert()        
        try:
            with open('score6.dat', 'rb') as file3: # Create database for Maximum Earthquake Time
                score6 = pickle.load(file3)    
        except:
            score6 = ""

class Forecast:
    def __init__(self):
        self.data = ForecastData()
        self.lock = threading.Lock()
        self.highgust = 0
        self.templow = 30
        self.temphigh = -10    
        self.updateTime = datetime.now()

    def getData(self):
        """Get most recently retrieved consistent set of data."""
        self.lock.acquire()
        data = self.data
        self.lock.release()
        return data

    def midnightReset(self):
        """Reset any values that require resetting at midnight"""
        self.lock.acquire()
        self.data.wind_gust = 0
        # Create or update the database file
        try:
            with open('score6.dat', 'wb') as file3:
                pickle.dump(self.data.year, file3)  # Save the value of self.data.year
        except Exception as e:
            logging.warning("Error creating/updating the database file: {}".format(e))
        self.lock.release()
    def update(self):
        """Update the forecast data"""   
        retry_count = 3  # Number of retries
        retry_delay = 5  # Delay between retries in seconds
        while retry_count > 0:
            try:
                data = ForecastData()
                req = urllib.request.Request(FORECAST_URL)            
                with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                    raw = response.read()             
                    forecast_json = json.loads(raw, object_hook=nullis0hook)
                    data.status = STATUS_OK
                    data.conditions = forecast_json["current_conditions"]["conditions"]  

                    iconnow = forecast_json["current_conditions"]["icon"] 
                    data.iconnow_filename = os.path.join("images",os.path.join("weather_icons",iconnow+".bmp"))
                    if os.path.exists(data.iconnow_filename):
                        data.iconnow = pg.image.load(data.iconnow_filename).convert()
                    else:
                        logging.warning("Weather icon file {} not found.".format(data.icon.iconnow_filename))

                    data.tempnow = forecast_json["current_conditions"]["air_temperature"] 
                    if data.tempnow < self.templow:
                        self.templow = data.tempnow
                    if data.tempnow > self.temphigh:
                        self.temphigh = data.tempnow
                    data.templow = self.templow
                    data.temphigh = self.temphigh            
                    
                    data.sea_level_pressure = forecast_json["current_conditions"]["sea_level_pressure"]
                    data.station_pressure = forecast_json["current_conditions"]["station_pressure"]
                    data.pressure_trend = forecast_json["current_conditions"]["pressure_trend"]

                    data.relative_humidity = forecast_json["current_conditions"]["relative_humidity"]
                    data.wind_avg = forecast_json["current_conditions"]["wind_avg"] * 2.23694  # Convert mps to mph
                    data.wind_gust = forecast_json["current_conditions"]["wind_gust"] * 2.23694  # Convert mps to mph
                    if data.wind_gust > data.highgust:
                        data.highgust = data.wind_gust 
                    else: 
                        data.highgust = data.highgust
                    data.angle = forecast_json["current_conditions"]["wind_direction"]
                    if data.angle <= 180:
                        data.angle = data.angle + 180
                    else:
                        data.angle = data.angle - 180                
                    data.wind_direction_cardinal = forecast_json["current_conditions"]["wind_direction_cardinal"]                     
                    data.solar_radiation = forecast_json["current_conditions"]["solar_radiation"]
                    data.brightness = forecast_json["current_conditions"]["brightness"]
                    data.uv = forecast_json["current_conditions"]["uv"]
                    data.feels_like = forecast_json["current_conditions"]["feels_like"]
                    lightning_strike_last_distance = forecast_json["current_conditions"].get("lightning_strike_last_distance", 0)                   
                    lightning1 = lightning_strike_last_distance * 0.621371  # Convert kph to mph     
                    data.lightning_strike_last_distance = "{0:.1f} Miles".format(lightning1)
                    strike_last_epoch = forecast_json["current_conditions"].get("lightning_strike_last_epoch")
                    if strike_last_epoch:
                        data.lightning_strike_last_epoch = strike_last_epoch    
                    data.precip_accum_local_yesterday = forecast_json["current_conditions"]["precip_accum_local_yesterday"]
                    data.precip_accum_local_day = forecast_json["current_conditions"]["precip_accum_local_day"]

                    # Check if data.precip_accum_local_day has changed
                    if data.precip_accum_local_day != data.year:
                        data.year += data.precip_accum_local_day
                        
                    # Check if it's a new day
                    if data.previous_day is None or data.previous_day.date() != self.updateTime.date():
                        # Store data.precip_accum_local_day at midnight
                        data.year += data.precip_accum_local_day
                        score6 = data.year
                        data.previous_day = self.updateTime

                    # Check if it's a new year
                    if data.previous_year != self.updateTime.year:
                        data.year = 0
                        data.previous_year = self.updateTime.year
                    
                    for day in range(6):
                        data.sunriseday[day] = forecast_json["forecast"]["daily"][day]["sunrise"]
                        data.sunriseday[day] = time.strftime("%H:%M:%S", time.localtime(data.sunriseday[day]))
                        data.sunsetday[day] = forecast_json["forecast"]["daily"][day]["sunset"]
                        data.sunsetday[day] = time.strftime("%H:%M:%S", time.localtime(data.sunsetday[day]))
                        data.condday[day] = forecast_json["forecast"]["daily"][day]["conditions"]
                        icon = forecast_json["forecast"]["daily"][day]["icon"]
                        data.iconday_filename[day] = os.path.join("images", os.path.join("forecast_icons", icon + "1.bmp"))
                        if os.path.exists(data.iconday_filename[day]):
                            iconimage = pg.image.load(data.iconday_filename[day]).convert()
                            data.iconday[day] = iconimage
                        else:
                            logging.warning("Forecast icon file {} not found.".format(data.iconday_filename[day]))                   
                        data.thighday[day] = forecast_json["forecast"]["daily"][day]["air_temp_high"]
                        data.tlowday[day] = forecast_json["forecast"]["daily"][day]["air_temp_low"]
                        data.precprday[day] = forecast_json["forecast"]["daily"][day]["precip_probability"]
                        if data.precprday[day] != 0:
                            data.precpiconday[day] = forecast_json["forecast"]["daily"][day]["precip_icon"]
                            data.preciptypeday[day] = forecast_json["forecast"]["daily"][day]["precip_type"]  
                    data.forecast_icon_filename = os.path.join("images", os.path.join("weather_icons", iconnow + ".bmp"))
                    if os.path.exists(data.forecast_icon_filename):
                        data.forecast_icon = pg.image.load(data.forecast_icon_filename).convert()
                    else:
                        logging.warning("Forecast icon file {} not found.".format(data.forecast_icon_filename))

                    for hours in range(13):                
                        ps = forecast_json["forecast"]["hourly"][hours]["conditions"]                  
                        if ps == "Wintry Mix Possible":
                            ps = "Winty-P" 
                        if ps ==  "Wintry Mix Likely":
                            ps = "Winty-L"      
                        if ps ==  "Rain Likely":
                            ps = "Rain-L" 
                        if ps ==  "Rain Possible":
                            ps ="Rain-P"  
                        if ps ==  "Snow Possible":
                            ps = "Snow-P"   
                        if ps ==  "Thunderstorms Likely":
                            ps = "ThundrL"          
                        if ps ==  "Thunderstorms Possible":
                            ps = "ThundrP"   
                        if ps==  "Partly Cloudy":
                            ps = "Clouds"   
                        if ps == "Very Light Rain":
                            ps = "drizzle"
                        data.conditionshour[hours] = "{}".format(ps)                   
                        data.iconhour[hours] = forecast_json["forecast"]["hourly"][hours]["icon"]
                        pp = forecast_json["forecast"]["hourly"][hours]["precip_probability"]
                        data.precipprhour[hours] = "{}%".format(pp)
                        if pp == 0:
                            data.preciptypehour[hours] = "0"
                        else:
                            data.preciptypehour[hours] = forecast_json["forecast"]["hourly"][hours]["precip_type"]
                        data.feelslikehour[hours] = "{} C".format(forecast_json["forecast"]["hourly"][hours]["feels_like"])
                        data.airtemphour[hours] = forecast_json["forecast"]["hourly"][hours]["air_temperature"]
                        data.wind_avghour[hours] = forecast_json["forecast"]["hourly"][hours]["wind_avg"] * 2.23694  # Convert mps to mph
                        data.sea_level_pressurehour[hours] = forecast_json["forecast"]["hourly"][hours]["sea_level_pressure"]     
                        data.wind_direction_cardinalhour[hours] = forecast_json["forecast"]["hourly"][hours]["wind_direction_cardinal"]
                    # datetime object containing current date and time
                    now = datetime.now()
                    data.updateTime = now.strftime("%H:%M:%S")
                    self.updateTime = now  # self.updateTime is a datetime object
                    break
            except (socket.timeout, socket.gaierror, IndexError, urllib.error.URLError, json.decoder.JSONDecodeError, pg.error, KeyError, TypeError):
                logging.warning("Error retrieving forecast data")
                retry_count -= 1  # Decrease retry count
                if retry_count > 0:
                    logging.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)

        if retry_count == 0:
            logging.warning("All retries failed. Using previous data.")

        # Now make it available to outside world.
        self.lock.acquire()
        self.data = data
        self.lock.release()
