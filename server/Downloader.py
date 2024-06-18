import enum
from typing import Dict, List

from pyee import BaseEventEmitter
from PIL import Image

from Constants import STATUS_CHANGED_EVENT

class Status(enum.Enum):
    NotLoggedIn = 1
    NeedToSendMFACode = 2
    WaitingForMFACode = 3
    LoggedIn = 4
    
class Photo:
    def __init__(self, photo, downloader):
        self.photo = photo
        self.downloader = downloader
        self.image = None
        self._status = Status.NotLoggedIn

    def download(self, destination):
        if not self.image:
            self.image = self.downloader.downloadPhoto(self.photo, destination)
        return self.image
    
    @property
    def id(self) -> str:
        return self.downloader.getIDForPhoto(self.photo)
    
    @property
    def filename(self) -> str:
        return self.downloader.getFileNameForPhoto(self.photo)
    
    @property
    def dimensions(self) -> List[int]:
        return self.downloader.getDimensionsForPhoto(self.photo)
    
    @property
    def created(self):
        return self.downloader.getCreatedDateForPhoto(self.photo)

class Downloader(BaseEventEmitter):
    _status = Status.NotLoggedIn
    
    def __init__(self):
        super().__init__()

    def getTimelineBuckets(self) -> List[Dict[str, object]]:
        raise NotImplementedError
    def getPhotosList(self) -> List[Photo]:
        raise NotImplementedError
    def downloadPhoto(self, photo, destination) -> Image:
        raise NotImplementedError
    def authenticate(self, userName, password):
        raise NotImplementedError
    def getIDForPhoto(self, photo):
        raise NotImplementedError
    def getFileNameForPhoto(self, photo):
        raise NotImplementedError
    def getDimensionsForPhoto(self, photo):
        raise NotImplementedError
    def getCreatedDateForPhoto(self, photo):
        raise NotImplementedError
    
    @property
    def numPhotosInAlbum(self):
        raise NotImplementedError
    
    @property
    def status(self):
        return self._status
    
    @status.setter
    def status(self, value):
        self._status = value
        self.emit(STATUS_CHANGED_EVENT, value)
    
    