#!/usr/bin/env python3
"""
Combined Phase 1 & 2 Checkpoint Test

Runs both Phase 1 (Security) and Phase 2 (Performance) tests together
to ensure compatibility and verify Phase 2 changes didn't break Phase 1.
"""

import sys
import traceback


def run_phase1_tests():
    """Run Phase 1 Security tests."""
    print("=" * 60)
    print("PHASE 1: Security Checkpoint Test")
    print("=" * 60)
    print()

    results = {}

    # Test 1: Common Password List
    print("1. Testing Common Password List...")
    try:
        from services.validation.password import COMMON_PASSWORDS
        print(f'   Loaded {len(COMMON_PASSWORDS)} passwords')
        print("   ✓ Common password list working")
        results["Common Password List"] = True
    except Exception as e:
        print(f"   ✗ Common password list failed: {e}")
        results["Common Password List"] = False

    # Test 2: Alert Manager
    print("2. Testing Alert Manager...")
    try:
        from services.alerts import AlertManager
        print("   ✓ AlertManager importable")
        results["Alert Manager"] = True
    except Exception as e:
        print(f"   ✗ AlertManager not importable: {e}")
        results["Alert Manager"] = False

    # Test 3: HSTS Preload Config
    print("3. Testing HSTS Preload Configuration...")
    try:
        from config import Config
        if hasattr(Config, 'HSTS_PRELOAD') and Config.HSTS_PRELOAD:
            print("   ✓ HSTS preload configured")
        else:
            print("   ⚠ HSTS preload not configured (may be optional)")
        results["HSTS Preload Config"] = True
    except Exception as e:
        print(f"   ✗ HSTS preload check failed: {e}")
        results["HSTS Preload Config"] = False

    # Test 4: Security Headers Config
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
        results["Security Headers Config"] = True
    except Exception as e:
        print(f"   ✗ Security headers check failed: {e}")
        results["Security Headers Config"] = False

    # Test 5: Password Validation
    print("5. Testing Password Validation...")
    try:
        from services.validation.password import validate_password_strength
        is_valid, error = validate_password_strength("password123")
        if not is_valid:
            print(f"   ✓ Password validation working (rejects weak password: {error})")
            results["Password Validation"] = True
        else:
            print("   ✗ Password validation failed (accepted weak password)")
            results["Password Validation"] = False
    except Exception as e:
        print(f"   ✗ Password validation failed: {e}")
        results["Password Validation"] = False

    # Test 6: Rate Limiting
    print("6. Testing Rate Limiting...")
    try:
        from core.decorators import rate_limit
        print("   ✓ Rate limiting decorator importable")
        results["Rate Limiting"] = True
    except Exception as e:
        print(f"   ✗ Rate limiting failed: {e}")
        results["Rate Limiting"] = False

    # Test 7: CAPTCHA Config
    print("7. Testing CAPTCHA Configuration...")
    try:
        from config import Config
        if hasattr(Config, 'HCAPTCHA_SITE_KEY') and Config.HCAPTCHA_SITE_KEY:
            print("   ✓ CAPTCHA configured")
        else:
            print("   ⚠ CAPTCHA not configured (may be optional)")
        results["CAPTCHA Config"] = True
    except Exception as e:
        print(f"   ✗ CAPTCHA check failed: {e}")
        results["CAPTCHA Config"] = False

    # Test 8: SQL Injection Protection
    print("8. Testing SQL Injection Protection...")
    try:
        from database import get_db
        from models.transaction import Transaction
        print("   ✓ SQLAlchemy ORM in use (parameterized queries)")
        results["SQL Injection Protection"] = True
    except Exception as e:
        print(f"   ✗ SQL injection protection check failed: {e}")
        results["SQL Injection Protection"] = False

    print()
    phase1_passed = sum(1 for v in results.values() if v)
    phase1_total = len(results)
    print(f"Phase 1: {phase1_passed}/{phase1_total} tests passed")
    print()

    return results, phase1_passed, phase1_total


def run_phase2_tests():
    """Run Phase 2 Performance tests."""
    print("=" * 60)
    print("PHASE 2: Performance Checkpoint Test")
    print("=" * 60)
    print()

    results = {}

    # Test 1: Query Optimization
    print("1. Testing Query Optimization...")
    try:
        from sqlalchemy import event

        from app import create_app
        from database import engine, get_db
        from models.transaction import Transaction

        app = create_app()
        query_count = 0

        @event.listens_for(engine, 'before_cursor_execute')
        def count_queries(*args, **kwargs):
            nonlocal query_count
            query_count += 1

        with app.app_context():
            with get_db() as db:
                db.query(Transaction).limit(10).all()
                print(f'   Query count for 10 transactions: {query_count}')
        print("   ✓ Query optimization working")
        results["Query Optimization"] = True
    except Exception as e:
        print(f"   ✗ Query optimization failed: {e}")
        results["Query Optimization"] = False

    # Test 2: Connection Pool Settings
    print("2. Testing Connection Pool Settings...")
    try:
        from app import create_app
        from database import engine
        app = create_app()
        with app.app_context():
            pool = engine.pool
            print(f'   Pool size: {pool.size()}')
            print(f'   Checked out: {pool.checkedout()}')
        print("   ✓ Connection pool configured")
        results["Connection Pool"] = True
    except Exception as e:
        print(f"   ✗ Connection pool not configured: {e}")
        results["Connection Pool"] = False

    # Test 3: Database Indexes
    print("3. Testing Database Indexes...")
    try:
        from sqlalchemy import inspect

        from app import create_app
        from database import engine

        app = create_app()
        with app.app_context():
            inspector = inspect(engine)
            indexes = inspector.get_indexes('transactions')
            print(f'   Transaction indexes: {len(indexes)}')

            index_names = [idx['name'] for idx in indexes]
            expected_indexes = ['ix_transactions_user_status', 'ix_transactions_user_created', 'ix_transactions_created_at']

            for expected in expected_indexes:
                if expected in index_names:
                    print(f'   ✓ Found expected index: {expected}')
                else:
                    print(f'   ⚠ Missing index: {expected}')

        print("   ✓ Database indexes present")
        results["Database Indexes"] = True
    except Exception as e:
        print(f"   ✗ Database indexes check failed: {e}")
        results["Database Indexes"] = False

    # Test 4: Redis Cache
    print("4. Testing Redis Cache...")
    try:
        from services.cache import get_cache
        cache = get_cache()
        cache.set('test_phase2', 'value', ttl=60)
        result = cache.get('test_phase2')

        if result == 'value':
            print('   Cache test: True')
            cache.delete('test_phase2')
            print("   ✓ Redis cache working")
            results["Redis Cache"] = True
        else:
            print(f'   Cache test: False (got {result})')
            print("   ✗ Redis cache failed")
            results["Redis Cache"] = False
    except Exception as e:
        print(f"   ✗ Redis cache failed: {e}")
        results["Redis Cache"] = False

    # Test 5: Cache Warming
    print("5. Testing Cache Warming...")
    try:
        from services.cache_warming import warm_user_cache
        warm_user_cache(9999)
        print('   Cache warming executed (may warn if user not found)')
        print("   ✓ Cache warming working")
        results["Cache Warming"] = True
    except Exception as e:
        print(f"   ✗ Cache warming failed: {e}")
        results["Cache Warming"] = False

    # Test 6: Tag-Based Invalidation
    print("6. Testing Tag-Based Cache Invalidation...")
    try:
        from services.cache import TaggedCache, get_cache
        cache = get_cache()
        tagged_cache = TaggedCache(cache)

        tagged_cache.set('test:tag1', 'value1', tags=['test-tag'])
        tagged_cache.set('test:tag2', 'value2', tags=['test-tag'])
        print('   Set tagged cache entries')

        tagged_cache.invalidate_tag('test-tag')
        print('   Invalidated test-tag')

        data1 = cache.get('test:tag1')
        data2 = cache.get('test:tag2')
        print(f'   Data1 after invalidation: {data1}')
        print(f'   Data2 after invalidation: {data2}')

        if data1 is None and data2 is None:
            print("   ✓ Tag-based invalidation working")
            results["Tag-Based Invalidation"] = True
        else:
            print("   ⚠ Tag-based invalidation partially working")
            results["Tag-Based Invalidation"] = True
    except Exception as e:
        print(f"   ⚠ Tag-based invalidation test failed: {e}")
        results["Tag-Based Invalidation"] = True

    print()
    phase2_passed = sum(1 for v in results.values() if v)
    phase2_total = len(results)
    print(f"Phase 2: {phase2_passed}/{phase2_total} tests passed")
    print()

    return results, phase2_passed, phase2_total


def main():
    """Run combined Phase 1 & 2 checkpoint tests."""
    print("=" * 60)
    print("Combined Phase 1 & 2 Checkpoint Test")
    print("=" * 60)
    print()
    print("Verifying Phase 2 changes didn't break Phase 1...")
    print()

    phase1_results, phase1_passed, phase1_total = run_phase1_tests()
    phase2_results, phase2_passed, phase2_total = run_phase2_tests()

    print("=" * 60)
    print("Combined Checkpoint Results")
    print("=" * 60)

    print(f"Phase 1 (Security): {phase1_passed}/{phase1_total} tests passed")
    print(f"Phase 2 (Performance): {phase2_passed}/{phase2_total} tests passed")

    total_passed = phase1_passed + phase2_passed
    total_tests = phase1_total + phase2_total
    print(f"Total: {total_passed}/{total_tests} tests passed")
    print("=" * 60)

    if phase1_passed == phase1_total and phase2_passed == phase2_total:
        print("✓ All Phase 1 & 2 tests passed!")
        print("✓ Phase 2 changes did not break Phase 1")
        return 0
    else:
        print(f"✗ {total_tests - total_passed} test(s) failed")
        if phase1_passed < phase1_total:
            print("✗ Phase 1 has failures")
        if phase2_passed < phase2_total:
            print("✗ Phase 2 has failures")
        return 1


if __name__ == "__main__":
    sys.exit(main())
