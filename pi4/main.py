#!/usr/bin/env python3
import serial
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import requests
import myapi
import threading
import traceback
# import gpiozero
# import board
# import busio
import time
import RPi.GPIO as GPIO
from utils import save_data, assign_sensor
from picamera2 import Picamera2
# from picamera2.outputs import FfmpegOutput
# from picamera2.encoders import H264Encoder
import csv
import datetime
import os
app = Flask(__name__)
CORS(app)
uart = serial.Serial("/dev/serial0", baudrate=9600, timeout=5)  # "/dev/serial0" is used for Raspberry Pi's UART (14TX/15RX)
print("UART Serial Port Opened: ", uart.name)

picam2 = Picamera2()

computer_ip = "127.0.0.1"
computer_port = "5000"
telemetry_route = "telemetry"
CSV_FILENAME = 'temp_log.csv'

# LIVE DATA, UPDATING EVERY OTHER SECOND'ISH
telemetry = {
    "Pressure": 0,
    "Temperature": 0,
    "Humidity": 0,
    "Oxygen": 0,
    "Carbon Monoxide": 0,
    "Carbon Dioxide": 0,
    "Proximity": 0,
}

# LEFT ITEM IN PAIR IS TARGET VALUE; RIGHT ITEM IS THE PLUS/MINUS
# CURRENT VALUES ARE PLACEHOLDERS
payload_configuration = {
    "Pressure": 0,
    "Temperature": 0,
    "Humidity": 0,
    "Oxygen": 0,
    "Carbon Monoxide": 0,
    "Carbon Dioxide": 0,
    "Light": [255,255,255],
    "Brightness": 1.0,
    "Humidity Tolerance": 0, #Dehumidifer 3-way-valve
    "Low Temp Tolerance": 0, #Cooling pump F 
    "High Temp Tolerance": 0,
}

control_states = {
    'cooling_pump': False,
}

# Sensor types
PRESSURE = 1
TEMPERATURE = 2
HUMIDITY = 3
OXYGEN = 4
CO = 5
CO2 = 6
PROXIMITY = 7
NONE = 0
Sensor = NONE

COOL_PIN = 17
VALVE_CW_PIN = 27
VALVE_CCW_PIN = 22

tolerance_check_interval = 10
last_time_sent = 0
message_started = False
message = []
new_config = True

def send_to_pico(message: str):
    message = f"{message}\n"
    print("sent ", message)
    uart.write(message.encode('utf-8'))
    return

def turn_humidity_valve(clockwise=True):
	if clockwise:
		GPIO.output(VALVE_CW_PIN, GPIO.LOW)
		time.sleep(10)
		GPIO.output(VALVE_CW_PIN,GPIO.HIGH)
	else:
		GPIO.output(VALVE_CW_PIN,GPIO.LOW)
		GPIO.output(VALVE_CCW_PIN,GPIO.LOW)
		time.sleep(10)
		GPIO.output(VALVE_CW_PIN,GPIO.HIGH)
		GPIO.output(VALVE_CCW_PIN,GPIO.HIGH)

def append_row(path, timestamp, temp):
    """Append a single row and flush immediately."""
    with open(path, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, temp])
        print("wrote: ", timestamp, temp)
        f.flush()

def switch_relay():
    global telemetry
    global payload_configuration
    global new_config
    states = {
	"humid": False,
    "cold": False,
    "hot": False,
    }

    try:
        while True:
            # IMPORTANT: HIGH MEANS OFF AND LOW MEANS ON (SO DUMB BUT IT WORKS)
            # CHANGE AIR PATH WHEN HUMIDITY IS HIGH
            if (telemetry["Humidity"] > int(payload_configuration["Humidity Tolerance"])) and not states["humid"]:
                print("humidity too high! switching to desiccant pathway...")
                # TURN HUMIDITY VALVE TO DESSICANT PATH
                turn_humidity_valve(False)
                states["humid"] = True
            # CHANGE AIR PATH WHEN HUMIDITY IS OK
            elif (telemetry["Humidity"] < int(payload_configuration["Humidity Tolerance"])) and states["humid"]:
                print("humidity too low! switching to non-desiccant pathway...")
                # TURN HUMIDITY VALVE TO NON-DESSICANT PATH
                turn_humidity_valve(True)
                states["humid"] = False
            
            # TURN ON/OFF COOLING PUMP WHEN TEMPERATURE EXCEEDS HIGH TOLERANCE
            if (telemetry["Temperature"] > int(payload_configuration["High Temp Tolerance"])) and not states["hot"]:
                GPIO.output(COOL_PIN, GPIO.LOW)
                states["hot"] = True
            elif (telemetry["Temperature"] < int(payload_configuration["High Temp Tolerance"])) and states["hot"]:
                GPIO.output(COOL_PIN, GPIO.HIGH)
                states["hot"] = False
        
            # SEND MESSAGE TO HEATING PICO WHEN TEMPERATURE IS BELOW LOW TOLERANCE
            if (telemetry["Temperature"] < int(payload_configuration["Low Temp Tolerance"])) and not states["cold"]:
                # SEND MESSAGE TO PICO TO START HEATING PROCESS
                send_to_pico("H:Y")
                # WHEN STATE IS COLD, DO NOT CONTINUE TO SEND MESSAGES TO PICO
                states["cold"] = True
            elif (telemetry["Temperature"] > int(payload_configuration["Low Temp Tolerance"])) and states["cold"]:
                # SEND MESSAGE TO PICO TO STOP HEATING PROCESS
                send_to_pico("H:N")
                # WHEN STATE IS NOT COLD, DO NOT CONTINUE TO SEND MESSAGES TO PICO
                states["cold"] = False
            
            if new_config:
                r, g, b = payload_configuration.get('Light', [255,255,255])
                brightness = payload_configuration.get('Brightness', 1.0)
                send_to_pico(f"L:r={r},g={g},b={b},br={brightness}")
                print(f"Sent L:r={r},g={g},b={b},br={brightness} to pico")
                new_config = False
            #with open(CSV_FILENAME, mode='a', newline='') as csvfile:
            #    writer = csv.DictWriter(csvfile, fieldnames=telemetry.keys())
            #    writer.writerow(telemetry)
            #    print("wrote to csv")

            time.sleep(20)
    except Exception as e:
        print(f"[switch_relay] error:", e)
        traceback.print_exc()

def sensor_loop():
    global telemetry
    global uart
    global last_time_sent
    global interval
    global now
    Sensor = NONE
    message_started = False
    message = []
    label_map = {
        	'p': 'Pressure',
        	't': 'Temperature',
        	'h': 'Humidity',
        	'o': 'Oxygen',
        	'm': 'Carbon Monoxide',
        	'd': 'Carbon Dioxide',
        	'x': 'Proximity',
    }
    try:
        while True:
            print(telemetry)
            now = int(time.monotonic())
            raw = uart.readline().decode('ascii').strip()
            if not raw:
                continue

            label = raw[0]
            value_str = raw[1:]
            try:
                value = float(value_str)
            except ValueError:
                print(f"Could not parse float from '{value_str}'")
                continue

            key = label_map.get(label)
            if key:
                telemetry[key] = value
           #     print(f"{key} updated to {value}")
            else:
                print(f"Unknown label '{label}' with value {value}")

    except Exception as e:
        print(f"[sensor_loop] error:", e)
        traceback.print_exc()
            


@app.route('/telemetry', methods=['GET'])
def send_telemetry_api():
    return telemetry

valve=False
@app.route('/test', methods=['POST'])
def activate_test_relays():
    global valve
    global control_states
    data = request.get_json()
    component = data.get('title')
    print(f"Received test command: {component}")
    if component == '3-way':
         # CHANGE AIR PATH WHEN HUMIDITY IS HIGH
        print("turning valve...")
        if not valve:
            # TURN HUMIDITY VALVE TO DESSICANT PATH
            turn_humidity_valve()
            valve = True
        # CHANGE AIR PATH WHEN HUMIDITY IS OK
        else:
            # TURN HUMIDITY VALVE TO NON-DESSICANT PATH
            turn_humidity_valve(False)
            valve = False
    if component == 'Cooler Pump':
        if control_states['cooling_pump']:
            GPIO.output(COOL_PIN, GPIO.HIGH)
            control_states['cooling_pump'] = False
        else:
            GPIO.output(COOL_PIN, GPIO.LOW)
            control_states['cooling_pump'] = True


    return jsonify(status="ok",
        received=component), 200

@app.route('/configure', methods=['POST'])
def configure_payload():
    global payload_configuration
    global new_config
    data = request.get_json()
    payload_configuration = data.get('payload_configuration')
    print("payload config changed to: \n", payload_configuration)
    new_config = True
    
    return jsonify(status="ok", received=payload_configuration), 200
    

@app.route('/video_feed')
def send_video_feed_api():
    return Response(myapi.generate_video_frames(picam2),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    video_config = picam2.create_video_configuration(
        main={"format": "RGB888", "size": (640, 480)}
    )
    picam2.configure(video_config)
    picam2.start()
    
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(17, GPIO.OUT, initial=GPIO.HIGH)
    GPIO.setup(22, GPIO.OUT, initial=GPIO.HIGH)
    GPIO.setup(27, GPIO.OUT, initial=GPIO.HIGH)
    GPIO.setup(5, GPIO.OUT, initial=GPIO.HIGH)

    if not os.path.exists(CSV_FILENAME):
        with open(CSV_FILENAME, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=telemetry.keys())
            writer.writeheader()
            print(f"Created new CSV with header at '{CSV_FILENAME}'")
    
    try:
        threading.Thread(target=sensor_loop, daemon=True).start()
        threading.Thread(target=switch_relay, daemon=True).start()
        app.run(host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\n Interrupted by user.")
    finally:
        GPIO.cleanup()
        picam2.stop()

        picam2.close()
        uart.close()


