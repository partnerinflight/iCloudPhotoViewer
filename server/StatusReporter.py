import zmq
import logging

class StatusReporter:
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