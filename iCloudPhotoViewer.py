from six.moves import input as raw_input
import pygame
from PIL import Image, ImageDraw, ImageFont
from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudAPIResponseException
from sys import exit
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

screenSaver = None
timeoutEvent : asyncio.Event = None

with open('config.json', 'r') as config:
    obj = json.load(config)
    logToFile = obj["logToFile"]

def cleanup():
    logging.critical("CLEANUP: Cleaning up...") 
    if screenSaver != None:
        screenSaver.cleanup()
    logging.info("CLEANUP: SettingTimeoutEvent")
    timeoutEvent.set()
    logging.info("CLEANUP: Exiting")
    _exit(0)

def keyboardInterruptHandler(signal, frame):
    cleanup()

def drawOnImage(image: Image, text: str, coordinates, font: ImageFont.FreeTypeFont, emboss: bool):
    draw = ImageDraw.Draw(image)
    if emboss:
        draw.text([coordinates[0] - 1, coordinates[0] - 1], text, fill=(000,000,000), font=font)
        draw.text([coordinates[0] + 1, coordinates[0] - 1], text, fill=(000,000,000), font=font)
        draw.text([coordinates[0] + 1, coordinates[0] + 1], text, fill=(000,000,000), font=font)
        draw.text([coordinates[0] - 1, coordinates[0] + 1], text, fill=(000,000,000), font=font)
    draw.text([coordinates[0] + 1, coordinates[0] + 1], text, fill=(255,222,000), font=font)
    
def authenticate(username, password) -> PyiCloudService:
    api = PyiCloudService(username, password)
    success = True
    if api.requires_2sa:
            logging.info("Two-step authentication required. Your trusted devices are:")
            devices = api.trusted_devices
            #print devices
            for i, device in enumerate(devices):
                print("  %s: %s" % (i, device.get('deviceName', "SMS to %s" % device.get('phoneNumber'))))
            device = devices[0]
            print (device)
            if not api.send_verification_code(device):
                logging.error("Failed to send verification code")
                exit(1)
            code = raw_input("Enter Verification Code: ")
            retry = 0
            success = api.validate_verification_code(device, code)
    if success:
        return api
    else:
        return None

async def main():
    signal.signal(signal.SIGINT, keyboardInterruptHandler)
  
    timeoutEvent = asyncio.Event()

    # fetch config data
    albumName = 'Frame2'
    username = ""
    password = ""

    with open('config.json', 'r') as config:
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
        if not username:
            username = obj["userName"]
        if not password:
            password = obj["password"]
        
    if not username:
        username = raw_input("Enter iCloud username:")
    if not password:
        password = getpass(f"Enter iCloud Password for {username}")
    authenticate(username, password)

    if timeout != None and timeout > 0:
        screenSaver = ScreenSaver(sensorPin, relayPin, timeout, timeoutEvent)

    retry = 0
    api = authenticate(username, password)
    while api == None and retry < 3:
        logging.warn(f"iCloud authentication failed, attempt = {retry}")
        sleep(5)
        api = authenticate(username, password)
        retry = retry + 1
    logging.info("iCloud Authentication OK !")
                     
    # Open a window on the screen
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

    cache = FileCache(maxSpace, workingDir, albumName, screen.get_size(), api, timeoutEvent, resizeImage)

    while(1):
        try:
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
                drawOnImage(img, f"{name}: {number}/{total}", [img.size[0] - 200, img.size[1] - 60], myfontSmall, True)

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
        except KeyboardInterrupt:
            cleanup()

if logToFile:
    logging.basicConfig(filename=f"{datetime.now().strftime('%Y-%m-%d--%H-%M')}.log", level=logging.INFO, format='%(asctime)s %(message)s')
else:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s: %(message)s')

asyncio.run(main())