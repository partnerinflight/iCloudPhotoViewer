
import time
import asyncio
import threading
import logging
runningOnPi = True
try:
    import RPi.GPIO as GPIO
except ModuleNotFoundError:
    runningOnPi = False

def toggleMonitor(channel):
    if not runningOnPi:
        return
    logging.info("Toggling monitor state")
    GPIO.output(channel, GPIO.HIGH)
    time.sleep(.4)
    GPIO.output(channel, GPIO.LOW)

class ScreenSaver:
    event: asyncio.Event = None
    expiryTime = time.monotonic()
    timeout = 3600
    timer: threading.Timer = None
    screenOn = True
    sensorPin = 0
    relayPin = 0

    def __init__(self, sensorPin, relayPin, timeoutSeconds, event) -> None:
        logging.getLogger().setLevel(logging.INFO)
        logging.info(f"Initiazing ScreenSaver with (S={sensorPin}, R={relayPin}, Timeout={timeoutSeconds})")
        if runningOnPi:
            logging.info(f"Configuring GPIO: {GPIO.RPI_INFO}")
            GPIO.setmode(GPIO.BOARD)
            self.sensorPin = sensorPin
            self.relayPin = relayPin
            GPIO.setup(sensorPin, GPIO.IN)
            GPIO.setup(relayPin, GPIO.OUT, initial = 0)
            GPIO.add_event_detect(sensorPin, GPIO.BOTH, self.switchPirState, 600)
        else:
            logging.warn(f"Not running on a Pi.")
        self.timeout = timeoutSeconds
        self.event = event
        self.timer = threading.Timer(self.timeout, self.timerFunction)
        self.timer.start()

    def timerFunction(self):
        if self.screenOn:
            logging.info("Screen was on. Turning off")
            toggleMonitor(self.relayPin)
            self.screenOn = False
            self.event.clear()
        self.timer.cancel()

    def switchPirState(self, channel):
        pirState = GPIO.input(channel)
        if pirState == 1:
            self.timer.cancel()
            self.timer = threading.Timer(self.timeout, self.timerFunction)
            self.timer.start()
            self.event.set()
            if self.screenOn == False:
                logging.info("Screen was off. Turning on.")
                toggleMonitor(self.relayPin)
                self.screenOn = True

    def turnOnScreen(self):
        if not self.screenOn:
            logging.info("Turning on screen")
            toggleMonitor(self.relayPin)
            self.screenOn = True
    
    def turnOffScreen(self):
        if self.screenOn:
            logging.info("Turning off screen")
            toggleMonitor(self.relayPin)
            self.screenOn = False

    def cleanup(self):
        logging.info("Cleaning up ScreenSaver")
        self.timer.cancel()
        self.event.set()
            