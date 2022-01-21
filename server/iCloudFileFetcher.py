import pygame
from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudAPIResponseException
import logging
import face_recognition
import numpy as np
from threading import Thread
from random import randint, choice
from math import trunc
from PIL import Image
from os import environ, path, remove
from FileCache import FileCache
from pyicloud.services.photos import PhotoAlbum
from SlideshowInterface import SlideshowInterface

canConvertHeif = True
try:
    import pyheif
except ModuleNotFoundError:
    logging.error("HEIC Conversion is disabled")
    canConvertHeif = False

class iCloudFileFetcher:    
    api: PyiCloudService = None
    photos = dict()
    photosAlbum: PhotoAlbum = None
    workingDir = "/tmp/photos"
    screenSize = [0,0]
    resize: bool = True
    workerThread: Thread
    albumName: str
    finished: bool = False
    _status = "Waiting for iCloud Credentials"
    cache: FileCache = None
    ipcSocket = 5001
    slideshowInterface: SlideshowInterface = None

    def __init__(self, albumName: str, resize: bool, maxSize, workingDir, ipcSocket):
        logging.getLogger().setLevel(logging.INFO)
        logging.info("Initializing Collector with params: Album: " + str(albumName) + " Resize: " + str(resize) + " MaxSize: " + str(maxSize) + " WorkingDir: " + str(workingDir))
        self.finished = False
        self.albumName = albumName
        self.resize = resize
        self.workingDir = workingDir
        self.cache = FileCache(maxSize, workingDir)
        self.workerThread = Thread(target=self.worker)
        self.slideshowInterface = SlideshowInterface(ipcSocket)
        
        environ["DISPLAY"]=":0,0"
        pygame.display.init()
        screen = pygame.display.set_mode() # [0,0], pygame.OPENGL)
        self.screenSize = screen.get_size()
        pygame.display.quit()
        
    @property
    def status(self):
        return self._status

    @property
    def numPhotosInAlbum(self):
        if self.photosAlbum != None:
            return len(self.photosAlbum)
        else:
            return 0

    @property
    def numPhotosProcessed(self):
        return self.cache.numFiles

    @property
    def album(self):
        if self.albumName == "":
            return "All Photos"
        else:
            return self.albumName

    @property
    def cacheUsePercent(self):
        return self.cache.usePercent

    def setApi(self, api: PyiCloudService):
        self.api = api
        if api:
            logging.info("Got a valid API. Starting fetcher")
            self.workerThread.start()
        
    def sendSlideshowCommand(self, command, params):
        self.slideshowInterface.sendCommand(command, params)

    def setPhotosList(self):
        if not self.albumName:
            self.photosAlbum = self.api.photos.all
        else:
            albums = []
            for album in self.api.photos.albums:
                albums.append(album.title())

            if self.albumName not in albums:
                self.albumName = choice(albums)
            self.photosAlbum = len(self.api.photos.albums[self.albumName])
        logging.info(f"# Fotos in album \"{self.photosAlbum.title}\": {len(self.photosAlbum)}")

    def worker(self):
        logging.info("Started FileCache Worker Thread")
        self._status = "Fetching Photos"
        self.setPhotosList()
        finishedIndexes = []
        albumSize = len(self.photosAlbum)
        numFailedPhotos = 0

        while not self.finished:
            if (len(finishedIndexes) == albumSize):
                self.finished = True
                self._status = "Finished"
                break

            # main retrieval loop
            # pick a photo from the list, then convert it / resize it / save it
            # keep doing that. When we fill up the file cache, start deleting files
            photoIndex = randint(0, albumSize - 1)
            
            if photoIndex in finishedIndexes:
                continue

            # try fetching the photo
            try:
                for photo in self.photosAlbum.photo(photoIndex):
                    if not self.cache.isPhotoInCache(photo):
                        self.processPhoto(photo)
            except:
                logging.error("Could not fetch photo index " + str(photoIndex))
                numFailedPhotos = numFailedPhotos + 1
            finally:
                finishedIndexes.append(photoIndex)
                photoIndex = photoIndex + 1
                self.slideshowInterface.report("working", albumSize, self.cache.numFiles, numFailedPhotos)
        
        self.slideshowInterface.report("Finished", albumSize, self.cache.numFiles, numFailedPhotos)

    def processPhoto(self, photo):
        logging.info(f"Picked photo {photo.filename} for processing")
        split = path.splitext(photo.filename)

        if not self.usePhoto(photo, split[1]):
            logging.warning(f"Photo {photo.filename} is not usable")
            raise Exception("Photo is not usable")
    
        self._status = f"Examining photo {photo.filename}"
        # convert/download photo from icloud
        if (split[1] == ".HEIC"):
            self._status = f"Converting {photo.filename}"
            image = self._convert_heic(photo, split[0])
        else:
            self._status = f"Downloading {photo.filename}"
            image = self._download_jpeg(photo)

        if image == None:
            logging.error(f"Failed to download image {photo.filename}")
            raise Exception("Failed to download image")
        
        fileName = split[0] + ".JPEG"
        logging.info(f"Download successful.")
        if self.resize:
            image = self._scan_and_resize(image, fileName)
            # and now just save it
            logging.info(f"Resize of {fileName} successful.")
        fullPath = self.workingDir + "/" + fileName
        originalPath = self.workingDir + "/" + photo.filename
        logging.info(f"Saving {fullPath}.")
        image.save(fullPath, "JPEG")
        if (fullPath != originalPath):
            remove(originalPath)

        self.cache.addPhotoToCache(fileName, fullPath)

    def usePhoto(self, photo, extension) -> bool:
        extension = extension.upper()
        canUseFormat = extension == ".JPEG" or extension == ".JPG" or (canConvertHeif and extension == ".HEIC")
        return photo \
            and canUseFormat \
            and not self.cache.isPhotoInCache(photo) \
            and photo.dimensions[0] * photo.dimensions[1] < 15000000


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
        numFaces, startX, startY, endX, endY = self._get_face_bounding_rect(image, name)

        if numFaces == 0:
            logging.warning(f"No faces detected in {name}")
            # just thumbnail the image to screen size, don't attempt to intelligently
            # resize it
            image.thumbnail(self.screenSize)
            return image

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

        return len(face_locations), startX, startY, endX, endY

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