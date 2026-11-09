# app/__init__.py
import os
from flask import Flask
from config import Config
from app.plugins import discover_plugins
from app.core.scheduler import init_scheduler
from app.blueprints.display_bp import display_bp
from app.blueprints.plugins_bp import plugins_bp
from app.blueprints.schedule_bp import schedule_bp
from app.blueprints.web_bp import web_bp


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure writable directories exist (created after privilege drop)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(app.root_path), "instance"), exist_ok=True)

    # Discover plugins and start persistent scheduler
    discover_plugins()
    init_scheduler(app.config["JOBSTORE_PATH"])

    # Register Flask Blueprints
    app.register_blueprint(display_bp)
    app.register_blueprint(plugins_bp)
    app.register_blueprint(schedule_bp)
    app.register_blueprint(web_bp)

    return app