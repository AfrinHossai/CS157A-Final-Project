import os
from datetime import timedelta
from pathlib import Path

from dotenv import dotenv_values

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

_dotenv = {k: v for k, v in dotenv_values(ENV_FILE).items() if v is not None}


def setting(name, default=None, allow_blank=False):
    for source in (_dotenv, os.environ):
        value = source.get(name)
        if value is not None and (value != "" or allow_blank):
            return value
    if default is not None:
        return default
    raise RuntimeError(f"{name} is not set in {ENV_FILE} or the environment.")


class Config:
    SECRET_KEY = None
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = False
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    MAX_CONTENT_LENGTH = 1_048_576
    PROPAGATE_EXCEPTIONS = False
    CSRF_ENABLED = True

    @staticmethod
    def load_secret(app):
        if not app.config.get("SECRET_KEY"):
            app.config["SECRET_KEY"] = setting("SECRET_KEY")


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key"
    CSRF_ENABLED = False


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


CONFIGS = {
    "development": DevelopmentConfig,
    "test": TestingConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
