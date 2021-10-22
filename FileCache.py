import shutil
import os
import time
from numpy.typing import _96Bit
from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudAPIResponseException
from os import path
from PIL import Image
import asyncio
import logging
import face_recognition
import numpy as np
from PIL import Image
from threading import Event, Thread
from random import choice
from math import trunc

canConvertHeif = True
try:
    import pyheif
except ModuleNotFoundError:
    canConvertHeif = False

class FileCache:
    freeSpace = 0 #how much disk free space is left
    photos = dict()
    workingDir = "/tmp/photos"
    usedSpace = 0
    finished = False
    workerThread: Thread
    albumName: str
    screenSize = [0,0]
    api: PyiCloudService
    blockEvent: asyncio.Event
    blocked: False
    resize: bool = True

    def __init__(self, maxSpace, workingDir, albumName, screenSize, api: PyiCloudService,
        blockEvent: Event, resize: bool) -> None:
        self.albumName = albumName
        self.screenSize = screenSize
        self.blockEvent = blockEvent
        self.api = api
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
        self.photos = dict.fromkeys(os.listdir(self.workingDir), time.time())        
        logging.info(f'Loaded {len(self.photos)} photos')

        for photo in self.photos:
            self.usedSpace += path.getsize(self.workingDir + "/" + photo)
        logging.info(f'Photo library currently occupies {self.usedSpace/(1<<30)}(GB)')

        # block until we have some photos to display
        if len(self.photos.keys()) > 0:
            self.blockEvent.set()
            self.blocked = False
        else:
            self.blockEvent.clear()
            self.blocked = True

        workerThread = Thread(target = self.worker)

        workerThread.start()
        self.cleanupCache()

    async def nextPhoto(self) -> Image:
        # return a random image from the ones already on disk

        if self.finished:
            return None
        
        # wait until there's something in the library
        await self.blockEvent.wait()

        # now return a random photo in the list
        photosList = list(self.photos.keys())
        logging.info(f"Next Image Requested, Library Size {len(photosList)} photos")

        photo = choice(photosList)
        self.photos[photo] = time.time()

        image = Image.open(self.workingDir + "/" + photo)

        return image, len(photosList), photosList.index(photo), photo

    def worker(self):
        logging.info("Started FileCache Worker Thread")

        # first let's get the full list of the photos
        if not self.albumName:
            logging.info("AlbumName not provided, using all photos")
            photos = self.api.photos.all
            logging.info(f'Fetched {len(photos)} photos')
        else:
            albums = []
            for album in self.api.photos.albums:
                albums.append(album.title())

            if self.albumName not in albums:
                self.albumName = choice(albums)
            photos = self.api.photos.albums[self.albumName]
            logging.info(f"# Fotos in album \"{self.albumName}\": {len(photos)}")

        photolist = []
        excludedList = []

        for photo in photos:
            photolist.append(photo)

        while not self.finished:
            # main retrieval loop
            # pick a photo from the list, then convert it / resize it / save it
            # keep doing that. When we fill up the file cache, start deleting files
            photo = choice(photolist)
            split = path.splitext(photo.filename)
            if photo in excludedList:
                continue

            if not self.usePhoto(photo, split[1], excludedList):
                excludedList.append(photo)
                continue
        
            logging.info(f"Examining photo {photo.filename}")
            # convert/download photo from icloud
            if (split[1] == ".HEIC"):
                logging.info(f"Converting {photo.filename}")
                image = self._convert_heic(photo, split[0])
            else:
                logging.info(f"Downloading {photo.filename}")
                image = self._download_jpeg(photo)

            if image == None:
                logging.error(f"Failed to download image {photo.filename}")
                continue
            
            fileName = split[0] + ".JPEG"
            logging.info(f"Download successful.")
            if self.resize:
                image = self._scan_and_resize(image, fileName)
                # and now just save it
                logging.info(f"Resize of {fileName} successful.")
            fullPath = self.workingDir + "/" + fileName
            logging.info(f"Saving {fullPath}.")
            image.save(fullPath, "JPEG")
            self.photos[fileName] = time.time()
            self.usedSpace += path.getsize(fullPath)

            logging.info(f"Total Local Storage Photos Before Cleanup: {len(photolist)}")
            # cleanup the cache. notice we'll never go down to zero photos; we leave one
            self.cleanupCache()
            if self.blocked:
                self.blocked = False
                self.blockEvent.set()
            logging.info(f"Total Local Storage Photos After Cleanup: {len(photolist)}")
 

    def usePhoto(self, photo, extension, exclusions) -> bool:
        canUseFormat = extension == ".JPG" or (canConvertHeif and extension == ".HEIC")
        return photo and photo not in self.photos and photo.dimensions[0] * photo.dimensions[1] < 15000000 and canUseFormat


    def _scan_and_resize(self, image:Image, name: str) -> Image:
        logging.info(f"Scanning and Resizing {name}")
        # first resize the image
        screenAspectRatio = self.screenSize[0] / self.screenSize[1]
        imageAspectRatio = image.size[0] / image.size[1]
        if imageAspectRatio > screenAspectRatio: #landscape
            percent = self.screenSize[1] / image.size[1]
        else:
            percent = self.screenSize[0] / image.size[0]

        newSize = (trunc(image.size[0] * percent), trunc(image.size[1] * percent))
        logging.info(f"Resizing {name} to {newSize}")
        image = image.resize(newSize)

        # now, do the face recognition block on that image
        startX, startY, endX, endY = self._get_face_bounding_rect(image, name)

        # now we simply need to see how to best crop the resulting image
        # we're already in screen coordinate frame
        if image.size[0] > self.screenSize[0]:
            # our width is exceeding screen. So let's crop
            if (endX - startX) > self.screenSize[0]:
                # oh oh. faces are bigger. we're going to have to 
                # resize the photo again
                percent = self.screenSize[0] / (endX - startX)
                image.thumbnail((image.size[0] * percent, image.size[1] * percent))
            
            # ok now faces at least fit. let's see how much we can expand
            # horizontally on both sides
            expansion = (self.screenSize[0] - (endX - startX)) / 2
            startX -= expansion
            endX += expansion
            if startX < 0:
                endX += abs(startX)
                startX = 0
            if endX > image.size[0]:
                startX = max(0, startX - (endX - image.size[0]))
                endX = image.size[0]
            logging.info(f"Cropping {name} to {startX}, {startY}, {endX}, {endY}")
            image = image.crop((startX, 0, endX, image.size[1]))

        if image.size[1] > self.screenSize[1]:
            # our height is exceeding screen. Let's crop height
            if (endY - startY) > self.screenSize[1]:
                # faces are bigger. resize the photo
                percent = self.screenSize[1] / (endY - startY)
                image.thumbnail([image.size[0] * percent, image.size[1] * percent])
            # ok now faces at least fit. let's see how much we can expand
            # horizontally on both sides
            expansion = (self.screenSize[1] - (endY - startY)) / 2
            startY -= expansion
            endY += expansion
            if startY < 0:
                endY += abs(startY)
                startY = 0
            if endY > image.size[0]:
                startY = max(0, startY - (endX - image.size[0]))
                endY = image.size[0]
            logging.info(f"Cropping {name} to {startX}, {startY}, {endX}, {endY}")
            image = image.crop((0, startY, image.size[0], endY))

        return image

    def _get_face_bounding_rect(self, image: Image, name: str):
        im = image.convert('RGB')
        face_locations = face_recognition.face_locations(np.array(im))

        logging.info(f"Found {len(face_locations)} faces in {name}")
        startX = image.size[0]
        endX = 0
        startY = image.size[1]
        endY = 0

        for location in face_locations:
            logging.info(f"Face Location: {location}")
            if location[0] < startY: # top
                startY = location[0]
            if location[1] > endX: # right
                endX = location[1]
            if location[2] > endY: # bottom
                endY = location[2]
            if location[3] < startX: # left
                startX = location[3]
        logging.info(f"Faces bounding box: {startX},{startY}--{endX}, {endY}")

        return startX, startY, endX, endY

    def _download_jpeg(self, photo) -> Image:
        try:
            fullPath = self.workingDir + "/" + photo.filename
            download = photo.download("medium")
            if not download:
                download = photo.download("original")

            if download:
                with open(fullPath, 'wb') as opened_file:
                    opened_file.write(download.raw.read())
                    opened_file.close()
                return Image.open(fullPath)
            else:
                return None
        except IOError as err:
            logging.error(err)
            return None
        except PyiCloudAPIResponseException as err:
            logging.error(err)
            return None

    def _convert_heic(self, photo, name) -> Image:
        if not canConvertHeif:
            logging.error('HEIF library not loaded. Conversion failed')
            return None
            
        try:
            download = photo.download()
            if download:
                with open("photo.HEIC", 'wb') as opened_file:
                    opened_file.write(download.raw.read())
                    opened_file.close()
            heif = pyheif.read("photo.HEIC")
            img = Image.frombytes(
                heif.mode, 
                heif.size, 
                heif.data, 
                "raw", 
                heif.mode, 
                heif.stride)
            return img
        except IOError as err:
            logging.error(err)
            return None
        except PyiCloudAPIResponseException as err:
            logging.error(err)
            return None

    def cleanup(self):
        self.finished = True
        self.workerThread.join()

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

