from flask import Flask

from . import auth, db
from .routes import auth as auth_routes


def create_app():
    app = Flask(__name__)
    db.init_app(app)
    auth.init_app(app)
    app.register_blueprint(auth_routes.bp)

    @app.route("/")
    def root():
        return "Hello from Flask!"

    return app
