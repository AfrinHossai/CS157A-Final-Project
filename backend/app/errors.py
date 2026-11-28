import logging
import re

from flask import jsonify
from mysql.connector import errorcode
from mysql.connector.errors import Error as MySQLError
from werkzeug.exceptions import HTTPException

log = logging.getLogger(__name__)

# Session-interval CHECKs must use a constraint name ending in `_interval`.
_INTERVAL_CONSTRAINT = re.compile(r"_interval$", re.IGNORECASE)
_CONSTRAINT_NAME = re.compile(r"constraint ['`]([^'`]+)['`]", re.IGNORECASE)
_KEY_NAME = re.compile(r"for key ['`]([^'`]+)['`]", re.IGNORECASE)
_ERROR_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}")

# code -> (HTTP status, public message)
ERRORS = {
    "INVALID_BODY": (400, "Request body must be a JSON object."),
    "VALIDATION_ERROR": (400, "The request is invalid."),
    "INVALID_ENUM": (400, "A field has an unsupported value."),
    "FIELD_TOO_LONG": (400, "A field is too long."),
    "UNAUTHENTICATED": (401, "You must be logged in."),
    "INVALID_CREDENTIALS": (401, "Incorrect email or password."),
    "INVALID_CREDENTIAL_TAG": (401, "Your session is no longer valid."),
    "FORBIDDEN": (403, "You do not have permission to do that."),
    "NOT_A_MEMBER": (403, "You are not a member of this group."),
    "NOT_LEADER": (403, "Only the current leader can do that."),
    "NOT_OWNER": (403, "You do not own this item."),
    "CSRF_FAILED": (403, "The security token is missing or invalid."),
    "NOT_FOUND": (404, "The requested item was not found."),
    "METHOD_NOT_ALLOWED": (405, "That method is not allowed."),
    "EMAIL_TAKEN": (409, "An account with that email already exists."),
    "DUPLICATE": (409, "That value already exists."),
    "DUPLICATE_MEMBERSHIP": (409, "You are already a member of this group."),
    "FOREIGN_KEY": (409, "That action conflicts with related data."),
    "INVALID_INTERVAL": (422, "The session end must be later than the start."),
    "TEMPORARILY_UNAVAILABLE": (503, "The operation could not be completed. Try again."),
    "BUSINESS_RULE": (400, "The request could not be completed."),
    "INTERNAL_ERROR": (500, "Something went wrong."),
}

_HTTP_ERRORS = {
    400: "INVALID_BODY",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    413: "VALIDATION_ERROR",
}


class APIError(Exception):
    def __init__(self, code, message, status):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def api_error(code, message=None, status=None):
    default_status, default_message = ERRORS.get(
        code, (400, ERRORS["BUSINESS_RULE"][1])
    )
    raise APIError(code, message or default_message, status or default_status)


def error_response(code, message, status):
    body = jsonify({"error": {"code": code, "message": message}})
    return body, status


def map_db_error(exc):
    errno = getattr(exc, "errno", None)
    sqlstate = getattr(exc, "sqlstate", None)
    if sqlstate == "45000" or errno == errorcode.ER_SIGNAL_EXCEPTION:
        return _from_signal(exc)
    if errno == errorcode.ER_DUP_ENTRY:
        key = _named(_KEY_NAME, exc)
        code = "EMAIL_TAKEN" if key and key.split(".")[-1].lower() == "email" else "DUPLICATE"
        return _known(code)
    if errno in (
        errorcode.ER_ROW_IS_REFERENCED,
        errorcode.ER_ROW_IS_REFERENCED_2,
        errorcode.ER_NO_REFERENCED_ROW,
        errorcode.ER_NO_REFERENCED_ROW_2,
    ):
        return _known("FOREIGN_KEY")
    if errno == errorcode.ER_DATA_TOO_LONG:
        return _known("FIELD_TOO_LONG")
    if errno == errorcode.ER_CHECK_CONSTRAINT_VIOLATED:
        name = _named(_CONSTRAINT_NAME, exc) or ""
        code = "INVALID_INTERVAL" if _INTERVAL_CONSTRAINT.search(name) else "INVALID_ENUM"
        return _known(code)
    if errno in (errorcode.ER_LOCK_DEADLOCK, errorcode.ER_LOCK_WAIT_TIMEOUT):
        return _known("TEMPORARILY_UNAVAILABLE")
    if errno == errorcode.ER_BAD_NULL_ERROR:
        return _known("VALIDATION_ERROR")
    log.error("unmapped database error errno=%s sqlstate=%s", errno, sqlstate)
    return _known("INTERNAL_ERROR")


def register_error_handlers(app):
    app.register_error_handler(APIError, _handle_api_error)
    app.register_error_handler(MySQLError, _handle_db_error)
    app.register_error_handler(HTTPException, _handle_http_error)
    app.register_error_handler(Exception, _handle_unexpected)


def _handle_api_error(err):
    return error_response(err.code, err.message, err.status)


def _handle_db_error(err):
    mapped = map_db_error(err)
    return error_response(mapped.code, mapped.message, mapped.status)


def _handle_http_error(err):
    code = _HTTP_ERRORS.get(err.code, "INTERNAL_ERROR")
    status, message = ERRORS[code]
    if err.code == 413:
        message = "Request body is too large."
        status = 400
    return error_response(code, message, status)


def _handle_unexpected(err):
    if isinstance(err, (APIError, MySQLError, HTTPException)):
        raise err
    log.exception("unhandled error")
    status, message = ERRORS["INTERNAL_ERROR"]
    return error_response("INTERNAL_ERROR", message, status)


def _known(code):
    status, message = ERRORS[code]
    return APIError(code, message, status)


def _from_signal(exc):
    text = getattr(exc, "msg", None) or ""
    token = text.strip().split(":", 1)[0].strip()
    if _ERROR_CODE.fullmatch(token) and token in ERRORS:
        return _known(token)
    log.error("unmapped signal errno=%s sqlstate=%s", getattr(exc, "errno", None), getattr(exc, "sqlstate", None))
    return _known("BUSINESS_RULE")


def _named(pattern, exc):
    text = getattr(exc, "msg", None) or ""
    match = pattern.search(text)
    return match.group(1) if match else None
