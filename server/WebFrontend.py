from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudAPIResponseException
import logging
from six.moves import input as raw_input
from os import _exit

webApp = Flask(__name__, static_url_path='')
@webApp.route('/')
def home():
    return webApp.send_static_file('index.html')

    
class WebFrontEnd:
    userName: str = ""
    password: str = ""

    def __init__(self, userName, password):
        self.userName = userName
        self.password = password

    def authenticate(self) -> PyiCloudService:
        api = PyiCloudService(self.userName, self.password)
        success = True
        if api.requires_2sa:
                logging.info("Two-step authentication required. Your trusted devices are:")
                devices = api.trusted_devices
                #print devices
                for i, device in enumerate(devices):
                    print("  %s: %s" % (i, device.get('deviceName', "SMS to %s" % device.get('phoneNumber'))))
                device = devices[0]
                print (device)
                if not api.send_verification_code(device):
                    logging.error("Failed to send verification code")
                    _exit(1)
                code = raw_input("Enter Verification Code: ")
                retry = 0
                success = api.validate_verification_code(device, code)
        if success:
            return api
        else:
            return None

    def GET(self):
        return "Hello, world!"