import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setup(23,GPIO.OUT)
while True:
	GPIO.output(23 , GPIO.HIGH)
	print("on")
	time.sleep(2)
	GPIO.output(23 , GPIO.LOW)
	print("off")
	time.sleep(2)
