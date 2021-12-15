import shutil
import os
import time
from os import path
from PIL import Image
import asyncio
import logging
from PIL import Image
from random import choice

class FileCache:
    freeSpace = 0 #how much disk free space is left
    photos = dict()
    workingDir = "/tmp/photos"
    usedSpace = 0
    finished = False

    screenSize = [0,0]
    blockEvent: asyncio.Event
    blocked: False
    resize: bool = True

    def __init__(self, maxSpace, workingDir, albumName, screenSize, blockEvent: asyncio.Event, resize: bool) -> None:
        self.albumName = albumName
        self.screenSize = screenSize
        self.blockEvent = blockEvent
        self.resize = resize
        total, used, free = shutil.disk_usage("/")
        self.freeSpace = min(free - 2, maxSpace * (1<<30))
        logging.info(f'File Cache using {self.freeSpace / (1<<30)}(GB) of space' )

        if workingDir:
            self.workingDir = workingDir

        checkfolder = path.isdir(self.workingDir)
        if not checkfolder:
            os.makedirs(self.workingDir)

        # initialize the photos dict
        self.loadPhotos()

        # block until we have some photos to display
        if len(self.photos.keys()) > 0:
            self.blockEvent.set()
            self.blocked = False
        else:
            self.blockEvent.clear()
            self.blocked = True
        self.cleanupCache()

    def loadPhotos(self):
        self.photos = dict.fromkeys(os.listdir(self.workingDir), time.time())        
        logging.info(f'Loaded {len(self.photos)} photos')

        for photo in self.photos:
            self.usedSpace += path.getsize(self.workingDir + "/" + photo)
        logging.info(f'Photo library currently occupies {self.usedSpace/(1<<30)}(GB)')

    async def nextPhoto(self) -> Image:
        # return a random image from the ones already on disk

        if self.finished:
            return None
        
        logging.info("Waiting for next photo")

        # wait until there's something in the library
        await self.blockEvent.wait()

        self.loadPhotos()   

        # now return a random photo in the list
        photosList = list(self.photos.keys())
        logging.info(f"Returning, Library Size {len(photosList)} photos")

        photo = choice(photosList)
        self.photos[photo] = time.time()

        image = Image.open(self.workingDir + "/" + photo)

        return image, len(photosList), photosList.index(photo), photo

    def cleanupCache(self):
        if self.freeSpace < self.usedSpace:
            logging.info(f'Cleaning up {(self.usedSpace - self.freeSpace)/(1 << 10)}(kb) of space', )
            # sort dictionary by timestamp, and 
            # start removing oldest
            sortedPhotos = sorted(self.photos.items(), key = lambda item: item[1])

            # now start removing until we are good or we have only one photo left
            retry = 0
            while len(self.photos.keys) > 1 and self.freeSpace < self.usedSpace and retry < 10:
                try:
                    file = sortedPhotos[0][0]
                    fullFilePath = self.workingDir + "/" + file
                    self.usedSpace -= path.getsize(fullFilePath)
                    logging.info(f'Cleanup deleting {fullFilePath}')
                    os.unlink(fullFilePath)
                    self.photos.pop(file)
                except FileNotFoundError:
                    retry = retry + 1
                    logging.error(f'Unable to delete {fullFilePath}: not found')
                    continue
                except PermissionError:
                    logging.error(f'Unable to delete {fullFilePath}: permissions')
                    retry = retry + 1
                    continue

