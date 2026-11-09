# run_daemon.py
import logging
import signal
import sys
from waitress import serve
from config import Config
from app.core.matrix_engine import matrix_engine
from app.core.scheduler import scheduler
from app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def handle_exit(signum, frame):
    logging.info("Shutting down Matrix Daemon...")
    if scheduler.running:
        scheduler.shutdown(wait=False)
    matrix_engine.shutdown()
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    # 1. Initialize hardware FIRST as root (automatically drops privileges to DROP_PRIV_USER)
    matrix_engine.init_hardware(Config)

    # 2. Initialize Flask app, SQLite jobstore, and plugins as unprivileged user
    flask_app = create_app(Config)

    # 3. Serve via Waitress (single process, multi-threaded)
    logging.info("Starting web interface on http://0.0.0.0:5000")
    serve(flask_app, host="0.0.0.0", port=5000, threads=4)