import RPi.GPIO as GPIO
import time
import asyncio

def toggleMonitor(channel):
    GPIO.output(channel, GPIO.HIGH)
    time.sleep(.5)
    GPIO.output(channel, GPIO.LOW)

class ScreenSaver:
    event = asyncio.Event()

    def __init__(self, sensorPin, relayPin) -> None:
        print ("Configuring GPIO: ", GPIO.RPI_INFO)
        GPIO.setmode(GPIO.BOARD)
        sensorPin = 11
        relayPin = 13
        GPIO.setup(sensorPin, GPIO.IN)
        GPIO.setup(relayPin, GPIO.OUT, initial = 1)
        GPIO.add_event_detect(sensorPin, GPIO.BOTH, self.switchPirState, 600)
        self.event.set()

    def switchPirState(self, channel):
        pirState = GPIO.input(channel)
        print("PIR State: ", pirState)