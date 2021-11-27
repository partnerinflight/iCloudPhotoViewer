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

    def setCredentials(self, userName, password):
        self.userName = userName
        self.password = password
        self.authenticate(userName, password)

    def authenticate(self, userName, password) -> PyiCloudService:
        try:
            logging.info("Authenticating...")
            self.api = PyiCloudService(userName, password)

            if self.api.requires_2sa:
                self.status = Status.NeedToSendMFACode
                logging.info("Two-step authentication required.")
                self.devices = self.api.trusted_devices
                logging.info(self.devices)
        except:
            logging.error("Failed to authenticate")
            self.status = Status.NotLoggedIn
            self.api = None

    def sendCode(self, deviceId):
        device = list(filter(lambda x: x['deviceId'] == deviceId, self.devices))[0]
        if not device:
            print("Device not found")
            return

        if not self.api.send_verification_code(device):
            logging.error("Failed to send verification code")
            self.status = Status.NotLoggedIn
            self.api = None
        else:
            self.status = Status.WaitingForMFACode

    def validateCode(self, code):
        if self.api.validate_verification_code(self.devices[0], code):
            self.status = Status.LoggedIn
            # TODO Kick off the receiver here...
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
    frontEnd.authenticate(request.form['userName'], request.form['password'])
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

    frontEnd.validateCode(request.form['code'])
    return frontEnd.getStatus()
