import os
import threading
from pathlib import Path

from dotenv import dotenv_values
from flask import g
from mysql.connector import pooling

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


_pool = None
_pool_lock = threading.Lock()


def _get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = pooling.MySQLConnectionPool(
                    pool_name="app",
                    pool_size=int(setting("DB_POOL_SIZE", "5")),
                    host=setting("DB_HOST", "127.0.0.1"),
                    port=int(setting("DB_PORT", "3306")),
                    user=setting("DB_USER"),
                    password=setting("DB_PASSWORD", allow_blank=True),
                    database=setting("DB_NAME"),
                )
    return _pool


def get_db():
    if "db" not in g:
        g.db = _get_pool().get_connection()
    return g.db

def close_db(exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()

def init_app(app):
    app.teardown_appcontext(close_db)
