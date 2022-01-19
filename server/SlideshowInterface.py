import zmq
import logging

class SlideshowInterface:
    def __init__(self, port):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind("tcp://*:%s" % port)

    def report(self, status, numTotalPhotos, numProcessedPhotos, numFailedPhotos):
        res = self.socket.send_json({
            "status": status,
            "numTotalPhotos": numTotalPhotos,
            "numProcessedPhotos": numProcessedPhotos,
            "numFailedPhotos": numFailedPhotos
        })
        logging.info("StatusReporter: %s" % res)

    def sendCommand(self, command, params):
        logging.info("Sending command %s with params %s to slideshow" % (command, params))
        res = self.socket.send_json({
            "command": command,
            "params": params
        })
        logging.info("CommandSender: %s" % res)