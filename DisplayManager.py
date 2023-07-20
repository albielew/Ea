import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide" # hide pygame prompt message
import pygame as pg
from pygame import mixer
import pygame.freetype  # Import the freetype module.
import time
import sys
from datetime import datetime
import pdb
from pygame.locals import *
import logging
import random

EARTHQUAKE_MAP_X = 0
EARTHQUAKE_MAP_Y = 1340
EARTHQUAKE_MAP_HEIGHT = 540
EARTHQUAKE_MAP_WIDTH = 1080

EARTHQUAKE_FONT_SIZE_BIG = 50
EARTHQUAKE_FONT_SIZE_REG = 24
EARTHQUAKE_FONT_SIZE_SMALL = 18

ANIM_MAG_SCALE = 5 #a scaling factor applied to given magnitude, to adjust intensity of animation
ANIM_FLASH_INTERVAL = 1 #animation flashing interval
ANIM_DURATION = 20*ANIM_FLASH_INTERVAL #animation duration in number of screen updates

class DisplayManager:
    def __init__(self, screen):
        self.screenPosX = EARTHQUAKE_MAP_X
        self.screenPosY = EARTHQUAKE_MAP_Y
        self.topTextRow = -16
        self.bottomTextRow = EARTHQUAKE_MAP_HEIGHT + 8
        self.fontSize = EARTHQUAKE_FONT_SIZE_REG
        self.middleTextRow = 250
        self.middleTextRow1 = 270
        self.middleTextRow2 = 290
        self.middleTextRow3 = 330
        self.middleTextRow4 = 350
        self.middleTextRow5 = 370
        self.textColor = (255, 255, 255)
        self.black = (0, 0, 0)
        self.white = (255, 255, 255)
        self.blue = (160,32,240)
        self.red = (255, 0, 0)
        self.green = (0, 255, 0)
        self.greena = (6, 255, 255)
        self.grey = (173, 216, 23)
        self.orange = (187, 62, 139)
        self.purple = (106, 13, 173)
        self.animCounter = 0
        self.animText = ""
        self.animTextOn = False
        self.screenWidth = EARTHQUAKE_MAP_WIDTH
        self.screenHeight = EARTHQUAKE_MAP_HEIGHT
        self.screen = screen
        self.mapImage = pg.image.load('images/new.bmp')
        self.mapImageRect = self.mapImage.get_rect()
        self.mapImageRect.y = (self.screenHeight - self.mapImageRect.height) / 2
        self.font = pg.freetype.Font('fonts/Sony.ttf', self.fontSize)

    def clearScreen(self):
        pg.draw.rect(
            self.screen,
            self.black,
            Rect(self.screenPosX, self.screenPosY, self.screenWidth, self.screenHeight)
        )

    # Select color from magnitude
    def colorFromMag(self, mag):
        if mag < 1:
            mag = 1.0
        imag = int(mag)
        color_dict = {
            1: self.grey,
            2: self.grey,
            3: self.grey,
#            4: self.greena,
#            5: self.greena,
#            6: self.greena,
            4: self.white,
            5: self.white,
            6: self.white,
            7: self.red,
            8: self.red,
            9: self.red
        }
        return color_dict.get(imag, self.green)

    # Display the map
    def displayMap(self):
        self.clearScreen()
        self.screen.blit(self.mapImage, (0, self.screenPosY))

    # Draw text
    def drawText(self, x, y, text):
        self.font.render_to(self.screen, (self.screenPosX + x, self.screenPosY + y), text, self.textColor)

    # Draw centered text
    def drawCenteredText(self, y, text):
        textSurface, rect = self.font.render(text, self.textColor)
        x = (self.screenWidth - rect.width) // 2
        self.font.render_to(self.screen, (self.screenPosX + x, self.screenPosY + y), text, self.textColor)

    # Draw right justified text
    def drawRightJustifiedText(self, y, text):
        textSurface, rect = self.font.render(text, self.textColor)
        x = self.screenWidth - rect.width - 5
        self.font.render_to(self.screen, (self.screenPosX + x, self.screenPosY + y), text, self.textColor)

        
    # Set text size
    def setTextSize(self, size):
        self.fontSize = size
        self.font = pg.freetype.Font('fonts/Sony.ttf', self.fontSize)

    # Set text color
    def setTextColor(self, color):
        self.textColor = color

    # Draw a circle on the screen
    def drawCircle(self, x, y, radius, color):
        pg.draw.circle(self.screen, color, (self.screenPosX + int(x), self.screenPosY + int(y)), int(radius), 2)


    # Draw a circle with size based on mag at lon, lat position on map
    def mapEarthquake(self, lon, lat, mag, color):
        # Calculate map X and Y
        if lon > -169:
            mapX = ((lon + 169) * self.mapImageRect.width) / 360.0
        else:
            mapX = (((lon + 169) * -1) + 1069)  # Start of new section of map

        mapY = (((-lat + 90.0) * self.mapImageRect.height) / 180.0) + self.mapImageRect.y

        # Return from function early for magnitude < 3.1 instead of redrawing.
        if mag <= 1.9:
            return

        # Diameter of circle
        if mag < 2:
            mag = 2.5
        radius = mag * 3

        # Check if earthquake falls within specific latitude and longitude ranges
        if (17.5 <= lat <= 38.5 and -17.5 <= lon <= 59.97) or (12.12 <= lat <= 50 and 59.5 >= lon >= 115.54) or (2.47 <= lat <= 12.27 and 37.12 >= lon >= 51.2):
            if mag < 7:
                color = self.blue

        self.drawCircle(mapX, mapY, radius, color)


    # Display earthquake time
    def displayEarthquakeTime(self, earthquakeTime):
        self.setTextColor(self.white)
        self.setTextSize(EARTHQUAKE_FONT_SIZE_REG)
        self.drawText(5, self.topTextRow, earthquakeTime) # time of earthquake

    def displayEarthquakeTime2(self, earthquakeTime2):
        self.setTextColor(self.white)
        self.setTextSize(EARTHQUAKE_FONT_SIZE_SMALL)
        self.drawText(1, self.middleTextRow5, earthquakeTime2) # date of max this year

    def displayEarthquakeTime1(self, earthquakeTime1):
        self.setTextColor(self.white)
        self.setTextSize(EARTHQUAKE_FONT_SIZE_SMALL)
        self.drawText(1, self.middleTextRow2, earthquakeTime1) #time of max today

    # Display magnitude
    def displayMagnitude(self, mag):
        self.setTextColor(self.white)
        self.setTextSize(EARTHQUAKE_FONT_SIZE_REG)
        self.drawRightJustifiedText(self.topTextRow, "Magnitude: " + str(mag))

    # Display max
    def displayMax(self, mag1, location1, mag2, location2):
        self.setTextColor(self.white)
        self.setTextSize(EARTHQUAKE_FONT_SIZE_SMALL)
        self.drawText(1, self.middleTextRow, "Max Event Today Mag: " + str(mag1))
        self.setTextColor(self.white)
        self.setTextSize(EARTHQUAKE_FONT_SIZE_SMALL)
        self.drawText(1, self.middleTextRow1, location1) #Max Event Today

        # Display max this year
        self.setTextColor(self.white)
        self.setTextSize(EARTHQUAKE_FONT_SIZE_SMALL)
        self.drawText(1, self.middleTextRow3, "Max Mag This Year Mag: " + str(mag2))
        self.setTextColor(self.white)
        self.setTextSize(EARTHQUAKE_FONT_SIZE_SMALL)
        self.drawText(1, self.middleTextRow4, location2) #Max Mag This Year 

    # Display depth
    def displayDepth(self, depth):
        # Convert kilometers to miles
        miles = depth / 1.609344
        milesStr = "Depth: {d:.2f} miles"
        self.setTextColor(self.white)
        self.setTextSize(EARTHQUAKE_FONT_SIZE_REG)
        self.drawRightJustifiedText(self.bottomTextRow, milesStr.format(d=miles))

    # Display Type *** Earthquake Type ***
    def displayEv(self, ev):
        ee = ev[0] if len(ev) > 0 else "n"
        ef = ev[1] if len(ev) > 1 else ""

        FIRST_CHAR = {
            "k": "Known ",
            "n": "Not Reported ",
            "s": "Suspected ",
            "u": "Unknown "
        }

        SECOND_CHAR = {
            "b": "Avalanche",
            "c": "Collapse",
            "d": "Industrial Explosion",
            "e": "Earthquake",
            "f": "Accidental Explosion",
            "g": "Controlled Explosion",
            "h": "Chemical Explosion",
            "i": "Triggered Event",
            "j": "Experimental Explosion",
            "k": "Fluid Injection",
            "l": "Landslide",
            "m": "Mining Explosion",
            "n": "Nuclear Explosion",
            "o": "Other",
            "p": "Plane/Train/Boat Crash",
            "q": "Fluid Extraction",
            "r": "Rock Burst",
            "s": "Sonic",
            "t": "Meteorite",
            "u": "Null",
            "v": "Volcanic Eruption",
            "w": "Reservoir Loading",
            "x": "Explosion",
            "y": "Hydroacoustic Event",
            "z": "Ice Quake",
            "": ""
        }

        typeStr = FIRST_CHAR.get(ee, "") + SECOND_CHAR.get(ef, "")
        self.setTextColor(self.white)

        e1 = FIRST_CHAR.get(ee, "")
        e2 = SECOND_CHAR.get(ef, "")
        aa = ''.join([e1, e2])
        self.setTextSize(EARTHQUAKE_FONT_SIZE_REG)
        self.drawCenteredText(self.topTextRow, aa)
        
    # Display number of events in DB
    def displayNumberOfEvents(self, num):
        self.setTextColor(self.white)
        self.setTextSize(EARTHQUAKE_FONT_SIZE_REG)
        self.drawText(5, self.bottomTextRow, "Earthquakes: " + str(num))

    # Display location with color from magnitude
    def displayLocation(self, location, mag):
        textColor = self.colorFromMag(mag)
        self.setTextSize(EARTHQUAKE_FONT_SIZE_REG)        
        self.drawCenteredText(self.bottomTextRow, location)
        

    # Trigger earthquake event animation
    def startAnimEQevent(self, animText):
        self.animCounter = ANIM_DURATION
        self.animText = animText

    # Needs to be called in the render loop. Will cause earthquake panel to animate for a while
    # if startAnimEQevent has been called.
    def animEQeventTick(self):
        if self.animCounter > 0:
            if (ANIM_DURATION - self.animCounter) % ANIM_FLASH_INTERVAL == 0:
                self.animTextOn = not self.animTextOn

            self.animCounter -= 1

            if self.animTextOn:
                self.setTextColor(self.white)
                self.setTextSize(EARTHQUAKE_FONT_SIZE_BIG)
                self.drawCenteredText(
                    int((self.screenHeight - EARTHQUAKE_FONT_SIZE_BIG) / 2),
                    self.animText
                )
                self.setTextColor(self.white)
                self.setTextSize(EARTHQUAKE_FONT_SIZE_REG)
        else:
            self.animTextOn = False
