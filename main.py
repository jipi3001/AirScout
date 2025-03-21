import sys
sys.path.append('/home/AirScout-main/lib/')
import os
import json
import logging
import threading
import time
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd1in54b_V2
import RPi.GPIO as GPIO
from sensor_reader import *
import urequests
import queue
import gps_readerV2

os.chdir("/home/AirScout-main")


#maximum amount of files than can be stored on the device locally
MAX_FILES = 50

# Konstante Verzögerungen
DISPLAY_DELAY = 0.2
MEASURE_DELAY = 60 #takes a measurement every 60s

# GPIO-Pins Layout
DISPLAY_SWITCH = 27
GPS_SWITCH = 22
SEND_SWITCH = 23

#Desired 
FIXED_LONG = 9.008371
FIXED_LAT = 48.702709

# Messdaten Speicherort
DATEN_PFAD = '/home/AirScout-main/messdaten/'
if not os.path.exists(DATEN_PFAD):		#creates folder if doesnt exist yet
    os.makedirs(DATEN_PFAD)

# API URL
URL = "https://www.gm4s.eu/api/addMarker"

# GPIO einrichten
GPIO.setmode(GPIO.BCM)
GPIO.setup(DISPLAY_SWITCH, GPIO.IN)
GPIO.setup(GPS_SWITCH, GPIO.IN)
GPIO.setup(SEND_SWITCH, GPIO.IN)

# Display Initialisierung
epd = epd1in54b_V2.EPD()
epd.init()
font = ImageFont.truetype("/home/AirScout-main/Font.ttc", 24)

q = queue.Queue(maxsize=1)		#only one measurement of the sensors can be stored in the queue at once

# Event für sauberen Thread-Stopp
stop_event = threading.Event()

def display():
    """ Zeigt Messwerte auf dem e-Paper Display an. """
    DISPLAY_LAST = 0
    DISPLAY_NOW = 0
    data_read = {}
    while not stop_event.is_set():
        blackimage = Image.new('1', (epd.width, epd.height), 255)
        redimage = Image.new('1', (epd.width, epd.height), 255)
        drawblack = ImageDraw.Draw(blackimage)
        drawred = ImageDraw.Draw(redimage)
        
        DISPLAY_NOW = GPIO.input(DISPLAY_SWITCH)
        
        if not q.empty():
            data_read = json.loads(q.get())
            if DISPLAY_NOW == 0:
                drawblack.text((0, 0), f'Part 1: {data_read.get("part_1", get_pm_1_0())}', font=font, fill=0)
                drawblack.text((0, 22), f'Part 2.5: {data_read.get("part_2_5", get_pm_2_5())}', font=font, fill=0)
                drawblack.text((0, 44), f'Part 10: {data_read.get("part_10", get_pm_10())}', font=font, fill=0)
                drawblack.text((0, 66), f'CO2: {data_read.get("co2", get_co2())}', font=font, fill=0)
                drawblack.text((0, 88), f'Temp: {data_read.get("temp", get_temperature())}', font=font, fill=0)
                drawblack.text((0, 110), f'Hum: {data_read.get("hum", get_humidity())}', font=font, fill=0)
                drawblack.text((0, 132), f'CH2O: {data_read.get("ch2o", get_ch2o())}', font=font, fill=0)
                drawblack.text((0, 154), f'CO: {data_read.get("co", get_co())}', font=font, fill=0)
                drawblack.text((0, 176), f'O3: {data_read.get("o3", get_o3())}', font=font, fill=0)
            else:
                drawblack.text((0, 0), f'Long: {data_read.get("long", "NaN")}', font=font, fill=0)
                drawblack.text((0, 22), f'Lat: {data_read.get("lat", "NaN")}', font=font, fill=0)
                drawblack.text((0, 44), f'Saved Meas: {sum(1 for f in os.listdir(DATEN_PFAD) if f.endswith(".json"))}', font=font, fill=0)
            epd.display(epd.getbuffer(blackimage), epd.getbuffer(redimage))
        
        if DISPLAY_NOW != DISPLAY_LAST:
            if DISPLAY_NOW == 0:
                drawblack.text((0, 0), f'Part 1: {data_read.get("part_1", get_pm_1_0())}', font=font, fill=0)
                drawblack.text((0, 22), f'Part 2.5: {data_read.get("part_2_5", get_pm_2_5())}', font=font, fill=0)
                drawblack.text((0, 44), f'Part 10: {data_read.get("part_10", get_pm_10())}', font=font, fill=0)
                drawblack.text((0, 66), f'CO2: {data_read.get("co2", get_co2())}', font=font, fill=0)
                drawblack.text((0, 88), f'Temp: {data_read.get("temp", get_temperature())}', font=font, fill=0)
                drawblack.text((0, 110), f'Hum: {data_read.get("hum", get_humidity())}', font=font, fill=0)
                drawblack.text((0, 132), f'CH2O: {data_read.get("ch2o", get_ch2o())}', font=font, fill=0)
                drawblack.text((0, 154), f'CO: {data_read.get("co", get_co())}', font=font, fill=0)
                drawblack.text((0, 176), f'O3: {data_read.get("o3", get_o3())}', font=font, fill=0)
            else:
                drawblack.text((0, 0), f'Long: {data_read.get("long", "NaN")}', font=font, fill=0)
                drawblack.text((0, 22), f'Lat: {data_read.get("lat", "NaN")}', font=font, fill=0)
                drawblack.text((0, 44), f'Saved Meas: {sum(1 for f in os.listdir(DATEN_PFAD) if f.endswith(".json"))}', font=font, fill=0)
            epd.display(epd.getbuffer(blackimage), epd.getbuffer(redimage))
        DISPLAY_LAST = DISPLAY_NOW
        time.sleep(DISPLAY_DELAY)

def messen():
    """ Misst Sensordaten und speichert sie lokal. """
    while not stop_event.is_set():
        sensor_data = read_sensor_data()
        #print(GPIO.input(GPS_SWITCH)) #remove # when wanting to see exact gps information
        if GPIO.input(GPS_SWITCH) == 0:
            data = {
                "long": FIXED_LONG,
                "lat": FIXED_LAT,
                "token": "f36f1180-66f3-4b35-a6ec-34a85d17198f",
                **sensor_data
            }
        else:
            print("waiting for GPS...")
            gps_data = None
            while gps_data is None:
                gps_data = gps_readerV2.readGPS()  # Call function directly to get GPS data
                time.sleep(0.1)
 
            print(gps_data)
            print("GPS connection established")

            data = {
                "long": gps_data["longitude"],
                "lat": gps_data["latitude"],
                "token": "f36f1180-66f3-4b35-a6ec-34a85d17198f",
                **sensor_data 
            }

        if not q.empty():
            q.get_nowait()
        q.put(json.dumps(data))

        # Speichern, wenn SEND_SWITCH gedrückt ist
        dateiname = f"messung_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        print(dateiname)
        with open(os.path.join(DATEN_PFAD, dateiname), 'w') as f:
            json.dump(data, f, indent=4)

        files = sorted((os.path.join(DATEN_PFAD, f) for f in os.listdir(DATEN_PFAD) if f.endswith(".json")), key=os.path.getctime)
        if len(files) > MAX_FILES:
            os.remove(files[0])
        if GPIO.input(SEND_SWITCH) == 1:
            for f in os.listdir(DATEN_PFAD):
                p = os.path.join(DATEN_PFAD, f)
                if p.endswith(".json") and os.path.isfile(p):
                    try:
                        with open(p, "r", encoding="utf-8") as file:
                            r = urequests.post(URL, json=json.load(file))
                        if r.status_code == 201:
                            os.remove(p)
                            #print(f"{f} erfolgreich gesendet und gelöscht.")
                    except Exception as e:
                        print(f"Fehler bei {f}: {e}")
        time.sleep(MEASURE_DELAY)

# Threads starten
display_thread = threading.Thread(target=display, daemon=True)
messen_thread = threading.Thread(target=messen, daemon=True)

display_thread.start()
messen_thread.start()

try:
    while True:
        time.sleep(1)  # Hauptthread bleibt aktiv
except KeyboardInterrupt:
    print("Beende Threads...")
    stop_event.set()
    display_thread.join()
    messen_thread.join()
    print("Alle Threads gestoppt.")
