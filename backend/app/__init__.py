from flask import Flask

from . import auth, csrf, db
from .config import CONFIGS
from .errors import register_error_handlers
from .routes import register_blueprints


def create_app(config="development"):
    app = Flask(__name__)
    if isinstance(config, type):
        selected = config
    else:
        try:
            selected = CONFIGS[config]
        except KeyError:
            raise ValueError(f"Unknown configuration {config!r}.") from None
    app.config.from_object(selected)
    selected.load_secret(app)
    db.init_app(app)
    auth.init_app(app)
    csrf.init_app(app)
    register_blueprints(app)
    register_error_handlers(app)
    return app
