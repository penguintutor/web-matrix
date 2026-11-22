# web-matrix
Web management for a Raspberry Pi RGB Matrix display

## Web Interface

The web interface is accessed through port 5000. 
If connecting from the Raspberry Pi then use http://localhost:5000 . From another computer replace localhost with the IP address of the Raspberry Pi.

For more details about the project please see the [PenguinTutor RPi Matrix Christmas Advent Calendar](https://www.penguintutor.com/projects/pi-matrix-advent). 

## Hardware

This is designed to run on a Raspberry Pi and control a HUB75 Matrix LED display. It can be hardwired directly (although needs the Raspberry Pi to be located close to the matrix as the matrix is designed for 5V compared with 3.3V from the Raspberry Pi. Details of how to wire directly are at: [PenguinTutor RPi Matrix wiring page](https://www.penguintutor.com/projects/rpi-matrix-rgbled). 

It can also make use of the Adafruit Matrix bonnet which includes logic level shifting. Note that the bonnet does have different wiring and so needs a configuration change.

This can run on a standard Rasbperry Pi 1, such as the Pi Zero W. However note that performance may be sluggish and install will take a long time to compile the appropriate libraries.


## Install

```bash
mkdir ~/venv
python -m venv ~/venv/pixels --system-site-packages
sudo apt-get install python-dev-is-python3 python3-pil cython3
source ~/venv/pixels/bin/activate
pip install --upgrade Cython
pip install git+https://github.com/hzeller/rpi-rgb-led-matrix
pip install Flask Pillow APScheduler SQLAlchemy waitress

git clone https://github.com/penguintutor/web-matrix.git
```

Note there will be some warnings during install of the pre-requisites. This is due to the use of system packages for some of the libraries to simplify install. 

### Automatic Startup (systemd)

To configure the daemon to start automatically on boot, run the setup script from your normal user account (not as root):

```bash
sudo ./setup/install-service.sh

This script will also disable audio on the Raspberry Pi by disabling snd_bcm2835. This is a pre-requisite of the matrix library that the software uses. You will need to restart the Raspberry Pi for this to take effect.
```

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
