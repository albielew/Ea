from collections import deque
import logging
import pygame
from pygame import mixer
#MAX_EVENTS = 200

class EventDB:
    def __init__(self):
        self.EQEventQueue = deque()
        self.EQEventQueue.clear()

    def getEvent(self, index):
        return self.EQEventQueue[index]

    def numberOfEvents(self):
        return len(self.EQEventQueue)

    def clear(self):
        self.EQEventQueue.clear()

    def addUpdateEvent(self, id, lon, lat, ev, mag, timestamp, update):
        try:
            index = list(map(lambda n: n[0], self.EQEventQueue)).index(id)
            existing_event = self.EQEventQueue[index]

            if existing_event[1:] == (lon, lat, ev, mag, timestamp):
                if update:
                    logging.info("Updating existing event: id {},lon {}, lat {}, ev {}, mag {}, timestamp {}".format(id))
                    self.EQEventQueue[index] = (id, lon, lat, ev, mag, timestamp)
                    return 0
                else:
                    return -1
            else:
                logging.info("Deleting original event: id {},lon {}, lat {}, ev {}, mag {}, timestamp {}".format(id))
                self.EQEventQueue.remove(existing_event)
                self.EQEventQueue.appendleft((id, lon, lat, ev, mag, timestamp))
                return 1

        except ValueError:
            if mag >= 7:
                logging.info("Playing Sound")
                mixer.init()
                mixer.music.load('Red Alert.mp3')
                mixer.music.set_volume(0.1)
                mixer.music.play()

            self.EQEventQueue.appendleft((id, lon, lat, ev, mag, timestamp))
            return 1

    def showEvents(self):
        print("Number of entries: ", len(self.EQEventQueue))
        print(self.EQEventQueue)
        print("\n")

    def getEvent(self, index):
        return self.EQEventQueue[index]
