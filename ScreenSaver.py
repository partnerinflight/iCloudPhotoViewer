import RPi.GPIO as GPIO
import time
import asyncio
import threading

def toggleMonitor(channel):
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
        print ("Configuring GPIO: ", GPIO.RPI_INFO)
        GPIO.setmode(GPIO.BOARD)
        self.sensorPin = sensorPin
        self.relayPin = relayPin
        GPIO.setup(sensorPin, GPIO.IN)
        GPIO.setup(relayPin, GPIO.OUT, initial = 0)
        GPIO.add_event_detect(sensorPin, GPIO.BOTH, self.switchPirState, 600)
        self.event.set()
        self.timer = threading.Timer(self.timeout, self.timerFunction)

    def getWaitEvent(self) -> asyncio.Event:
        return self.event

    def timerFunction(self):
        if self.screenOn:
            toggleMonitor(self.relayPin)
            self.screenOn = False
            self.event.clear()
        self.timer.cancel()
        self.timer.start()

    def switchPirState(self, channel):
        pirState = GPIO.input(channel)
        print("PIR State: ", pirState)
        if pirState == 1:
            self.timer.cancel()
            self.timer.start()
            self.event.set()
            