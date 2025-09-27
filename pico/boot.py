import board
import busio
import adafruit_bmp3xx
import adafruit_scd4x
import adafruit_hdc302x
import apds9960
from DFRobot_Oxygen import *
import time

# Initializing i2c ports
scl = board.GP1
sda = board.GP0
i2c = busio.I2C(scl,sda)
# Starting sensors at i2c ports
scd4x = adafruit_scd4x.SCD4X(i2c)
scd4x.start_periodic_measurement()
hdc302x = adafruit_hdc302x.HDC302x(i2c)
bmp3xx = adafruit_bmp3xx.BMP3XX_I2C(i2c)
bmp3xx.sea_level_pressure = 1019
prox = apds9960.APDS9960(i2c)

# Further initializations for distance and oxygen sensors
prox.enable_proximity = True
ADDRESS_3    = 0x73
COLLECT_NUMBER   = 10              # collect number, the collection range is 1-100
IIC_MODE         = 0x01            # default use IIC1
oxygen = DFRobot_Oxygen_IIC(IIC_MODE, ADDRESS_3)

# Enable uart connection
uart = busio.UART(board.GP16, board.GP17, baudrate=9600, timeout=0)
# setting up intervals to send UART buffer every 5 seconds
UPDATE_INTERVAL = 5.0
last_time_sent = 0

while True:
    # Send sensor values only every UPDATE_INTERVAL seconds.
    now = time.monotonic()
    if now - last_time_sent >= UPDATE_INTERVAL:
        uart.write(bytes(f"<p{bmp3xx.pressure}>", "ascii"))
        uart.write(bytes(f"<t{hdc302x.temperature}>", "ascii"))
        uart.write(bytes(f"<h{hdc302x.relative_humidity}>", "ascii"))
        uart.write(bytes(f"<x{prox.proximity}>", "ascii"))
        uart.write(bytes(f"<d{scd4x.CO2}>", "ascii"))
        uart.write(bytes(f"<o{oxygen.get_oxygen_data(COLLECT_NUMBER)}>", "ascii"))

        
        print("Sending sensor values from Pico 1!")
        last_time_sent = now
