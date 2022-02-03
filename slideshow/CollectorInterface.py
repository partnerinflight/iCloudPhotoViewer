from time import sleep
import zmq
import threading
import logging
import subprocess
from os import path
from ScreenSaver import ScreenSaver
class CollectorInterface:
    state: bool = False
    totalPhotos: int = 0
    processedPhotos: int = 0
    failedPhotos: int = 0
    ingesterThread: threading.Thread = None
    finished: bool = False
    collectorThread: threading.Thread = None
    loggingPort: int = 0
    screenSaver: ScreenSaver
    def __init__(self, statusPort, loggingPort, screenSaver,  autoLaunchCollector=True):
        self.statusPort = statusPort
        self.screenSaver = screenSaver
        # start the status ingester
        self.ingesterThread = threading.Thread(target=self.runIngester)
        self.ingesterThread.start()
        if autoLaunchCollector:
            self.collectorThread = threading.Thread(target=self.collectorThread)
            self.collectorThread.start()
        
        # create the logging socket
        self.loggingContext = zmq.Context()
        self.loggingSocket = self.loggingContext.socket(zmq.PUB)
        self.loggingSocket.bind("tcp://*:%s" % loggingPort)

    def reportDisplayedPhoto(self, photoName):
        self.loggingSocket.send_json({
            "command": "displayedPhoto",
            "params": photoName
        })

    def launchCollector(self):
        logging.info('Starting Photo Collector')
        fullPath = path.join(path.dirname(path.realpath(__file__)), "../server/WebFrontend.py")
        return subprocess.Popen(f'python {fullPath}', shell=True)

    def collectorThread(self):
        # Start the collector process and keep it alive
        p = self.launchCollector()

        while not self.finished:
            res = p.poll()
            if res is not None:
                self.state = False
                logging.info('Photo Collector exited, restarting')
                p = self.launchCollector()
            sleep(30)

    def runIngester(self):
        logging.info('Status ingester started')
        self.statusContext = zmq.Context()
        self.statusSocket = self.statusContext.socket(zmq.SUB)
        self.statusSocket.connect("tcp://localhost:%s" % self.statusPort)
        self.statusSocket.setsockopt_string(zmq.SUBSCRIBE, "")
        while not self.finished:
            packet = self.statusSocket.recv_json()
            if "status" in packet:
                self.state = packet["status"].lower() != "finished"
                self.totalPhotos = packet["numTotalPhotos"]
                self.processedPhotos = packet["numProcessedPhotos"]
                self.failedPhotos = packet["numFailedPhotos"]
            elif "command" in packet:
                if packet["command"] == "screen":
                    logging.info("Sending screen command")
                    if packet['params'] == "on":
                        self.screenSaver.turnOnScreen()
                    else:
                        self.screenSaver.turnOffScreen()

    def cleanup(self):
        self.finished = True
        self.statusSocket.close()
        self.statusContext.term()
        self.loggingSocket.close()
        self.loggingContext.term()
        self.ingesterThread.join()
        if self.collectorThread is not None:
            self.collectorThread.join()

    @property
    def status(self):
        return self.state

    @property
    def numTotalPhotos(self):
        return self.totalPhotos
    
    @property
    def numProcessedPhotos(self):
        return self.processedPhotos
    
    @property
    def numFailedPhotos(self):
        return self.failedPhotos