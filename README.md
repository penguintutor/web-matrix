# web-matrix
Web management for a Raspberry Pi RGB Matrix display


## Install

mkdir ~/venv
python -m venv ~/venv/pixels --system-site-packages
sudo apt-get install python-dev-is-python3 python3-pil cython3
source ~/venv/pixels/bin/activate
pip install --upgrade Cython
pip install git+https://github.com/hzeller/rpi-rgb-led-matrix
pip install Flask Pillow APScheduler SQLAlchemy waitress


## Enable /dev/serial0 on the PiZero

If using Hardware UART on GPIO 14/15, make sure the Linux serial login shell is disabled and the UART hardware is enabled on the Pi Zero W:

Run sudo raspi-config → Interface Options → Serial Port.

Select No for "Would you like a login shell to be accessible over serial?"

Select Yes for "Would you like the serial port hardware to be enabled?" and reboot.



## Using a Pico Controller

The MicroPython script (pic_controller directory) runs on a Raspberry Pi Pico. It drives a 128x64 I2C SSD1306 OLED display and supports both a Rotary Encoder (or Up/Down buttons) on GP14/GP15 and a Select button on GP16.

Pico Pinout Summary
I2C OLED (SSD1306): SDA → GP4, SCL → GP5, VCC → 3V3, GND → GND

Controls (Internal Pull-Ups Enabled—wire switches to GND):

GP14: Rotary Encoder CLK or Up Button

GP15: Rotary Encoder DT or Down Button

GP16: Rotary Encoder SW or Select / Activate Button

GP17: Optional Refresh / Clear Button (Hold to Clear, Click to Refresh list)

UART to Pi Zero: GP0 (TX) → Pi Zero GPIO 15 (RX), GP1 (RX) → Pi Zero GPIO 14 (TX), GND → GND

The MicroPython library ssd1306.py also needs to be installed on the Pico