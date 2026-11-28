from datetime import timedelta

from flask import session
from flask_login import LoginManager, UserMixin, login_user

from .config import setting
from .errors import api_error
from .repositories import users

login_manager = LoginManager()


class User(UserMixin):
    def __init__(self, row):
        self.user_id = row["user_id"]
        self.name = row["name"]
        self.email = row["email"]

    def get_id(self):
        return str(self.user_id)

    def to_dict(self):
        return {"user_id": self.user_id, "name": self.name, "email": self.email}


def init_app(app):
    app.config.update(
        SECRET_KEY=setting("SECRET_KEY"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
        REMEMBER_COOKIE_DURATION=timedelta(days=30),
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_SAMESITE="Lax",
    )
    login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None
    row = users.find_by_id(user_id)
    return User(row) if row else None


@login_manager.unauthorized_handler
def unauthorized():
    api_error("UNAUTHENTICATED", "You must be logged in.", 401)


def log_in(user, remember=False):
    session.clear()
    session.permanent = True
    login_user(user, remember=remember)
