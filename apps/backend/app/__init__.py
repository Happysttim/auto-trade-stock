from __future__ import annotations

import atexit

from flask import Flask
from flask_cors import CORS

from .api import api_blueprint
from .config import load_settings
from .runtime import build_container


def create_app() -> Flask:
    settings = load_settings()
    container = build_container(settings)

    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    CORS(app)
    app.extensions["container"] = container
    app.register_blueprint(api_blueprint)

    container.scheduler.start()
    atexit.register(container.shutdown)
    return app
