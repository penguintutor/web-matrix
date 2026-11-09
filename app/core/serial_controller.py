import logging
import threading
import time
from app.core.presets import preset_manager
from app.core.matrix_engine import matrix_engine

logger = logging.getLogger(__name__)

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    logger.warning("pyserial not installed. Physical Pico controller disabled.")


class SerialController:
    def __init__(self):
        self.port = "/dev/serial0"
        self.baud = 115200
        self._stop_event = threading.Event()
        self._ser = None
        self._thread = None

    def start(self, port: str, baud: int = 115200) -> None:
        if not SERIAL_AVAILABLE:
            return
        self.port = port
        self.baud = baud
        self._thread = threading.Thread(
            target=self._serial_loop, name="PicoSerialThread", daemon=True
        )
        self._thread.start()

    def _serial_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                with serial.Serial(self.port, self.baud, timeout=1.0) as ser:
                    self._ser = ser
                    logger.info(f"Connected to physical controller on {self.port}")
                    # Immediately push preset list on connection
                    self.send_preset_list()

                    while not self._stop_event.is_set():
                        raw = ser.readline()
                        if not raw:
                            continue
                        line = raw.decode("utf-8", errors="ignore").strip()
                        if line:
                            self._handle_command(line)
            except Exception as exc:
                logger.debug(f"Serial wait ({self.port}): {exc}")
                time.sleep(3.0)

    def _handle_command(self, cmd: str) -> None:
        logger.info(f"Pico Serial Command: {cmd}")
        if cmd == "LIST":
            self.send_preset_list()
        elif cmd.startswith("RUN:"):
            try:
                idx = int(cmd.split(":", 1)[1])
                name = preset_manager.trigger_preset(idx)
                if name:
                    self._write_line(f"ACTIVE:{name}")
                else:
                    self._write_line("ERR:Invalid Index")
            except ValueError:
                self._write_line("ERR:Bad Format")
        elif cmd == "CLEAR":
            matrix_engine.clear()
            self._write_line("ACTIVE:Cleared")
        elif cmd == "STATUS":
            self._write_line(f"ACTIVE:{matrix_engine.active_label}")

    def send_preset_list(self) -> None:
        """Formats presets as PRESETS:0:NameA|1:NameB|2:NameC"""
        items = [f"{i}:{p['name']}" for i, p in enumerate(preset_manager.presets)]
        self._write_line("PRESETS:" + "|".join(items))
        self._write_line(f"ACTIVE:{matrix_engine.active_label}")

    def _write_line(self, text: str) -> None:
        if self._ser and self._ser.is_open:
            try:
                self._ser.write((text + "\n").encode("utf-8"))
            except Exception as exc:
                logger.error(f"Serial write error: {exc}")


serial_controller = SerialController()