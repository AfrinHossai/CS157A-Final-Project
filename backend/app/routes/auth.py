import re

from flask import Blueprint, jsonify, session
from flask_login import current_user, login_required, logout_user
from mysql.connector import errorcode
from mysql.connector.errors import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from .. import csrf
from ..auth import User, log_in
from ..db import get_db
from ..errors import api_error
from ..repositories import users
from ..validation import json_body, require_str

bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
NAME_MAX = 150
EMAIL_MAX = 254
PASSWORD_MIN = 8
PASSWORD_MAX = 128

_DUMMY_HASH = generate_password_hash("not-a-real-password")


def normalize_email(email):
    return email.strip().lower()


@bp.post("/register")
def register():
    data = json_body()
    name = require_str(data, "name").strip()
    email = normalize_email(require_str(data, "email"))
    password = require_str(data, "password")

    if not 1 <= len(name) <= NAME_MAX:
        api_error("VALIDATION_ERROR", f"Name must be 1-{NAME_MAX} characters.", 400)
    if len(email) > EMAIL_MAX or not EMAIL_RE.match(email):
        api_error("VALIDATION_ERROR", "Email address is not valid.", 400)
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        api_error(
            "VALIDATION_ERROR",
            f"Password must be {PASSWORD_MIN}-{PASSWORD_MAX} characters.",
            400,
        )

    try:
        user_id = users.create(name, email, generate_password_hash(password))
    except IntegrityError as err:
        get_db().rollback()
        if err.errno == errorcode.ER_DUP_ENTRY:
            api_error("EMAIL_TAKEN", "An account with that email already exists.", 409)
        raise

    user = User({"user_id": user_id, "name": name, "email": email})
    log_in(user)
    return jsonify({"user": user.to_dict()}), 201


@bp.post("/login")
def login():
    data = json_body()
    email = normalize_email(require_str(data, "email"))
    password = require_str(data, "password")
    remember = data.get("remember") is True

    row = users.find_by_email(email)
    password_ok = check_password_hash(row["password_hash"] if row else _DUMMY_HASH, password)
    if row is None or not password_ok:
        api_error("INVALID_CREDENTIALS", "Incorrect email or password.", 401)

    user = User(row)
    log_in(user, remember=remember)
    return jsonify({"user": user.to_dict()})


@bp.post("/logout")
def logout():
    logout_user()
    session.clear()
    csrf.rotate_token()
    return "", 204


@bp.get("/me")
@login_required
def me():
    return jsonify({"user": current_user.to_dict()})
