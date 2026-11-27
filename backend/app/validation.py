from flask import request

from .errors import api_error


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        api_error("INVALID_BODY", "Request body must be a JSON object.", 400)
    return data


def require_str(data, field):
    value = data.get(field)
    if not isinstance(value, str):
        api_error("VALIDATION_ERROR", f"'{field}' is required.", 400)
    return value
