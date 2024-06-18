# This will simply instantiate the appropriate downloader and PhotoProcessor and start processing
# It requires username/password to be set in the config file


import datetime
import json
import logging
from os import mkdir, path
from Constants import STATUS_CHANGED_EVENT
from PhotoProcessor import PhotoProcessor
from ImmichDownloader import ImmichDownloader

def downloaderStatusChanged(status):
    logging.info(f"Downloader status changed to {status}")

def main():
    config = None
    configPath = path.join(path.dirname(path.realpath(__file__)), "../config.json")
    with open(configPath, 'r') as config:
        config = json.load(config)
        logToFile = config["logToFile"]
        workingDir = config["workingDir"]
        if not path.exists(workingDir):
            mkdir(workingDir)
        thumbnailDir = config["thumbnailDir"]
        if not path.exists(thumbnailDir):
            mkdir(thumbnailDir)

    if logToFile:
        filePath = path.join(path.dirname(path.realpath(__file__)), f"../logs/server_{datetime.datetime.now().strftime('%Y-%m-%d--%H-%M')}.log")
        logging.basicConfig(filename=filePath, level=logging.INFO, format='%(asctime)s %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s: %(message)s')
    logging.info("Starting server")
    downloader = ImmichDownloader(config)
    downloader.on(STATUS_CHANGED_EVENT, downloaderStatusChanged)
    fetcher = PhotoProcessor(downloader, config)
    downloader.authenticate(config["userName"], config["password"])

if __name__ == "__main__":
    main()