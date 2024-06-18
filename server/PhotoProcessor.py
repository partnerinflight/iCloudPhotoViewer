import pygame
import logging
import face_recognition
import numpy as np
from threading import Thread
from random import choices, randint, choice
from math import trunc
from PIL import Image
from os import environ, path, remove
from FileCache import FileCache
from pyicloud.services.photos import PhotoAlbum
from SlideshowInterface import SlideshowInterface
import time
import piexif

from Downloader import STATUS_CHANGED_EVENT, Downloader, Photo, Status
from Constants import CONFIG_ALBUM_NAME, CONFIG_IPC_SOCKET, CONFIG_KEEP_ORIGINAL_FILES, CONFIG_MAXSIZE, CONFIG_RECENCY_BIAS, CONFIG_RESIZE_IMAGE, CONFIG_STATUS_SOCKET, CONFIG_WORKING_DIR

canConvertHeif = True
try:
    import pyheif
except ModuleNotFoundError:
    logging.error("HEIC Conversion is disabled")
    canConvertHeif = False

zeroth_ifd = {
    piexif.ImageIFD.Artist: u"PhotoFrame",
    piexif.ImageIFD.XResolution: (96, 1),
    piexif.ImageIFD.YResolution: (96, 1),
    piexif.ImageIFD.Software: u"piexif"
    }

class PhotoProcessor:    
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
    keepOriginalFiles: bool = False
    rejectedPhotos = []
    
    def __init__(self, downloader: Downloader, config):
        logging.getLogger().setLevel(logging.INFO)
        self.albumName = config[CONFIG_ALBUM_NAME]
        self.recencyBias = config[CONFIG_RECENCY_BIAS]
        resize = config[CONFIG_RESIZE_IMAGE]
        maxSize = config[CONFIG_MAXSIZE]
        workingDir = config[CONFIG_WORKING_DIR]
        ipcSocket = config[CONFIG_IPC_SOCKET]
        statusPort = config[CONFIG_STATUS_SOCKET]
        self.numPhotosInAlbum = 0
        if CONFIG_KEEP_ORIGINAL_FILES in config:
            keepOriginalFiles = config[CONFIG_KEEP_ORIGINAL_FILES]
        else:
            keepOriginalFiles = False
    
        logging.info("Initializing Collector with params: Album: " + str(self.albumName) + " Resize: " + str(resize) + " MaxSize: " + str(maxSize) + " WorkingDir: " + str(workingDir))
        self.finished = False
        self.resize = resize
        self.workingDir = workingDir
        self.cache = FileCache(maxSize, workingDir)
        self.workerThread = Thread(target=self.worker)
        self.slideshowInterface = SlideshowInterface(ipcSocket, statusPort)
        self.keepOriginalFiles = keepOriginalFiles
        self.downloader = downloader
        self.downloader.on(STATUS_CHANGED_EVENT, lambda status: self.onDownloaderStatusChanged(status))
        #pull rejected photos from a text file
        if path.exists("rejected.txt"):
            with open("rejected.txt", "r") as f:
                self.rejectedPhotos = f.read().splitlines()

        environ["DISPLAY"]=":0,0"
        pygame.display.init()
        screen = pygame.display.set_mode() # [0,0], pygame.OPENGL)
        self.screenSize = screen.get_size()
        pygame.display.quit()

    def onDownloaderStatusChanged(self, status):
        if status == Status.LoggedIn:
            self.workerThread.start()

    @property
    def displayedList(self):
        return self.slideshowInterface.displayedPhotos

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
        return self.cache.cacheUsePercent
      
    def deletePhoto(self, photo: str):
        # Here we want to delete the photo and add it to the list
        # of photos not to be fetched.
        self.cache.deletePhoto(photo)
        self.rejectedPhotos.append(photo)
        self.slideshowInterface.displayedPhotos = [value for value in self.slideshowInterface.displayedPhotos if value != photo]

    def sendSlideshowCommand(self, command, params):
        self.slideshowInterface.sendCommand(command, params)

    def worker(self):
        logging.info("Started FileCache Worker Thread")
        self._status = "Fetching Photos"
        finishedIds = []
        numFailedPhotos = 0
        cachedBuckets = {}

        # get the timeline buckets we have to work with
        buckets = self.downloader.getTimelineBuckets()

        # count up the total number of photos, which is the sum of 'count' entries in the buckets
        self.numPhotosInAlbum = 0
        for bucket in buckets:
            self.numPhotosInAlbum += bucket["count"]

        weights = [(i / len(buckets))**(1 - self.recencyBias) for i in range(len(buckets))]
        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]

        while not self.finished:
            if (len(finishedIds) == self.numPhotosInAlbum):
                self.finished = True
                self._status = "Finished"
                break

            # main retrieval loop
            # pick a random timeline bucket from the list (with recency bias). Then get the photos from that bucket
            # and store them in a cache dictionary
            # Determine weights based on recency preference
            # Download photos based on weights
            bucket = choices(buckets, weights=normalized_weights)
            
            # if we've already cached this bucket, skip retrieval
            bucketName = bucket[0]["timeBucket"]

            if bucketName not in cachedBuckets:
                photos = self.downloader.getPhotosForBucket(bucketName)
                cachedBuckets[bucketName] = photos

            # pick a random photo from the bucket
            photoIndex = randint(0, len(cachedBuckets[bucketName]) - 1)

            if photoIndex in finishedIds:
                continue

            # delay based on # of photos in the library
            # this is to prevent the app from getting throttled by iCloud
            # when we're downloading a lot of photos
            delay = trunc(self.cache.numFiles / 100)
            if delay < 1:
                delay = 1
            delay = randint(delay, delay * 2)
            logging.info(f"Delaying {delay} seconds")
            time.sleep(delay)

            # try fetching the photo
            try:
                photo = cachedBuckets[bucketName][photoIndex]
                if not self.cache.isPhotoInCache(photo):
                    self.processPhoto(photo)
            except Exception as e:
                logging.error("Could not fetch photo: " + photo.filename + ": " + str(e))
                numFailedPhotos = numFailedPhotos + 1
            finally:
                finishedIds.append(photo.id)
                self.slideshowInterface.report("working", self.numPhotosInAlbum, self.cache.numFiles, numFailedPhotos)
        
        self.slideshowInterface.report("Finished", self.numPhotosInAlbum, self.cache.numFiles, numFailedPhotos)

    def processPhoto(self, photo: Photo):
        logging.info(f"Picked photo {photo.filename} for processing")
        split = path.splitext(photo.filename)

        if not self.usePhoto(photo, split[1]):
            logging.warning(f"Photo {photo.filename} is not usable")
            raise Exception("Photo is not usable")

        self._status = f"Examining photo {photo.filename}"
        self._status = f"Downloading {photo.filename}"
        image = photo.download(self._get_temp_path(photo.filename))

        if image == None:
            logging.error(f"Failed to download image {photo.filename}")
            raise Exception("Failed to download image")
        
        exif_dict = piexif.load(image.info["exif"])

        fileName = split[0] + ".JPEG"
        logging.info(f"Download successful.")
        numFaces = 0
        if self.resize:
            image, numFaces = self._scan_and_resize(image, fileName)
            # and now just save it
            logging.info(f"Resize of {fileName} successful.")
        fullPath = self.workingDir + "/" + fileName
        logging.info(f"Saving {fileName} to {fullPath}")
        originalPath = self._get_temp_path(photo.filename)
        logging.info(f"Saving {fullPath}.")
        # create the exif tag for the image
        exif_dict["Exif"][piexif.ExifIFD.SubjectArea] = numFaces
        date = photo.created
        bDate = bytes(date, "utf-8")
        exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = bDate
        exif_bytes = piexif.dump(exif_dict)
        image.save(fullPath, "JPEG", exif=exif_bytes)
        if not self.keepOriginalFiles:
            remove(originalPath)

        self.cache.addPhotoToCache(photo, fullPath)

    def usePhoto(self, photo, extension) -> bool:
        extension = extension.upper()
        #canUseFormat = extension == ".JPEG" or extension == ".JPG" or (canConvertHeif and extension == ".HEIC")
        return photo \
            and not self.cache.isPhotoInCache(photo) \
            and photo.id not in self.rejectedPhotos \
            and photo.dimensions[0] > 500 \
            and photo.dimensions[1] > 500 \
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
            return image, 0

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

        return image, numFaces

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

    def _get_temp_path(self, filename) -> str:
        return "/tmp/photos/" + filename

    def _convert_heic(self, photo) -> Image:
        if not canConvertHeif:
            logging.error('HEIF library not loaded. Conversion failed')
            return None
            
        try:
            download = photo.download(self._get_temp_path(photo.filename))
            if not download:
                logging.error('Failed to download HEIC photo')
                return None
            
            fullPath = self._get_temp_path(photo.filename)
            if download:
                with open(fullPath, 'wb') as opened_file:
                    opened_file.write(download.raw.read())
                    opened_file.close()
            heif = pyheif.read(fullPath)
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

    def cleanup(self):
        self.finished = True
        self.workerThread.join()
        # write the rejected photos list back to rejected file
        with open("rejected.txt", 'w') as f:
            for photo in self.rejectedPhotos:
                f.write(photo + "\n")