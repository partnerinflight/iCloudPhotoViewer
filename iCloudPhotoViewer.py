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

def keyboardInterruptHandler(signal, frame):
    logging.critical("KeyboardInterrupt (ID: {}) has been caught. Cleaning up...".format(signal)) 
    exit(0)

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
        timeout = obj["screenTimeout"]
        if not username:
            username = obj["userName"]
        if not password:
            password = obj["password"]

    if not username:
        username = raw_input("Enter iCloud username:")
    if not password:
        password = getpass("Enter iCloud Password for %s: "%username)

    api = PyiCloudService(username, password)
    cache = FileCache(maxSpace, workingDir)

    timeoutEvent = asyncio.Event()
    timeoutEvent.set()
    if timeout != None and timeout > 0:
        screenSaver = ScreenSaver(sensorPin, relayPin, timeout, timeoutEvent)

    if api.requires_2sa:
        logging.info("Two-step authentication required. Your trusted devices are:")
        devices = api.trusted_devices
        #print devices
        for i, device in enumerate(devices):
            logging.info ("  %s: %s" % (i, device.get('deviceName', "SMS to %s" % device.get('phoneNumber'))))
        device = devices[0]
        print (device)
        if not api.send_verification_code(device):
            logging.error("Failed to send verification code")
            exit(1)
        code = raw_input("Enter Verification Code: ")
        retry = 0
        success = False
        while retry < 5 and success == False:
            sleep(1)
            success = api.validate_verification_code(device, code)
            retry = retry + 1
        
        if not success:
            logging.critical("Failed to verify verification code")
            exit(1)

    logging.info("iCloud Authentication OK !")
                    
  
    # Open a window on the screen
    screen = pygame.display.set_mode() # [0,0], pygame.OPENGL)
    pygame.mouse.set_visible(0)
    logging.info(pygame.display.get_driver())
    logging.info(pygame.display.Info())

    if adornPhotos:
        myfont = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSans.ttf", 25)

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

    logging.info("# Fotos in album \"%s\": %d"%(albumName,len(photolist)))

    pygame.event.set_allowed(pygame.KEYDOWN)

    while(1):
        try:
            # first wait for our timeout, if any. i.e. if the screen is blanking
            # then there's no point doing further processing.
            await timeoutEvent.wait()
            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN and chr(event.key) == 'q':
                    exit(0)
                
            photo = choice(photolist)
            if photo and photo.dimensions[0] * photo.dimensions[1] < 15000000:
                print (photo.filename, photo.size, photo.dimensions)
                filename = await cache[photo]
                if not filename:
                    logging.error(f'Photo {photo.filename} could not be retrieved. Skipping.')
                    continue
                img = Image.open(filename)
                img.thumbnail(screen.get_size())
                draw = ImageDraw.Draw(img)
                if adornPhotos:
                    draw.text([19,19], albumName, fill=(000,000,000), font=myfont)
                    draw.text([21,19], albumName, fill=(000,000,000), font=myfont)
                    draw.text([21,21], albumName, fill=(000,000,000), font=myfont)
                    draw.text([19,21], albumName, fill=(000,000,000), font=myfont)
                    draw.text([20,20], albumName, fill=(255,222,000), font=myfont)

                # convert to pygame image
                image = pygame.image.fromstring(img.tobytes(), img.size, img.mode)
                image = image.convert()

                # center and draw
                ssize = img.size
                tsize = screen.get_size()
                screen.fill([0,0,0])
                screen.blit(image, [(tsize[0]-ssize[0])/2,(tsize[1]-ssize[1])/2])
                pygame.display.flip() # display update

                sleep(delaySecs)
            else:
                logging.info("skipping large photo")
        except KeyboardInterrupt:
            logging.critical("Bye!")
            exit(0)

logging.basicConfig(level=logging.INFO)
asyncio.run(main())