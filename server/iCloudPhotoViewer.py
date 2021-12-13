
import pygame
from PIL import Image, ImageDraw, ImageFont
from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudAPIResponseException
from sys import exit, argv, stderr
from os import environ, system, path, _exit
from random import choice
from time import sleep
from getpass import getpass
import json
from FileCache import FileCache
from ScreenSaver import ScreenSaver
import signal
import asyncio
import logging
from datetime import datetime
from WebFrontend import webApp, frontEnd
from iCloudFileFetcher import iCloudFileFetcher
import threading

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

async def slideshow():
    global timeoutEvent  
    timeoutEvent = asyncio.Event()

    # fetch config data
    albumName = ""
    username = ""
    password = ""

    with open(configPath, 'r') as config:
        obj = json.load(config)
        albumName = obj["albumName"]
        workingDir = obj["workingDir"]
        maxSpace = obj["maxSpaceGb"]
        adornPhotos = obj["adornPhotos"]
        delaySecs = obj["delaySecs"]
        sensorPin = obj["sensorPin"]
        relayPin = obj["relayPin"]
        resizeImage = obj["resizeImage"]
        timeout = obj["screenTimeout"]
        skipDisplay = obj["skipDisplay"]
        if not username:
            username = obj["userName"]
        if not password:
            password = obj["password"]
        
    cloudFetcher = iCloudFileFetcher(albumName, resizeImage)

    global frontEnd
    frontEnd.setFetcher(cloudFetcher)
    frontEnd.setCredentials(username, password)

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
    cloudFetcher.setScreenSize(pygame.display.Info().current_w, pygame.display.Info().current_h)

    if adornPhotos:
        myfontLarge = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSans.ttf", 25)
        myfontSmall = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSans.ttf", 14)
 
    pygame.event.set_allowed(pygame.KEYDOWN)

    cache = FileCache(maxSpace, workingDir, albumName, screen.get_size(), timeoutEvent, resizeImage)

    while(1):
       # try:
        # first wait for our timeout, if any. i.e. if the screen is blanking
        # then there's no point doing further processing.
        await timeoutEvent.wait()
        for event in pygame.event.get():
            try:
                if event.type == pygame.KEYDOWN and chr(event.key) == 'q':
                    return
            except ValueError:
                continue
        img, total, number, name = await cache.nextPhoto()

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
        # except KeyboardInterrupt:
        #     cleanup()

def runWebApp():
    logging.info("Starting web app")
    webApp.run(use_reloader=False, threaded=True)

async def main():
    mainTask = asyncio.create_task(slideshow())
    await asyncio.gather(asyncio.to_thread(runWebApp), mainTask)

if logToFile:
    logging.basicConfig(filename=f"{datetime.now().strftime('%Y-%m-%d--%H-%M')}.log", level=logging.INFO, format='%(asctime)s %(message)s')
else:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s: %(message)s')

if __name__ == '__main__':  # If the script that was run is this script (we have not been imported)
    host_name = "0.0.0.0"
    port = 5001
    threading.Thread(target=lambda: webApp.run(host=host_name, port=port, use_reloader=False)).start()
    asyncio.run(slideshow())
