from flask import abort, jsonify, make_response


def api_error(code, message, status):
    abort(make_response(jsonify({"error": {"code": code, "message": message}}), status))
