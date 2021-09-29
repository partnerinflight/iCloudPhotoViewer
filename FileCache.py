import shutil
import os
import time
from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudAPIResponseException
from os import path
from PIL import Image
import asyncio
import logging

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

    def __init__(self, maxSpace, workingDir) -> None:
        total, used, free = shutil.disk_usage("/")
        self.freeSpace = min(free - 2, maxSpace<<30)
        logging.info(f'File Cache using {self.freespace}(GB) of space' )

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

        self.cleanup()

    def _convert_heic(self, fullPath, photo):
        logging.info(f'Converting {fullPath}')

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
            img.save(fullPath, "JPEG")
        except IOError as err:
            logging.error(err)
            return None
        except PyiCloudAPIResponseException as err:
            logging.error(err)
            return None

    async def __getitem__(self, photo): 
        #try to return filename from cache given photo name. if it's not there, then 
        #download, convert, and save it

        # first check for empty space and clean up if need be
        self.cleanup()
        
        # first, if it's HEIC, gotta find the converted version
        split = path.splitext(photo.filename)
        filename = split[0] + ".JPG"
        fullPath = self.workingDir + "/" + filename

        if filename in self.photos:
            self.photos[filename] = time.time()
            return fullPath

        # ok, now we're going to have to download and possibly convert
        if split[1] == ".HEIC":
            logging.info(f'Initiating conversion of HEIC file {fullPath}')
            if (await asyncio.get_running_loop().run_in_executor(None, self._convert_heic, fullPath, photo) == None):
                logging.error("Coroutine HEIC conversion failed")
                return None
        elif split[1] == ".JPG":
            try:
                download = photo.download("medium")
                if download:
                    with open(fullPath, 'wb') as opened_file:
                        opened_file.write(download.raw.read())
                        opened_file.close()
            except IOError as err:
                print(err)
                return None
            except PyiCloudAPIResponseException as err:
                print (err)
                return None
        else:
            return None
        self.photos[filename] = time.time()

        self.usedSpace += path.getsize(fullPath)

        return fullPath

    def cleanup(self):
        if self.freeSpace < self.usedSpace:
            logging.info(f'Cleaning up {(self.usedSpace - self.freeSpace)/(1 << 10)}(kb) of space', )
            # sort dictionary by timestamp, and 
            # start removing oldest
            sortedPhotos = sorted(self.photos.items(), key = lambda item: item[1])

            # now start removing until we are good
            while self.freeSpace < self.usedSpace:
                try:
                    file = sortedPhotos[0][0]
                    fullFilePath = self.workingDir + "/" + file
                    self.usedSpace -= path.getsize(fullFilePath)
                    logging.info(f'Cleanup deleting {fullFilePath}')
                    os.unlink(fullFilePath)
                    self.photos.pop(file)
                except FileNotFoundError:
                    logging.error(f'Unable to delete {fullFilePath}: not found')
                    continue
