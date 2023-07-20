""" Interface to receive UDP packages from a Smart Weather station. """

# pylint: disable=import-error
import os
import select
import socket
import sys
import json
import threading
import time
import datetime

from . import utils

from .constants import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_UNITS
)

class SWReceiver(threading.Thread):
    """ Open a UDP socket to monitor for incoming packets. """

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, units=DEFAULT_UNITS):
        """Construct a Smart Weather interface object."""
        threading.Thread.__init__(self)
        self.stopped = threading.Event()
        self._callbacks = []
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.setblocking(False)
        self.host = host
        self.port = port
        self.units = units
        self._socket.bind((host, port))
        self._state = 'idle'
        self._precipitation = 0
        self._precipitation_raw = 0
        self._precipitation_rate = 0
        self._precipitation_rate_raw = 0
        self._precipitation_date = datetime.datetime.today().strftime('%Y-%m-%d')

    def registerCallback(self, callback):
        self._callbacks.append(callback)

    def run(self):
        """Main loop of Smart Weather thread."""
        while not self.stopped.isSet():
            #try:
                # if the current state is idle, just block and wait forever
                # if the current state is any other state, then a timeout of 200ms should
                # be reasonable in all cases.
                timeout = (self._state != 'idle') and 0.2 or None
                rdlist, _, _ = select.select([self._socket.fileno()], [], [], timeout)
                if not rdlist:
                    if self._state != 'idle':
                        self._state = 'idle'
                    continue
                data = self._socket.recv(1024)
                if not data:
                    # check if the socket is still valid
                    try:
                        os.fstat(recv._socket.fileno())
                    except socket.error:
                        break
                    continue

                ds = utils.getDataSet(data, self.units, ignore_errors=True)
                if ds:
                    if ds.type == 'st':
                        # Calculated Values
                        ds.wind_chill = utils.WeatherFunctions.getWindChill(self, ds.wind_speed, ds.temperature)
                        ds.feels_like = utils.WeatherFunctions.getFeelsLike(self, ds.temperature, ds.wind_chill, ds.heat_index)
                        self._precipitation_rate_raw = ds.precipitation_rate
                        self._precipitation_rate = round(self._precipitation_rate_raw * 60,2)
                        # Reset the Precipitation at Midnight
                        if datetime.datetime.fromtimestamp(ds.timestamp).strftime('%Y-%m-%d') != self._precipitation_date:
                            self._precipitation_date = datetime.datetime.fromtimestamp(ds.timestamp).strftime('%Y-%m-%d')
                            self._precipitation = 0
                            self._precipitation_raw =0
                        self._precipitation_raw = self._precipitation_raw + self._precipitation_rate_raw
                        self._precipitation = round(self._precipitation_raw,1)
                        ds.precipitation = self._precipitation
                        ds.precipitation_rate = self._precipitation_rate
                        
                    for callback in self._callbacks:
                        callback(ds)
            #except:
            #    time.sleep(0.1)

    def stop(self):
        self.stopped.set()
        # force receiver thread to wake from select
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect((self.host, self.port))
        msg = "stop"
        datagram = sys.version_info[0] == 2 and bytes(msg) or bytes(msg, "utf-8")
        sock.send(datagram)
        sock.close()
        self.join()
        self._socket.close()
