import base64
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

from flask import request

from .errors import APIError, api_error

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_OFFSET = re.compile(r"(?:Z|[+-]\d{2}:\d{2})$")
_POSITIVE_INT = re.compile(r"[1-9][0-9]*$")
_DIGITS = re.compile(r"[0-9]+$")

NAME_MAX = 150
EMAIL_MAX = 254
PASSWORD_MIN = 8
PASSWORD_MAX = 128
URL_MAX = 2048
DEFAULT_LIMIT = 20
MAX_LIMIT = 100
MAX_OFFSET = 1_000_000_000

RSVP_STATUSES = frozenset({"going", "tentative", "declined"})
RESOURCE_TYPES = frozenset({"notes", "link", "guide", "practice_material"})

REGISTER_FIELDS = frozenset({"name", "email", "password"})
LOGIN_FIELDS = frozenset({"email", "password"})
PROFILE_FIELDS = frozenset({"name", "email", "current_password"})
PASSWORD_FIELDS = frozenset({"current_password", "new_password"})


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        api_error("INVALID_BODY", "Request body must be a JSON object.", 400)
    return data


def reject_unknown(data, allowed):
    extra = sorted(set(data) - set(allowed))
    if extra:
        api_error("VALIDATION_ERROR", f"Unexpected fields: {', '.join(extra)}.", 400)


def require_str(data, field, *, min_len=None, max_len=None, strip=False):
    value = data.get(field)
    if not isinstance(value, str):
        api_error("VALIDATION_ERROR", f"'{field}' is required.", 400)
    if strip:
        value = value.strip()
    if min_len is not None and len(value) < min_len:
        api_error("VALIDATION_ERROR", f"'{field}' must be at least {min_len} characters.", 400)
    if max_len is not None and len(value) > max_len:
        api_error("FIELD_TOO_LONG", f"'{field}' must be at most {max_len} characters.", 400)
    return value


def optional_str(data, field, *, max_len=None, strip=True):
    if field not in data or data[field] is None:
        return None
    return require_str(data, field, max_len=max_len, strip=strip)


def require_email(data, field="email"):
    value = require_str(data, field, strip=True, min_len=1, max_len=EMAIL_MAX).lower()
    if not EMAIL_RE.fullmatch(value):
        api_error("VALIDATION_ERROR", "Email address is not valid.", 400)
    return value


def require_password(data, field="password"):
    value = require_str(data, field)
    if not PASSWORD_MIN <= len(value) <= PASSWORD_MAX:
        api_error(
            "VALIDATION_ERROR",
            f"Password must be {PASSWORD_MIN}-{PASSWORD_MAX} characters.",
            400,
        )
    return value


def require_enum(data, field, allowed):
    value = require_str(data, field)
    if value not in allowed:
        api_error("INVALID_ENUM", f"'{field}' is not a supported value.", 400)
    return value


def require_http_url(data, field, *, max_len=URL_MAX):
    value = require_str(data, field, min_len=1, max_len=max_len)
    parts = urlsplit(value)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
    ):
        api_error("VALIDATION_ERROR", f"'{field}' must be an http or https URL.", 400)
    return value


def require_id(data, field):
    value = data.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        api_error("VALIDATION_ERROR", f"'{field}' must be a positive integer.", 400)
    return value


def parse_datetime(value, *, field):
    if not isinstance(value, str) or "T" not in value or _OFFSET.search(value) is None:
        api_error("VALIDATION_ERROR", f"'{field}' must be a timezone-aware ISO 8601 timestamp.", 400)
    text = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        api_error("VALIDATION_ERROR", f"'{field}' must be a timezone-aware ISO 8601 timestamp.", 400)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        api_error("VALIDATION_ERROR", f"'{field}' must be a timezone-aware ISO 8601 timestamp.", 400)
    return parsed.astimezone(timezone.utc)


def format_utc(value):
    utc = value.astimezone(timezone.utc)
    if utc.microsecond:
        rendered = utc.strftime("%Y-%m-%dT%H:%M:%S.%f")
    else:
        rendered = utc.strftime("%Y-%m-%dT%H:%M:%S")
    return f"{rendered}Z"


def require_datetime(data, field):
    if field not in data or data[field] is None:
        api_error("VALIDATION_ERROR", f"'{field}' is required.", 400)
    return parse_datetime(data[field], field=field)


def optional_datetime(data, field):
    if field not in data or data[field] is None:
        return None
    return parse_datetime(data[field], field=field)


def require_interval(starts, ends):
    if ends <= starts:
        api_error("INVALID_INTERVAL")


def parse_limit(value):
    return _bounded_int(value, field="limit", default=DEFAULT_LIMIT, minimum=1, maximum=MAX_LIMIT)


def parse_offset(value):
    return _bounded_int(value, field="offset", default=0, minimum=0, maximum=MAX_OFFSET)


def page_window():
    return parse_limit(request.args.get("limit")), parse_offset(request.args.get("offset"))


def encode_cursor(moment, row_id):
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("cursor timestamp must be timezone-aware")
    if isinstance(row_id, bool) or not isinstance(row_id, int) or row_id < 1:
        raise ValueError("cursor id must be a positive integer")
    payload = f"{format_utc(moment)}\n{row_id}".encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_cursor(token):
    if not isinstance(token, str) or not token:
        api_error("VALIDATION_ERROR", "The before cursor is invalid.", 400)
    padded = token + ("=" * (-len(token) % 4))
    try:
        text = base64.b64decode(padded, altchars=b"-_", validate=True).decode()
        stamp, row_text = text.split("\n")
        if _POSITIVE_INT.fullmatch(row_text) is None:
            raise ValueError
        moment = parse_datetime(stamp, field="before")
    except APIError:
        api_error("VALIDATION_ERROR", "The before cursor is invalid.", 400)
    except (ValueError, UnicodeError):
        api_error("VALIDATION_ERROR", "The before cursor is invalid.", 400)
    return moment, int(row_text)


def page_cursor():
    raw = request.args.get("before")
    if raw is None:
        return None
    return decode_cursor(raw)


def parse_bool(value, *, field, default=False):
    if value is None:
        return default
    if value == "true":
        return True
    if value == "false":
        return False
    api_error("VALIDATION_ERROR", f"'{field}' must be true or false.", 400)


def _bounded_int(value, *, field, default, minimum, maximum):
    if value is None:
        return default
    if not isinstance(value, str) or _DIGITS.fullmatch(value.strip()) is None:
        api_error("VALIDATION_ERROR", f"'{field}' must be an integer.", 400)
    number = int(value.strip())
    if number < minimum or number > maximum:
        api_error(
            "VALIDATION_ERROR",
            f"'{field}' must be from {minimum} to {maximum}.",
            400,
        )
    return number
