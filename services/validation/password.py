"""
OnePay — Password strength validator.
"""

import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Base common passwords (will be expanded from file)
COMMON_PASSWORDS = {
    "password",
    "password123",
    "password1",
    "password12",
    "password1234",
    "admin",
    "admin123",
    "admin1234",
    "administrator",
    "12345678",
    "123456789",
    "1234567890",
    "123123",
    "123321",
    "qwerty",
    "qwerty123",
    "qwerty1234",
    "qwertyuiop",
    "welcome",
    "welcome123",
    "welcome1",
    "letmein",
    "letmein123",
    "monkey",
    "monkey123",
    "dragon",
    "dragon123",
    "master",
    "master123",
    "abc123",
    "abc123456",
    "password!",
    "password123!",
    "admin!",
    "admin123!",
    "p@ssw0rd",
    "p@ssword",
    "passw0rd",
    "pass123",
    "pass1234",
    "changeme",
    "changeme123",
    "default",
    "default123",
    "root",
    "root123",
    "toor",
    "test",
    "test123",
    "guest",
    "guest123",
    "user",
    "user123",
    "demo",
    "demo123",
}


def load_common_passwords_from_file(filepath: str) -> int:
    """Load common passwords from file."""
    global COMMON_PASSWORDS
    try:
        with open(filepath, encoding="utf-8") as f:
            loaded = {line.strip().lower() for line in f if line.strip()}
        COMMON_PASSWORDS.update(loaded)
        logger.info("Loaded %d common passwords from %s", len(loaded), filepath)
        return len(loaded)
    except FileNotFoundError:
        logger.warning("Common passwords file not found: %s", filepath)
        return 0
    except Exception as e:
        logger.error("Error loading common passwords: %s", e)
        return 0


# Load common passwords from file on module import
COMMON_PASSWORDS_FILE = os.getenv("COMMON_PASSWORDS_FILE", "services/validation/common_passwords.txt")
if os.path.exists(COMMON_PASSWORDS_FILE):
    load_count = load_common_passwords_from_file(COMMON_PASSWORDS_FILE)
    logger.info("Loaded %d additional common passwords from %s", load_count, COMMON_PASSWORDS_FILE)


def is_common_password(password: str) -> bool:
    """Check if password is in common password list."""
    return password.lower() in COMMON_PASSWORDS


def validate_password_strength(password: str) -> tuple[bool, Optional[str]]:
    """
    Validate password strength against security requirements.

    Returns:
        (is_valid, error_message)
        - is_valid: True if password meets all requirements
        - error_message: None if valid, error description if invalid
    """
    if len(password) < 12:
        return False, "Password must be at least 12 characters"

    if len(password) > 1000:
        return False, "Password is too long (max 1000 characters)"

    if not re.search(r"[a-z]", password):
        return False, "Password must contain lowercase letters"

    if not re.search(r"[A-Z]", password):
        return False, "Password must contain uppercase letters"

    if not re.search(r"[0-9]", password):
        return False, "Password must contain numbers"

    if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/~`]', password):
        return False, "Password must contain special characters"

    if is_common_password(password):
        return False, "This password is too common. Please choose a stronger password."

    lower_pass = password.lower()
    for i in range(len(lower_pass) - 2):
        if ord(lower_pass[i + 1]) == ord(lower_pass[i]) + 1 and ord(lower_pass[i + 2]) == ord(lower_pass[i]) + 2:
            return False, "Password contains sequential characters"

    for i in range(len(password) - 2):
        if password[i] == password[i + 1] == password[i + 2]:
            return False, "Password contains too many repeated characters"

    return True, None


def load_common_passwords_from_file(filepath: str) -> int:
    """Load common passwords from file."""
    global COMMON_PASSWORDS
    try:
        with open(filepath, encoding="utf-8") as f:
            loaded = {line.strip().lower() for line in f if line.strip()}
        COMMON_PASSWORDS.update(loaded)
        logger.info("Loaded %d common passwords from %s", len(loaded), filepath)
        return len(loaded)
    except FileNotFoundError:
        logger.warning("Common passwords file not found: %s", filepath)
        return 0
    except Exception as e:
        logger.error("Error loading common passwords: %s", e)
        return 0
