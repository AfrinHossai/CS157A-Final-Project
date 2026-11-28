from datetime import datetime, timedelta, timezone

import pytest

from app import create_app
from app.errors import APIError
from app.validation import (
    RSVP_STATUSES,
    decode_cursor,
    encode_cursor,
    format_utc,
    json_body,
    page_cursor,
    page_window,
    parse_bool,
    parse_datetime,
    reject_unknown,
    require_email,
    require_enum,
    require_http_url,
    require_id,
    require_interval,
    require_password,
    require_str,
)


def _app():
    return create_app("testing")


def _raises(function, *args, **kwargs):
    with pytest.raises(APIError) as caught:
        function(*args, **kwargs)
    return caught.value


def test_json_body_requires_an_object():
    app = _app()
    with app.test_request_context("/register", method="POST", json=["nope"]):
        error = _raises(json_body)
    assert error.code == "INVALID_BODY"
    assert error.status == 400


def test_register_fields_reject_unknown_names():
    error = _raises(reject_unknown, {"name": "A", "role": "admin"}, {"name", "email", "password"})
    assert error.status == 400
    assert "role" in error.message
    assert "admin" not in error.message


def test_string_length_and_stripping():
    assert require_str({"name": "  Ada "}, "name", strip=True, min_len=1, max_len=5) == "Ada"
    short = _raises(require_str, {"name": " "}, "name", strip=True, min_len=1)
    long = _raises(require_str, {"name": "x" * 6}, "name", max_len=5)
    assert short.code == "VALIDATION_ERROR"
    assert long.code == "FIELD_TOO_LONG"


def test_email_is_trimmed_and_lowercased():
    assert require_email({"email": "  Ada@Example.EDU "}) == "ada@example.edu"
    error = _raises(require_email, {"email": "not-an-email"})
    assert error.status == 400


def test_password_keeps_spaces_and_enforces_bounds():
    assert require_password({"password": "correct horse"}) == "correct horse"
    error = _raises(require_password, {"password": "short"})
    assert error.status == 400
    assert "short" not in error.message


def test_enum_url_and_id():
    assert require_enum({"status": "going"}, "status", RSVP_STATUSES) == "going"
    enum_error = _raises(require_enum, {"status": "Going"}, "status", RSVP_STATUSES)
    assert enum_error.code == "INVALID_ENUM"
    assert require_http_url({"resource_url": "https://example.com/notes"}, "resource_url") == "https://example.com/notes"
    url_error = _raises(require_http_url, {"resource_url": "javascript:alert(1)"}, "resource_url")
    assert url_error.status == 400
    assert require_id({"course_id": 4}, "course_id") == 4
    id_error = _raises(require_id, {"course_id": True}, "course_id")
    assert id_error.status == 400


def test_timestamps_require_an_offset_and_convert_to_utc():
    parsed = parse_datetime("2026-05-01T12:30:00.100000-07:00", field="starts_at")
    assert parsed == datetime(2026, 5, 1, 19, 30, 0, 100000, tzinfo=timezone.utc)
    assert format_utc(parsed) == "2026-05-01T19:30:00.100000Z"
    assert format_utc(parse_datetime("2026-05-01T19:30:00Z", field="starts_at")) == "2026-05-01T19:30:00Z"
    naive = _raises(parse_datetime, "2026-05-01T19:30:00", field="starts_at")
    assert naive.status == 400


def test_session_interval_must_move_forward():
    start = datetime(2026, 5, 1, 19, 0, tzinfo=timezone.utc)
    error = _raises(require_interval, start, start)
    assert error.code == "INVALID_INTERVAL"
    assert error.status == 422
    require_interval(start, start + timedelta(seconds=1))


def test_page_window_defaults_and_bounds():
    app = _app()
    with app.test_request_context("/courses"):
        assert page_window() == (20, 0)
    with app.test_request_context("/courses?limit=100&offset=15"):
        assert page_window() == (100, 15)
    with app.test_request_context("/courses?limit=101"):
        error = _raises(page_window)
    assert error.status == 400


def test_before_cursor_carries_timestamp_and_id():
    moment = datetime(2026, 5, 1, 19, 30, 0, 100000, tzinfo=timezone.utc)
    token = encode_cursor(moment, 42)
    assert decode_cursor(token) == (moment, 42)
    app = _app()
    with app.test_request_context(f"/messages?before={token}"):
        assert page_cursor() == (moment, 42)
    with app.test_request_context("/messages"):
        assert page_cursor() is None
    error = _raises(decode_cursor, "42")
    assert error.status == 400
    assert "42" not in error.message


def test_query_bool():
    assert parse_bool(None, field="unread") is False
    assert parse_bool("true", field="unread") is True
    error = _raises(parse_bool, "yes", field="unread")
    assert error.status == 400
