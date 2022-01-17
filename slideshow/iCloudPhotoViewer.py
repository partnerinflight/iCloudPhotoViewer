
import pygame
from PIL import Image, ImageDraw, ImageFont
from os import environ, path, _exit
import json
from ScreenSaver import ScreenSaver
import asyncio
import logging
from datetime import datetime
import os
from time import sleep
from random import choice
from StatusIngester import StatusIngester

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
    size = draw.textsize(text, font=font)
    coordinates = list(coordinates)
    if coordinates[0] + size[0] > image.size[0]:
        coordinates[0] = image.size[0] - size[0] - 20
    if coordinates[1] + size[1] > image.size[1]:
        coordinates[1] = image.size[1] - size[1] - 20

    if emboss:
        draw.text([coordinates[0] - 1, coordinates[1] - 1], text, fill=(000,000,000), font=font)
        draw.text([coordinates[0] + 1, coordinates[1] - 1], text, fill=(000,000,000), font=font)
        draw.text([coordinates[0] + 1, coordinates[1] + 1], text, fill=(000,000,000), font=font)
        draw.text([coordinates[0] - 1, coordinates[1] + 1], text, fill=(000,000,000), font=font)
    draw.text([coordinates[0], coordinates[1]], text, fill=(255,222,000), font=font)
    return draw

def drawStatus(image: Image, screenSize, status: StatusIngester, font: ImageFont.FreeTypeFont, emboss: bool):
    draw = drawOnImage(image, f'{status.numProcessedPhotos}/{status.numTotalPhotos}', (40, screenSize[1] - 20), font, emboss)
    size = draw.textsize("123", font=font)
    offset = max(size[1], 5)
 
    if status.status:
        fill = "green"
    else:
        fill = "red"
    draw.ellipse((20, screenSize[1] - 20, 20 + offset, screenSize[1] - 20 + offset), fill=fill)

def nextPhoto(workingDir) -> Image:
    # return a random image from the ones already on disk
    try:
        photos = os.listdir(workingDir)
        if len(photos) == 0:
            logging.info('No photos found in library')
            return None, 0, 0, ""
        logging.info(f'Found {len(photos)} photos in library')

        photo = choice(photos)
        logging.info(f'Selected {photo}')
        img = Image.open(path.join(workingDir, photo))
        return img, len(photos), photos.index(photo), photo
    except:
        return None, 0, 0, ""

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
        statusPort = obj["ipcSocket"]
        showStatus = obj["showStatus"]
        autoLaunchCollector = obj["autoLaunchCollector"]

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
    tsize = screen.get_size()
    if adornPhotos:
        try:
            myfontLarge = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSans.ttf", 25)
            myfontSmall = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSans.ttf", 14)
        except:
            logging.error("Could not load fonts")
            myfontLarge = ImageFont.truetype("arial.ttf", 25)
            myfontSmall = ImageFont.truetype("arial.ttf", 14)

    pygame.event.set_allowed(pygame.KEYDOWN)

    logging.info("SLIDESHOW: Starting slideshow")

    # start the status ingester
    if showStatus:
        statusIngester = StatusIngester(statusPort, autoLaunchCollector)

    while(True):
        for event in pygame.event.get():
            try:
                if event.type == pygame.KEYDOWN and chr(event.key) == 'q':
                    return
            except ValueError:
                continue
        img, total, number, name = nextPhoto(workingDir)
        if img == None:
            continue

        if adornPhotos:
            logging.info(f"Drawing {name} on the image")
            drawOnImage(img, f"{name}: {number}/{total}", [tsize[0] - 200, tsize[1] - 60], myfontLarge, True)
            drawStatus(img, tsize, statusIngester, myfontSmall, True)

        # convert to pygame image
        image = pygame.image.fromstring(img.tobytes(), img.size, img.mode)
        image = image.convert()

        # center and draw
        screen.fill([0,0,0])
        ssize = img.size
        screen.blit(image, [(tsize[0]-ssize[0])/2,(tsize[1]-ssize[1])/2])
        pygame.display.flip() # display update
        event = pygame.event.wait(100)
        if event != pygame.NOEVENT and event.type == pygame.KEYDOWN:
            statusIngester.cleanup()
            cleanup()
        pygame.event.clear()
        sleep(delaySecs)

if logToFile:
    logging.basicConfig(filename=f"view_{datetime.now().strftime('%Y-%m-%d--%H-%M')}.log", level=logging.INFO, format='%(asctime)s %(message)s')
else:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s: %(message)s')

if __name__ == '__main__':  # If the script that was run is this script (we have not been imported)
    slideshow()
    _exit(0)
