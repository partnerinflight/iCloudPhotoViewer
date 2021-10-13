from six.moves import input as raw_input
import pygame
from PIL import Image, ImageDraw, ImageFont
from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudAPIResponseException
from sys import exit
from os import environ, system, path
from random import choice
from time import sleep
from getpass import getpass
import json
from FileCache import FileCache
from ScreenSaver import ScreenSaver
import signal
import asyncio
import logging

screenSaver: ScreenSaver = None
timeoutEvent = asyncio.Event()

def keyboardInterruptHandler(signal, frame):
    logging.critical(f"KeyboardInterrupt (ID: {signal}) has been caught. Cleaning up...") 
    if screenSaver != None:
        screenSaver.cleanup()
    print("CLEANUP: SettingTimeoutEvent")
    timeoutEvent.set()
    print("CLEANUP: Exiting")
    exit(0)

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
    # fetch config data
    albumName = 'Frame2'

    username = ""
    password = ""

    with open('config.json', 'r') as config:
        obj = json.load(config)
        album = obj["albumName"]
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

    cache = FileCache(maxSpace, workingDir)

    timeoutEvent.set()
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

    if not album:
        photos = api.photos.all
    else:
        albums = []
        for album in api.photos.albums:
            albums.append(album.title())

        if albumName not in albums:
            albumName = choice(albums)
        photos = api.photos.albums[albumName]

    photolist = []
    for photo in photos:
        photolist.append(photo)

    logging.info(f"# Fotos in album \"{albumName}\": {len(photolist)}")

    pygame.event.set_allowed(pygame.KEYDOWN)

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
                
            photo = choice(photolist)
            if photo and photo.dimensions[0] * photo.dimensions[1] < 15000000:
                print (photo.filename, photo.size, photo.dimensions)
                filename = await cache[photo]
                if not filename:
                    logging.error(f'Photo {photo.filename} could not be retrieved. Skipping.')
                    continue
                
                tsize = screen.get_size()
                img = Image.open(filename)
                if resizeImage:
                    size = max(tsize[0], tsize[1])
                    img.thumbnail([size, size])
                else:
                    img.thumbnail(screen.get_size())
                
                if adornPhotos:
                    drawOnImage(img, photo.name, [20, 20], myfontLarge, True)

                # convert to pygame image
                image = pygame.image.fromstring(img.tobytes(), img.size, img.mode)
                image = image.convert()

                # center and draw
                ssize = img.size
                screen.fill([0,0,0])
                screen.blit(image, [(tsize[0]-ssize[0])/2,(tsize[1]-ssize[1])/2])
                pygame.display.flip() # display update

                event = pygame.event.wait(delaySecs * 1000)
                if event != pygame.NOEVENT and event.type == pygame.KEYDOWN and chr(event.key) == 'q':
                    logging.critical("Got an exit command. Exiting...")
                    return
            else:
                logging.info("skipping large photo")
        except KeyboardInterrupt:
            logging.critical("Bye!")
            return

logging.basicConfig(level=logging.INFO)
asyncio.run(main())