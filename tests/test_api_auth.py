"""Tests for API key authentication functionality"""
import pytest
from datetime import datetime, timezone


def test_api_key_model_creation():
    """Test that APIKey model can be created with required fields"""
    from models.api_key import APIKey
    
    key = APIKey(
        user_id=1,
        key_hash="abc123",
        key_prefix="onepay_live_abc12345",
        name="Test Key"
    )
    assert key.user_id == 1
    assert key.key_hash == "abc123"
    assert key.key_prefix == "onepay_live_abc12345"
    assert key.name == "Test Key"



def test_generate_api_key_format():
    """Test that generated API keys have the correct format"""
    from core.api_auth import generate_api_key
    
    key = generate_api_key()
    assert key.startswith("onepay_live_")
    assert len(key) == 76  # onepay_live_ (12) + 64 hex chars
    
    # Verify it's actually hex
    hex_part = key[12:]
    assert all(c in '0123456789abcdef' for c in hex_part)



def test_hash_api_key():
    """Test that API key hashing is consistent and secure"""
    from core.api_auth import hash_api_key
    
    key = "onepay_live_abc123"
    hash1 = hash_api_key(key)
    hash2 = hash_api_key(key)
    
    assert hash1 == hash2  # Consistent
    assert len(hash1) == 64  # SHA256 hex
    assert hash1 != key  # Actually hashed
    assert all(c in '0123456789abcdef' for c in hash1)  # Valid hex
