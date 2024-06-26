import shutil
import os
from os import path
import logging

from Downloader import Photo

class FileCache:
    maxAvailableSpace = 0
    photos = dict()
    workingDir = "/tmp/photos"
    usedSpace = 0
    finished = False

    def __init__(self, maxSpace, workingDir) -> None:
        logging.getLogger().setLevel(logging.INFO)
        total, used, free = shutil.disk_usage("/")
        self.maxAvailableSpace = min(free - (1<<30), maxSpace * (1<<30))
        logging.info(f'File Cache can use up to {self.maxAvailableSpace / (1<<30)}(GB) of space' )

        if workingDir:
            self.workingDir = workingDir

        checkfolder = path.isdir(self.workingDir)
        if not checkfolder:
            os.makedirs(self.workingDir)

        # initialize the photos dict
        self.loadPhotos()
        self.cleanupCache()

    def deletePhoto(self, photo: Photo):
        fullFilePath = self.workingDir + "/" + photo.id
        self.usedSpace -= path.getsize(fullFilePath)
        logging.info(f'Deleting {fullFilePath}')
        os.unlink(fullFilePath)
        self.photos.pop(photo)
        self.cleanupCache()

    def loadPhotos(self):
        for file in os.listdir(self.workingDir):
            fullFilePath = os.path.join(self.workingDir, file)
            if path.isfile(fullFilePath):
                self.photos[file] = os.path.getmtime(fullFilePath)
                self.usedSpace += path.getsize(fullFilePath)

    def isPhotoInCache(self, file):
        return file in self.photos.keys()

    @property
    def numFiles(self):
        return len(self.photos.keys())
        
    @property
    def cacheUsePercent(self):
        if self.maxAvailableSpace > 0:
            result = round((float(self.usedSpace) / float(self.maxAvailableSpace)) * 100.0, 2)
            logging.info(f'Used: {self.usedSpace}, Max: {self.maxAvailableSpace}, Cache usage is {result}%')
        else:
            result = 100
        return result

    def addPhotoToCache(self, photo, fullPath):
        self.photos[photo.id] = os.path.getmtime(fullPath)
        self.usedSpace += path.getsize(fullPath)
        logging.info(f'Added {photo.id} to cache')
        self.cleanupCache()

    def cleanupCache(self):
        if self.maxAvailableSpace <= self.usedSpace:
            logging.info(f'Cleaning up {(self.usedSpace - self.maxAvailableSpace)/(1 << 10)}(kb) of space', )
            # sort dictionary by timestamp, and 
            # start removing oldest
            sortedPhotos = sorted(self.photos.items(), key = lambda item: item[1])

            # now start removing until we are good or we have only one photo left
            retry = 0
            while len(self.photos.keys()) > 1 and self.maxAvailableSpace < self.usedSpace and retry < 10:
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

