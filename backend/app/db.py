import threading

from flask import g
from mysql.connector import pooling

from .config import setting

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
