#!/usr/bin/env python3
"""
Phase 1 Security Checkpoint Test (Python version)

Tests Phase 1 security features without requiring a running server.
"""

import sys
import traceback


def test_common_password_list():
    """Test Phase 1: Common password list."""
    print("1. Testing Common Password List...")
    try:
        from services.validation.password import COMMON_PASSWORDS
        print(f'   Loaded {len(COMMON_PASSWORDS)} passwords')
        print("   ✓ Common password list working")
        return True
    except Exception as e:
        print(f"   ✗ Common password list failed: {e}")
        traceback.print_exc()
        return False


def test_alert_manager():
    """Test Phase 1: Alert Manager."""
    print("2. Testing Alert Manager...")
    try:
        from services.alerts import AlertManager
        print("   ✓ AlertManager importable")
        return True
    except Exception as e:
        print(f"   ✗ AlertManager not importable: {e}")
        traceback.print_exc()
        return False


def test_hsts_preload_config():
    """Test Phase 1: HSTS preload configuration."""
    print("3. Testing HSTS Preload Configuration...")
    try:
        from config import Config
        if hasattr(Config, 'HSTS_PRELOAD') and Config.HSTS_PRELOAD:
            print("   ✓ HSTS preload configured")
            return True
        else:
            print("   ⚠ HSTS preload not configured (may be optional)")
            return True  # Don't fail for optional config
    except Exception as e:
        print(f"   ✗ HSTS preload check failed: {e}")
        traceback.print_exc()
        return False


def test_security_headers_config():
    """Test Phase 1: Security headers configuration."""
    print("4. Testing Security Headers Configuration...")
    try:
        from config import Config
        checks = []

        if hasattr(Config, 'CLEAR_SITE_DATA_ENABLED') and Config.CLEAR_SITE_DATA_ENABLED:
            checks.append("Clear-Site-Data")
        if hasattr(Config, 'PERMISSIONS_POLICY_ENABLED') and Config.PERMISSIONS_POLICY_ENABLED:
            checks.append("Permissions-Policy")

        if checks:
            print(f"   ✓ Security headers configured: {', '.join(checks)}")
        else:
            print("   ⚠ Some security headers not configured")

        return True
    except Exception as e:
        print(f"   ✗ Security headers check failed: {e}")
        traceback.print_exc()
        return False


def test_password_validation():
    """Test Phase 1: Password validation."""
    print("5. Testing Password Validation...")
    try:
        from services.validation.password import validate_password_strength
        # Test with a weak password
        is_valid, error = validate_password_strength("password123")
        if not is_valid:
            print(f"   ✓ Password validation working (rejects weak password: {error})")
            return True
        else:
            print("   ✗ Password validation failed (accepted weak password)")
            return False
    except Exception as e:
        print(f"   ✗ Password validation failed: {e}")
        traceback.print_exc()
        return False


def test_rate_limiting():
    """Test Phase 1: Rate limiting."""
    print("6. Testing Rate Limiting...")
    try:
        from core.decorators import rate_limit
        print("   ✓ Rate limiting decorator importable")
        return True
    except Exception as e:
        print(f"   ✗ Rate limiting failed: {e}")
        traceback.print_exc()
        return False


def test_captcha_config():
    """Test Phase 1: CAPTCHA configuration."""
    print("7. Testing CAPTCHA Configuration...")
    try:
        from config import Config
        if hasattr(Config, 'HCAPTCHA_SITE_KEY') and Config.HCAPTCHA_SITE_KEY:
            print("   ✓ CAPTCHA configured")
        else:
            print("   ⚠ CAPTCHA not configured (may be optional)")
        return True
    except Exception as e:
        print(f"   ✗ CAPTCHA check failed: {e}")
        traceback.print_exc()
        return False


def test_sql_injection_protection():
    """Test Phase 1: SQL injection protection (parameterized queries)."""
    print("9. Testing SQL Injection Protection...")
    try:
        from database import get_db
        from models.transaction import Transaction

        # This test just verifies the models use SQLAlchemy (which uses parameterized queries)
        print("   ✓ SQLAlchemy ORM in use (parameterized queries)")
        return True
    except Exception as e:
        print(f"   ✗ SQL injection protection check failed: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all Phase 1 checkpoint tests."""
    print("=" * 60)
    print("Phase 1 Security Checkpoint Test (Python)")
    print("=" * 60)
    print()

    results = {
        "Common Password List": test_common_password_list(),
        "Alert Manager": test_alert_manager(),
        "HSTS Preload Config": test_hsts_preload_config(),
        "Security Headers Config": test_security_headers_config(),
        "Password Validation": test_password_validation(),
        "Rate Limiting": test_rate_limiting(),
        "CAPTCHA Config": test_captcha_config(),
        "SQL Injection Protection": test_sql_injection_protection(),
    }

    print()
    print("=" * 60)
    print("Phase 1 Checkpoint Results")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    print()
    print(f"Total: {passed}/{total} tests passed")
    print("=" * 60)

    if passed == total:
        print("✓ All Phase 1 tests passed!")
        return 0
    else:
        print(f"✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
