import re
from datetime import timedelta

from flask import Blueprint, abort, jsonify, make_response, request, session
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from mysql.connector import errorcode
from mysql.connector.errors import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_db, setting

bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")
login_manager = LoginManager()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
NAME_MAX = 150
EMAIL_MAX = 254
PASSWORD_MIN = 8
PASSWORD_MAX = 128

_DUMMY_HASH = generate_password_hash("not-a-real-password")


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
    app.register_blueprint(bp)


def _error(code, message, status):
    abort(make_response(jsonify({"error": {"code": code, "message": message}}), status))


@login_manager.user_loader
def load_user(user_id):
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None
    row = _find_user_by_id(user_id)
    return User(row) if row else None


@login_manager.unauthorized_handler
def unauthorized():
    _error("UNAUTHENTICATED", "You must be logged in.", 401)


def normalize_email(email):
    return email.strip().lower()


def _json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        _error("INVALID_BODY", "Request body must be a JSON object.", 400)
    return data


def _require_str(data, field):
    value = data.get(field)
    if not isinstance(value, str):
        _error("VALIDATION_ERROR", f"'{field}' is required.", 400)
    return value


def _find_user_by_email(email):
    with get_db().cursor(dictionary=True) as cur:
        cur.execute(
            "SELECT user_id, name, email, password_hash FROM `User` WHERE email = %s",
            (email,),
        )
        return cur.fetchone()


def _find_user_by_id(user_id):
    with get_db().cursor(dictionary=True) as cur:
        cur.execute(
            "SELECT user_id, name, email FROM `User` WHERE user_id = %s",
            (user_id,),
        )
        return cur.fetchone()


def _log_in(user, remember=False):
    session.clear()
    session.permanent = True
    login_user(user, remember=remember)


@bp.post("/register")
def register():
    data = _json_body()
    name = _require_str(data, "name").strip()
    email = normalize_email(_require_str(data, "email"))
    password = _require_str(data, "password")

    if not 1 <= len(name) <= NAME_MAX:
        _error("VALIDATION_ERROR", f"Name must be 1-{NAME_MAX} characters.", 400)
    if len(email) > EMAIL_MAX or not EMAIL_RE.match(email):
        _error("VALIDATION_ERROR", "Email address is not valid.", 400)
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        _error(
            "VALIDATION_ERROR",
            f"Password must be {PASSWORD_MIN}-{PASSWORD_MAX} characters.",
            400,
        )

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO `User` (name, email, password_hash) VALUES (%s, %s, %s)",
                (name, email, generate_password_hash(password)),
            )
            user_id = cur.lastrowid
        conn.commit()
    except IntegrityError as err:
        conn.rollback()
        if err.errno == errorcode.ER_DUP_ENTRY:
            _error("EMAIL_TAKEN", "An account with that email already exists.", 409)
        raise

    user = User({"user_id": user_id, "name": name, "email": email})
    _log_in(user)
    return jsonify({"user": user.to_dict()}), 201


@bp.post("/login")
def login():
    data = _json_body()
    email = normalize_email(_require_str(data, "email"))
    password = _require_str(data, "password")
    remember = data.get("remember") is True

    row = _find_user_by_email(email)
    password_ok = check_password_hash(row["password_hash"] if row else _DUMMY_HASH, password)
    if row is None or not password_ok:
        _error("INVALID_CREDENTIALS", "Incorrect email or password.", 401)

    user = User(row)
    _log_in(user, remember=remember)
    return jsonify({"user": user.to_dict()})


@bp.post("/logout")
def logout():
    logout_user()
    session.clear()
    return "", 204


@bp.get("/me")
@login_required
def me():
    return jsonify({"user": current_user.to_dict()})
