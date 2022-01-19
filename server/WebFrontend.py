from datetime import datetime
from flask import Flask, request
from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudAPIResponseException
import logging
import enum
import json
from iCloudFileFetcher import iCloudFileFetcher
from os import path

configPath = path.join(path.dirname(path.realpath(__file__)), "../config.json")
with open(configPath, 'r') as config:
    obj = json.load(config)
    logToFile = obj["logToFile"]
    serverSocket = obj["serverSocket"]
    ipcSocket = obj["ipcSocket"]
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
    fetcher: iCloudFileFetcher = None

    def __init__(self, fetcher):
        self.fetcher = fetcher

    def setCredentials(self, userName, password):
        self.userName = userName
        self.password = password
        self.authenticate(userName, password)

    def setLoggedIn(self):
        logging.info("Logged in, sending API to fetcher")
        self.status = Status.LoggedIn
        self.fetcher.setApi(self.api)

    def authenticate(self, userName, password) -> PyiCloudService:
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
        elif self.api.requires_2sa:
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

 # fetch config data
with open(configPath, 'r') as config:
    obj = json.load(config)
    albumName = obj["albumName"]
    workingDir = obj["workingDir"]
    maxSpace = obj["maxSpaceGb"]
    resizeImage = obj["resizeImage"]
    logToFile = obj["logToFile"]

if logToFile:
    filePath = path.join(path.dirname(path.realpath(__file__)), f"../logs/server_{datetime.now().strftime('%Y-%m-%d--%H-%M')}.log")
    logging.basicConfig(filename=filePath, level=logging.INFO, format='%(asctime)s %(message)s')
else:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s: %(message)s')

# setup major parts of the system
fetcher = iCloudFileFetcher(albumName, resizeImage, maxSpace, workingDir, ipcSocket)
frontEnd = WebFrontEnd(fetcher)

logging.info("Starting web app")
host_name = "0.0.0.0"
port = serverSocket
print(f"Starting web app on {host_name}:{port}")
webApp.run(host=host_name, port=port, use_reloader=False, threaded=True)