import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

MATRIX_PROFILE = os.environ.get("MATRIX_PROFILE", "zero").lower()

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-matrix-secret-key")
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    IMAGES_FOLDER = os.path.join(UPLOAD_FOLDER, "images")
    SEQUENCES_FOLDER = os.path.join(UPLOAD_FOLDER, "sequences")
    FONTS_FOLDER = os.path.join(BASE_DIR, "fonts")
    PRESETS_FILE = os.path.join(BASE_DIR, "instance", "presets.json")
    JOBSTORE_PATH = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'jobs.sqlite')}"

    SERIAL_ENABLED = True
    SERIAL_PORT = "/dev/serial0"
    SERIAL_BAUD = 115200

    DROP_PRIVILEGES = True
    DROP_PRIV_USER = os.environ.get("SUDO_USER", "daemon")
    DROP_PRIV_GROUP = os.environ.get("SUDO_USER", "daemon")

    # --- Hardware Profiles ---
    if MATRIX_PROFILE == "large":
        # Pi 3 / Pi 4 running 2x2 grid (128x64)
        MATRIX_ROWS = 32
        MATRIX_COLS = 64
        MATRIX_CHAIN_LENGTH = 4
        MATRIX_PARALLEL = 1
        MATRIX_PIXEL_MAPPER = "U-mapper"
        MATRIX_HARDWARE_MAPPING = "adafruit-hat"
        MATRIX_BRIGHTNESS = 80
        MATRIX_GPIO_SLOWDOWN = 2
        MOCK_WIDTH = 128
        MOCK_HEIGHT = 64
    else:
        # Pi Zero W running your current setup
        MATRIX_ROWS = 32
        MATRIX_COLS = 64
        MATRIX_CHAIN_LENGTH = 1
        MATRIX_PARALLEL = 1
        MATRIX_PIXEL_MAPPER = ""
        #MATRIX_HARDWARE_MAPPING = "adafruit-hat"
        MATRIX_HARDWARE_MAPPING = "regular"
        MATRIX_BRIGHTNESS = 80
        MATRIX_GPIO_SLOWDOWN = 1
        MOCK_WIDTH = 64
        MOCK_HEIGHT = 32