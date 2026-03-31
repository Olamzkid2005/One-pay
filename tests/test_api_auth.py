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
