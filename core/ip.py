"""
OnePay — Client IP extraction.
Single implementation used by all blueprints.
"""
from flask import request
from config import Config


def client_ip() -> str:
    """
    Extract the real client IP.
    Respects X-Forwarded-For only when TRUST_X_FORWARDED_FOR is enabled
    (i.e. you control the reverse proxy that sets this header).
    """
    if Config.TRUST_X_FORWARDED_FOR:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"
