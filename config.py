import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-matrix-secret-key")
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    IMAGES_FOLDER = os.path.join(UPLOAD_FOLDER, "images")   
    SEQUENCES_FOLDER = os.path.join(UPLOAD_FOLDER, "sequences")
    FONTS_FOLDER = os.path.join(BASE_DIR, "fonts")  # Place .bdf fonts (e.g. 10x20.bdf) here
    PRESETS_FILE = os.path.join(BASE_DIR, "instance", "presets.json")
    JOBSTORE_PATH = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'jobs.sqlite')}"

    # --- Serial Physical Controller (Pico) ---
    SERIAL_ENABLED = True
    SERIAL_PORT = "/dev/serial0"  # Use "/dev/ttyACM0" if connecting Pico via USB
    SERIAL_BAUD = 115200

    # --- RGB Matrix Hardware Configuration ---
    MATRIX_ROWS = 32
    MATRIX_COLS = 64
    MATRIX_CHAIN_LENGTH = 1
    MATRIX_PARALLEL = 1
    # Select adafruit / regular depending upon hardware
    #MATRIX_HARDWARE_MAPPING = "adafruit-hat"  # or "regular", "adafruit-hat-pwm"
    MATRIX_HARDWARE_MAPPING = "regular"
    MATRIX_BRIGHTNESS = 80
    MATRIX_GPIO_SLOWDOWN = 4                  # Adjust (1-4) for Pi 3/4/5 stability

    # --- Privilege Dropping Configuration ---
    # After RGBMatrix initializes hardware as root, drop privileges to daemon user
    DROP_PRIVILEGES = True
    DROP_PRIV_USER = os.environ.get("SUDO_USER", "daemon")
    DROP_PRIV_GROUP = os.environ.get("SUDO_USER", "deamon")