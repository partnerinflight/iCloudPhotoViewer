import zmq
import threading
import logging
import subprocess
from os import path

class StatusIngester:
    state: bool = False
    totalPhotos: int = 0
    processedPhotos: int = 0
    failedPhotos: int = 0
    ingesterThread: threading.Thread = None
    finished: bool = False
    collectorThread: threading.Thread = None
    port: int = 0
    def __init__(self, port, autoLaunchCollector=True):
        self.port = port
        # start the status ingester
        self.ingesterThread = threading.Thread(target=self.runIngester)
        self.ingesterThread.start()
        if autoLaunchCollector:
            self.collectorThread = threading.Thread(target=self.collectorThread)
            self.collectorThread.start()

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

    def runIngester(self):
        logging.info('Status ingester started')
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect("tcp://localhost:%s" % self.port)
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
        while not self.finished:
            status = self.socket.recv_json()
            self.state = status["status"].lower() != "finished"
            self.totalPhotos = status["numTotalPhotos"]
            self.processedPhotos = status["numProcessedPhotos"]
            self.failedPhotos = status["numFailedPhotos"]

    def cleanup(self):
        self.finished = True
        self.socket.close()

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