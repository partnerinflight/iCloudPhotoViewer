import os
from typing import Dict, List
import requests
from Downloader import Downloader, Photo, Status
from Constants import CONFIG_ALBUM_NAME, CONFIG_IMMICH_SERVER_URL, CONFIG_WORKING_DIR
from urllib.parse import quote
from PIL import Image

class ImmichDownloader(Downloader):
  def __init__(self, config) -> None:
    super().__init__()
    self.albumName = config[CONFIG_ALBUM_NAME]
    self.workingDir = config[CONFIG_WORKING_DIR]
    self.server_url = config[CONFIG_IMMICH_SERVER_URL]
    self.accessToken = None
    self.timelineBuckets = None

  def initialize(self):
    pass

  def getIDForPhoto(self, photo):
    return photo['id']
  
  def getFileNameForPhoto(self, photo):
    return photo['originalFileName']
  
  def getDimensionsForPhoto(self, photo):
    return [photo['exifInfo']['exifImageWidth'], photo['exifInfo']['exifImageHeight']]
  
  def getCreatedDateForPhoto(self, photo):
    return photo['fileCreatedAt']

  def getTimelineBuckets(self) -> List[Dict[str, object]]:
    headers = {
        "Authorization": f"Bearer {self.accessToken}"
    }

    # first get the list of albums
    buckets_url = f"{self.server_url}/api/timeline/buckets?isArchived=false&size=MONTH&withPartners=true&withStacked=true"
    response = requests.get(buckets_url, headers=headers)
    response.raise_for_status()
    self.timelineBuckets = response.json()
    return self.timelineBuckets
  
  def getPhotosForBucket(self, bucket_id: str) -> List[Photo]:
    headers = {
        "Authorization": f"Bearer {self.accessToken}"
    }

    buckets_url = f"{self.server_url}/api/timeline/bucket?isArchived=false&size=MONTH&timeBucket={quote(bucket_id)}&withPartners=true&withStacked=true"
    response = requests.get(buckets_url, headers=headers)
    response.raise_for_status()
    photos = response.json()
    return [Photo(photo, self) for photo in photos]

  def downloadPhoto(self, photo, destination):
    headers = {
        "Authorization": f"Bearer {self.accessToken}" 
    }

    photo_url = f"{self.server_url}/api/assets/{photo['id']}/thumbnail?size=preview"
    response = requests.get(photo_url, headers=headers, stream=True)
    response.raise_for_status()

    # Save the photo to the specified download folder
    with open(destination, 'wb') as photo_file:
        for chunk in response.iter_content(chunk_size=8192):
            photo_file.write(chunk)
    
    # now return a PIL image from this file
    return Image.open(destination)

  def authenticate(self, userName, password):
    auth_url = f"{self.server_url}/api/auth/login"
    payload = {
        "email": userName,
        "password": password
    }
    response = requests.post(auth_url, json=payload)
    response.raise_for_status()
    self.accessToken = response.json()['accessToken']
    self.status = Status.LoggedIn