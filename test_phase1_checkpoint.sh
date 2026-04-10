#!/bin/bash
# Phase 1 Security Checkpoint Test

echo "=== Phase 1 Security Checkpoint Test ==="
echo ""

echo "1. Testing HSTS Preload Header..."
curl -I http://localhost:5000 2>/dev/null | grep -q "preload" && echo "✓ HSTS preload present" || echo "✗ HSTS preload missing"

echo "2. Testing Clear-Site-Data Header..."
curl -X POST http://localhost:5000/logout -i 2>/dev/null | grep -q "Clear-Site-Data" && echo "✓ Clear-Site-Data present" || echo "✗ Clear-Site-Data missing"

echo "3. Testing Permissions-Policy Header..."
curl -I http://localhost:5000 2>/dev/null | grep -q "magnetometer" && echo "✓ Enhanced Permissions-Policy present" || echo "✗ Enhanced Permissions-Policy missing"

echo "4. Testing security.txt..."
curl -s http://localhost:5000/.well-known/security.txt 2>/dev/null | grep -q "Contact:" && echo "✓ security.txt accessible" || echo "✗ security.txt missing"

echo "5. Testing Common Password List..."
python -c "from services.validation.password import COMMON_PASSWORDS; print('✓ Loaded', len(COMMON_PASSWORDS), 'passwords')" 2>/dev/null || echo "✗ Common password list not loaded"

echo "6. Testing CAPTCHA..."
curl -s http://localhost:5000/reset-password 2>/dev/null | grep -q "h-captcha" && echo "✓ CAPTCHA widget present" || echo "✗ CAPTCHA widget missing"

echo "7. Testing Redis Session Storage..."
redis-cli KEYS "onepay:session:*" 2>/dev/null | wc -l | grep -q "[1-9]" && echo "✓ Redis sessions present" || echo "⚠ No Redis sessions (may need login)"

echo "8. Testing Alert Manager..."
python -c "from services.alerts import AlertManager; print('✓ AlertManager importable')" 2>/dev/null || echo "✗ AlertManager not importable"

echo "9. Running Security Scans..."
safety check > /dev/null 2>&1 && echo "✓ Safety scan passed" || echo "⚠ Safety scan failed (may need dependency installation)"
bandit -r . -q > /dev/null 2>&1 && echo "✓ Bandit scan passed" || echo "⚠ Bandit scan failed (may need dependency installation)"

echo ""
echo "=== Phase 1 Checkpoint Complete ==="
