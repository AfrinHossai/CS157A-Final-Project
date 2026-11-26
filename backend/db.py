import os
from pathlib import Path

from dotenv import dotenv_values
from flask import g
from mysql.connector import pooling

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

_dotenv = {k: v for k, v in dotenv_values(ENV_FILE).items() if v is not None}


def setting(name, default=None):
    if name in _dotenv:
        return _dotenv[name]
    if name in os.environ:
        return os.environ[name]
    if default is not None:
        return default
    raise RuntimeError(f"{name} is not set in {ENV_FILE} or the environment.")


pool = pooling.MySQLConnectionPool(
    pool_name="app",
    pool_size=5,
    host=setting("DB_HOST", "127.0.0.1"),
    port=int(setting("DB_PORT", "3306")),
    user=setting("DB_USER"),
    password=setting("DB_PASSWORD"),
    database=setting("DB_NAME"),
)

def get_db():
    if "db" not in g:
        g.db = pool.get_connection()
    return g.db

def close_db(exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()

def init_app(app):
    app.teardown_appcontext(close_db)
