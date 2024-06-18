from datetime import datetime
from flask import Flask, request, send_file
from werkzeug.routing import BaseConverter
import logging
import json
from PhotoProcessor import Downloader, Status, PhotoProcessor
from os import path, mkdir
import sys
import threading
from io import BytesIO
from PIL import Image, ImageOps

from ImmichDownloader import ImmichDownloader
from Constants import CONFIG_LOG_TO_FILE, CONFIG_SERVER_SOCKET, CONFIG_THUMBNAIL_DIR, CONFIG_WORKING_DIR, STATUS_CHANGED_EVENT

class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]

class WebFrontEnd:
    status = Status.NotLoggedIn
    devices = None
    downloader: Downloader = None
    fetcher: PhotoProcessor = None
    mfaDevice: None

    def __init__(self, fetcher):
        self.fetcher = fetcher
        self.downloader = fetcher.downloader

    def setCredentials(self, userName, password):
        self.userName = userName
        self.password = password
        self.fetcher.downloader.authenticate(userName, password)

    def setLoggedIn(self):
        logging.info("Logged in!")
        self.status = Status.LoggedIn

    def getStatus(self):
        return json.dumps({
            'status': self.status.name
        })
    
    def setStatus(self, status):
        self.status = status

webApp = Flask(__name__, static_url_path='')
webApp.url_map.converters['regex'] = RegexConverter

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
    frontEnd.setCredentials(json['userName'], json['password'])
    return frontEnd.getStatus()

@webApp.route('/api/mfa_device_choice', methods=['GET', 'POST'])
def mfa_device_choice():
    global frontEnd
    if request.method == 'POST':
        deviceJson = json.loads(request.data)
        frontEnd.downloader.sendCode(deviceJson['device'])
        return frontEnd.getStatus()
    else:
        devices = frontEnd.downloader.getDevices()
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
        'status': str(frontEnd.downloader.status),
        'album': frontEnd.fetcher.albumName,
        'numPhotos': frontEnd.fetcher.numPhotosInAlbum,
        'numPhotosProcessed': frontEnd.fetcher.numPhotosProcessed,
        'cacheUsePercent': frontEnd.fetcher.cacheUsePercent,
    })

@webApp.route('/api/displayed_list', methods=['GET'])
def displayed_list():
    global frontEnd
    return json.dumps(frontEnd.fetcher.displayedList)

def get_thumbnail(name):
    global workingDir
    global thumbnailDir
    filepath = path.join(workingDir, name)
    thumbPath = path.join(thumbnailDir, name)

    if path.exists(thumbPath):
        return thumbPath

    with open(filepath, 'rb') as f:            
        image = Image.open(BytesIO(f.read()))
    try:
        image.load()
    except (IOError, OSError):
        logging.warning('Thumbnail not load image: %s', filepath)
        return filepath

    image = ImageOps.fit(image, (200, 200), Image.ANTIALIAS)
    image.save(thumbPath, 'JPEG')
    return thumbPath

@webApp.route('/media/<regex("([a-zA-Z0-9\s_\\.\-\(\):%])+.(?:JPEG)"):filename>')
def thumbnail(filename):
    return send_file(get_thumbnail(filename))

@webApp.route('/api/delete_photo', methods=['POST'])
def delete_photo():
    global frontEnd
    json = request.get_json()
    frontEnd.fetcher.deletePhoto(json['photo'])
    return frontEnd.getStatus()

@webApp.route('/api/screen_control', methods=['POST'])
def screen_control():
    global frontEnd
    json = request.get_json()
    logging.info("Screen control command: " + json['action'])
    if json['action'] == 'on':
        logging.info("Sending Screen On command")
        frontEnd.fetcher.sendSlideshowCommand('screen', 'on')
    elif json['action'] == 'off':
        logging.info("Sending Screen Off command")
        frontEnd.fetcher.sendSlideshowCommand('screen', 'off')
    return downloader_status()

def downloaderStatusChanged(status):
    global downloader
    logging.info(f"Downloader status changed to {status}")
    if status == Status.LoggedIn:
        frontEnd.setLoggedIn()
    elif status == Status.WaitingForMFACode:
        frontEnd.status = Status.WaitingForMFACode
        frontEnd.devices = downloader.devices
    elif status == Status.NeedToSendMFACode:
        frontEnd.status = Status.NeedToSendMFACode
        frontEnd.devices = downloader.devices

def handle_unhandled_exception(exc_type, exc_value, exc_traceback):
    """Handler for unhandled exceptions that will write to the logs"""
    if issubclass(exc_type, KeyboardInterrupt):
        # call the default excepthook saved at __excepthook__
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_unhandled_exception

def patch_threading_excepthook():
    """Installs our exception handler into the threading modules Thread object
    Inspired by https://bugs.python.org/issue1230540
    """
    old_init = threading.Thread.__init__
    def new_init(self, *args, **kwargs):
        old_init(self, *args, **kwargs)
        old_run = self.run
        def run_with_our_excepthook(*args, **kwargs):
            try:
                old_run(*args, **kwargs)
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                sys.excepthook(*sys.exc_info())
        self.run = run_with_our_excepthook
    threading.Thread.__init__ = new_init

patch_threading_excepthook()

frontEnd = None
workingDir = None
thumbnailDir = None
downloader = None

def main():
    # setup major parts of the system
    global frontEnd, workingDir, thumbnailDir, downloader

    config = None
    configPath = path.join(path.dirname(path.realpath(__file__)), "../config.json")
    with open(configPath, 'r') as config:
        config = json.load(config)
        logToFile = config[CONFIG_LOG_TO_FILE]
        serverSocket = config[CONFIG_SERVER_SOCKET]
        workingDir = config[CONFIG_WORKING_DIR]
        thumbnailDir = config[CONFIG_THUMBNAIL_DIR]
        if not path.exists(thumbnailDir):
            mkdir(thumbnailDir)

    if logToFile:
        filePath = path.join(path.dirname(path.realpath(__file__)), f"../logs/server_{datetime.now().strftime('%Y-%m-%d--%H-%M')}.log")
        logging.basicConfig(filename=filePath, level=logging.INFO, format='%(asctime)s %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s: %(message)s')
    logging.info("Starting server")
    downloader = ImmichDownloader(config)
    downloader.on(STATUS_CHANGED_EVENT, downloaderStatusChanged)
    fetcher = PhotoProcessor(downloader, config)
    frontEnd = WebFrontEnd(fetcher)

    logging.info("Starting web app")
    host_name = "0.0.0.0"
    port = serverSocket
    print(f"Starting web app on {host_name}:{port}")
    webApp.run(host=host_name, port=port, use_reloader=False, threaded=True)

if __name__ == "__main__":
    main()