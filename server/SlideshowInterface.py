import zmq
import logging
import threading

class SlideshowInterface:
    def __init__(self, commandPort, statusPort):
        self.commandContext = zmq.Context()
        self.commandSocket = self.commandContext.socket(zmq.PUB)
        self.commandSocket.bind("tcp://*:%s" % commandPort)

        # start the status ingester
        self.displayedPhotos = []
        self.finished = False
        self.statusPort = statusPort
        self.ingesterThread = threading.Thread(target=self._runIngester)
        self.ingesterThread.start()
        
    def _runIngester(self):
        logging.info('Status ingester started')
        self.statusContext = zmq.Context()
        self.statusSocket = self.statusContext.socket(zmq.SUB)
        self.statusSocket.connect("tcp://localhost:%s" % self.statusPort)
        self.statusSocket.setsockopt_string(zmq.SUBSCRIBE, "")
        while True:
            msg = self.statusSocket.recv_json()
            logging.info("Status ingester: %s" % msg)
            if "command" in msg and msg["command"] == "displayedPhoto":
                # add the displayed photo name to list of displayed photos
                self.displayedPhotos.insert(0, msg["params"])


    def report(self, status, numTotalPhotos, numProcessedPhotos, numFailedPhotos):
        res = self.commandSocket.send_json({
            "status": status,
            "numTotalPhotos": numTotalPhotos,
            "numProcessedPhotos": numProcessedPhotos,
            "numFailedPhotos": numFailedPhotos
        })
        logging.info("StatusReporter: %s" % res)

    def sendCommand(self, command, params):
        logging.info("Sending command %s with params %s to slideshow" % (command, params))
        res = self.commandSocket.send_json({
            "command": command,
            "params": params
        })
        logging.info("CommandSender: %s" % res)

    def cleanup(self):
        self.finished = True
        self.ingesterThread.join()
        self.commandSocket.close()
        self.statusSocket.close()
        self.commandContext.term()
        self.statusContext.term()