import contextlib
with contextlib.redirect_stdout(None): #this removed the pygame info screen
    import pygame as pg
from pygame import mixer
from pygame.locals import *
import sys
import time
from time import sleep
import logging
import logging.handlers
import getopt
import threading
import forecast
import skyudp as sky #imports lOCAL Sky device over UDP
import pollen
import moonphase
import DisplayManager
import EQMap
import EQEventGatherer
import pdb
import serial
import os
from datetime import datetime
from datetime import date
from datetime import timedelta
import math
from math import *
import board
import busio
from digitalio import DigitalInOut, Direction, Pull
import adafruit_mcp9808 #Temperature Sensor 0.25°C accuracy
from adafruit_pm25.i2c import PM25_I2C #Air Quality Sensor
reset_pin = None
i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
mcp = None
pm25 = None

WEATHERSTATION_VERSION = "3.10"
import os
if sys.platform == "win32":
    HRES = 1080//2 #Window/Screen resolution. Should be 16:9 aspect ratio.
    VRES = 1920//2
else:
    HRES = 1080 #Window/Screen resolution. Should be 16:9 aspect ratio.
    VRES = 1920
BACKGROUND_COLOR = pg.Color(25,25,112)
#BACKGROUND_COLOR = pg.Color(10,10,51)   #Darker Blue
DEFAULT_LOG_LEVEL = logging.INFO #Can be DEBUG, INFO, WARNING, ERROR or CRITICAL
#logging.basicConfig(filename='exceptions.log', level=logging.INFO)
NUM_LOG_BACKUPS = 3 #Number of logfile backups maintained
LOG_FILE_MAX_BYTES = 4024*4024 #Max. size of logfile before rotating.
LOGFILENAME = 'wsLog.log'
if sys.platform == "win32":
    FONT_SIZE=20//2
    FONT_SIZE_SMALL=16//2
else:
    FONT_SIZE=20
    FONT_SIZE_SMALL=16
    
COMPASS_POINTER_BASE_SIZE = 40
EVERY_MINUTE_THREAD_FUNCTION_EVENT = pg.USEREVENT+1
EVERY_FIVE_MINUTES_THREAD_FUNCTION_EVENT = pg.USEREVENT+2
EVERY_HOUR_THREAD_FUNCTION_EVENT = pg.USEREVENT+3
EVERY_100MS_EVENT = pg.USEREVENT+4
THREE_SECONDS_THREAD_FUNCTION_EVENT = pg.USEREVENT+5
NUM_FLASHES = 5
LIGHTNING_IMAGE_FILEPATH = os.path.join("images","lightning.jpg")
today = date.today()
screen = None #pygrame screen surfac. Set up during init()
logger = None #Logger object, set up during init()
forecastObj = None #This object will maintain forecast data
pollenObj = None #This object maintains pollen data
skyDevice = None #This object maintains sky device data
font = None #PyGame font object

day_endings = {
    1: 'st',
    2: 'nd',
    3: 'rd',
    21: 'st',
    22: 'nd',
    23: 'rd',
    31: 'st'
}
initialWeatherUpdateReceived = False #This flag will be set to true as soon as we have received our initial set of weather data.
moonimage = None #Moon phase image
lightningImage = None #Lightning image
hourThreadRunning = False #Flag indicating if hourThread is currently running
SecondThreadRunning = False #Flag indicating if SecondThread is currently running
everyMinuteThreadRunning = False #Flag indicating if everyminuteThread is currently running
fiveMinuteThreadRunning = False #Flag indicating if fiveMinute is currently running
showLightning = False #Flag indicating if display should show lightning image instead of panels
lightningFlashCount = 0 #Count how often we flashed in the currently lightning flash sequence
eqBlinkPeriodCount = 0 #Count number of 100ms periods to blink earthquake map
previousLightningTime = 0
displayManager = None #DisplayManager object used by earthQuake logic
eqMap = None #Earthquake logic top level object
prevTime = time.localtime() #Used to decide to reset at 6am
now = datetime.now()
pmsSensor = None  #Air particle sensor
aqdata = None
logging.info('Initialising MCP9808 object.')

def initialize_devices():
    global mcp, pm25

    try:
        mcp = adafruit_mcp9808.MCP9808(i2c, address=0x18)
        logging.info('MCP9808 sensor initialized.')
    except RuntimeError as err:
        logging.error('Failed to initialize MCP9808 sensor: {}'.format(err))
        mcp = None
    
    try:
        pm25 = PM25_I2C(i2c, reset_pin)
        logging.info('PM2.5 sensor initialized.')
    except RuntimeError as err:
        logging.error('Failed to initialize PM2.5 sensor: {}'.format(err))
        pm25 = None

initialize_devices()  # Initialize the devices

def custom_strftime(format, t):
    return time.strftime(format, t).replace('{TH}', str(t[2]) + day_endings.get(t[2], 'th'))

def checkMidnightRollOver():
    """Checks if we went past midnight and executes midnight actions if we did."""
    global today, forecastObj

    if today != date.today():
        today = date.today()
        logging.info("Midnight rollover.")
        if forecastObj:
            forecastObj.midnightReset()
        if skyDevice:
            skyDevice.midnightReset()
 #           logging.info("skyData midnight reset")

def checkRollOver():
    """Checks if we went past 9pm and executes RESET DATABASE actions if we did."""
    now = datetime.now()
    if now.hour == 21 and now.minute == 0 and now.second == 0:
        logging.info("9pm Earthquake reset.")
        if eqMap:
            eqMap.midnightReset()

# Initialize mixer and load thunder sound file outside the function
mixer.init()
mixer.music.load('thunder.mp3')
mixer.music.set_volume(0.5)

def checkLightning():
    global showLightning, lightningFlashCount, previousLightningTime

    forecastData = forecastObj.getData()
    if forecastData.lightning_strike_last_epoch > previousLightningTime:
#        logging.info("Lightning strike at {}".format(time.strftime("%d %b %H:%M", time.localtime(forecastData.lightning_strike_last_epoch))))
#        logging.info("Lightning distance: {}".format(forecastData.lightning_strike_last_distance))
        previousLightningTime = forecastData.lightning_strike_last_epoch
        # Start lightning flash sequence
        lightningFlashCount = 3
        mixer.music.play()


def SecondThreadFunction():
    """This thread function executes once every second."""
    global SecondThreadRunning, aqdata, tempC, tempF, mcp, pm25
    
    checkMidnightRollOver()
    checkRollOver()
    try:
        if mcp is not None:
            tempC = mcp.temperature  # Get Temp °C
            tempF = mcp.temperature * 9 / 5 + 32  # Get Temp °F
        else:
            tempC = None
            tempF = None
            logging.error("MCP9808 sensor not initialized.")
    except (OSError, RuntimeError) as err:
        logging.error("Error reading temperature from MCP9808 sensor: {}".format(err))
        tempC = None
        tempF = None

    try:
        if pm25 is not None:
            aqdata = pm25.read()  # Get Air Quality Readings
        else:
            aqdata = None
            logging.error("PM2.5 sensor not initialized.")
    except (OSError, RuntimeError) as err:
#        logging.error("Error reading air quality from PM2.5 sensor: {}".format(err))
        aqdata = None

    return aqdata, tempC, tempF

def everyHourThreadFunction():
    """This thread function executes once every 60 minutes."""
    global hourThreadRunning
    hourThreadRunning = True
    try:
        assert(pollenObj)
#        logging.info("Updating pollen.")
        pollenObj.update()
        pollenData = pollenObj.getData()
        # logging.info("pollen data: {}".format(vars(pollenData)))
    except Exception as e:
        logging.error("Pollen Data not recieved in everyHourThreadFunction: {}".format(e))
    hourThreadRunning = False

def everyFiveMinutesThreadFunction():
    """This thread function executes once every 5 minutes."""
    global moonimage, fiveMinuteThreadRunning
    fiveMinuteThreadRunning = True
    moonage = moonphase.computeMoonPhase()
    imagefile = os.path.join("images",os.path.join("moon","{}.bmp".format(int(moonage))))      
    if os.path.exists(imagefile):
        moonimage = pg.image.load(imagefile).convert()
    fiveMinuteThreadRunning = False

def everyMinuteThreadFunction():
    """This thread function executes once every minute."""
    global initialWeatherUpdateReceived, everyMinuteThreadRunning, skyDevice, forecastObj

    everyMinuteThreadRunning = True

    assert(forecastObj)

    # Update sky device data
    skyDevice.update()
    skyData = skyDevice.getData()

    if skyData.status == sky.STATUS_OK:
        pass
    else:
        logging.warning("Error retrieving sky device data")

    # Update forecast data
    forecastObj.update()
    forecastData = forecastObj.getData()

    if forecastData.status != forecast.STATUS_OK:
        logging.info("Forecast failed.")

    # The first time we pass here is a good time to kick off the five minute task. We now have our first
    # forecast/sky device data available
    if not initialWeatherUpdateReceived:
        # Program a periodic timer used to kick off the everyFiveMinutesThreadFunction.
        pg.time.set_timer(EVERY_FIVE_MINUTES_THREAD_FUNCTION_EVENT, 60000)  # now 1 minute
        pg.time.set_timer(EVERY_HOUR_THREAD_FUNCTION_EVENT, 60 * 60000)
        # Kick off the task now, for the initial interval.
        t = threading.Thread(target=everyFiveMinutesThreadFunction, args=())
        t.daemon = True
        t.start()
        t1 = threading.Thread(target=everyHourThreadFunction, args=())
        t1.daemon = True
        t1.start()

    initialWeatherUpdateReceived = True
    everyMinuteThreadRunning = False



def setFontSize(fontSize):
    """Set current font size to given size"""
    font = pg.font.SysFont('Verdana', fontSize, bold=False) 

def setup_thread_excepthook():
    """
    Workaround for `sys.excepthook` thread bug from:
    http://bugs.python.org/issue1230540

    Call once from the main thread before creating any threads.
    """

    init_original = threading.Thread.__init__

    def init(self, *args, **kwargs):

        init_original(self, *args, **kwargs)
        run_original = self.run

        def run_with_except_hook(*args2, **kwargs2):
            try:
                run_original(*args2, **kwargs2)
            except Exception:
                sys.excepthook(*sys.exc_info())

        self.run = run_with_except_hook

    threading.Thread.__init__ = init

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

#    os._exit(1)
    os._exit(0)
def init():
    """Initialization logic goes here."""
    global logger, screen, font, forecastObj, year1, pollenObj, aqdata, pmsSensor, mcp, adafruit_mcp9808, lightningImage, skyDevice, eqMap, displayManager
    
    setup_thread_excepthook()

    # configure logger
    logger = logging.getLogger() #Get root logger
    logger.setLevel(DEFAULT_LOG_LEVEL)

    # create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    #Creating a RotatingFileHandler and set level
    rfh = logging.handlers.RotatingFileHandler(LOGFILENAME, mode='w', maxBytes=LOG_FILE_MAX_BYTES, backupCount=NUM_LOG_BACKUPS)
    rfh.setLevel(DEFAULT_LOG_LEVEL)

    # add formatter to rfh
    rfh.setFormatter(formatter)

    # add rfh to logger
    logger.addHandler(rfh)

    # create console handler and set level 
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(DEFAULT_LOG_LEVEL)

    # add formatter to ch
    ch.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(ch)

    #Make sure unhandled exceptions get logged
    sys.excepthook = handle_exception

    logging.info("Software Version {}".format(WEATHERSTATION_VERSION))
    logging.info('Starting display.')
    pg.init()
    screen = pg.display.set_mode((HRES, VRES))
    logging.info('Switching to fullscreen.')
    pg.display.toggle_fullscreen()
    logging.info('Loading font.')
    font = pg.font.SysFont('Verdana', FONT_SIZE, bold=False)
    logging.info('Creating forecast object.')
    forecastObj = forecast.Forecast()          
    logging.info('Creating Sky object')
    skyDevice = sky.SkyDevice()
    logging.info('Creating pollen object.')
    pollenObj = pollen.Pollen()   
    lightningImage = pg.image.load(LIGHTNING_IMAGE_FILEPATH).convert()
    logging.info('Initializing EarthQuake module')
    displayManager = DisplayManager.DisplayManager(screen)
    eqMap = EQMap.EQMap(displayManager)
    t = threading.Thread(target=EQEventGatherer.listener_start, args=(eqMap,))
    t.daemon = True
    t.start()
    t = threading.Thread(target=SecondThreadFunction, args=())
    t.daemon = True
    t.start()
    #program a periodic timer used to kick off the SecondThreadFunction.
    pg.time.set_timer(THREE_SECONDS_THREAD_FUNCTION_EVENT, 1000) # checks every SECOND not 3 as it originally was
    #Kick off task to retrieve forecast data etc. 
    #This will be done periodically from now one through a EVERY_MINUTE_THREAD_FUNCTION_EVENT.
    t = threading.Thread(target=everyMinuteThreadFunction, args=())
    t.daemon = True
    t.start()
    #program a periodic timer used to kick off the everyMinuteThreadFunction.
    pg.time.set_timer(EVERY_MINUTE_THREAD_FUNCTION_EVENT, 30000)
    #program a periodic timer used to flash lightning
    pg.time.set_timer(EVERY_100MS_EVENT, 100)
    #hide mouse
    pg.mouse.set_visible(0)   
    logging.info("Init complete.")

def renderLightning():
    global lightningImage
    if lightningImage:
        ren = lightningImage
        screen.blit(pg.transform.smoothscale(ren, (ren.get_width(), ren.get_height())), (0, 0))

def renderPanelp(hour):
    pollenData = pollenObj.getData() 
    
def renderPanels():
    """Renders layout panels to screen."""
    assert(screen)

#top panel
    pg.draw.rect(screen, pg.Color(162, 160, 160), Rect(0, 0, HRES, 40))  #top panel grey colour full screen width
    #dividing line
    pg.draw.line(screen, pg.Color(162, 160, 160), (0, 550), (1080, 550), 1) # dividing line    
    pg.draw.line(screen, pg.Color(162, 160, 160), (0, 690), (1080, 690), 1) # dividing line      
    pg.draw.line(screen, pg.Color(162, 160, 160), (0, 1299), (1080, 1299), 1) # dividing line
  
#lower bottom panel

    #day1 panel
    pg.draw.rect(screen, pg.Color(162, 160, 160), Rect(int(HRES/5*2), int(907), int(HRES//5), int(60)))
    pg.draw.rect(screen, pg.Color(162, 160, 160), Rect(0,907, HRES//5, 60)) 

    #day2 panel
    pg.draw.rect(screen, pg.Color(162, 160, 160), Rect(HRES//5, 907, HRES//5, 60))
    pg.draw.rect(screen, pg.Color(162, 160, 160), Rect(HRES//5, 907, HRES//5, 60), 1)
    #day3 panel
    pg.draw.rect(screen, pg.Color(162, 160, 160), Rect(int(HRES/5*2), int(907), int(HRES//5), int(60)))
    pg.draw.rect(screen, pg.Color(162, 160, 160), Rect(int(HRES/5*2), int(907), int(HRES//5),int(1)))
    #day4 panel
    pg.draw.rect(screen, pg.Color(162, 160, 160), Rect(HRES//5*3, 907, HRES//5, 60))
    pg.draw.rect(screen, pg.Color(162, 160, 160), Rect(HRES//5*3, 907, HRES//5, 60), 1)
    #day5 panel
    pg.draw.rect(screen, pg.Color(162, 160, 160), Rect(HRES//5*4, 907, HRES//5, 60))
    pg.draw.rect(screen, pg.Color(162, 160, 160), Rect(HRES//5*4, 907, HRES//5, 60), 1)

def rotateTriangle(angle_deg, pointerRelPoints):
    angle_rad = angle_deg*2*pi/360
    res = []
    for (x,y) in pointerRelPoints:
        xrot = x*cos(angle_rad) - y*sin(angle_rad)
        yrot = x*sin(angle_rad) + y*cos(angle_rad)
        res.append((xrot,yrot))
    return res    
   
def renderCompassRose(cx, cy, wid):
    """Render compass rose to screen at given coordinates and size."""
    ren = pg.transform.rotozoom(font.render("NE", 1, pg.Color(162, 160, 160), pg.Color(25,25,112)), -45, 0.5)
    x = cx+1.2*wid*cos(pi/4)-ren.get_width()//2
    y = cy-1.2*wid*sin(pi/4)-ren.get_height()//4
    screen.blit(ren, (int(x), int(y)))
    ren = pg.transform.rotozoom(font.render("SE", 1, pg.Color(162, 160, 160), pg.Color(25,25,112)), -135, 0.5)
    x = cx+1.1*wid*cos(pi/4)-ren.get_width()//2
    y = cy+1.1*wid*sin(pi/4)-ren.get_height()//4
    screen.blit(ren, (int(x), int(y)))
    ren = pg.transform.rotozoom(font.render("NW", 1, pg.Color(162, 160, 160), pg.Color(25,25,112)), 45, 0.5)
    x = cx-1.2*wid*cos(pi/4)-ren.get_width()//2
    y = cy-1.2*wid*sin(pi/4)-ren.get_height()//4
    screen.blit(ren, (int(x), int(y)))
    ren = pg.transform.rotozoom(font.render("SW", 1, pg.Color(162, 160, 160), pg.Color(25,25,112)), 135, 0.5)
    x = cx-1.1*wid*cos(pi/4)-ren.get_width()//2
    y = cy+1.1*wid*sin(pi/4)-ren.get_height()//4
    screen.blit(ren, (int(x), int(y)))
    ren = font.render("N", 3, pg.Color(162, 160, 160), pg.Color(25,25,112))
    screen.blit(ren, (int(cx - ren.get_width()//2), int(cy - 1.30*wid - ren.get_height()//4)))
    ren = font.render("S", 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
    screen.blit(ren, (int(cx - ren.get_width()//2), int(cy + 1.20*wid - ren.get_height()//4)))
    ren = font.render("E", 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
    screen.blit(ren, (int(cx + 1.20*wid - ren.get_width()//2), int(cy - ren.get_height()//4)))
    ren = font.render("W", 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
    screen.blit(ren, (int(cx - 1.30*wid - ren.get_width()//2), int(cy - ren.get_height()//4)))
    #tick marks, every 5 degrees (360/5 = 72)
    a = 0.0
    while a<2*pi:
        x1 = cx + cos(a)*(wid-4*HRES//1080)
        y1 = cy - sin(a)*(wid-4*VRES//1920)
        x2 = cx + cos(a)*(wid+1*HRES//1080)
        y2 = cy - sin(a)*(wid+1*VRES//1920)
        pg.draw.line(screen, pg.Color(162, 160, 160), (int(x1), int(y1)), (int(x2), int(y2)), 1)
        a+=2*pi/72
    #pointers to cardinal directions
    a = 0
    while a<2*pi:
        x1 = cx - sin(a)*(wid + 2*HRES//1080)
        y1 = cy - cos(a)*(wid + 2*VRES//1920) 
        x2 = cx + cos(a)*wid*0.11
        y2 = cy + sin(a)*wid*0.11
        x3 = cx - cos(a)*wid*0.11
        y3 = cy - sin(a)*wid*0.11
        a += pi/2

    #The compass pointer triangle
    forecastData = forecastObj.getData()   
    skyData = skyDevice.getData() 
    
    pointerBase = COMPASS_POINTER_BASE_SIZE*HRES//1080
    pointerRadius = wid-4*HRES//1080
    pointerRelPoints = [(0,-pointerRadius),
        (-pointerBase/1,0),(pointerBase/2,0)]
    #coordinates translated to compass center on screen    
    pointerRelPointsRotated = rotateTriangle(skyData.wind_bearing_rapid, pointerRelPoints)
    pointerAbsPoints = [(int(x)+cx,int(y)+cy) for (x,y) in pointerRelPointsRotated]  
    if skyData.wind_speed_rapid > 0: 
        pg.draw.polygon(screen, pg.Color(162, 160, 160), pointerAbsPoints)
    pg.draw.circle(screen, pg.Color(25,25,112), (cx, cy), int(wid*0.76))      
    pg.draw.circle(screen, pg.Color(162, 160, 160), (cx, cy), int(wid*0.75), 1)   #inner circle

    #MPH in compass
    setFontSize(FONT_SIZE_SMALL) #temporarily set small font     
    if skyData.status == sky.STATUS_OK:
        ren = font.render("mph", 1, pg.Color(162, 160, 160), pg.Color(25,25,112)) #mph
        screen.blit(ren, (117, 418))    
        box1 = pg.Rect(cx-33, cy-12, 68, 27)   # draw windspeed box    
        pg.draw.rect(screen, (255,255,255), box1 , 1) 
        ren = font.render("{0:.2f}".format(skyData.wind_speed_rapid), 1, pg.Color(162, 160, 160), pg.Color(25,25,112)) #windspeed  
        setFontSize(FONT_SIZE) #restore regular fontren_rect = ren.get_rect(center = box1.center)      
        ren_rect = ren.get_rect(center = box1.center)
        screen.blit(ren, ren_rect)   
    else:
        ren = font.render("mph", 1, pg.Color(162, 160, 160), pg.Color(25,25,112)) #mph
        screen.blit(ren, (117, 418))    
        box1 = pg.Rect(cx-33, cy-12, 68, 27)   # draw windspeed box    
        pg.draw.rect(screen, (255,255,255), box1 , 1) 
        ren = font.render("", 1, pg.Color(162, 160, 160), pg.Color(25,25,112)) #windspeed  
        setFontSize(FONT_SIZE) #restore regular fontren_rect = ren.get_rect(center = box1.center)      
        ren_rect = ren.get_rect(center = box1.center)
        screen.blit(ren, ren_rect)   


def renderTopPanel():
    '''Renders top panel info on screen'''
    assert(forecastObj)      
    assert screen
    assert font   
    
    forecastData = forecastObj.getData()             
    skyData = skyDevice.getData() 
    now = datetime.now()  
    dateString = now.strftime("%d-%B-%Y")
    timeString = now.strftime("%H:%M:%S")
    dayOfWeekString = now.strftime("%A")
    dow = now+timedelta()

    #Day, Date & Time at top of screen
    ren = font.render(custom_strftime('%A {TH} %b', time.localtime()) + " " + timeString, 1, pg.Color(25,25,112), pg.Color(162, 160, 160)) 
    screen.blit(ren, (5, 12))  

    box2 = pg.Rect(400, 12, 200, 27)   # draw windspeed box    
    pg.draw.rect(screen, (162,160,160), box2 , 1) 
    if skyData.solar_radiation <= 100:   #Line 454
        ren = font.render("Battery: Not Charging  " + " {:4.2f} V".format(skyData.skybattery), 1, pg.Color(25,25,112), pg.Color(162, 160, 160))
    else:
        ren = font.render("Battery: Charging  " + " {} V".format(skyData.skybattery), 1, pg.Color(25,25,112), pg.Color(162,160,160))        
    ren_rect = ren.get_rect(center = box2.center)
    screen.blit(ren, ren_rect)   

    #Weather updated time at top of screen
    oldUpdateTime = forecastData.updateTime  # Store the existing updateTime
    if forecastData.status == forecast.STATUS_OK:
        ren = font.render("Updated: " + custom_strftime('%d %b', time.localtime()), 1, pg.Color(25, 25, 112), pg.Color(162, 160, 160))
        screen.blit(ren, (830, 12))
        ren = font.render("{}".format(forecastData.updateTime), 1, pg.Color(25, 25, 112), pg.Color(162, 160, 160))
        screen.blit(ren, (985, 12))
    else:
        ren = font.render("Updated: ", 1, pg.Color(25, 25, 112), pg.Color(162, 160, 160))
        screen.blit(ren, (830, 12))
        ren = font.render("{}".format(oldUpdateTime), 1, pg.Color(25, 25, 112), pg.Color(162, 160, 160))
        screen.blit(ren, (995, 12))
  
    
def renderPanel1Data():
    assert(forecastObj)      
    assert screen
    assert font  
    forecastData = forecastObj.getData()
    skyData = skyDevice.getData()

    ren = font.render("Indoor Temp:", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
    screen.blit(ren, (5, 50))
    if mcp and tempF is not None:
        ren = font.render("{0:.1f}F ".format(tempF), 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        screen.blit(ren, (screen.get_width() - ren.get_width() - 885, 50))
        ren = font.render("{0:.1f}C ".format(tempC), 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        screen.blit(ren, (screen.get_width() - ren.get_width() - 816, 50))

    if skyData.status == sky.STATUS_OK:
        ren = font.render("Temperature:", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        screen.blit(ren, (5, 90))
        ren = font.render("{0:.1f}°C".format(skyData.temperature), 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        screen.blit(ren, (screen.get_width() - ren.get_width() - 816, 90))
        ren = font.render("{0:.1f}F ".format(skyData.temperature * 9 / 5 + 32), 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        screen.blit(ren, (screen.get_width() - ren.get_width() - 885, 90))

        ren = font.render("Feels like:", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        screen.blit(ren, (5, 130))
        ren = font.render("{0:.1f}°C".format(skyData.feels_like), 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        screen.blit(ren, (screen.get_width() - ren.get_width() - 816, 130))

        ren = font.render("Humidity:", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        screen.blit(ren, (5, 170))
        ren = font.render("{}%".format(skyData.humidity), 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        screen.blit(ren, (screen.get_width() - ren.get_width() - 816, 170))
        
        ren = font.render("Pressure:", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        screen.blit(ren, (5, 210))
        ren = font.render("{}mb".format(forecastData.sea_level_pressure), 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        screen.blit(ren, (screen.get_width() - ren.get_width() - 816, 210))

        ren = font.render("Pressure trend:", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        screen.blit(ren, (5, 250))
        ren = font.render("{}".format(forecastData.pressure_trend.capitalize()), 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        screen.blit(ren, (screen.get_width() - ren.get_width() - 816, 250))
        
        ren = font.render("UV Index: ", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        screen.blit(ren, (5, 290))
        if skyData.uv < 2:
            ren = font.render("LOW", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        elif skyData.uv < 5:
            ren = font.render("Moderate", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        elif skyData.uv < 10:
            ren = font.render("High", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        elif skyData.uv < 10:
            ren = font.render("Very High", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        else:
            ren = font.render("Extreme", 1, pg.Color(162, 160, 160), pg.Color('red'))
        screen.blit(ren, (screen.get_width() - ren.get_width() - 816, 290))      
    else:
        ren = font.render("Temperature:", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        screen.blit(ren, (5, 90))
        ren = font.render("Feels like:", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        screen.blit(ren, (5, 130))
        ren = font.render("Humidity:", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        screen.blit(ren, (5, 170))     
        ren = font.render("UV Index: ", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        screen.blit(ren, (5, 290))      
        
    if forecastData.status == forecast.STATUS_OK:
        ren = font.render("Pressure:", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        screen.blit(ren, (5, 210))
        ren = font.render("{}mb".format(forecastData.sea_level_pressure), 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        screen.blit(ren, (screen.get_width() - ren.get_width() - 816, 210))
    else:
        ren = font.render("Pressure:", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        screen.blit(ren, (5, 210))
        ren = font.render("Pressure trend:", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        screen.blit(ren, (5, 250))   

    if forecastData.status == forecast.STATUS_OK:
        ren1 = font.render("Lightning:   ", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        ren2 = font.render(time.strftime("%d %b ") + str(forecastData.lightning_strike_last_distance), 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112)) 
        ren3 = font.render("Precipitation Today:  ", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        ren4 = font.render(str(forecastData.precip_accum_local_day) + " mm", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        ren5 = font.render("Rain This Year:  ", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        ren6 = font.render(str(forecastData.year) + " mm", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
    else:
        ren1 = font.render("", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
        ren2 = None
        ren3 = None
        ren4 = None
        ren5 = None
        ren6 = None

    screen.blit(ren1, (5, 330))
    if ren2:
        ren2_width = ren2.get_width()
        screen.blit(ren2, (270 - ren2_width, 330))
    if ren3:
        screen.blit(ren3, (290, 520))
    if ren4:
        screen.blit(ren4, (470, 520))
    if ren5:
        screen.blit(ren5, (560, 520))
    if ren6:
        screen.blit(ren6, (710, 520))

def renderPanel2data():
    assert(skyDevice)
    assert(forecastObj)
    skyData = skyDevice.getData()
    forecastData = forecastObj.getData()
  
    # Used for UDP Calls from Sky device
    if skyData.status == sky.STATUS_OK:
        ren = font.render("Sunrise:", 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (810, 250))
        ren = font.render(forecastData.sunriseday[0], 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        width = ren.get_width()
        screen.blit(ren, (screen.get_width() - ren.get_width() - 5, 250))
        ren = font.render("Sunset:", 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (810, 290))
        ren = font.render(forecastData.sunsetday[0], 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        width = ren.get_width()
        screen.blit(ren, (screen.get_width() - ren.get_width() - 5, 290))
        ren = font.render("Brightness:", 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (810, 330))
        ren = font.render("{} lumens".format(skyData.illuminance), 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        width = ren.get_width()
        screen.blit(ren, (screen.get_width() - ren.get_width() - 5, 330))
    else:
        ren = font.render("Sunset:", 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (810, 290))
        ren = font.render("Brightness:", 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (810, 330))

def renderPanel3data():
    assert(pollenObj)
    forecastData = forecastObj.getData()
    skyData = skyDevice.getData()
    
    # Weather Map

    if forecastData.kia:
        ren = forecastData.kia
        screen.blit(ren, (270, 50))
    ren = font.render("Conditions:", 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
    screen.blit(ren, (810, 50))
    ren = font.render("{}".format(forecastData.conditions), 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
    width = ren.get_width()
    screen.blit(ren, (screen.get_width() - ren.get_width() - 5, 50))
    if skyData.status == sky.STATUS_OK:
        hres_div = 810 * HRES // 1080
        ren = font.render("Low Temp Today:", 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (hres_div, 90))
        ren = font.render("{}°C".format(skyData.templow), 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        width = ren.get_width()
        screen.blit(ren, (screen.get_width() - ren.get_width() - 5, 90))
        ren = font.render("High Temp Today:", 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (810, 130))
        ren = font.render("{}°C".format(skyData.temphigh), 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        width = ren.get_width()
        screen.blit(ren, (screen.get_width() - ren.get_width() - 5, 130))
        ren = font.render("Rain today:", 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (hres_div, 170))
        ren = font.render("{}mm".format(forecastData.precip_accum_local_day), 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        width = ren.get_width()
        screen.blit(ren, (screen.get_width() - ren.get_width() - 5, 170))
        ren = font.render("Max Wind Gust:", 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (hres_div, 210))
        ren = font.render("{0:.2f}mph".format(skyData.highgust), 5, pg.Color(162, 160, 160), pg.Color(25,25,112))
        width = ren.get_width()
        screen.blit(ren, (screen.get_width() - ren.get_width() - 5, 210))
        ren = font.render("Weather Sensor Status:", 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (hres_div, 370))
        ren = font.render("{} ".format(skyData.sensor_status), 5, pg.Color(162, 160, 160), pg.Color(25,25,112))
        width = ren.get_width()
        screen.blit(ren, (screen.get_width() - ren.get_width() - 3, 370))
    else:
        hres_div = 810 * HRES // 1080
        ren = font.render("Low Temp Today:", 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (hres_div, 90))
        ren = font.render("High Temp Today:", 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (hres_div, 130))
        ren = font.render("Rain today:", 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (hres_div, 170))
        ren = font.render("Max Wind Gust:", 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (hres_div, 210))
        ren = font.render("Weather Sensor Status: 999", 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (hres_div, 370))

#air quality section    
    ren = font.render("Indoor Air Quality:", 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
    screen.blit(ren, (10*HRES//1080, 570))

#if aqdata is not None:
    if aqdata is not None and aqdata["pm25 standard"] <=  12:      #if value is 12 or less print in green
        pg.draw.rect(screen, pg.Color("green"), Rect(190*HRES//1080, 570, 60, 20))  #Air quality indicator           
    elif aqdata is not None and aqdata["pm25 standard"] <= 34.5:     #if value is 35.4 or less print in yellow                   
        pg.draw.rect(screen, pg.Color("yellow"), Rect(190*HRES//1080, 570, 60, 20))  #Air quality indicator  
    elif aqdata is not None and aqdata["pm25 standard"] >= 35:     #if value is 35.4 or less print in yellow                   
        pg.draw.rect(screen, pg.Color("red"), Rect(190*HRES//1080, 570, 60, 20))  #Air quality indicator       
    if aqdata is not None:
        ren = font.render("pm1:               {}".format(aqdata["pm10 standard"]), 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (10*HRES//1080, 600))   
        ren = font.render("pm2.5:            {}".format(aqdata["pm25 standard"]), 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (10*HRES//1080, 630))   
        ren = font.render("pm10:             {}".format(aqdata["pm100 standard"]), 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (10*HRES//1080, 660))
    
        ren = font.render("03um Particles in 100ml of air:      {}".format(aqdata["particles 03um"]), 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (275*HRES//1080, 600))   
        ren = font.render("05um Particles in 100ml of air:      {}".format(aqdata["particles 05um"]), 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (275*HRES//1080, 630))   
        ren = font.render("10um Particles in 100ml of air:      {}".format(aqdata["particles 10um"]), 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (275*HRES//1080, 660))

        ren = font.render("25um Particles in 100ml of air:      {}".format(aqdata["particles 25um"]), 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (725*HRES//1080, 600))   
        ren = font.render("50um Particles in 100ml of air:      {}".format(aqdata["particles 50um"]), 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (725*HRES//1080, 630))   
        ren = font.render("100um Particles in 100ml of air:    {}".format(aqdata["particles 100um"]), 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
        screen.blit(ren, (725*HRES//1080, 660))
        
#end of air quality section  

    
def renderPanelx(hour):
    assert(pollenObj)  
    pollenData = pollenObj.getData()   
    forecastData = forecastObj.getData()  
    
    xof1 = [-201, 95, 195, 295, 395, 495, 595, 695, 795, 895, 995]   

    time_text = "Time:"
    chance_text = "Chance:"
    sky_text = "Sky:"
    temp_text = "Temp:"
    wind_text = "Wind:"

    xof1 = [-201, 95, 195, 295, 395, 495, 595, 695, 795, 895, 995]  
    ren_time = font.render(time_text, 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
    screen.blit(ren_time, (5, 702))
    ren_chance = font.render(chance_text, 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
    screen.blit(ren_chance, (5, 744))
    ren_sky = font.render(sky_text, 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
    screen.blit(ren_sky, (5, 786))
    ren_temp = font.render(temp_text, 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
    screen.blit(ren_temp, (5, 828))
    ren_wind = font.render(wind_text, 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
    screen.blit(ren_wind, (5, 870))
    
    time_var = (datetime.now() + timedelta(hours=hour)).strftime('%H:%M') if forecastData.status == forecast.STATUS_OK else None
    ren_time = font.render(time_var if time_var is not None else "", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
    screen.blit(ren_time, (xof1[hour] * HRES // 1080, 702))

    chance_var = forecastData.precipprhour[hour] if forecastData.status == forecast.STATUS_OK else None
    ren_chance = font.render(chance_var if chance_var is not None else "", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
    screen.blit(ren_chance, (xof1[hour] * HRES // 1080, 744))

    sky_var = forecastData.conditionshour[hour] if forecastData.status == forecast.STATUS_OK else None
    ren_sky = font.render(sky_var if sky_var is not None else "", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
    screen.blit(ren_sky, (xof1[hour] * HRES // 1080, 786))
   
    temp_var = "{0:.1f}°C".format(forecastData.airtemphour[hour]) if forecastData.status == forecast.STATUS_OK else None
    ren_temp = font.render(temp_var if temp_var is not None else "", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
    screen.blit(ren_temp, (xof1[hour] * HRES // 1080, 828))

    wind_var = "{0:.1f} mph".format(forecastData.wind_avghour[hour]) if forecastData.status == forecast.STATUS_OK else None
    ren_wind = font.render(wind_var if wind_var is not None else "", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
    screen.blit(ren_wind, (xof1[hour] * HRES // 1080, 870))


    # Pollen Data    
    ren = font.render("Pollen Level:", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112)) 
    screen.blit(ren, (300 * HRES // 1080, 570))
    ren = font.render("Allergy Levels:", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112)) 
    screen.blit(ren, (570 * HRES // 1080, 570))
    ren = font.render("Outside Air Quality:", 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112)) 
    screen.blit(ren, (820 * HRES // 1080, 570)) 
    # Pollen Colours 
    colors = {"Very Low": "green", "Low": "green", "Moderate": "yellow", "High": "red", "Very High": "purple"}
    pollen_level_color = colors.get(pollenData.pollen[1], "green")
    allergy_level_color = colors.get(pollenData.allergy[1], "green")
    air_quality_color = colors.get(pollenData.airquality[1], "green")
    
    pg.draw.rect(screen, pg.Color(pollen_level_color), Rect(430 * HRES // 1080, 570, 60, 20))
    pg.draw.rect(screen, pg.Color(allergy_level_color), Rect(720 * HRES // 1080, 570, 60, 20))
    pg.draw.rect(screen, pg.Color(air_quality_color), Rect(1010 * HRES // 1080, 570, 60, 20))
      

#Moon phase image  
    if moonimage:
        ren = moonimage   
    screen.blit(pg.transform.smoothscale(ren, (120 , 120)), (880, 400))  
 
#Daily forecast
def renderPanelB(day):
    forecastData = forecastObj.getData()
    daypositions = [-1, 30, 246, 462, 678, 894]
    xpositions = [-1, 5, 231, 448, 662, 879]
    iconpositions = [-1, 60, 276, 492, 708, 924]
    now = datetime.now()
    dow = now + timedelta(days=day)
    dayOfWeekString = dow.strftime("%A")

    ren = font.render(dayOfWeekString  + " " + custom_strftime('{TH}', dow.timetuple()) , 1, pg.Color(25,25,112), pg.Color(162, 160, 160))
    screen.blit(ren, (daypositions[day]*HRES//1080, 925))    
    ren = font.render(("\u0332".join("Conditions:")), 1, pg.Color(162, 160, 160), pg.Color(25,25,112))
    screen.blit(ren, (daypositions[day]*HRES//1080, 980))  

    if forecastData.status == forecast.STATUS_OK:
        renderText(forecastData.condday[day], xpositions[day], 1010)
        renderText("High Temp    {}°C".format(forecastData.thighday[day]), xpositions[day], 1040)
        renderText("Low Temp    {}°C".format(forecastData.tlowday[day]), xpositions[day], 1070)
        renderText("Chance    {}%".format(forecastData.precprday[day]), xpositions[day], 1100)
        renderText("Precipitation Type:", xpositions[day], 1130)
        renderText(forecastData.preciptypeday[day], xpositions[day], 1160)
        screen.blit(forecastData.iconday[day], (iconpositions[day] * HRES // 1080, 1170))
    else:
        renderText("", xpositions[day], 1010)
        renderText("", xpositions[day], 1040)
        renderText("", xpositions[day], 1070)
        renderText("", xpositions[day], 1100)
        renderText("", xpositions[day], 1130)
#        pg.image.load(os.path.join("images", os.path.join("weather_icons", "--_.bmp"))), (iconpositions[day] * HRES // 1080, 1170)
        pg.image.load(os.path.join("images", os.path.join("weather_icons", "--_.bmp"))).convert(), (iconpositions[day] * HRES // 1080, 1170)
 #       screen.blit(os.path.join("images",os.path.join("weather_icons","--_.bmp")), (iconpositions[day] * HRES // 1080, 1170))
#        screen.blit("--_1.bmp", (iconpositions[day] * HRES // 1080, 1170))

def renderText(text, x, y):
    ren = font.render(text, 1, pg.Color(162, 160, 160), pg.Color(25, 25, 112))
    screen.blit(ren, (x * HRES // 1080, y))

    
def renderEarthquakePanel():
    global eqMap, displayManager

    assert(eqMap)
    assert(displayManager)

    screen.fill(pg.Color('black'), rect=Rect(0, 1300, 1080, 620))  # Background for Map
    eqMap.repaintMap()

def loop():
    """The program's main loop."""
    global everyMinuteThreadRunning, fiveMinuteThreadRunning, SecondThreadRunning, showLightning
    global lightningFlashCount, eqBlinkPeriodCount, eqMap
 
    clock = pg.time.Clock()

    try:
        while True:
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    skyDevice.stop()
                    pg.display.quit() 
                    sys.exit()
                 
                elif event.type == pg.KEYDOWN:
                    if event.key == pg.K_r:
                        if eqMap:
                            eqMap.midnightReset()
                            logging.info('earthquake module reset')
                        if EQEventGatherer:    
                            EQEventGatherer.initial_event()
                    if event.key == pg.K_x:
                        EQEventGatherer.listener_stop()
                        skyDevice.stop()
                        pg.display.quit()
                        sys.exit(0)
                    elif event.key == pg.K_t:
                        pg.display.toggle_fullscreen()
                    elif event.key == pg.K_f:
                        pg.display.toggle_fullscreen()
                    elif event.key == pg.K_l:
                        logging.info("L key pressed.")
                        skyDevice.data.lightning_distance = 100 #For testing purposes
                        forecastObj.data.lightning_strike_last_epoch = time.time() #for testing purposes
                        skyDevice.data.lightning_time = time.time() #For testing purposes
                        logging.info('Initializing Mixer')
                        mixer.init()
                        mixer.music.load('thunder.mp3')
                        mixer.music.set_volume(0.1)
                        mixer.music.play()
                        
                elif event.type == THREE_SECONDS_THREAD_FUNCTION_EVENT:
                    if not SecondThreadRunning:
                        t = threading.Thread(target=SecondThreadFunction, args=())
                        t.daemon = True
                        t.start()
                    else:
                        logging.warning("Previous threeSecond thread still running. Not relaunching.")
                elif event.type == EVERY_MINUTE_THREAD_FUNCTION_EVENT:
                    if not everyMinuteThreadRunning:
                        t = threading.Thread(target=everyMinuteThreadFunction, args=())
                        t.daemon = True
                        t.start()
                    else:
                        logging.warning("Previous every-minute thread still running. Not relaunching.")
                elif event.type == EVERY_FIVE_MINUTES_THREAD_FUNCTION_EVENT:
                    #Kick off the 5-minute thread:
                    if not fiveMinuteThreadRunning:
                        t = threading.Thread(target=everyFiveMinutesThreadFunction, args=())
                        t.daemon = True
                        t.start()
                    else:
                        logging.warning("Previous five-minutes thread still running. Not relaunching.")
                elif event.type == EVERY_HOUR_THREAD_FUNCTION_EVENT:
                    #Kick off the hour thread:
                    if not hourThreadRunning:
                        t = threading.Thread(target=everyHourThreadFunction, args=())
                        t.daemon = True
                        t.start()
                    else:
                        logging.warning("Previous hour thread still running. Not relaunching.")                        
                elif event.type == EVERY_100MS_EVENT:
                    #Every 500ms called earthquake every500ms() method.
                    eqBlinkPeriodCount += 1
                    if eqBlinkPeriodCount >= 5:
                        eqBlinkPeriodCount = 0
                        assert(eqMap)
                        eqMap.every500ms()

                    if lightningFlashCount > 0:
                        if lightningFlashCount > 2*NUM_FLASHES:
                            lightningFlashCount = 0
                            showLightning = False
                        else:     
                            #Toggle lightning
                            showLightning = not showLightning
                            lightningFlashCount += 1

            if not initialWeatherUpdateReceived:
                screen.fill(BACKGROUND_COLOR)
                renderPanels()
                #renderPlaceholderText()
                renderCompassRose(135, 455, 60)
            else:
                if showLightning:
                    renderLightning()
                else:
                    screen.fill(BACKGROUND_COLOR)
                    renderPanels()
                    renderTopPanel()
                    renderEarthquakePanel()
                    renderPanel1Data()
                    renderPanel2data()
                    try:
                        renderPanel3data()
                    except RuntimeError:
                        pass
                    renderPanelB(1) #next 5 days weather forecast ^^  
                    renderPanelB(2)
                    renderPanelB(3)
                    renderPanelB(4)
                    renderPanelB(5)           
                    renderPanelx(0) #next 8 hours weather forecast ^^  
                    renderPanelx(1)
                    renderPanelx(2)
                    renderPanelx(3)   
                    renderPanelx(4)
                    renderPanelx(5)
                    renderPanelx(6) 
                    renderPanelx(7)         
                    renderPanelx(8)   
                    renderPanelx(9)  
                    renderPanelx(10)                        
                    renderCompassRose(135, 455, 60)  
            
            checkLightning()
            pg.display.flip() #Double buffering
            clock.tick(30) #30fps framerate
    except:
        skyDevice.stop()
        pg.display.quit()
        raise #rethrow exception

def usage():
    """Prints commandline usage string."""
    print()
    print("Usage:")
    print("python weather1.py [-h] [-t] [-p <pms5003 serial port>] ")
    print("-t: Run in test mode: windowed instead of full screen and with fake serial I/O.")
    print("<pms5003 serial port> can be set to 'test' to use a fake serial port and simulated data for that device.")
    print("-h: Display this help.")
    print()
    print("Default pms5003 serial port is: {}".format(PMS5003_DEFAULT_SERIAL_DEV_NAME))
    print()
    print("Example:")
    print("Start weatherStation, using default serial ports:")
    print("python3 weather1.py")
    print()
    print("Start weatherStation, passing in serial ports:")
    print("python3 weather1.py -p /dev/ttyAMA0")
    print()
    print("Start weatherStation with a real pms5003:")
    print("python3 weather1.py -p /dev/ttyAMA0")
    print()
    print("Start weatherStation in test mode:")
    print("python3 weather1.py -t")
    print()


def main():
    """Program entry point."""
    global pms5003SerialDevName
    print("weatherStation.py V{}.".format(WEATHERSTATION_VERSION))
    try:
        opts, args = getopt.getopt(sys.argv[1:], "htp:c:", ["help", "test", 'pms='])
    except getopt.GetoptError as err:
        # print help information and exit:
        print(err)  # will print something like "option -a not recognized"
        usage()
        sys.exit(2)

    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-t", "--test"):
            testMode = True
#        elif o in ("-p", "--pms"):
#            pms5003SerialDevName = a
        else:
            assert False, "unhandled option"


 #   if (pms5003SerialDevName != "test") and not os.path.exists(pms5003SerialDevName):
#      print("Serial Device not found: {}".format(pms5003SerialDevName))
 #       usage()
 #       sys.exit(1)

    init()
    loop()

if __name__ == "__main__":
    main()

#Information only*****
'''"sensor_status" definitions
0 = Sensors OK
1 = lightning failed
2 = lightning noise
4 = lightning disturber
8 = pressure failed
16 = temperature failed
32 = rh failed
64 = wind failed
128 = precip failed
256 = light/uv failed
512 = Sensors OK
8000 = power booster depleted
10000 = power booster shore power
" Radio status definitions"
0   Version
1   Reboot Count
2   I2C Bus Error Count
3   Radio Status (0 = Radio Off, 1 = Radio On, 3 = Radio Active, 7 = BLE Connected)
4   Radio Network ID'''
