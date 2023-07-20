import logging
import json
from datetime import datetime
from dateutil import tz
import requests
from tornado.websocket import websocket_connect
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado import gen


ioloop = None
eqMap = None
echo_uri = 'wss://www.seismicportal.eu/standing_order/websocket'
PING_INTERVAL = 15

active_connections = 0
periodic_cb = None

class EQEventParser:
    def __init__(self, jsonData):
        self.jsonData = jsonData
    def getID(self):
        if not self.jsonData:
            return None
        return self.jsonData['unid']
    def getLon(self):
        if not self.jsonData:
            return None
        return float(self.jsonData['lon'])
    def getLat(self):
        if not self.jsonData:
            return None
        return float(self.jsonData['lat'])
    def getMag(self):
        if not self.jsonData:
            return None
        return float(self.jsonData['mag'])
    def getDepth(self):
        if not self.jsonData:
            return None
        return float(self.jsonData['depth'])
    def getLocation(self):
        if not self.jsonData:
            return None
        return self.jsonData['flynn_region']
    def getEv(self):
        if not self.jsonData:
            return None
        return self.jsonData['evtype']       # *** Eerthquake Type ***
    def getTime(self):
        if not self.jsonData:
            return None
        tString = self.jsonData['time'].split('.')[0]
        time_obj = datetime.strptime(tString, "%Y-%m-%dT%H:%M:%S")
        return time_obj

class WS:
    def __init__(self, ws=None, key=None):
        self.ws = ws
		
# This function gets called when a new earthquake event is received.
def myprocessing(message):
    global eqMap
    max_retries = 3
    retry_delay = 5  # seconds
    for attempt in range(max_retries):
        try:
            r = requests.get("https://www.seismicportal.eu/fdsnws/event/1/query?limit=1&format=json")
            if r.status_code == 200:
                # Process the earthquake data
                data = json.loads(message)
                if data['action'] == 'create':
                    now = datetime.now()
                    parser = EQEventParser(data['data']['properties'])
                    if eqMap and parser.getTime().strftime("%d-%m-%Y") == now.strftime("%d-%m-%Y"):
                        eqMap.earthquakeEvent(
                            parser.getID(),
                            parser.getLocation(),
                            parser.getLon(),
                            parser.getLat(),
                            parser.getEv(),  # *** Earthquake Type ***
                            parser.getMag(),
                            parser.getDepth(),
                            parser.getTime()
                        )
                return True
            break  # Break out of the retry loop since we got a successful response
        except Exception as e:
            logging.warning(f"An exception occurred: {str(e)}")
            # Handle the exception and retry after the specified delay
            logging.warning(f"Failed to get Earthquake Data. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
    else:
        logging.warning(f"Maximum number of retries reached. Waiting for 5 minutes before retrying...")
        time.sleep(300)  # Wait for 5 minutes (300 seconds) before retrying
        # Restart the process by calling the necessary functions
        myprocessing(message)  # Retry the data retrieval
        
def on_close(self):
    print("### closed ###")

@gen.coroutine
def listen(ws):
    while True:
        msg = yield ws.read_message()
        if msg is None:
            logging.info("Empty message!")
            launch_client() # This will restart the process if the internet connection drops
        else:
            myprocessing(msg)

@gen.coroutine
def launch_client():
    global active_connections, periodic_cb

    if active_connections > 0:
        return

    try:
        logging.info("Open WebSocket connection to %s", echo_uri)
        active_connections += 1

        periodic_cb = PeriodicCallback(check_idle_and_connect, 100)
        periodic_cb.start()

        ws = yield websocket_connect(echo_uri, ping_interval=PING_INTERVAL, connect_timeout=45)
        logging.info("Waiting for messages...")
        active_connections += 1
        listen(ws)
    except Exception as e:
        logging.exception("Connection error: %s", str(e))
        yield gen.sleep(3)
        launch_client()
        
@gen.coroutine
def check_idle_and_connect():
    global active_connections, periodic_cb

    if active_connections == 0:
        if periodic_cb is not None:  # Check if periodic_cb has been assigned a value
            periodic_cb.stop()
            periodic_cb = None  # Reset periodic_cb to None
        # Convert the IOLoop to SSL and establish the WebSocket connection
        ws = yield websocket_connect(echo_uri, ping_interval=PING_INTERVAL, connect_timeout=30)
        logging.info("Waiting for messages...")
        active_connections += 1
        listen(ws)

def on_close():
    global active_connections
    active_connections -= 1
        
#Start the WebSocket listener
def listener_start(eqMapRef):
    global eqMap, ioloop
    eqMap = eqMapRef
    initial_event()
    ioloop = IOLoop()
    launch_client()
    ioloop.start()
    return ioloop  # Return the IOLoop instance

# Stop the WebSocket listener
def listener_stop():
    global ioloop
    logging.info("Close WebSocket")
    ioloop.stop()

#Retrieve the most recent event, so we have something to start with
def initial_event():
    global eqMap
    try:
        r = requests.get("https://www.seismicportal.eu/fdsnws/event/1/query?limit=1&format=json")
        if r.status_code == 200:
            jsonData = json.loads(r.text)
            parser = EQEventParser(jsonData['features'][0]['properties'])
            if eqMap:
                logging.info('Initial earthquake event data received.')
                # Pass the event to eqMap
                eqMap.earthquakeEvent(
                    parser.getID(),
                    parser.getLocation(),
                    parser.getLon(),
                    parser.getLat(),
                    parser.getEv(),     # *** Earthquake Type ***
                    parser.getMag(),
                    parser.getDepth(),
                    parser.getTime())
            return True
        else:
            logging.warning("EQEvent request status code {}".format(r.status_code))
            return False
    except requests.exceptions.RequestException as e:
        logging.warning("Error retrieving seismicportal data: {}".format(str(e)))
        return False


