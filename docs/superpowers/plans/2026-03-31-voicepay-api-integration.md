# VoicePay API Integration Implementation Plan

**Goal:** Enable machine-to-machine API access to OnePay for VoicePay integration

**Architecture:** Add parallel authentication system supporting both session-based (web UI) and API key-based (M2M) authentication. API keys bypass CSRF validation while maintaining security through cryptographic key validation.

**Tech Stack:** Python 3.11+, Flask, SQLAlchemy, Alembic, bcrypt, HMAC-SHA256, PostgreSQL/SQLite

---

## File Structure Overview

**New files to create:**
- `core/api_auth.py` - API key validation logic
- `models/api_key.py` - APIKey database model
- `blueprints/api_keys.py` - API key management endpoints
- `blueprints/webhooks.py` - Inbound webhook receiver
- `alembic/versions/20260401000002_add_api_keys_table.py` - Database migration
- `tests/test_api_auth.py` - Unit tests for API key logic
- `tests/test_api_key_endpoints.py` - Integration tests
- `tests/test_csrf_bypass.py` - CSRF bypass tests
- `tests/test_inbound_webhooks.py` - Webhook tests
- `static/openapi.json` - OpenAPI spec
- `templates/api_keys.html` - Dedicated API keys page

**Files to modify:**
- `app.py` - Add API key middleware, register blueprints
- `core/auth.py` - Update current_user_id() for dual auth
- `config.py` - Add new configuration values
- `blueprints/payments.py` - Add CSRF bypass logic
- `blueprints/public.py` - Enhance health check
- `templates/settings.html` - Add API keys section

---

## PHASE 1: API Key Infrastructure

### Task 1: Create APIKey Database Model

**Files:**
- Create: `models/api_key.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_auth.py
def test_api_key_model_creation():
    from models.api_key import APIKey
    from datetime import datetime, timezone
    
    key = APIKey(
        user_id=1,
        key_hash="abc123",
        key_prefix="onepay_live_abc12345",
        name="Test Key"
    )
    assert key.user_id == 1
    assert key.key_hash == "abc123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_auth.py::test_api_key_model_creation -v`
Expected: FAIL with "No module named 'models.api_key'"

- [ ] **Step 3: Write minimal implementation**

```python
# models/api_key.py
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Index
from models.base import Base

class APIKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    key_hash = Column(String(255), unique=True, nullable=False, index=True)
    key_prefix = Column(String(20), nullable=False)
    name = Column(String(100), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_auth.py::test_api_key_model_creation -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add models/api_key.py tests/test_api_auth.py
git commit -m "feat: add APIKey database model"
```

---

### Task 2: Create Database Migration

**Files:**
- Create: `alembic/versions/20260401000002_add_api_keys_table.py`

- [ ] **Step 1: Generate migration file**

Run: `alembic revision -m "add_api_keys_table"`
Expected: New file created in `alembic/versions/`

- [ ] **Step 2: Write upgrade migration**

```python
def upgrade():
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('key_hash', sa.String(255), nullable=False),
        sa.Column('key_prefix', sa.String(20), nullable=False),
        sa.Column('name', sa.String(100), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_api_keys_user_id', 'api_keys', ['user_id'])
    op.create_index('idx_api_keys_key_hash', 'api_keys', ['key_hash'])
```

- [ ] **Step 3: Write downgrade migration**

```python
def downgrade():
    op.drop_index('idx_api_keys_key_hash', 'api_keys')
    op.drop_index('idx_api_keys_user_id', 'api_keys')
    op.drop_table('api_keys')
```

- [ ] **Step 4: Run migration**

Run: `alembic upgrade head`
Expected: Migration applied successfully

- [ ] **Step 5: Verify table created**

Run: `python -c "from database import get_db; from models.api_key import APIKey; print('Table exists')"`
Expected: "Table exists"

- [ ] **Step 6: Commit**

```bash
git add alembic/versions/20260401000002_add_api_keys_table.py
git commit -m "feat: add api_keys table migration"
```

---

### Task 3: Implement API Key Generation

**Files:**
- Create: `core/api_auth.py`
- Modify: `tests/test_api_auth.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_auth.py
def test_generate_api_key_format():
    from core.api_auth import generate_api_key
    
    key = generate_api_key()
    assert key.startswith("onepay_live_")
    assert len(key) == 76  # onepay_live_ (12) + 64 hex chars
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_auth.py::test_generate_api_key_format -v`
Expected: FAIL with "No module named 'core.api_auth'"

- [ ] **Step 3: Write minimal implementation**

```python
# core/api_auth.py
import secrets

def generate_api_key() -> str:
    """Generate a new API key with secure random bytes"""
    random_bytes = secrets.token_bytes(32)
    hex_string = random_bytes.hex()
    return f"onepay_live_{hex_string}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_auth.py::test_generate_api_key_format -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/api_auth.py tests/test_api_auth.py
git commit -m "feat: add API key generation function"
```

---

### Task 4: Implement API Key Hashing

**Files:**
- Modify: `core/api_auth.py`
- Modify: `tests/test_api_auth.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_auth.py
def test_hash_api_key():
    from core.api_auth import hash_api_key
    
    key = "onepay_live_abc123"
    hash1 = hash_api_key(key)
    hash2 = hash_api_key(key)
    
    assert hash1 == hash2  # Consistent
    assert len(hash1) == 64  # SHA256 hex
    assert hash1 != key  # Actually hashed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_auth.py::test_hash_api_key -v`
Expected: FAIL with "cannot import name 'hash_api_key'"

- [ ] **Step 3: Write minimal implementation**

```python
# core/api_auth.py
import hashlib

def hash_api_key(key: str) -> str:
    """Hash API key using SHA256"""
    return hashlib.sha256(key.encode('utf-8')).hexdigest()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_auth.py::test_hash_api_key -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/api_auth.py tests/test_api_auth.py
git commit -m "feat: add API key hashing function"
```

---

### Task 5: Implement API Key Validation

**Files:**
- Modify: `core/api_auth.py`
- Modify: `tests/test_api_auth.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_auth.py
def test_validate_api_key_valid(db_session):
    from core.api_auth import generate_api_key, hash_api_key, validate_api_key
    from models.api_key import APIKey
    
    # Create test key
    key = generate_api_key()
    api_key = APIKey(
        user_id=1,
        key_hash=hash_api_key(key),
        key_prefix=key[:20],
        is_active=True
    )
    db_session.add(api_key)
    db_session.commit()
    
    # Validate
    is_valid, user_id = validate_api_key(key)
    assert is_valid is True
    assert user_id == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_auth.py::test_validate_api_key_valid -v`
Expected: FAIL with "cannot import name 'validate_api_key'"

- [ ] **Step 3: Write minimal implementation**

```python
# core/api_auth.py
from datetime import datetime, timezone
from database import get_db
from models.api_key import APIKey

def validate_api_key(key: str) -> tuple[bool, int | None]:
    """Validate API key and return (is_valid, user_id)"""
    if not key or not key.startswith('onepay_live_'):
        return False, None
    
    key_hash = hash_api_key(key)
    
    with get_db() as db:
        api_key = db.query(APIKey).filter(
            APIKey.key_hash == key_hash,
            APIKey.is_active == True
        ).first()
        
        if not api_key:
            return False, None
        
        # Check expiration
        if api_key.expires_at:
            if api_key.expires_at < datetime.now(timezone.utc):
                return False, None
        
        # Update last used
        api_key.last_used_at = datetime.now(timezone.utc)
        db.flush()
        
        return True, api_key.user_id
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_auth.py::test_validate_api_key_valid -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/api_auth.py tests/test_api_auth.py
git commit -m "feat: add API key validation function"
```

---

### Task 6: Add API Key Authentication Middleware

**Files:**
- Modify: `app.py`
- Modify: `core/api_auth.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_auth.py
def test_api_key_authenticated_flag(client, db_session):
    from core.api_auth import generate_api_key, hash_api_key
    from models.api_key import APIKey
    from flask import g
    
    # Create test key
    key = generate_api_key()
    api_key = APIKey(user_id=1, key_hash=hash_api_key(key), key_prefix=key[:20], is_active=True)
    db_session.add(api_key)
    db_session.commit()
    
    # Make request with API key
    response = client.get('/health', headers={'Authorization': f'Bearer {key}'})
    
    # Check g.api_key_authenticated was set
    # (This will be verified in endpoint tests)
    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_auth.py::test_api_key_authenticated_flag -v`
Expected: FAIL (middleware not yet added)

- [ ] **Step 3: Add helper function to api_auth.py**

```python
# core/api_auth.py
from flask import g

def is_api_key_authenticated() -> bool:
    """Check if current request authenticated via API key"""
    return getattr(g, 'api_key_authenticated', False)
```

- [ ] **Step 4: Add middleware to app.py**

```python
# app.py (add before_request hook)
from core.api_auth import validate_api_key

@app.before_request
def authenticate_api_key():
    """Check for API key in Authorization header"""
    auth_header = request.headers.get('Authorization', '')
    
    if auth_header.startswith('Bearer '):
        api_key = auth_header[7:]
        is_valid, user_id = validate_api_key(api_key)
        
        if is_valid:
            g.api_key_authenticated = True
            g.user_id = user_id
            g.api_key = api_key
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_api_auth.py::test_api_key_authenticated_flag -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app.py core/api_auth.py tests/test_api_auth.py
git commit -m "feat: add API key authentication middleware"
```

---

### Task 7: Update current_user_id() for Dual Auth

**Files:**
- Modify: `core/auth.py`
- Create: `tests/test_csrf_bypass.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_csrf_bypass.py
def test_current_user_id_from_api_key(client, db_session):
    from core.api_auth import generate_api_key, hash_api_key
    from models.api_key import APIKey
    from core.auth import current_user_id
    from flask import g
    
    # Create test key
    key = generate_api_key()
    api_key = APIKey(user_id=42, key_hash=hash_api_key(key), key_prefix=key[:20], is_active=True)
    db_session.add(api_key)
    db_session.commit()
    
    # Simulate API key auth
    with client.application.test_request_context(headers={'Authorization': f'Bearer {key}'}):
        client.application.preprocess_request()
        user_id = current_user_id()
        assert user_id == 42
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_csrf_bypass.py::test_current_user_id_from_api_key -v`
Expected: FAIL (current_user_id doesn't check g.user_id yet)

- [ ] **Step 3: Update current_user_id() function**

```python
# core/auth.py
from flask import g, session

def current_user_id() -> int | None:
    """Get user ID from session OR API key"""
    # Check API key first
    if hasattr(g, 'api_key_authenticated') and g.api_key_authenticated:
        return g.user_id
    # Fall back to session
    return session.get("user_id")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_csrf_bypass.py::test_current_user_id_from_api_key -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/auth.py tests/test_csrf_bypass.py
git commit -m "feat: update current_user_id to support API key auth"
```

---

### Task 8: Add CSRF Bypass Logic to Payment Endpoints

**Files:**
- Modify: `blueprints/payments.py`
- Modify: `tests/test_csrf_bypass.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_csrf_bypass.py
def test_create_payment_link_with_api_key_skips_csrf(client, db_session):
    from core.api_auth import generate_api_key, hash_api_key
    from models.api_key import APIKey
    
    # Create test key
    key = generate_api_key()
    api_key = APIKey(user_id=1, key_hash=hash_api_key(key), key_prefix=key[:20], is_active=True)
    db_session.add(api_key)
    db_session.commit()
    
    # Make request WITHOUT CSRF token
    response = client.post(
        '/api/payments/link',
        json={'amount': '1000.00', 'currency': 'NGN'},
        headers={'Authorization': f'Bearer {key}'}
    )
    
    # Should succeed (no CSRF required)
    assert response.status_code != 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_csrf_bypass.py::test_create_payment_link_with_api_key_skips_csrf -v`
Expected: FAIL with 403 (CSRF still required)

- [ ] **Step 3: Update create_payment_link endpoint**

```python
# blueprints/payments.py
from core.api_auth import is_api_key_authenticated

@payments_bp.route("/api/payments/link", methods=["POST"])
def create_payment_link():
    if not current_user_id():
        return unauthenticated()
    
    # Skip CSRF for API key authenticated requests
    if not is_api_key_authenticated():
        csrf_header = request.headers.get("X-CSRFToken")
        if not is_valid_csrf_token(csrf_header):
            return error("CSRF validation failed", "CSRF_ERROR", 403)
    
    # ... rest of endpoint
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_csrf_bypass.py::test_create_payment_link_with_api_key_skips_csrf -v`
Expected: PASS

- [ ] **Step 5: Update other POST endpoints**

Apply same pattern to:
- `/api/payments/reissue/<tx_ref>`
- `/api/settings/webhook`
- `/api/account/settings`

- [ ] **Step 6: Run all tests**

Run: `pytest tests/test_csrf_bypass.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add blueprints/payments.py tests/test_csrf_bypass.py
git commit -m "feat: add CSRF bypass for API key authenticated requests"
```

---

### Task 9: Add Configuration Values

**Files:**
- Modify: `config.py`

- [ ] **Step 1: Add new config section**

```python
# config.py
# ── API Keys ──────────────────────────────────────────────────────────
API_KEY_MAX_PER_USER = int(os.getenv("API_KEY_MAX_PER_USER", "10"))
API_KEY_GENERATION_RATE_LIMIT = int(os.getenv("API_KEY_GENERATION_RATE_LIMIT", "5"))

# ── Inbound Webhooks ──────────────────────────────────────────────────
INBOUND_WEBHOOK_SECRET = os.getenv("INBOUND_WEBHOOK_SECRET", "")

# ── API Rate Limits ───────────────────────────────────────────────────
RATE_LIMIT_API_LINK_CREATE = int(os.getenv("RATE_LIMIT_API_LINK_CREATE", "100"))
RATE_LIMIT_API_STATUS_CHECK = int(os.getenv("RATE_LIMIT_API_STATUS_CHECK", "500"))
```

- [ ] **Step 2: Add validation in Config.validate()**

```python
# config.py in Config.validate()
if app_env == "production":
    if not cls.INBOUND_WEBHOOK_SECRET:
        errors.append("INBOUND_WEBHOOK_SECRET is required in production")
    elif len(cls.INBOUND_WEBHOOK_SECRET) < 32:
        errors.append("INBOUND_WEBHOOK_SECRET too short (minimum 32 characters)")
```

- [ ] **Step 3: Update .env.example**

```bash
# .env.example
API_KEY_MAX_PER_USER=10
API_KEY_GENERATION_RATE_LIMIT=5
INBOUND_WEBHOOK_SECRET=
RATE_LIMIT_API_LINK_CREATE=100
RATE_LIMIT_API_STATUS_CHECK=500
```

- [ ] **Step 4: Commit**

```bash
git add config.py .env.example
git commit -m "feat: add API key and webhook configuration"
```

---

## PHASE 2: API Key Management UI

### Task 10: Create API Key Management Endpoints

**Files:**
- Create: `blueprints/api_keys.py`
- Create: `tests/test_api_key_endpoints.py`

- [ ] **Step 1: Write the failing test for list endpoint**

```python
# tests/test_api_key_endpoints.py
def test_list_api_keys(client, db_session, auth_user):
    from models.api_key import APIKey
    from core.api_auth import hash_api_key
    
    # Create test keys
    key1 = APIKey(user_id=auth_user.id, key_hash=hash_api_key("test1"), key_prefix="onepay_live_test1", name="Key 1")
    db_session.add(key1)
    db_session.commit()
    
    response = client.get('/api/api-keys')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert len(data['api_keys']) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_key_endpoints.py::test_list_api_keys -v`
Expected: FAIL with 404 (endpoint doesn't exist)

- [ ] **Step 3: Create blueprint with list endpoint**

```python
# blueprints/api_keys.py
from flask import Blueprint, request, jsonify
from core.auth import current_user_id, unauthenticated
from database import get_db
from models.api_key import APIKey

api_keys_bp = Blueprint("api_keys", __name__)

@api_keys_bp.route("/api/api-keys", methods=["GET"])
def list_api_keys():
    user_id = current_user_id()
    if not user_id:
        return unauthenticated()
    
    with get_db() as db:
        keys = db.query(APIKey).filter(APIKey.user_id == user_id).all()
        return jsonify({
            "success": True,
            "api_keys": [k.to_dict() for k in keys]
        })
```

- [ ] **Step 4: Register blueprint in app.py**

```python
# app.py
from blueprints.api_keys import api_keys_bp
app.register_blueprint(api_keys_bp)
```

- [ ] **Step 5: Add to_dict() method to APIKey model**

```python
# models/api_key.py
def to_dict(self):
    return {
        "id": self.id,
        "name": self.name,
        "key_prefix": self.key_prefix,
        "created_at": self.created_at.isoformat() if self.created_at else None,
        "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        "is_active": self.is_active
    }
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_api_key_endpoints.py::test_list_api_keys -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add blueprints/api_keys.py app.py models/api_key.py tests/test_api_key_endpoints.py
git commit -m "feat: add API key list endpoint"
```

---

### Task 11: Add API Key Generation Endpoint

**Files:**
- Modify: `blueprints/api_keys.py`
- Modify: `tests/test_api_key_endpoints.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_key_endpoints.py
def test_generate_api_key(client, db_session, auth_user):
    response = client.post('/api/api-keys', json={'name': 'Test Key'})
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'api_key' in data
    assert data['api_key']['api_key'].startswith('onepay_live_')
    assert len(data['api_key']['api_key']) == 76
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_key_endpoints.py::test_generate_api_key -v`
Expected: FAIL with 405 (method not allowed)

- [ ] **Step 3: Add generate endpoint**

```python
# blueprints/api_keys.py
from core.api_auth import generate_api_key, hash_api_key
from datetime import datetime, timezone

@api_keys_bp.route("/api/api-keys", methods=["POST"])
def create_api_key():
    user_id = current_user_id()
    if not user_id:
        return unauthenticated()
    
    data = request.get_json(silent=True) or {}
    name = data.get('name', '')
    
    with get_db() as db:
        # Generate key
        key = generate_api_key()
        key_hash = hash_api_key(key)
        key_prefix = key[:20]
        
        # Create record
        api_key = APIKey(
            user_id=user_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=name
        )
        db.add(api_key)
        db.flush()
        
        # Return full key (only time it's shown)
        result = api_key.to_dict()
        result['api_key'] = key
        
        return jsonify({"success": True, "api_key": result})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_key_endpoints.py::test_generate_api_key -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add blueprints/api_keys.py tests/test_api_key_endpoints.py
git commit -m "feat: add API key generation endpoint"
```

---

### Task 12: Add API Key Revocation Endpoint

**Files:**
- Modify: `blueprints/api_keys.py`
- Modify: `tests/test_api_key_endpoints.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_key_endpoints.py
def test_revoke_api_key(client, db_session, auth_user):
    from models.api_key import APIKey
    from core.api_auth import hash_api_key
    
    # Create test key
    key = APIKey(user_id=auth_user.id, key_hash=hash_api_key("test"), key_prefix="test", is_active=True)
    db_session.add(key)
    db_session.commit()
    key_id = key.id
    
    # Revoke it
    response = client.delete(f'/api/api-keys/{key_id}')
    assert response.status_code == 200
    
    # Verify it's inactive
    db_session.refresh(key)
    assert key.is_active is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_key_endpoints.py::test_revoke_api_key -v`
Expected: FAIL with 404 (endpoint doesn't exist)

- [ ] **Step 3: Add revoke endpoint**

```python
# blueprints/api_keys.py
from core.responses import error

@api_keys_bp.route("/api/api-keys/<int:key_id>", methods=["DELETE"])
def revoke_api_key(key_id):
    user_id = current_user_id()
    if not user_id:
        return unauthenticated()
    
    with get_db() as db:
        api_key = db.query(APIKey).filter(
            APIKey.id == key_id,
            APIKey.user_id == user_id
        ).first()
        
        if not api_key:
            return error("API key not found", "NOT_FOUND", 404)
        
        api_key.is_active = False
        db.flush()
        
        return jsonify({"success": True, "message": "API key revoked"})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_key_endpoints.py::test_revoke_api_key -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add blueprints/api_keys.py tests/test_api_key_endpoints.py
git commit -m "feat: add API key revocation endpoint"
```

---

## PHASE 3: Inbound Webhook Receiver

### Task 13: Implement HMAC Signature Verification

**Files:**
- Create: `blueprints/webhooks.py`
- Create: `tests/test_inbound_webhooks.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_inbound_webhooks.py
import hmac
import hashlib
import json

def test_verify_webhook_signature_valid():
    from blueprints.webhooks import verify_webhook_signature
    
    payload = b'{"tx_ref": "TEST123"}'
    secret = "test-secret"
    
    # Generate valid signature
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    
    # Verify
    assert verify_webhook_signature(payload, f"sha256={sig}", secret) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_inbound_webhooks.py::test_verify_webhook_signature_valid -v`
Expected: FAIL with "No module named 'blueprints.webhooks'"

- [ ] **Step 3: Create webhooks blueprint with verification**

```python
# blueprints/webhooks.py
import hmac
import hashlib
from flask import Blueprint

webhooks_bp = Blueprint("webhooks", __name__)

def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC signature from inbound webhook"""
    if not signature.startswith('sha256='):
        return False
    
    expected_sig = signature[7:]
    computed_sig = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_sig, computed_sig)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_inbound_webhooks.py::test_verify_webhook_signature_valid -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add blueprints/webhooks.py tests/test_inbound_webhooks.py
git commit -m "feat: add webhook HMAC signature verification"
```

---

### Task 14: Create Webhook Receiver Endpoint

**Files:**
- Modify: `blueprints/webhooks.py`
- Modify: `tests/test_inbound_webhooks.py`
- Modify: `app.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_inbound_webhooks.py
def test_receive_payment_status_webhook(client, db_session):
    import hmac
    import hashlib
    import json
    from models.transaction import Transaction
    
    # Create test transaction
    tx = Transaction(tx_ref="TEST123", status="PENDING", amount=1000, currency="NGN", user_id=1)
    db_session.add(tx)
    db_session.commit()
    
    # Prepare webhook payload
    payload = {"tx_ref": "TEST123", "status": "VERIFIED"}
    payload_bytes = json.dumps(payload).encode()
    
    # Sign it
    secret = "test-secret"
    sig = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    
    # Send webhook
    response = client.post(
        '/api/webhooks/payment-status',
        json=payload,
        headers={'X-Webhook-Signature': f'sha256={sig}'}
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_inbound_webhooks.py::test_receive_payment_status_webhook -v`
Expected: FAIL with 404 (endpoint doesn't exist)

- [ ] **Step 3: Add webhook receiver endpoint**

```python
# blueprints/webhooks.py
from flask import request, jsonify
from config import Config
from database import get_db
from models.transaction import Transaction
from core.responses import error
from core.ip import client_ip
import logging

logger = logging.getLogger(__name__)

@webhooks_bp.route("/api/webhooks/payment-status", methods=["POST"])
def receive_payment_status():
    """Receive payment status updates from external services"""
    
    # Verify signature
    signature = request.headers.get("X-Webhook-Signature", "")
    if not verify_webhook_signature(request.data, signature, Config.INBOUND_WEBHOOK_SECRET):
        logger.warning("Invalid webhook signature | ip=%s", client_ip())
        return error("Invalid signature", "UNAUTHORIZED", 401)
    
    # Parse payload
    data = request.get_json(silent=True) or {}
    tx_ref = data.get("tx_ref")
    status = data.get("status")
    
    if not tx_ref or not status:
        return error("Missing required fields", "VALIDATION_ERROR", 400)
    
    # Update transaction
    with get_db() as db:
        transaction = db.query(Transaction).filter(
            Transaction.tx_ref == tx_ref
        ).first()
        
        if not transaction:
            return error("Transaction not found", "NOT_FOUND", 404)
        
        transaction.status = status
        db.flush()
        
        logger.info("Webhook processed | tx_ref=%s status=%s", tx_ref, status)
        
        return jsonify({"success": True, "tx_ref": tx_ref})
```

- [ ] **Step 4: Register blueprint in app.py**

```python
# app.py
from blueprints.webhooks import webhooks_bp
app.register_blueprint(webhooks_bp)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_inbound_webhooks.py::test_receive_payment_status_webhook -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add blueprints/webhooks.py app.py tests/test_inbound_webhooks.py
git commit -m "feat: add webhook receiver endpoint"
```

---

## PHASE 4: Production Hardening

### Task 15: Add API Versioning

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Update blueprint registrations**

```python
# app.py
# Change from:
app.register_blueprint(payments_bp)
app.register_blueprint(api_keys_bp)
app.register_blueprint(webhooks_bp)

# To:
app.register_blueprint(payments_bp, url_prefix="/api/v1")
app.register_blueprint(api_keys_bp, url_prefix="/api/v1")
app.register_blueprint(webhooks_bp, url_prefix="/api/v1")
```

- [ ] **Step 2: Update route definitions in blueprints**

```python
# blueprints/payments.py
# Change from: @payments_bp.route("/api/payments/link", ...)
# To: @payments_bp.route("/payments/link", ...)

# blueprints/api_keys.py
# Change from: @api_keys_bp.route("/api/api-keys", ...)
# To: @api_keys_bp.route("/api-keys", ...)

# blueprints/webhooks.py
# Change from: @webhooks_bp.route("/api/webhooks/payment-status", ...)
# To: @webhooks_bp.route("/webhooks/payment-status", ...)
```

- [ ] **Step 3: Update all tests to use /v1/ prefix**

Run: `pytest tests/ -v`
Expected: All tests updated and passing

- [ ] **Step 4: Commit**

```bash
git add app.py blueprints/ tests/
git commit -m "feat: add API versioning with /v1/ prefix"
```

---

### Task 16: Implement Separate Rate Limits

**Files:**
- Modify: `blueprints/payments.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_auth.py
def test_api_rate_limit_higher_than_web(client, db_session, auth_user):
    from core.api_auth import generate_api_key, hash_api_key
    from models.api_key import APIKey
    
    # Create API key
    key = generate_api_key()
    api_key = APIKey(user_id=auth_user.id, key_hash=hash_api_key(key), key_prefix=key[:20], is_active=True)
    db_session.add(api_key)
    db_session.commit()
    
    # Make 11 requests (web limit is 10)
    for i in range(11):
        response = client.post(
            '/api/v1/payments/link',
            json={'amount': '1000.00', 'currency': 'NGN'},
            headers={'Authorization': f'Bearer {key}'}
        )
    
    # 11th request should succeed (API limit is 100)
    assert response.status_code != 429
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_auth.py::test_api_rate_limit_higher_than_web -v`
Expected: FAIL with 429 (rate limited at 10)

- [ ] **Step 3: Update rate limiting logic**

```python
# blueprints/payments.py
from core.api_auth import is_api_key_authenticated
from config import Config

@payments_bp.route("/payments/link", methods=["POST"])
def create_payment_link():
    # ... auth checks ...
    
    with get_db() as db:
        # Separate rate limits
        if is_api_key_authenticated():
            rate_key = f"api_link:{g.api_key}"
            limit = Config.RATE_LIMIT_API_LINK_CREATE
        else:
            rate_key = f"link:user:{current_user_id()}"
            limit = Config.RATE_LIMIT_LINK_CREATE
        
        if not check_rate_limit(db, rate_key, limit):
            return rate_limited()
        
        # ... rest of endpoint
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_auth.py::test_api_rate_limit_higher_than_web -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add blueprints/payments.py tests/test_api_auth.py
git commit -m "feat: implement separate rate limits for API clients"
```

---

### Task 17: Enhance Health Check Endpoint

**Files:**
- Modify: `blueprints/public.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_health_check.py
def test_health_check_includes_dependencies(client):
    response = client.get('/health')
    
    assert response.status_code == 200
    data = response.get_json()
    assert 'checks' in data
    assert 'database' in data['checks']
    assert 'timestamp' in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_health_check.py::test_health_check_includes_dependencies -v`
Expected: FAIL (checks not in response)

- [ ] **Step 3: Update health check endpoint**

```python
# blueprints/public.py
from datetime import datetime, timezone
from database import get_db

@public_bp.route("/health", methods=["GET"])
def health_check():
    """Comprehensive health check"""
    checks = {
        "database": _check_database(),
    }
    
    all_healthy = all(v for v in checks.values() if v is not None)
    status_code = 200 if all_healthy else 503
    
    return jsonify({
        "status": "healthy" if all_healthy else "unhealthy",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0"
    }), status_code

def _check_database() -> bool:
    try:
        with get_db() as db:
            db.execute("SELECT 1")
        return True
    except Exception:
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_health_check.py::test_health_check_includes_dependencies -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add blueprints/public.py tests/test_health_check.py
git commit -m "feat: enhance health check with dependency checks"
```

---

### Task 18: Create OpenAPI Documentation

**Files:**
- Create: `static/openapi.json`
- Modify: `app.py`

- [ ] **Step 1: Install flask-swagger-ui**

Run: `pip install flask-swagger-ui`
Add to requirements.txt: `flask-swagger-ui==4.11.1`

- [ ] **Step 2: Create OpenAPI spec file**

```json
{
  "openapi": "3.0.0",
  "info": {
    "title": "OnePay API",
    "version": "1.0.0",
    "description": "OnePay payment processing API"
  },
  "servers": [
    {"url": "/api/v1"}
  ],
  "components": {
    "securitySchemes": {
      "BearerAuth": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "API Key"
      }
    }
  },
  "paths": {
    "/payments/link": {
      "post": {
        "summary": "Create payment link",
        "security": [{"BearerAuth": []}],
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "amount": {"type": "string"},
                  "currency": {"type": "string"}
                }
              }
            }
          }
        },
        "responses": {
          "200": {"description": "Success"}
        }
      }
    }
  }
}
```

- [ ] **Step 3: Add Swagger UI to app.py**

```python
# app.py
from flask_swagger_ui import get_swaggerui_blueprint

SWAGGER_URL = '/api/docs'
API_URL = '/static/openapi.json'

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={'app_name': "OnePay API"}
)

app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)
```

- [ ] **Step 4: Test documentation**

Run app and visit: `http://localhost:5000/api/docs`
Expected: Swagger UI loads with API documentation

- [ ] **Step 5: Commit**

```bash
git add static/openapi.json app.py requirements.txt
git commit -m "feat: add OpenAPI documentation with Swagger UI"
```

---

## Final Integration Testing

### Task 19: Run Full Test Suite

- [ ] **Step 1: Run all unit tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/ -m integration -v`
Expected: All integration tests PASS

- [ ] **Step 3: Check test coverage**

Run: `pytest --cov=. --cov-report=html tests/`
Expected: Coverage > 80%

- [ ] **Step 4: Run linter**

Run: `ruff check .`
Expected: No errors

- [ ] **Step 5: Commit if any fixes needed**

```bash
git add .
git commit -m "test: ensure full test suite passes"
```

---

### Task 20: Update Documentation

**Files:**
- Create: `docs/API_KEYS.md`
- Update: `docs/README.md`

- [ ] **Step 1: Create API keys documentation**

Document:
- How to generate API keys
- How to use API keys for authentication
- Rate limits for API clients
- Security best practices

- [ ] **Step 2: Update main README**

Add section about:
- API access via API keys
- Link to API documentation (/api/docs)
- Webhook integration guide

- [ ] **Step 3: Commit**

```bash
git add docs/
git commit -m "docs: add API key and webhook documentation"
```

---

## Plan Complete

**Total estimated time: 8-10 days**

Ready to execute tasks? I can proceed with implementation following this plan, task by task, using TDD workflow (RED-GREEN-REFACTOR) for each step.
