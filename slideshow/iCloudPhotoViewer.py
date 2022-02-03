
import pygame
from PIL import Image, ImageDraw, ImageFont
from os import environ, path, _exit
import json
from ScreenSaver import ScreenSaver
import asyncio
import logging
from datetime import datetime
import os
import glob
from time import sleep
from random import choice
from CollectorInterface import CollectorInterface
import sys
import threading
import piexif

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

def drawStatus(image: Image, screenSize, collector: CollectorInterface, font: ImageFont.FreeTypeFont, emboss: bool):
    draw = drawOnImage(image, f'{collector.numProcessedPhotos}/{collector.numTotalPhotos}', (40, screenSize[1] - 20), font, emboss)
    size = draw.textsize("123", font=font)
    offset = max(size[1], 5)
 
    if collector.status:
        fill = "green"
    else:
        fill = "red"
    draw.ellipse((20, screenSize[1] - 20, 20 + offset, screenSize[1] - 20 + offset), fill=fill)

def fileName(fullPath):
    return path.basename(fullPath)

def nextPhoto(workingDir) -> Image:
    # return a random image from the ones already on disk
    try:
        photos = list(map(fileName, glob.glob(workingDir + "/*.JPEG")))
        if len(photos) == 0:
            logging.info('No photos found in library')
            return None, 0, 0, ""
     #   logging.info(f'Found {len(photos)} photos in library')

        photo = choice(photos)
      #  logging.info(f'Selected {photo}')
        img = Image.open(path.join(workingDir, photo))
        return img, len(photos), photos.index(photo), photo
    except Exception as e:
        logging.error(f'Error selecting photo: {e}')
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
        loggingPort = obj["loggingSocket"]
        showStatus = obj["showStatus"]
        autoLaunchCollector = obj["autoLaunchCollector"]

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

    # start the interface with the collector process
    collector = CollectorInterface(statusPort, loggingPort, screenSaver, autoLaunchCollector)

    while(True):
        try:
            for event in pygame.event.get():
                try:
                    if event.type == pygame.KEYDOWN and chr(event.key) == 'q':
                        return
                except ValueError:
                    continue
            img, total, number, name = nextPhoto(workingDir)
            if img == None:
                sleep(delaySecs)
                continue
           
            if adornPhotos:
                try:
                    exif_dict = piexif.load(img.info["exif"])
                    if "Exif" in exif_dict:
                        exif = exif_dict["Exif"]
                        if piexif.ExifIFD.DateTimeOriginal in exif:
                            dateTime = exif[piexif.ExifIFD.DateTimeOriginal]
                            dateTime = datetime.strptime(str(dateTime, 'utf-8'), '%Y:%m:%d %H:%M:%S')
                            dateTime = dateTime.strftime('%d %b %Y %H:%M')
                        else:
                            dateTime = ""
                        if piexif.ExifIFD.SubjectArea in exif:
                            numFaces = exif[piexif.ExifIFD.SubjectArea]
                        else:
                            numFaces = 0
                    else:
                        numFaces = 0
                        dateTime = ""
                except Exception as e:
                    logging.error(f"Could not read EXIF data: {e}")
                    numFaces = 0
                    dateTime = ""
                drawOnImage(img, f"{dateTime}, F: {numFaces}", [tsize[0] - 200, tsize[1] - 60], myfontLarge, True)
                drawStatus(img, tsize, collector, myfontSmall, True)

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
                collector.cleanup()
                cleanup()
            pygame.event.clear()
            collector.reportDisplayedPhoto(name)
            sleep(delaySecs)
        except Exception as e:
            logging.error(f"SLIDESHOW: Error: {e}. Continuing.")


if logToFile:
    filePath = path.join(path.dirname(path.realpath(__file__)), f"../logs/view_{datetime.now().strftime('%Y-%m-%d--%H-%M')}.log")
    logging.basicConfig(filename=filePath, level=logging.INFO, format='%(asctime)s %(message)s')
else:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s: %(message)s')


def handle_unhandled_exception(exc_type, exc_value, exc_traceback):
    """Handler for unhandled exceptions that will write to the logs"""
    if issubclass(exc_type, KeyboardInterrupt):
        # call the default excepthook saved at __excepthook__
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_unhandled_exception

def patch_threading_excepthook():
    """Installs our exception handler into the threading modules Thread object
    Inspired by https://bugs.python.org/issue1230540
    """
    old_init = threading.Thread.__init__
    def new_init(self, *args, **kwargs):
        old_init(self, *args, **kwargs)
        old_run = self.run
        def run_with_our_excepthook(*args, **kwargs):
            try:
                old_run(*args, **kwargs)
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                sys.excepthook(*sys.exc_info())
        self.run = run_with_our_excepthook
    threading.Thread.__init__ = new_init

patch_threading_excepthook()

if __name__ == '__main__':  # If the script that was run is this script (we have not been imported)
    slideshow()
    _exit(0)
