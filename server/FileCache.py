import shutil
import os
import time
from os import path
import logging

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
    def cacheUsagePercent(self):
        result = int(self.usedSpace / self.maxAvailableSpace * 100)
        logging.info(f'Cache usage is {result}%')
        return result

    def addPhotoToCache(self, file, fullPath):
        self.photos[file] = os.path.getmtime(fullPath)
        self.usedSpace += path.getsize(fullPath)
        logging.info(f'Added {file} to cache')
        self.cleanupCache()

    def cleanupCache(self):
        if self.maxAvailableSpace <= self.usedSpace:
            logging.info(f'Cleaning up {(self.usedSpace - self.maxAvailableSpace)/(1 << 10)}(kb) of space', )
            # sort dictionary by timestamp, and 
            # start removing oldest
            sortedPhotos = sorted(self.photos.items(), key = lambda item: item[1])

            # now start removing until we are good or we have only one photo left
            retry = 0
            while len(self.photos.keys) > 1 and self.maxAvailableSpace < self.usedSpace and retry < 10:
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

