"""
OnePay — Shared JSON response helpers.
Imported by all blueprints — no circular imports.
"""
from flask import jsonify


def error(message: str, code: str, status: int):
    """Return a standard error JSON response."""
    return jsonify({"success": False, "message": message, "error_code": code}), status


def rate_limited():
    return error("Too many requests — please wait before trying again", "RATE_LIMITED", 429)


def unauthenticated():
    return error("Authentication required", "UNAUTHENTICATED", 401)
