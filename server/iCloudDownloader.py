from typing import List
from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudAPIResponseException
from PhotoProcessor import Downloader, Status, PhotoAlbum
from random import choice
import logging
from PIL import Image

from Downloader import Photo

class iCloudDownloader(Downloader):
    api: PyiCloudService = None
    photos = dict()
    photosAlbum: PhotoAlbum = None

    def __init__(self, albumName: str = None, workingDir: str = "/tmp/photos") -> None:
      super().__init__()
      self.albumName = albumName
      self.workingDir = workingDir
        
    def authenticate(self, userName, password):
      try:
          logging.info("Authenticating...")
          self.api = PyiCloudService(userName, password)

          if self.api.requires_2fa:
              logging.info("Two factor authentication required")
              self.status = Status.WaitingForMFACode
          elif self.api.requires_2sa:
              self.status = Status.NeedToSendMFACode
              logging.info("Two-step authentication required.")
              self.devices = self.api.trusted_devices
              logging.info(self.devices)
          else:
              self.setLoggedIn()
      except:
          logging.error("Failed to authenticate")
          self.status = Status.NotLoggedIn
          self.api = None

    def downloadPhoto(self, photo):
      try:
          fullPath = self._get_temp_path(photo.filename)
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
    
    def sendCode(self, deviceId):
        device = list(filter(lambda x: x['deviceId'] == deviceId, self.devices))[0]
        if not device:
            print("Device not found")
            return
        
        self.chosenDevice = device
        if not self.api.send_verification_code(device):
            logging.error("Failed to send verification code")
            self.status = Status.NotLoggedIn
            self.api = None
        else:
            self.status = Status.WaitingForMFACode

    def validateCode(self, code):
        logging.info(f"Received code ${code}")
        if self.api.requires_2fa:
            result = self.api.validate_2fa_code(code)
            if not result:
                logging.error("Failed to validate code")
                self.status = Status.NotLoggedIn
                self.api = None
                return
            if not self.api.is_trusted_session:
                logging.info("Session is not trusted")
                result = self.api.trust_session()
                if not result:
                    logging.error("Failed to trust session")
                    self.status = Status.NotLoggedIn
                    self.api = None
            self.setLoggedIn()
        elif self.api.requires_2sa:
            if self.api.validate_verification_code(self.chosenDevice, code):
                self.setLoggedIn()
        else:
            self.status = Status.NotLoggedIn
            self.api = None

    def getDevices(self):
        return self.devices

    @property
    def numPhotosInAlbum(self):
        if self.photosAlbum != None:
            return len(self.photosAlbum)
        else:
            return 0
        
    def setApi(self, api: PyiCloudService):
        self.api = api

    def getPhotosList(self) -> List[Photo]:
      # first check if we have a photo album
      if not self.photosAlbum:
        self.photosAlbum = self.getPhotoAlbum()
      
      # now take every photo from that album, and convert it to the Photo class, a return a list of that
      photos = []
      for photo in self.photosAlbum:
          photos.append(Photo(photo, photo.filename, self))
      return photos

    def getPhotoAlbum(self) -> PhotoAlbum:
      if not self.albumName:
        return self.api.photos.all
      else:
        albums = []
        for album in self.api.photos.albums:
            albums.append(album.title())

        if self.albumName not in albums:
            self.albumName = choice(albums)
        return len(self.api.photos.albums[self.albumName])