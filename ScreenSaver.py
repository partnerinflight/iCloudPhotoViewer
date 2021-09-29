import RPi.GPIO as GPIO
import time
import asyncio
import threading
import logging

def toggleMonitor(channel):
    logging.info("Toggling monitor state")
    GPIO.output(channel, GPIO.HIGH)
    time.sleep(.5)
    GPIO.output(channel, GPIO.LOW)

class ScreenSaver:
    event = asyncio.Event()
    expiryTime = time.monotonic()
    timeout = 3600
    timer: threading.Timer = None
    screenOn = True
    sensorPin = 0
    relayPin = 0

    def __init__(self, sensorPin, relayPin, timeoutSeconds) -> None:
        logging.info("Initiazing ScreenSaver with SensorPin=", sensorPin, "RelayPin=", relayPin, "timeout=", timeoutSeconds)
        logging.info("Configuring GPIO: ", GPIO.RPI_INFO)
        GPIO.setmode(GPIO.BOARD)
        self.sensorPin = sensorPin
        self.relayPin = relayPin
        GPIO.setup(sensorPin, GPIO.IN)
        GPIO.setup(relayPin, GPIO.OUT, initial = 0)
        GPIO.add_event_detect(sensorPin, GPIO.BOTH, self.switchPirState, 600)
        self.timeout = timeoutSeconds
        self.event.set()
        self.timer = threading.Timer(self.timeout, self.timerFunction)
        self.timer.start()

    def getWaitEvent(self) -> asyncio.Event:
        return self.event

    def timerFunction(self):
        logging.info("Timer fired!")
        if self.screenOn:
            logging.info("Screen was on. Turning off")
            toggleMonitor(self.relayPin)
            self.screenOn = False
            self.event.clear()
        self.timer.cancel()
        self.timer = threading.Timer(self.timeout, self.timerFunction)
        self.timer.start()

    def switchPirState(self, channel):
        pirState = GPIO.input(channel)
        logging.info("PIR State: ", pirState)
        if pirState == 1:
            logging.info("Restarting timer")
            self.timer.cancel()
            self.timer = threading.Timer(self.timeout, self.timerFunction)
            self.timer.start()
            self.event.set()
            