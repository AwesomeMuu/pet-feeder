###########################################################################################
# petfeeder.py v 1.0
#
# Author: Krish Sivakumar
# Created Dec 2015
#
# Program to automate on-demand pet feeding through the internet
# Uses Raspberry Pi as a controller
#
# Distributed under Creative Commons Attribution-NonCommercial-Sharealike licensing
# https://creativecommons.org/licenses/by-nc-sa/3.0/us/
#
############################################################################################


import imaplib
import time
import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email import Encoders
import os
import sys
import RPi.GPIO as GPIO
import httplib2
import json
import html2text
from Adafruit_CharLCD import Adafruit_CharLCD as LCD

# pin configuration and 16x2 setup. Pin numbers are (BCM)
lcd_rs        = 27  
lcd_en        = 22
lcd_d4        = 25
lcd_d5        = 24
lcd_d6        = 23
lcd_d7        = 18
lcd_backlight = 4
lcd_columns   = 16
lcd_rows      = 2




DEBUG = False
MOTORON = True
CHUCKNORRIS = False
NUMBERTRIVIA = True

# Here is our logfile
LOGFILE = "/tmp/petfeeder.log"

# Variables for checking email
GMAILHOSTNAME = 'imap.gmail.com' # Insert your mailserver here - Gmail uses 'imap.gmail.com'
MAILBOX = 'Inbox' # Insert the name of your mailbox. Gmail uses 'Inbox'
GMAILUSER = 'ali.latyf' # Insert your email username
GMAILPASSWD = '1234'# Insert your email password
NEWMAIL_OFFSET = 0
lastEmailCheck = time.time()
MAILCHECKDELAY = 30  # Don't check email too often since Gmail will complain

# GPIO pins for feeder control
MOTORCONTROLPIN = 19
FEEDBUTTONPIN = 6
RESETBUTTONPIN = 13

# Variables for feeding information
readyToFeed = False # not used now but for future use
feedInterval = 28800 # This translates to 8 hours in seconds
FEEDFILE="/home/pi/Desktop/petfeeder/lastfeed"
cupsToFeed = 1
motorTime = cupsToFeed * 27 # It takes 27 seconds of motor turning (~1.75 rotations) to get 1 cup of feed


# Function that gets Chuck Norris jokes from the internet. It uses an HTTP GET and then a JSON parser
def getChuckNorrisQuote():
    # The database where the jokes are stored
    ICNDB="http://api.icndb.com/jokes/random"
    # Doing a HTTP request to get the response (resp) and content (content)
    resp, content = httplib2.Http().request(ICNDB)
    # The content is in the following JSON format and needs to be parsed
    # {u'type': u'success', u'value' : {u'joke': 'Text of the joke', u'id': 238, u'categories': []}}
    parsed_content = json.loads(content)
    joke = "\n\n** Random Chuck Norris Quote **:\n" + html2text.html2text(parsed_content['value']['joke'])
    return joke
    

# Function that gets a number trivia from the internet. It uses an HTTP GET and then a JSON parser
def getNumberTrivia():
    # The database where the trivia are stored
    NUMDB="http://numbersapi.com/random/trivia?json"
    # Doing a HTTP request to get the response (resp) and content (content)
    resp, content = httplib2.Http().request(NUMDB)
    # The content is in the following JSON format and needs to be parsed
    # {u'text': u'Text of trivia', u'type' : u'trivia, u'number': <number>, u'found': True}
    parsed_content = json.loads(content)
    trivia = "\n\n** Fact about the number " + str(parsed_content['number']) + " **\n"
    trivia = trivia + parsed_content['text']
    return trivia
    

# Function to check email
def checkmail():
    global lastEmailCheck
    global lastFeed
    global feedInterval
    
    if (time.time() > (lastEmailCheck + MAILCHECKDELAY)):  # Make sure that that atleast MAILCHECKDELAY time has passed
        lastEmailCheck = time.time()
        server = imaplib(GMAILHOSTNAME, use_uid=True, ssl=True)  # Create the server class from IMAPClient with HOSTNAME mail server
        server.login(GMAILUSER, GMAILPASSWD)
        server.select_folder(MAILBOX)
        
        # See if there are any messages with subject "When" that are unread
        whenMessages = server.search([u'UNSEEN', u'SUBJECT', u'When'])

        # Respond to the when messages
        if whenMessages:
            for msg in whenMessages:
                msginfo = server.fetch([msg], ['BODY[HEADER.FIELDS (FROM)]'])
                fromAddress = str(msginfo[msg].get('BODY[HEADER.FIELDS (FROM)]')).split('<')[1].split('>')[0]
                msgBody = "The last feeding was done on " + time.strftime("%b %d at %I:%M %P", time.localtime(lastFeed))

                if (time.time() - lastFeed) > feedInterval:
                    msgBody = msgBody + "\nReady to feed now!"
                else:
                    msgBody = msgBody + "\nThe next feeding can begin on " + time.strftime("%b %d at %I:%M %P", time.localtime(lastFeed + feedInterval))

                if NUMBERTRIVIA:
                    msgBody = msgBody + getNumberTrivia()

                if CHUCKNORRIS:
                    msgBody = msgBody + getChuckNorrisQuote()
                                                
                sendemail(fromAddress, "Thanks for your feeding query", msgBody)
                server.add_flags(whenMessages, [SEEN])


        # See if there are any messages with subject "Feed" that are unread
        feedMessages = server.search([u'UNSEEN', u'SUBJECT', u'Feed'])
        
        # Respond to the feed messages and then exit
        if feedMessages:
            for msg in feedMessages:
                msginfo = server.fetch([msg], ['BODY[HEADER.FIELDS (FROM)]'])
                fromAddress = str(msginfo[msg].get('BODY[HEADER.FIELDS (FROM)]')).split('<')[1].split('>')[0]

                msgBody = "The last feeding was done at " + time.strftime("%b %d at %I:%M %P", time.localtime(lastFeed))
                if (time.time() - lastFeed) > feedInterval:
                    msgBody = msgBody + "\nReady to be fed, will be feeding Lucky shortly"
                else:
                    msgBody = msgBody + "\nThe next feeding can begin at " + time.strftime("%b %d at %I:%M %P", time.localtime(lastFeed + feedInterval))

                if NUMBERTRIVIA:
                    msgBody = msgBody + getNumberTrivia()

                if CHUCKNORRIS:
                    msgBody = msgBody + getChuckNorrisQuote()
                                                
                sendemail(fromAddress, "Thanks for your feeding request", msgBody)

                server.add_flags(feedMessages, [SEEN])
            return True

    return False


def sendemail(to, subject, text, attach=None):
    msg = MIMEMultipart()
    msg['From'] = GMAILUSER
    msg['To'] = to
    msg['Subject'] = subject
    msg.attach(MIMEText(text))
    if attach:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(open(attach, 'rb').read())
        Encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(attach))
        msg.attach(part)
    mailServer = smtplib.SMTP("smtp.gmail.com", 587)
    mailServer.ehlo()
    mailServer.starttls()
    mailServer.ehlo()
    mailServer.login(GMAILUSER, GMAILPASSWD)
    mailServer.sendmail(GMAILUSER, to, msg.as_string())
    mailServer.close()



def buttonpressed(PIN):
    # Check if the button is pressed
    global GPIO
    
    # Cheap (sleep) way of controlling bounces / rapid presses
    time.sleep(0.2)
    button_state = GPIO.input(PIN)
    if button_state == False:
        return True
    else:
        return False


def remotefeedrequest():
    # At this time we are only checking for email
    # Other mechanisms for input (e.g. web interface or iOS App) is a TO-DO
    return checkmail()


def printlcd(row, col, LCDmesg):
    # Set the row and column for the LCD and print the message
    global logFile
    global lcd
    
    lcd.setCursor(row, col)
    lcd.message(LCDmesg)


def feednow():
    # Run the motor for motorTime, messages in the LCD during the feeeding
    global GPIO
    global MOTORCONTROLPIN
    global motorTime
    global lastFeed
    global GMAILUSER

    lcd.clear()
    printlcd(0,0,"Feeding now.....")
    if MOTORON:
        GPIO.output(MOTORCONTROLPIN, True)
        time.sleep(motorTime)
        GPIO.output(MOTORCONTROLPIN, False)
        printlcd(0,1, "Done!")
        sendemail(GMAILUSER, "Fed at " + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(lastFeed)), "Feeding done!")
        time.sleep(2)
    return time.time()

def saveLastFeed():
    global FEEDFILE
    global lastFeed
    with open(FEEDFILE, 'w') as feedFile:
        feedFile.write(str(lastFeed))
    feedFile.close()


# This is the main program, essentially runs in a continuous loop looking for button press or remote request
try:

    #### Begin initializations #########################
    ####################################################
    
    # Initialize the logfile
    logFile = open(LOGFILE, 'a')

    # Initialize the LCD
   # lcd = Adafruit_CharLCD()
    #lcd.begin(16,2)
    #lcd.clear()
    
    

    # Initialize the GPIO system
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    # Initialize the pin for the motor control
    GPIO.setup(MOTORCONTROLPIN, GPIO.OUT)
    GPIO.output(MOTORCONTROLPIN, False)

    # Initialize the pin for the feed and reset buttons
    GPIO.setup(FEEDBUTTONPIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(RESETBUTTONPIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    # Initialize lastFeed
    if os.path.isfile(FEEDFILE):
        with open(FEEDFILE, 'r') as feedFile:
            lastFeed = float(feedFile.read())
        feedFile.close()
    else:
        lastFeed = time.time()
        saveLastFeed()
        

    #### End of initializations ########################
    ####################################################

    #### The main loop ####
    
    while True:

        #### If reset button pressed, then reset the counter
        if buttonpressed(RESETBUTTONPIN):
            lcd.clear()
            printlcd(0,0, "Resetting...   ")
            time.sleep(2)
            lastFeed = time.time() - feedInterval + 5
            saveLastFeed()
        
        #### Check if we are ready to feed
        if (time.time() - lastFeed) > feedInterval:
            printlcd(0,0, time.strftime("%m/%d %I:%M:%S%P", time.localtime(time.time())))
            printlcd(0,1, "Ready to feed   ")

            #### See if the button is pressed
            if buttonpressed(FEEDBUTTONPIN):
                lastFeed = feednow()
                saveLastFeed()
            
            #### Check if remote feed request is available
            elif remotefeedrequest():
                lastFeed = feednow()
                saveLastFeed()
                
        #### Since it is not time to feed yet, keep the countdown going
        else:
            timeToFeed = (lastFeed + feedInterval) - time.time()
            printlcd(0,0, time.strftime("%m/%d %I:%M:%S%P", time.localtime(time.time())))
            printlcd(0,1, 'Next:' + time.strftime("%Hh %Mm %Ss", time.gmtime(timeToFeed)))
            checkmail()
            if buttonpressed(FEEDBUTTONPIN):
                lcd.clear()
                printlcd(0,0, "Not now, try at ")
                printlcd(0,1, time.strftime("%b/%d %H:%M", time.localtime(lastFeed + feedInterval)))
                time.sleep(2)
        time.sleep(.6)

#### Cleaning up at the end
except KeyboardInterrupt:
    logFile.close()
    lcd.clear()
    GPIO.cleanup()

except SystemExit:
    logFile.close()
    lcd.clear()
    GPIO.cleanup()





