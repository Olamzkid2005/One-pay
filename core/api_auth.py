"""API key authentication module for machine-to-machine access"""
import secrets


def generate_api_key() -> str:
    """Generate a new API key with secure random bytes
    
    Returns:
        str: API key in format 'onepay_live_<64-hex-chars>' (76 chars total)
    """
    random_bytes = secrets.token_bytes(32)
    hex_string = random_bytes.hex()
    return f"onepay_live_{hex_string}"
