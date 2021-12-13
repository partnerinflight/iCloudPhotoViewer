from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudAPIResponseException
import logging
from os import _exit
import enum
import json
from iCloudFileFetcher import iCloudFileFetcher

class Status(enum.Enum):
    NotLoggedIn = 1
    NeedToSendMFACode = 2
    WaitingForMFACode = 3
    LoggedIn = 4


class WebFrontEnd:
    status = Status.NotLoggedIn
    devices = None
    api: PyiCloudService = None
    fetcher: iCloudFileFetcher = None
    mfaDevice: None
    def setCredentials(self, userName, password):
        self.userName = userName
        self.password = password
        self.authenticate(userName, password)

    def setFetcher(self, fetcher):
        self.fetcher = fetcher

    def setLoggedIn(self):
        logging.info("Logged in, sending API to fetcher")
        self.status = Status.LoggedIn
        self.fetcher.setApi(self.api)

    def authenticate(self, userName, password) -> PyiCloudService:
        try:
            logging.info("Authenticating...")
            self.api = PyiCloudService(userName, password)

            if self.api.requires_2sa:
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
        if self.api.validate_verification_code(self.chosenDevice, code):
            self.setLoggedIn()
        else:
            self.status = Status.NotLoggedIn
            self.api = None

    def getDevices(self):
        return self.devices

    def getStatus(self):
        return json.dumps({
            'status': self.status.name
        })
    
    def setStatus(self, status):
        self.status = status

frontEnd = WebFrontEnd()
webApp = Flask(__name__, static_url_path='')


@webApp.route('/')
def home():
    return webApp.send_static_file('index.html')

# here we need to define routes for the various APIs

@webApp.route('/api/status')
def status():
    global frontEnd
    return frontEnd.getStatus()
    
@webApp.route('/api/login', methods=['POST'])
def login():
    global frontEnd
    json = request.get_json()
    frontEnd.authenticate(json['userName'], json['password'])
    return frontEnd.getStatus()

@webApp.route('/api/mfa_device_choice', methods=['GET', 'POST'])
def mfa_device_choice():
    global frontEnd
    if request.method == 'POST':
        deviceJson = json.loads(request.data)
        frontEnd.sendCode(deviceJson['device'])
        return frontEnd.getStatus()
    else:
        devices = frontEnd.getDevices()
        return json.dumps(devices)

@webApp.route('/api/mfa_code', methods=['POST'])
def mfa():
    global frontEnd
    codeJson = json.loads(request.data)
    frontEnd.validateCode(codeJson['code'])
    return frontEnd.getStatus()

@webApp.route('/api/downloader_status', methods=['GET'])
def downloader_status():
    global frontEnd
    return json.dumps({
        'status': frontEnd.fetcher.getStatus(),
        'album': frontEnd.fetcher.getAlbum(),
        'numPhotos': frontEnd.fetcher.getNumPhotos(),
        'numPhotosProcessed': frontEnd.fetcher.getNumPhotosProcessed(),
    })