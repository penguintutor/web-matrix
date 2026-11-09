import logging
import threading
from PIL import Image
from app.core.tasks import DisplayTask, ClearTask

logger = logging.getLogger(__name__)

try:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions
    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False
    logger.warning("rgbmatrix bindings not found. Running in software mock mode.")


class MatrixEngine:
    """
    Thread-safe singleton managing the RGBMatrix hardware and VSync render loop.
    """

    def __init__(self):
        self.matrix = None
        self.canvas = None
        self.width = 64
        self.height = 32

        self._lock = threading.Lock()
        self._new_task_event = threading.Event()
        self._stop_event = threading.Event()
        self._pending_task: DisplayTask | None = None
        self._worker_thread: threading.Thread | None = None

    def init_hardware(self, config_obj) -> None:
        """
        Must be called FIRST while the process still has root privileges.
        After RGBMatrix(options) completes, root privileges are dropped if configured.
        """
        self.width = config_obj.MATRIX_COLS * config_obj.MATRIX_CHAIN_LENGTH
        self.height = config_obj.MATRIX_ROWS * config_obj.MATRIX_PARALLEL

        if HARDWARE_AVAILABLE:
            options = RGBMatrixOptions()
            options.rows = config_obj.MATRIX_ROWS
            options.cols = config_obj.MATRIX_COLS
            options.chain_length = config_obj.MATRIX_CHAIN_LENGTH
            options.parallel = config_obj.MATRIX_PARALLEL
            options.hardware_mapping = config_obj.MATRIX_HARDWARE_MAPPING
            options.brightness = config_obj.MATRIX_BRIGHTNESS
            options.gpio_slowdown = config_obj.MATRIX_GPIO_SLOWDOWN

            # Configure privilege dropping so Flask runs as unprivileged user
            options.drop_privileges = config_obj.DROP_PRIVILEGES
            if config_obj.DROP_PRIV_USER:
                options.drop_priv_user = config_obj.DROP_PRIV_USER
            if config_obj.DROP_PRIV_GROUP:
                options.drop_priv_group = config_obj.DROP_PRIV_GROUP

            self.matrix = RGBMatrix(options=options)
            self.canvas = self.matrix.CreateFrameCanvas()
            logger.info(f"Initialized RGBMatrix ({self.width}x{self.height})")
        else:
            logger.info(f"Mock Matrix initialized ({self.width}x{self.height})")

        # Start the background render daemon thread
        self._worker_thread = threading.Thread(
            target=self._render_loop, name="MatrixRenderThread", daemon=True
        )
        self._worker_thread.start()

    def set_task(self, task: DisplayTask) -> None:
        """Thread-safe method called by Flask routes or APScheduler to switch displays."""
        with self._lock:
            self._pending_task = task
            self._new_task_event.set()  # Immediately wakes the render thread

    def clear(self) -> None:
        self.set_task(ClearTask())

    def shutdown(self) -> None:
        self._stop_event.set()
        self._new_task_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        if self.matrix:
            self.matrix.Clear()

    def _render_loop(self) -> None:
        active_task: DisplayTask | None = None

        while not self._stop_event.is_set():
            # 1. Check if a new task was pushed
            if self._new_task_event.is_set():
                with self._lock:
                    active_task = self._pending_task
                    self._pending_task = None
                    self._new_task_event.clear()

                if active_task is not None:
                    try:
                        active_task.setup(self.width, self.height)
                    except Exception as exc:
                        logger.error(f"Error setting up display task: {exc}", exc_info=True)
                        active_task = None

            # 2. If no task is active, wait until one arrives
            if active_task is None:
                self._new_task_event.wait()
                continue

            # 3. Render the next frame of the active task
            try:
                frame, delay = active_task.render_next_frame()
                if frame is not None:
                    self._push_to_hardware(frame)
            except Exception as exc:
                logger.error(f"Error rendering frame: {exc}", exc_info=True)
                active_task = None
                continue

            # 4. Wait for next frame timing (or wake immediately if a new task arrives)
            if delay > 0:
                self._new_task_event.wait(timeout=delay)
            else:
                # Static image: sleep indefinitely until interrupted by a new task
                self._new_task_event.wait()

    def _push_to_hardware(self, image: Image.Image) -> None:
        if HARDWARE_AVAILABLE and self.matrix and self.canvas:
            self.canvas.SetImage(image)
            self.canvas = self.matrix.SwapOnVSync(self.canvas)
        else:
            logger.debug(f"[MOCK DISPLAY] Rendered frame {image.size}")


# Singleton instance imported by Blueprints and Scheduler
matrix_engine = MatrixEngine()