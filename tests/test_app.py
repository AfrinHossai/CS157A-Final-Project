from datetime import timedelta

from mysql.connector import errorcode
from mysql.connector.errors import DatabaseError, IntegrityError

from app import create_app
from app.config import ProductionConfig
from app.errors import map_db_error


def _client():
    return create_app("testing").test_client()


def test_testing_config_sets_session_cookies():
    app = create_app("testing")

    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["SESSION_COOKIE_SECURE"] is False
    assert app.config["PERMANENT_SESSION_LIFETIME"] == timedelta(days=7)
    assert app.config["REMEMBER_COOKIE_HTTPONLY"] is True
    assert app.config["REMEMBER_COOKIE_SAMESITE"] == "Lax"
    assert app.config["MAX_CONTENT_LENGTH"] == 1_048_576
    assert "auth" in app.blueprints


def test_production_config_marks_cookies_secure():
    class ProductionForTest(ProductionConfig):
        SECRET_KEY = "prod-test-secret"

    app = create_app(ProductionForTest)

    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["REMEMBER_COOKIE_SECURE"] is True


def test_unknown_route_is_json():
    response = _client().get("/missing")

    assert response.status_code == 404
    assert response.get_json() == {
        "error": {"code": "NOT_FOUND", "message": "The requested item was not found."}
    }


def test_login_required_is_json_401():
    response = _client().get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "UNAUTHENTICATED"


def test_malformed_json_is_400():
    response = _client().post(
        "/api/v1/auth/login",
        data="{",
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_BODY"


def test_oversized_body_is_400():
    app = create_app("testing")
    app.config["MAX_CONTENT_LENGTH"] = 16
    response = app.test_client().post(
        "/api/v1/auth/login",
        data="{" + ("x" * 40) + "}",
        content_type="application/json",
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "x" * 40 not in response.get_data(as_text=True)


def test_database_errors_use_the_status_table():
    cases = [
        (IntegrityError(msg="Duplicate entry 'a@b.c' for key 'User.email'", errno=errorcode.ER_DUP_ENTRY), "EMAIL_TAKEN", 409, "a@b.c"),
        (IntegrityError(msg="Duplicate entry '1-2' for key 'GroupMember.group_id'", errno=errorcode.ER_DUP_ENTRY), "DUPLICATE", 409, "1-2"),
        (IntegrityError(msg="Cannot add or update a child row", errno=errorcode.ER_NO_REFERENCED_ROW_2), "FOREIGN_KEY", 409, None),
        (IntegrityError(msg="Cannot delete or update a parent row", errno=errorcode.ER_ROW_IS_REFERENCED_2), "FOREIGN_KEY", 409, None),
        (DatabaseError(msg="Data too long for column 'name'", errno=errorcode.ER_DATA_TOO_LONG), "FIELD_TOO_LONG", 400, "name"),
        (DatabaseError(msg="Check constraint 'chk_rsvp_status' is violated.", errno=errorcode.ER_CHECK_CONSTRAINT_VIOLATED), "INVALID_ENUM", 400, "chk_rsvp_status"),
        (DatabaseError(msg="Check constraint 'chk_study_session_interval' is violated.", errno=errorcode.ER_CHECK_CONSTRAINT_VIOLATED), "INVALID_INTERVAL", 422, "chk_study_session_interval"),
        (DatabaseError(msg="Deadlock found", errno=errorcode.ER_LOCK_DEADLOCK), "TEMPORARILY_UNAVAILABLE", 503, "Deadlock"),
        (DatabaseError(msg="NOT_A_MEMBER", errno=errorcode.ER_SIGNAL_EXCEPTION, sqlstate="45000"), "NOT_A_MEMBER", 403, None),
        (DatabaseError(msg="SELECT secret FROM User", errno=errorcode.ER_SIGNAL_EXCEPTION, sqlstate="45000"), "BUSINESS_RULE", 400, "SELECT"),
    ]

    for exc, code, status, hidden in cases:
        mapped = map_db_error(exc)
        assert mapped.code == code
        assert mapped.status == status
        if hidden:
            assert hidden not in mapped.message
