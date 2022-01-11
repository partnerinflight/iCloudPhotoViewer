
import pygame
from PIL import Image, ImageDraw, ImageFont
from os import environ, path, _exit
import json
from ScreenSaver import ScreenSaver
import asyncio
import logging
from datetime import datetime
import os

from random import choice

screenSaver = None
timeoutEvent : asyncio.Event = None

configPath = path.join(path.dirname(path.realpath(__file__)), "../config.json")
with open(configPath, 'r') as config:
    obj = json.load(config)
    logToFile = obj["logToFile"]

def cleanup():
    global timeoutEvent
    logging.critical("CLEANUP: Cleaning up...") 
    if screenSaver != None:
        screenSaver.cleanup()
    logging.info("CLEANUP: SettingTimeoutEvent")
    timeoutEvent.set()
    logging.info("CLEANUP: Exiting")
    _exit(0)

def drawOnImage(image: Image, text: str, coordinates, font: ImageFont.FreeTypeFont, emboss: bool):
    draw = ImageDraw.Draw(image)
    if emboss:
        draw.text([coordinates[0] - 1, coordinates[0] - 1], text, fill=(000,000,000), font=font)
        draw.text([coordinates[0] + 1, coordinates[0] - 1], text, fill=(000,000,000), font=font)
        draw.text([coordinates[0] + 1, coordinates[0] + 1], text, fill=(000,000,000), font=font)
        draw.text([coordinates[0] - 1, coordinates[0] + 1], text, fill=(000,000,000), font=font)
    draw.text([coordinates[0] + 1, coordinates[0] + 1], text, fill=(255,222,000), font=font)

def nextPhoto(workingDir) -> Image:
    # return a random image from the ones already on disk
    photos = os.listdir(workingDir)
    if len(photos) == 0:
        logging.info('No photos found in library')
        return None
    logging.info(f'Found {len(photos)} photos in library')

    photo = choice(photos)
    logging.info(f'Selected {photo}')
    img = Image.open(path.join(workingDir, photo))
    return img, len(photos), photos.index(photo), photo

def slideshow():
    global timeoutEvent  
    timeoutEvent = asyncio.Event()

    # fetch config data
    with open(configPath, 'r') as config:
        obj = json.load(config)
        workingDir = obj["workingDir"]
        adornPhotos = obj["adornPhotos"]
        delaySecs = obj["delaySecs"]
        sensorPin = obj["sensorPin"]
        relayPin = obj["relayPin"]
        timeout = obj["screenTimeout"]
        skipDisplay = obj["skipDisplay"]

    if timeout != None and timeout > 0:
        screenSaver = ScreenSaver(sensorPin, relayPin, timeout, timeoutEvent)
                 
    # Open a window on the screen
    if skipDisplay:
        return

    environ["DISPLAY"]=":0,0"
    pygame.display.init()
    screen = pygame.display.set_mode() # [0,0], pygame.OPENGL)
    pygame.mouse.set_visible(0)
    logging.info(pygame.display.get_driver())
    logging.info(pygame.display.Info())

    if adornPhotos:
        myfontLarge = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSans.ttf", 25)
        myfontSmall = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSans.ttf", 14)
 
    pygame.event.set_allowed(pygame.KEYDOWN)

    logging.info("SLIDESHOW: Starting slideshow")

    while(1):
        for event in pygame.event.get():
            try:
                if event.type == pygame.KEYDOWN and chr(event.key) == 'q':
                    return
            except ValueError:
                continue
        img, total, number, name = nextPhoto(workingDir)

        if adornPhotos:
            logging.info(f"Drawing {name} on the image")
            drawOnImage(img, f"{name}: {number}/{total}", [img.size[0] - 200, img.size[1] - 60], myfontLarge, True)

        # convert to pygame image
        image = pygame.image.fromstring(img.tobytes(), img.size, img.mode)
        image = image.convert()

        # center and draw
        screen.fill([255,0,0])
        screen.blit(image, [0,0])
        pygame.display.flip() # display update
        event = pygame.event.wait(delaySecs * 1000)
        if event != pygame.NOEVENT and event.type == pygame.KEYDOWN:
            cleanup()

if logToFile:
    logging.basicConfig(filename=f"view_{datetime.now().strftime('%Y-%m-%d--%H-%M')}.log", level=logging.INFO, format='%(asctime)s %(message)s')
else:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s: %(message)s')

if __name__ == '__main__':  # If the script that was run is this script (we have not been imported)
    slideshow()
    _exit(0)
