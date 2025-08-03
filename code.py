# KS0429 keyestudio TDS Meter
import time
import board
import busio
import analogio
import displayio
import i2cdisplaybus
from adafruit_thermistor import Thermistor
from adafruit_display_text import label
from adafruit_bitmap_font import bitmap_font
from adafruit_displayio_ssd1306 import SSD1306
import watchdog
import microcontroller
import neopixel
from random import randint

displayio.release_displays()

led = neopixel.NeoPixel(board.NEOPIXEL, 1)
led.brightness = 0.1  # 10% brightness
led.fill((0, 0, 255))  # initially blue

wdt = microcontroller.watchdog
wdt.timeout = 5
wdt.mode = watchdog.WatchDogMode.RESET  # RAISE or RESET

time.sleep(0.3)  # give oled time to boot
led.fill((222, 0, 0))  # RED indicates WDT set

# displayio.release_displays()
i2c = busio.I2C(board.IO1, board.IO2)
display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3C)
oled = SSD1306(display_bus, width=128, height=64, rotation=180)

# Make the display context
splash = displayio.Group()
oled.root_group = splash

oled_bitmap = displayio.Bitmap(128, 64, 1)
oled_palette = displayio.Palette(1)
oled_palette[0] = 0x000000  # Black screen

# Draw a label
text1 = "----"
text2 = "temp"
WHITE = 0xFFFFFF
font = bitmap_font.load_font("/fonts/spleen-12x24.bdf")

tds_text = label.Label(font=font, text=text1, color=WHITE, scale=2)
tds_text.anchor_point = (0.0, 0.0)  # point on text
tds_text.anchored_position = (0, 0)  # screen position

ppm_text = label.Label(font=font, text="ppm", color=WHITE, scale=1)
ppm_text.anchor_point = (1.0, 0.0)
ppm_text.anchored_position = (128, 0)  # screen position

therm_text = label.Label(font=font, text=text2, color=WHITE, scale=1)
therm_text.anchor_point = (0.0, 1.0)  # point on text
therm_text.anchored_position = (0, 64)  # screen position

for item in (tds_text, ppm_text, therm_text):
    splash.append(item)

# Constants for thermistor
SAMPLE_COUNT = 10
# SAMPLE_DELAY = 0.05  # seconds between samples
# READ_DELAY = 1.0  # seconds between average reports

# Setup thermistor
thermistor = Thermistor(board.IO8, 10800.0, 10000.0, 25.0, 3950.0, high_side=True)


def get_average_temp():
    temps_c = [thermistor.temperature for _ in range(SAMPLE_COUNT)]
    avg_c = sum(temps_c) / SAMPLE_COUNT
    avg_f = (avg_c * 1.8) + 32
    return avg_c, avg_f

# Configuration of TDS meter
TdsSensorPin = board.D5  # Analog input pin
VREF = 3.3  # CircuitPython typically uses 3.3V reference
SCOUNT = 30  # Number of samples for averaging

# Variables for TDS meter
analogBuffer = [0] * SCOUNT
analogBufferTemp = [0] * SCOUNT
analogBufferIndex = 0
copyIndex = 0
averageVoltage = 0.0
tdsValue = 0.0
avg_c = 25.0  # initial value for compensation

# Analog input setup
tds_sensor = analogio.AnalogIn(TdsSensorPin)

# Median filtering function
def getMedianNum(bArray, iFilterLen):
    bTab = bArray[:]  # Create a copy of the array
    for j in range(iFilterLen - 1):
        for i in range(iFilterLen - j - 1):
            if bTab[i] > bTab[i + 1]:
                bTemp = bTab[i]
                bTab[i] = bTab[i + 1]
                bTab[i + 1] = bTemp
    if (iFilterLen & 1) > 0:
        bTemp = bTab[(iFilterLen - 1) // 2]
    else:
        bTemp = (bTab[iFilterLen // 2] + bTab[iFilterLen // 2 - 1]) / 2
    return bTemp


# Main loop
analogSampleTimepoint = time.monotonic()
printTimepoint = time.monotonic()
led.fill((0, 28, 0))  # LED green

while True:
    if time.monotonic() - analogSampleTimepoint > 0.04:  # 40 milliseconds
        analogSampleTimepoint = time.monotonic()
        analogBuffer[analogBufferIndex] = tds_sensor.value  # read analog value
        analogBufferIndex += 1
        if analogBufferIndex == SCOUNT:
            analogBufferIndex = 0

    if time.monotonic() - printTimepoint > 1.0:  # >1 second
        printTimepoint = time.monotonic()

        # Convert analog reading to voltage
        averageVoltage = getMedianNum(analogBuffer, SCOUNT) * (
            VREF / 65535.0
        )  # 16 bit reading.

        # Temperature compensation
        compensationCoefficient = 1.0 + 0.02 * (avg_c - 25.0)
        compensationVoltage = averageVoltage / compensationCoefficient

        # Convert voltage to TDS value
        tdsValue = (
            133.42 * compensationVoltage * compensationVoltage * compensationVoltage
            - 255.86 * compensationVoltage * compensationVoltage
            + 857.39 * compensationVoltage
        ) * 0.5

        avg_c, avg_f = get_average_temp()
        print(f"Temperature: {avg_c:.1f}°C = {avg_f:.1f}°F")
        therm_text.text = f"{avg_f:.1f} °F"
        print(f"voltage: {averageVoltage:.2f} V = ", f"TDS Value: {tdsValue:.0f} ppm")
        tds_text.text = "{:.0f}".format(tdsValue)
        wdt.feed()  # feed the watchdog timer so it doesn't timeout
        led[0] = (randint(0, 255), randint(0, 255), randint(0, 255))
