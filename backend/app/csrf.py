import hmac
import secrets

from flask import Blueprint, current_app, g, jsonify, request, session

from .errors import api_error

SESSION_KEY = "_csrf_token"
HEADER_NAME = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

bp = Blueprint("csrf", __name__, url_prefix="/api/v1")

_exempt_views = set()


def get_token():
    token = session.get(SESSION_KEY)
    if not token:
        token = rotate_token()
    return token


def rotate_token():
    token = secrets.token_urlsafe(32)
    session[SESSION_KEY] = token
    g.csrf_token_rotated = True
    return token


def exempt(view):
    _exempt_views.add(f"{view.__module__}.{view.__name__}")
    return view


def _is_exempt():
    view = current_app.view_functions.get(request.endpoint)
    return view is not None and f"{view.__module__}.{view.__name__}" in _exempt_views


def _protect():
    if not current_app.config.get("CSRF_ENABLED", True):
        return
    if request.method in SAFE_METHODS or _is_exempt():
        return
    expected = session.get(SESSION_KEY)
    sent = request.headers.get(HEADER_NAME)
    if not expected or not sent or not hmac.compare_digest(expected, sent):
        api_error("CSRF_FAILED")


def _expose_rotated_token(response):
    if g.get("csrf_token_rotated"):
        response.headers[HEADER_NAME] = session[SESSION_KEY]
    return response


@bp.get("/csrf")
def csrf_token():
    return jsonify({"csrf_token": get_token()})


def init_app(app):
    app.before_request(_protect)
    app.after_request(_expose_rotated_token)
    app.register_blueprint(bp)
