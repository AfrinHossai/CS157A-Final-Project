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
from ..validation import (
    LOGIN_FIELDS,
    NAME_MAX,
    REGISTER_FIELDS,
    json_body,
    reject_unknown,
    require_email,
    require_password,
    require_str,
)

bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")

_DUMMY_HASH = generate_password_hash("not-a-real-password")


@bp.post("/register")
def register():
    data = json_body()
    reject_unknown(data, REGISTER_FIELDS)
    name = require_str(data, "name", strip=True, min_len=1, max_len=NAME_MAX)
    email = require_email(data)
    password = require_password(data)

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
    reject_unknown(data, LOGIN_FIELDS)
    email = require_email(data)
    password = require_str(data, "password")

    row = users.find_by_email(email)
    password_ok = check_password_hash(row["password_hash"] if row else _DUMMY_HASH, password)
    if row is None or not password_ok:
        api_error("INVALID_CREDENTIALS", "Incorrect email or password.", 401)

    user = User(row)
    log_in(user)
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
