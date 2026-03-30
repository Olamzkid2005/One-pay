# Tasks: VoicePay Integration Readiness

**Spec ID:** voicepay-integration-readiness  
**Workflow:** Requirements-First  
**Type:** Feature  
**Estimated Duration:** 35-40 developer-days  
**Critical Path:** Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7

## Overview

This comprehensive work breakdown structure implements machine-to-machine (M2M) authentication capabilities for OnePay, enabling VoicePay and other external services to integrate without browser sessions. The implementation follows a 7-phase approach with 200+ granular tasks, each with specific acceptance criteria, performance targets, and security constraints.

## Task Status Legend

- `[ ]` Not started
- `[~]` Queued (ready to start, dependencies met)
- `[>]` In progress  
- `[x]` Completed
- `[!]` Blocked (waiting on dependency)
- `[*]` Optional (nice-to-have, not critical path)

## Dependency Notation

- **Depends on:** Task IDs that must complete before this task can start
- **Blocks:** Task IDs that cannot start until this task completes
- **Parallel with:** Tasks that can be executed concurrently

## Performance Targets

- **API Key Validation:** < 50ms at p95, < 100ms at p99
- **Webhook Processing:** < 200ms at p95, < 500ms at p99
- **Rate Limit Check:** < 20ms at p95, < 50ms at p99
- **Database Query:** < 10ms at p95 for indexed lookups
- **UI Response Time:** < 100ms for API key management operations
- **Test Execution:** < 5 minutes for full test suite
- **Property-Based Tests:** 100 iterations minimum, 1000 for critical paths

## Security Constraints

- **Zero Plaintext Storage:** API keys never stored in plaintext (hash only)
- **Constant-Time Operations:** All cryptographic comparisons use constant-time algorithms
- **Audit Trail:** All security-sensitive operations logged with request ID
- **Secrets Rotation:** Support for zero-downtime secret rotation
- **Rate Limiting:** Enforced at multiple layers (application, database, infrastructure)
- **Input Validation:** All external inputs validated before processing
- **Error Handling:** No sensitive information leaked in error messages

## Scalability Targets

- **Concurrent Users:** Support 1000+ concurrent API key authentications
- **Webhook Throughput:** Process 100+ webhooks/second
- **Database Connections:** Efficient connection pooling (max 20 connections)
- **Memory Footprint:** < 512MB per worker process
- **Horizontal Scaling:** Stateless design supports unlimited horizontal scaling
- **Cache Hit Rate:** > 90% for webhook replay detection cache

---

## Phase 1: Foundation (Database, Models, Authentication)

**Duration:** 8-10 developer-days  
**Critical Path:** Yes  
**Dependencies:** None (entry point)  
**Blocks:** All subsequent phases

### 1. Database Schema Design and Migration

**Owner:** Backend Engineer  
**Estimated Time:** 1.5 days  
**Risk Level:** Medium (schema changes require careful planning)

#### 1.1 Database Schema Analysis and Design

**Depends on:** None  
**Blocks:** 1.2, 1.3, 1.4  
**Parallel with:** None

- [ ] 1.1.1 Analyze existing database schema
  - **File:** Review `models/user.py`, `models/transaction.py`
  - **Action:** Document current schema structure and relationships
  - **Acceptance Criteria:**
    - Schema diagram created showing users, transactions, and new api_keys table
    - Foreign key relationships documented
    - Index strategy documented with rationale
  - **Performance Target:** N/A (documentation task)
  - **Security Constraint:** Ensure CASCADE DELETE prevents orphaned API keys

- [ ] 1.1.2 Design api_keys table schema
  - **File:** Create `docs/database/api_keys_schema.md`
  - **Action:** Define complete table structure with all constraints
  - **Acceptance Criteria:**
    - All 10 columns defined with types and constraints
    - 3 indexes defined (user_id, key_hash, is_active)
    - Foreign key CASCADE DELETE to users table
    - UNIQUE constraint on key_hash
    - Default values specified (is_active=true, created_at=NOW())
  - **Performance Target:** Index selectivity > 95% for key_hash lookups
  - **Security Constraint:** key_hash column sized for SHA256 (64 hex chars)

- [ ] 1.1.3 Estimate storage requirements
  - **File:** `docs/database/capacity_planning.md`
  - **Action:** Calculate storage per API key and project growth
  - **Acceptance Criteria:**
    - Storage per row calculated (~500 bytes)
    - Growth projection for 10K, 100K, 1M API keys
    - Index size estimates included
    - Backup strategy documented
  - **Performance Target:** Support 100K API keys without degradation
  - **Scalability:** Plan for 1M+ API keys in 2 years

- [ ] 1.1.4 Review schema with DBA/senior engineer
  - **File:** N/A (review meeting)
  - **Action:** Present schema design for feedback
  - **Acceptance Criteria:**
    - Schema approved by senior engineer
    - Performance concerns addressed
    - Security review completed
    - Migration strategy approved
  - **Performance Target:** N/A (review task)
  - **Security Constraint:** Security review sign-off required

#### 1.2 Alembic Migration Creation

**Depends on:** 1.1.4  
**Blocks:** 1.3, 2.1  
**Parallel with:** None

- [ ] 1.2.1 Generate Alembic migration file
  - **File:** `alembic/versions/YYYYMMDD_add_api_keys_table.py`
  - **Command:** `alembic revision -m "add_api_keys_table"`
  - **Action:** Create migration with upgrade() and downgrade() functions
  - **Acceptance Criteria:**
    - Migration file created with unique revision ID
    - upgrade() function creates table with all columns
    - upgrade() function creates all 3 indexes
    - downgrade() function drops indexes then table
    - Migration includes docstring with purpose and date
  - **Performance Target:** Migration completes in < 5 seconds on 100K user database
  - **Security Constraint:** No default/placeholder values in migration

- [ ] 1.2.2 Implement upgrade() function
  - **File:** `alembic/versions/YYYYMMDD_add_api_keys_table.py`
  - **Action:** Write complete table creation logic
  - **Acceptance Criteria:**
    - CREATE TABLE statement with all columns
    - Column types match design (INTEGER, VARCHAR, TEXT, TIMESTAMP, BOOLEAN)
    - NOT NULL constraints on required fields
    - DEFAULT values for created_at and is_active
    - UNIQUE constraint on key_hash
    - Foreign key to users(id) with ON DELETE CASCADE
  - **Performance Target:** Table creation < 1 second
  - **Security Constraint:** Verify CASCADE DELETE prevents orphaned keys

- [ ] 1.2.3 Implement index creation
  - **File:** `alembic/versions/YYYYMMDD_add_api_keys_table.py`
  - **Action:** Create all 3 indexes with proper naming
  - **Acceptance Criteria:**
    - idx_api_keys_user_id on user_id column
    - idx_api_keys_key_hash on key_hash column (UNIQUE)
    - idx_api_keys_is_active on is_active column
    - Index names follow naming convention
    - Indexes created AFTER table creation
  - **Performance Target:** Index creation < 2 seconds on empty table
  - **Scalability:** B-tree indexes support millions of rows

- [ ] 1.2.4 Implement downgrade() function
  - **File:** `alembic/versions/YYYYMMDD_add_api_keys_table.py`
  - **Action:** Write complete rollback logic
  - **Acceptance Criteria:**
    - DROP INDEX statements for all 3 indexes
    - DROP TABLE statement for api_keys
    - Indexes dropped BEFORE table drop
    - No errors if table/indexes don't exist (IF EXISTS)
    - Rollback tested successfully
  - **Performance Target:** Rollback completes in < 3 seconds
  - **Security Constraint:** Rollback doesn't leave orphaned data

- [ ] 1.2.5 Add migration metadata and comments
  - **File:** `alembic/versions/YYYYMMDD_add_api_keys_table.py`
  - **Action:** Document migration purpose and dependencies
  - **Acceptance Criteria:**
    - Module docstring explains purpose
    - Revision ID and down_revision set correctly
    - Comments explain each step
    - Migration linked to requirements document
    - Breaking changes documented (none expected)
  - **Performance Target:** N/A (documentation task)
  - **Security Constraint:** Document security implications

#### 1.3 Migration Testing in Development

**Depends on:** 1.2.5  
**Blocks:** 1.4  
**Parallel with:** None

- [ ] 1.3.1 Backup development database
  - **File:** `onepay.db` → `onepay.db.backup.YYYYMMDD`
  - **Command:** `cp onepay.db onepay.db.backup.$(date +%Y%m%d)`
  - **Action:** Create backup before migration
  - **Acceptance Criteria:**
    - Backup file created successfully
    - Backup file size matches original
    - Backup file readable and valid SQLite database
    - Backup timestamp recorded
  - **Performance Target:** Backup completes in < 10 seconds
  - **Security Constraint:** Backup stored securely (not in git)

- [ ] 1.3.2 Run migration upgrade
  - **File:** N/A (database operation)
  - **Command:** `alembic upgrade head`
  - **Action:** Apply migration to development database
  - **Acceptance Criteria:**
    - Migration completes without errors
    - Alembic version table updated
    - api_keys table created
    - All columns present with correct types
    - All indexes created
  - **Performance Target:** Migration completes in < 5 seconds
  - **Security Constraint:** No sensitive data exposed during migration

- [ ] 1.3.3 Verify table structure
  - **File:** N/A (database inspection)
  - **Command:** `sqlite3 onepay.db ".schema api_keys"`
  - **Action:** Inspect created table structure
  - **Acceptance Criteria:**
    - All 10 columns present
    - Column types correct (INTEGER, VARCHAR, TEXT, TIMESTAMP, BOOLEAN)
    - Constraints present (NOT NULL, UNIQUE, DEFAULT)
    - Foreign key to users table present
    - Table name correct (api_keys)
  - **Performance Target:** N/A (inspection task)
  - **Security Constraint:** Verify no plaintext storage columns

- [ ] 1.3.4 Verify indexes created
  - **File:** N/A (database inspection)
  - **Command:** `sqlite3 onepay.db ".indexes api_keys"`
  - **Action:** Verify all indexes exist
  - **Acceptance Criteria:**
    - idx_api_keys_user_id exists
    - idx_api_keys_key_hash exists (UNIQUE)
    - idx_api_keys_is_active exists
    - Index names match convention
    - Indexes on correct columns
  - **Performance Target:** Index lookups < 1ms on 1K rows
  - **Scalability:** Indexes support 1M+ rows efficiently

- [ ] 1.3.5 Test foreign key cascade delete
  - **File:** N/A (database test)
  - **Action:** Create test user, create API key, delete user, verify cascade
  - **Acceptance Criteria:**
    - Test user created successfully
    - API key created for test user
    - User deletion succeeds
    - API key automatically deleted (CASCADE)
    - No orphaned API keys remain
  - **Performance Target:** Cascade delete < 10ms
  - **Security Constraint:** Cascade prevents orphaned sensitive data

- [ ] 1.3.6 Test migration rollback
  - **File:** N/A (database operation)
  - **Command:** `alembic downgrade -1`
  - **Action:** Roll back migration and verify cleanup
  - **Acceptance Criteria:**
    - Rollback completes without errors
    - api_keys table dropped
    - All indexes dropped
    - Alembic version table updated
    - Database returns to previous state
  - **Performance Target:** Rollback completes in < 3 seconds
  - **Security Constraint:** Rollback doesn't leave sensitive data

- [ ] 1.3.7 Re-apply migration
  - **File:** N/A (database operation)
  - **Command:** `alembic upgrade head`
  - **Action:** Re-apply migration after successful rollback test
  - **Acceptance Criteria:**
    - Migration re-applies successfully
    - Table and indexes recreated
    - Database in correct state for development
    - No errors or warnings
  - **Performance Target:** Re-application < 5 seconds
  - **Security Constraint:** Clean state after rollback/re-apply

- [ ] 1.3.8 Document migration test results
  - **File:** `docs/database/migration_test_results.md`
  - **Action:** Record test outcomes and any issues
  - **Acceptance Criteria:**
    - All test steps documented
    - Pass/fail status for each test
    - Performance measurements recorded
    - Any issues or warnings noted
    - Sign-off from tester
  - **Performance Target:** N/A (documentation task)
  - **Security Constraint:** Document security test results

#### 1.4 Migration Validation and Sign-off

**Depends on:** 1.3.8  
**Blocks:** 2.1, 3.1  
**Parallel with:** None

- [ ] 1.4.1 Run EXPLAIN QUERY PLAN on key queries
  - **File:** `docs/database/query_plans.md`
  - **Action:** Analyze query execution plans for API key lookups
  - **Acceptance Criteria:**
    - EXPLAIN output for SELECT by key_hash shows index usage
    - EXPLAIN output for SELECT by user_id shows index usage
    - No full table scans on indexed columns
    - Query plans documented with analysis
  - **Performance Target:** Index seeks, not scans
  - **Scalability:** Query plans efficient at 1M+ rows

- [ ] 1.4.2 Benchmark migration on large dataset
  - **File:** `tests/performance/test_migration_performance.py`
  - **Action:** Test migration on database with 100K users
  - **Acceptance Criteria:**
    - Migration completes in < 30 seconds on 100K users
    - No memory issues during migration
    - Database remains responsive during migration
    - Rollback tested on large dataset
  - **Performance Target:** < 30 seconds for 100K users
  - **Scalability:** Linear scaling with user count

- [ ] 1.4.3 Security review of migration
  - **File:** N/A (review meeting)
  - **Action:** Security team reviews migration for vulnerabilities
  - **Acceptance Criteria:**
    - No SQL injection vulnerabilities
    - No plaintext storage of sensitive data
    - CASCADE DELETE reviewed and approved
    - Index strategy reviewed for timing attacks
    - Security sign-off obtained
  - **Performance Target:** N/A (review task)
  - **Security Constraint:** Security team approval required

- [ ] 1.4.4 Create production migration runbook
  - **File:** `docs/deployment/migration_runbook.md`
  - **Action:** Document step-by-step production migration procedure
  - **Acceptance Criteria:**
    - Pre-migration checklist included
    - Backup procedure documented
    - Migration command documented
    - Verification steps included
    - Rollback procedure documented
    - Estimated downtime documented (< 1 minute)
  - **Performance Target:** Production migration < 1 minute downtime
  - **Security Constraint:** Backup encryption documented

- [ ] 1.4.5 Migration sign-off
  - **File:** `docs/database/migration_approval.md`
  - **Action:** Obtain approvals from stakeholders
  - **Acceptance Criteria:**
    - Backend lead approval
    - DBA approval (if applicable)
    - Security team approval
    - Product owner awareness
    - Migration scheduled for production
  - **Performance Target:** N/A (approval task)
  - **Security Constraint:** Security approval mandatory

### 2. APIKey Model Implementation

**Owner:** Backend Engineer  
**Estimated Time:** 2 days  
**Risk Level:** Low (standard ORM model)

#### 2.1 Model Class Definition

**Depends on:** 1.4.5  
**Blocks:** 2.2, 3.1  
**Parallel with:** None

- [ ] 2.1.1 Create model file structure
  - **File:** `models/api_key.py`
  - **Action:** Create new file with imports and class skeleton
  - **Acceptance Criteria:**
    - File created in models/ directory
    - SQLAlchemy Base imported
    - Required types imported (Integer, String, Text, DateTime, Boolean)
    - Class APIKey(Base) defined
    - __tablename__ = "api_keys" set
  - **Performance Target:** N/A (file creation)
  - **Security Constraint:** No hardcoded secrets in model

- [ ] 2.1.2 Define primary key and user relationship
  - **File:** `models/api_key.py`
  - **Action:** Add id column and user_id foreign key
  - **Acceptance Criteria:**
    - id = Column(Integer, primary_key=True)
    - user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    - relationship('User', back_populates='api_keys') defined
    - Index on user_id column
  - **Performance Target:** Foreign key lookups < 5ms
  - **Security Constraint:** CASCADE DELETE prevents orphaned keys

- [ ] 2.1.3 Define API key storage columns
  - **File:** `models/api_key.py`
  - **Action:** Add key_hash and key_prefix columns
  - **Acceptance Criteria:**
    - key_hash = Column(String(255), unique=True, nullable=False, index=True)
    - key_prefix = Column(String(20), nullable=False)
    - key_hash sized for SHA256 (64 hex chars)
    - key_prefix stores first 8 chars for display
    - UNIQUE constraint on key_hash
  - **Performance Target:** Hash lookups < 1ms via index
  - **Security Constraint:** No plaintext key storage

- [ ] 2.1.4 Define metadata columns
  - **File:** `models/api_key.py`
  - **Action:** Add name, scopes, timestamps, and status columns
  - **Acceptance Criteria:**
    - name = Column(String(100), nullable=True)
    - scopes = Column(Text, nullable=True)  # JSON array
    - last_used_at = Column(DateTime(timezone=True), nullable=True)
    - created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    - expires_at = Column(DateTime(timezone=True), nullable=True)
    - is_active = Column(Boolean, default=True, nullable=False, index=True)
  - **Performance Target:** Timestamp operations < 1ms
  - **Security Constraint:** Scopes stored as JSON, validated on use

- [ ] 2.1.5 Implement __repr__ method
  - **File:** `models/api_key.py`
  - **Action:** Add string representation for debugging
  - **Acceptance Criteria:**
    - __repr__ returns "<APIKey(id={id}, user_id={user_id}, prefix={prefix})>"
    - Does NOT include key_hash in repr
    - Includes key_prefix for identification
    - Safe for logging (no sensitive data)
  - **Performance Target:** N/A (debugging method)
  - **Security Constraint:** Never expose key_hash in repr

#### 2.2 Model Helper Methods

**Depends on:** 2.1.5  
**Blocks:** 2.3, 3.2  
**Parallel with:** None

- [ ] 2.2.1 Implement to_dict() method
  - **File:** `models/api_key.py`
  - **Action:** Convert model to dictionary for API responses
  - **Acceptance Criteria:**
    - Returns dict with id, user_id, key_prefix, name, scopes, timestamps, is_active
    - Does NOT include key_hash
    - Converts datetime objects to ISO 8601 strings
    - Parses scopes JSON to list
    - Handles None values gracefully
  - **Performance Target:** Serialization < 1ms
  - **Security Constraint:** Never expose key_hash

- [ ] 2.2.2 Implement has_scope() method
  - **File:** `models/api_key.py`
  - **Action:** Check if API key has specific scope
  - **Acceptance Criteria:**
    - Method signature: has_scope(self, scope: str) -> bool
    - Parses scopes JSON to list
    - Returns True if scope in list
    - Returns False if scopes is None or empty
    - Handles JSON parse errors gracefully
    - Logs warning on parse errors
  - **Performance Target:** Scope check < 0.1ms
  - **Security Constraint:** Fail closed on parse errors

- [ ] 2.2.3 Implement is_valid() method
  - **File:** `models/api_key.py`
  - **Action:** Check if API key is currently valid
  - **Acceptance Criteria:**
    - Returns False if is_active is False
    - Returns False if expires_at is in the past
    - Returns True if active and not expired
    - Uses timezone-aware datetime comparison
    - No database queries (uses loaded attributes)
  - **Performance Target:** Validation < 0.1ms
  - **Security Constraint:** Timezone-aware to prevent manipulation

- [ ] 2.2.4 Implement get_scopes() method
  - **File:** `models/api_key.py`
  - **Action:** Return list of scopes
  - **Acceptance Criteria:**
    - Returns list of scope strings
    - Returns empty list if scopes is None
    - Parses JSON safely
    - Caches parsed result (property decorator)
    - Handles malformed JSON gracefully
  - **Performance Target:** < 0.1ms (cached)
  - **Security Constraint:** Validate JSON structure

- [ ] 2.2.5 Add model-level validation
  - **File:** `models/api_key.py`
  - **Action:** Add SQLAlchemy validators
  - **Acceptance Criteria:**
    - @validates('key_hash') ensures 64 hex chars
    - @validates('key_prefix') ensures 8 chars
    - @validates('scopes') validates JSON format
    - @validates('expires_at') ensures future date
    - Validation errors raise ValueError with clear message
  - **Performance Target:** Validation < 1ms
  - **Security Constraint:** Prevent invalid data at model level

#### 2.3 Model Unit Tests

**Depends on:** 2.2.5  
**Blocks:** 3.1  
**Parallel with:** None

- [ ] 2.3.1 Test model creation
  - **File:** `tests/unit/test_api_key_model.py`
  - **Action:** Test creating APIKey instances
  - **Acceptance Criteria:**
    - Test creates APIKey with all required fields
    - Test creates APIKey with optional fields
    - Test default values (is_active=True, created_at=now)
    - Test relationship to User model
    - All assertions pass
  - **Performance Target:** Test execution < 100ms
  - **Security Constraint:** Test doesn't use real secrets

- [ ] 2.3.2 Test to_dict() method
  - **File:** `tests/unit/test_api_key_model.py`
  - **Action:** Test dictionary serialization
  - **Acceptance Criteria:**
    - Test to_dict() includes all safe fields
    - Test to_dict() excludes key_hash
    - Test datetime serialization to ISO 8601
    - Test scopes JSON parsing
    - Test None value handling
  - **Performance Target:** Test execution < 50ms
  - **Security Constraint:** Verify key_hash never in output

- [ ] 2.3.3 Test has_scope() method
  - **File:** `tests/unit/test_api_key_model.py`
  - **Action:** Test scope checking logic
  - **Acceptance Criteria:**
    - Test returns True for existing scope
    - Test returns False for missing scope
    - Test handles None scopes
    - Test handles empty scopes array
    - Test handles malformed JSON
    - Test case sensitivity
  - **Performance Target:** Test execution < 50ms
  - **Security Constraint:** Test fail-closed behavior

- [ ] 2.3.4 Test is_valid() method
  - **File:** `tests/unit/test_api_key_model.py`
  - **Action:** Test validity checking
  - **Acceptance Criteria:**
    - Test returns True for active, non-expired key
    - Test returns False for inactive key
    - Test returns False for expired key
    - Test handles None expires_at (never expires)
    - Test timezone-aware comparison
  - **Performance Target:** Test execution < 50ms
  - **Security Constraint:** Test timezone manipulation resistance

- [ ] 2.3.5 Test cascade delete
  - **File:** `tests/unit/test_api_key_model.py`
  - **Action:** Test foreign key cascade behavior
  - **Acceptance Criteria:**
    - Create user and API key
    - Delete user
    - Verify API key deleted automatically
    - Verify no orphaned records
    - Test with multiple API keys per user
  - **Performance Target:** Test execution < 100ms
  - **Security Constraint:** Verify no orphaned sensitive data

- [ ] 2.3.6 Test model validators
  - **File:** `tests/unit/test_api_key_model.py`
  - **Action:** Test SQLAlchemy validators
  - **Acceptance Criteria:**
    - Test key_hash validator rejects invalid length
    - Test key_hash validator rejects non-hex
    - Test key_prefix validator rejects invalid length
    - Test scopes validator rejects invalid JSON
    - Test expires_at validator rejects past dates
    - All validators raise ValueError with clear messages
  - **Performance Target:** Test execution < 100ms
  - **Security Constraint:** Test validation prevents injection

- [ ] 2.3.7 Test edge cases
  - **File:** `tests/unit/test_api_key_model.py`
  - **Action:** Test boundary conditions and edge cases
  - **Acceptance Criteria:**
    - Test maximum name length (100 chars)
    - Test empty name (None)
    - Test maximum scopes array size
    - Test Unicode in name field
    - Test concurrent updates to last_used_at
    - Test expires_at exactly at current time
  - **Performance Target:** Test execution < 200ms
  - **Security Constraint:** Test Unicode injection attempts

#### 2.4 Model Integration

**Depends on:** 2.3.7  
**Blocks:** 3.1  
**Parallel with:** None

- [ ] 2.4.1 Update models/__init__.py
  - **File:** `models/__init__.py`
  - **Action:** Export APIKey model
  - **Acceptance Criteria:**
    - from models.api_key import APIKey added
    - APIKey included in __all__ list
    - Import order correct (after Base, before usage)
    - No circular import issues
  - **Performance Target:** N/A (import statement)
  - **Security Constraint:** No sensitive data in module

- [ ] 2.4.2 Update User model with relationship
  - **File:** `models/user.py`
  - **Action:** Add back_populates for api_keys
  - **Acceptance Criteria:**
    - api_keys = relationship('APIKey', back_populates='user', cascade='all, delete-orphan')
    - Cascade delete configured
    - Lazy loading configured appropriately
    - Relationship documented in docstring
  - **Performance Target:** Lazy loading prevents N+1 queries
  - **Security Constraint:** Cascade prevents orphaned keys

- [ ] 2.4.3 Test model imports
  - **File:** `tests/unit/test_model_imports.py`
  - **Action:** Verify all models import correctly
  - **Acceptance Criteria:**
    - from models import APIKey succeeds
    - from models import User, APIKey succeeds
    - No circular import errors
    - All relationships resolve correctly
    - SQLAlchemy metadata includes api_keys table
  - **Performance Target:** Import time < 100ms
  - **Security Constraint:** No import-time side effects

- [ ] 2.4.4 Generate SQLAlchemy metadata
  - **File:** N/A (runtime operation)
  - **Action:** Verify metadata generation includes new model
  - **Acceptance Criteria:**
    - Base.metadata.tables includes 'api_keys'
    - Table has all columns
    - Table has all indexes
    - Foreign keys registered
    - Metadata can generate CREATE TABLE statements
  - **Performance Target:** Metadata generation < 50ms
  - **Security Constraint:** No sensitive defaults in metadata

- [ ] 2.4.5 Document model usage
  - **File:** `docs/models/api_key.md`
  - **Action:** Create comprehensive model documentation
  - **Acceptance Criteria:**
    - All fields documented with types and constraints
    - All methods documented with examples
    - Relationship to User documented
    - Security considerations documented
    - Example usage code included
  - **Performance Target:** N/A (documentation)
  - **Security Constraint:** Document security best practices

### 3. API Auth Service

- [ ] 3.1 Create APIAuthService (`services/api_auth.py`)
  - Implement generate_api_key() - returns "onepay_live_{64-hex-chars}"
  - Implement hash_api_key(api_key: str) - returns SHA256 hash
  - Implement create_api_key(db, user_id, name, scopes, expires_at) - returns (plaintext_key, db_record)
  - Implement validate_api_key(api_key: str) - returns (user_id, key_id) or (None, None)
  - Implement check_scope(api_key_id: int, required_scope: str) - returns bool
  - Implement require_scope(scope: str) decorator

- [ ] 3.2 Write unit tests for API auth service (`tests/unit/test_api_auth_service.py`)
  - Test generate_api_key() format (76 chars, correct prefix, hex chars)
  - Test generate_api_key() uniqueness (1000 keys, no duplicates)
  - Test hash_api_key() returns 64-char hex string
  - Test create_api_key() stores hash only (not plaintext)
  - Test create_api_key() stores correct prefix (first 8 chars)
  - Test validate_api_key() with valid key returns (user_id, key_id)
  - Test validate_api_key() with invalid key returns (None, None)
  - Test validate_api_key() with expired key returns (None, None)
  - Test validate_api_key() with revoked key returns (None, None)
  - Test validate_api_key() updates last_used_at
  - Test check_scope() with matching scope returns True
  - Test check_scope() with missing scope returns False
  - Test require_scope() decorator allows requests with correct scope
  - Test require_scope() decorator blocks requests with missing scope

- [ ] 3.3 Write property-based tests (`tests/property/test_api_key_properties.py`)
  - **Property 1:** API Key Format Invariant (Validates: Requirements 1.1)
  - **Property 2:** Hash-Only Storage (Validates: Requirements 1.2, 9.3)
  - **Property 3:** Prefix Extraction Correctness (Validates: Requirements 1.3)
  - **Property 4:** Authentication Round-Trip (Validates: Requirements 1.4, 1.6)
  - **Property 5:** Constant-Time Comparison (Validates: Requirements 1.5, 9.2, 4.4)
  - **Property 6:** Authentication Failure Modes (Validates: Requirements 1.7, 1.9, 1.10)
  - **Property 7:** Last Used Timestamp Update (Validates: Requirements 1.8)
  - **Property 20:** API Key Entropy/Uniqueness (Validates: Requirements 9.1)

### 4. API Auth Middleware

- [ ] 4.1 Create API auth middleware (`core/api_auth_middleware.py`)
  - Implement check_api_key_auth() function
  - Extract Authorization header
  - Check for "Bearer {api_key}" format
  - Call validate_api_key() if API key present
  - Set g.api_key_id and g.api_key_user_id if valid
  - Set session['user_id'] and session['username'] for backward compatibility

- [ ] 4.2 Integrate middleware in app.py
  - Import check_api_key_auth
  - Register as @app.before_request
  - Ensure it runs after inject_request_id() and before CSRF validation

- [ ] 4.3 Write unit tests for middleware (`tests/unit/test_api_auth_middleware.py`)
  - Test middleware extracts API key from Authorization header
  - Test middleware sets g.api_key_id and g.api_key_user_id
  - Test middleware sets session variables for backward compatibility
  - Test middleware does nothing if no Authorization header
  - Test middleware does nothing if Authorization header is not Bearer format

### 5. Auth Helpers

- [ ] 5.1 Extend core/auth.py with API key helpers
  - Implement is_api_key_authenticated() - returns bool
  - Implement get_api_key_id() - returns int | None

- [ ] 5.2 Write unit tests for auth helpers (`tests/unit/test_auth_helpers.py`)
  - Test is_api_key_authenticated() returns True when g.api_key_id set
  - Test is_api_key_authenticated() returns False when g.api_key_id not set
  - Test get_api_key_id() returns correct ID when set
  - Test get_api_key_id() returns None when not set

### 6. CSRF Bypass Implementation

- [ ] 6.1 Update CSRF validation in blueprints/payments.py
  - Modify create_payment_link() to skip CSRF if is_api_key_authenticated()
  - Modify reissue_payment_link() to skip CSRF if is_api_key_authenticated()
  - Modify update_webhook_settings() to skip CSRF if is_api_key_authenticated()

- [ ] 6.2 Write integration tests for CSRF bypass (`tests/integration/test_csrf_bypass.py`)
  - **Property 8:** CSRF Bypass for API Keys (Validates: Requirements 3.1)
  - **Property 9:** CSRF Required for Sessions (Validates: Requirements 3.2, 15.2)
  - Test API key authenticated POST without CSRF token succeeds
  - Test session authenticated POST without CSRF token fails with 403

---

## Phase 2: API Key Management UI

### 7. API Key Management Endpoints

- [ ] 7.1 Create API key management endpoints in blueprints/payments.py
  - Add GET /api/v1/settings/api-keys (list user's API keys)
  - Add POST /api/v1/settings/api-keys (create new API key)
  - Add DELETE /api/v1/settings/api-keys/<key_id> (revoke API key)
  - All endpoints require session authentication and CSRF validation
  - Verify ownership before allowing operations

- [ ] 7.2 Write unit tests for API key endpoints (`tests/unit/test_api_key_endpoints.py`)
  - Test GET /api/v1/settings/api-keys returns user's keys only
  - Test POST /api/v1/settings/api-keys creates key and returns plaintext once
  - Test POST validates scopes are in allowed list
  - Test DELETE revokes key (sets is_active=false)
  - Test DELETE requires ownership (can't revoke other user's keys)
  - Test all endpoints require CSRF token
  - Test all endpoints require session authentication

### 8. API Key Management UI

- [ ] 8.1 Update settings.html template
  - Add "API Keys" section after webhook settings
  - Add table to display API keys (name, prefix, scopes, last_used, created, actions)
  - Add "Create API Key" button
  - Add modal for creating API key (name, scopes checkboxes, expiration date)
  - Add modal for displaying API key once (with copy button and warning)
  - Add revoke confirmation dialog

- [ ] 8.2 Create settings.js for API key management
  - Implement loadAPIKeys() to fetch and display keys
  - Implement showCreateAPIKeyModal() to show creation form
  - Implement createAPIKey() to POST new key
  - Implement showAPIKeyOnceModal() to display plaintext key
  - Implement copyToClipboard() for API key
  - Implement revokeAPIKey() with confirmation
  - Add event listeners for all buttons

- [ ] 8.3 Write integration tests for UI flow (`tests/integration/test_api_key_ui.py`)
  - Test complete flow: create key → display once → list keys → revoke key
  - Test API key only shown once (refresh doesn't show it again)
  - Test copy to clipboard functionality
  - Test revoke confirmation dialog

### 9. Audit Logging for API Keys

- [ ] 9.1 Add audit logging to API key operations
  - Log api_key.created when key is created (include user_id, key_id, scopes)
  - Log api_key.revoked when key is revoked (include user_id, key_id)
  - Log api_key.auth_success when key authenticates successfully
  - Log api_key.auth_failed when key authentication fails
  - Never log full API key (only prefix)

- [ ] 9.2 Write tests for audit logging (`tests/unit/test_api_key_audit.py`)
  - Test api_key.created event logged on creation
  - Test api_key.revoked event logged on revocation
  - Test api_key.auth_success logged on successful auth
  - Test api_key.auth_failed logged on failed auth
  - Test full API key never appears in logs

---

## Phase 3: Inbound Webhooks

### 10. Webhook Secret Configuration

- [ ] 10.1 Add INBOUND_WEBHOOK_SECRET to config.py
  - Add INBOUND_WEBHOOK_SECRET environment variable
  - Implement validate_webhook_secrets() function
  - Check INBOUND_WEBHOOK_SECRET exists and is at least 32 chars
  - Check INBOUND_WEBHOOK_SECRET differs from WEBHOOK_SECRET and HMAC_SECRET
  - Call validation at app startup

- [ ] 10.2 Update .env.example with INBOUND_WEBHOOK_SECRET
  - Add INBOUND_WEBHOOK_SECRET with placeholder
  - Add generation command comment

- [ ] 10.3 Write tests for secret validation (`tests/unit/test_webhook_secrets.py`)
  - Test validation fails if INBOUND_WEBHOOK_SECRET missing
  - Test validation fails if INBOUND_WEBHOOK_SECRET too short
  - Test validation fails if INBOUND_WEBHOOK_SECRET equals WEBHOOK_SECRET
  - Test validation succeeds with valid unique secrets

### 11. Webhook Cache Service

- [ ] 11.1 Create webhook cache service (`services/webhook_cache.py`)
  - Implement is_signature_processed(signature: str) - returns bool
  - Implement mark_signature_processed(signature: str)
  - Implement cleanup_expired_signatures()
  - Use in-memory cache with threading.Lock for thread safety
  - 10-minute TTL for signatures

- [ ] 11.2 Write unit tests for webhook cache (`tests/unit/test_webhook_cache.py`)
  - Test is_signature_processed() returns False for new signature
  - Test is_signature_processed() returns True for processed signature
  - Test mark_signature_processed() adds signature to cache
  - Test signatures expire after 10 minutes
  - Test cleanup_expired_signatures() removes old entries
  - Test thread safety with concurrent access

### 12. Webhook Receiver

- [ ] 12.1 Create webhooks blueprint (`blueprints/webhooks.py`)
  - Create webhooks_bp Blueprint
  - Implement POST /api/v1/webhooks/payment-status endpoint
  - Implement verify_webhook_signature(payload_bytes, signature_header)
  - Implement validate_webhook_timestamp(timestamp)
  - Verify HMAC signature using constant-time comparison
  - Check timestamp (reject if >5 min old or >1 min future)
  - Check for duplicate signature (replay protection)
  - Parse and validate payload (tx_ref format, status values)
  - Update transaction status in database
  - Trigger invoice sync on VERIFIED status
  - Return appropriate error codes for each failure mode

- [ ] 12.2 Register webhooks blueprint in app.py
  - Import webhooks_bp
  - Register with url_prefix="/api/v1"

- [ ] 12.3 Write unit tests for webhook receiver (`tests/unit/test_webhook_receiver.py`)
  - Test valid webhook signature accepted
  - Test invalid webhook signature rejected with 401 INVALID_SIGNATURE
  - Test missing signature header rejected with 401 MISSING_SIGNATURE
  - Test webhook >5 min old rejected with 401 WEBHOOK_TOO_OLD
  - Test webhook >1 min future rejected with 401 WEBHOOK_TIMESTAMP_INVALID
  - Test duplicate signature rejected with 409 WEBHOOK_ALREADY_PROCESSED
  - Test invalid tx_ref format rejected with 400 INVALID_TX_REF
  - Test invalid status value rejected with 400 INVALID_STATUS
  - Test non-existent tx_ref rejected with 404 TRANSACTION_NOT_FOUND
  - Test transaction status updated correctly
  - Test verified_at set for VERIFIED status
  - Test invoice sync triggered

- [ ] 12.4 Write property-based tests (`tests/property/test_webhook_properties.py`)
  - **Property 10:** Webhook Signature Round-Trip (Validates: Requirements 4.2, 4.3)
  - **Property 11:** Webhook Signature Rejection (Validates: Requirements 4.5)
  - **Property 12:** Transaction Reference Format Validation (Validates: Requirements 4.6)
  - **Property 13:** Status Value Validation (Validates: Requirements 4.7)
  - **Property 14:** Transaction Status Update (Validates: Requirements 4.8)
  - **Property 15:** Verified Timestamp Setting (Validates: Requirements 4.9)
  - **Property 16:** Transaction Not Found Error (Validates: Requirements 4.10)
  - **Property 21:** Webhook Timestamp Validation Old (Validates: Requirements 10.1)
  - **Property 22:** Webhook Timestamp Validation Future (Validates: Requirements 10.2)
  - **Property 23:** Webhook Replay Detection (Validates: Requirements 10.3)

- [ ] 12.5 Write integration tests (`tests/integration/test_webhook_flow.py`)
  - Test complete webhook flow: sign → send → verify → update transaction
  - Test webhook with valid signature updates transaction
  - Test webhook replay protection across multiple requests
  - Test webhook timestamp validation edge cases

---

## Phase 4: Rate Limiting and Scopes

### 13. Rate Limiting Configuration

- [ ] 13.1 Add API rate limit constants to config.py
  - Add RATE_LIMIT_API_LINK_CREATE = 100
  - Add RATE_LIMIT_API_STATUS_CHECK = 200
  - Add RATE_LIMIT_API_HISTORY = 100

- [ ] 13.2 Update rate limiting in blueprints/payments.py
  - Modify create_payment_link() to use API rate limit if is_api_key_authenticated()
  - Modify transaction_status() to use API rate limit if is_api_key_authenticated()
  - Modify transaction_history() to use API rate limit if is_api_key_authenticated()
  - Use rate key format: "api_link:{api_key_id}" for API keys
  - Use rate key format: "link:user:{user_id}" for sessions

- [ ] 13.3 Update rate_limited() response in core/responses.py
  - Add X-RateLimit-Limit header
  - Add X-RateLimit-Remaining header
  - Add X-RateLimit-Reset header
  - Add Retry-After header

- [ ] 13.4 Write tests for rate limiting (`tests/property/test_rate_limit_properties.py`)
  - **Property 17:** API Key Rate Limit Enforcement (Validates: Requirements 6.1, 6.3)
  - **Property 18:** Session Rate Limit Enforcement (Validates: Requirements 6.2, 6.3)
  - Test API key can make 100 payment link requests in 60 seconds
  - Test session can make 10 payment link requests in 60 seconds
  - Test 101st API key request returns 429
  - Test 11th session request returns 429
  - Test rate limit headers included in responses

### 14. Scope Enforcement

- [ ] 14.1 Add @require_scope decorators to endpoints
  - Add @require_scope("payments:create") to create_payment_link()
  - Add @require_scope("payments:read") to transaction_status()
  - Add @require_scope("payments:read") to transaction_history()
  - Add @require_scope("webhooks:receive") to receive_payment_status()

- [ ] 14.2 Write tests for scope enforcement (`tests/property/test_scope_properties.py`)
  - **Property 19:** Scope-Based Authorization (Validates: Requirements 8.1, 8.2)
  - Test API key with payments:create can create payment links
  - Test API key without payments:create gets 403 INSUFFICIENT_SCOPE
  - Test API key with payments:read can check status
  - Test API key without payments:read gets 403 INSUFFICIENT_SCOPE
  - Test session auth bypasses scope checks (full access)

---

## Phase 5: API Versioning and Documentation

### 15. API Versioning

- [ ] 15.1 Create API versioning middleware (`core/api_versioning.py`)
  - Implement check_api_version() function
  - Log deprecation warning for unversioned API requests
  - Add X-API-Deprecation header to unversioned responses
  - Add X-API-Version header to all API responses

- [ ] 15.2 Update blueprint registration in app.py
  - Register payments_bp with url_prefix="/api/v1"
  - Register webhooks_bp with url_prefix="/api/v1"
  - Keep unversioned registrations for backward compatibility

- [ ] 15.3 Write tests for API versioning (`tests/unit/test_api_versioning.py`)
  - Test /api/v1/payments/link works
  - Test /api/payments/link still works (backward compatibility)
  - Test unversioned endpoints log deprecation warning
  - Test X-API-Version header present in all responses
  - Test X-API-Deprecation header present in unversioned responses

### 16. Health Check Endpoint

- [ ] 16.1 Create health check endpoint in blueprints/public.py
  - Add GET /health endpoint
  - Check database connectivity
  - Check Quickteller API connectivity (optional)
  - Return 200 with status "healthy" if all checks pass
  - Return 503 with status "unhealthy" if any check fails
  - Include individual check results in response
  - No authentication required

- [ ] 16.2 Write tests for health check (`tests/unit/test_health_check.py`)
  - Test /health returns 200 when all systems operational
  - Test /health returns 503 when database unavailable
  - Test /health includes timestamp in response
  - Test /health includes individual check results

### 17. Request ID Tracing

- [ ] 17.1 Update request ID middleware in app.py
  - Check for X-Request-ID header in incoming requests
  - Use provided X-Request-ID if present, generate UUID if not
  - Store request_id in g.request_id
  - Include X-Request-ID in all responses
  - Include request_id in all log messages

- [ ] 17.2 Update outbound webhook calls to include X-Request-ID
  - Modify services/webhook.py to include X-Request-ID header

- [ ] 17.3 Write tests for request ID tracing (`tests/unit/test_request_id.py`)
  - Test request with X-Request-ID uses provided ID
  - Test request without X-Request-ID generates new UUID
  - Test X-Request-ID included in response
  - Test request_id included in log messages

### 18. API Documentation

- [ ] 18.1 Create OpenAPI specification (`docs/openapi.json`)
  - Document all /api/v1/* endpoints
  - Include request/response schemas
  - Document authentication requirements (API key or session)
  - Document rate limits for each endpoint
  - Include example requests and responses
  - Document error codes and responses

- [ ] 18.2 Create API documentation endpoint
  - Add GET /api/docs endpoint serving Swagger UI
  - Add GET /api/openapi.json endpoint serving OpenAPI spec
  - No authentication required

- [ ] 18.3 Create API usage guide (`docs/API.md`)
  - Document API key creation process
  - Document authentication methods
  - Document rate limits
  - Document error handling
  - Include code examples in Python and JavaScript
  - Document webhook integration

---

## Phase 6: Testing and Verification

### 19. Integration Tests

- [ ] 19.1 Write end-to-end API key auth flow test (`tests/integration/test_api_key_auth_flow.py`)
  - Create user → Create API key → Authenticate with key → Create payment link → Verify success
  - Test complete flow without CSRF token
  - Test scope enforcement throughout flow

- [ ] 19.2 Write end-to-end webhook flow test (`tests/integration/test_webhook_flow.py`)
  - Create transaction → Send webhook → Verify signature → Update status → Check invoice sync
  - Test replay protection
  - Test timestamp validation

- [ ] 19.3 Write backward compatibility tests (`tests/integration/test_backward_compatibility.py`)
  - **Property 24:** Backward Compatibility (Validates: Requirements 15.1, 15.3)
  - Run existing test suite with session authentication
  - Verify all existing functionality still works
  - Test session auth still requires CSRF
  - Test unversioned endpoints still work

### 20. Performance Tests

- [ ] 20.1 Write performance tests (`tests/performance/test_latency.py`)
  - Test API key validation latency < 50ms at p95
  - Test webhook processing latency < 200ms at p95
  - Test rate limit check latency < 20ms at p95

### 21. Security Tests

- [ ] 21.1 Write security tests (`tests/security/test_api_key_security.py`)
  - Test constant-time comparison (timing variance < 10ms)
  - Test API key never logged in full (only prefix)
  - Test hash-only storage (plaintext never in database)
  - Test replay attack prevention
  - Test timing attack resistance

### 22. Manual Testing Checklist

- [ ] 22.1 Create manual testing checklist (`tests/MANUAL_TESTING_CHECKLIST.md`)
  - API key creation flow in UI
  - API key display once (copy to clipboard)
  - API key revocation
  - API authentication with valid key
  - API authentication with invalid key
  - Webhook signature verification
  - Webhook replay protection
  - Rate limiting for API keys vs sessions
  - Scope enforcement
  - Backward compatibility with session auth

---

## Phase 7: Documentation and Deployment

### 23. Documentation

- [ ] 23.1 Update README.md
  - Add section on API key authentication
  - Add link to API documentation
  - Add webhook integration instructions

- [ ] 23.2 Update DEPLOYMENT.md
  - Add INBOUND_WEBHOOK_SECRET generation instructions
  - Add webhook secret validation steps
  - Add API key migration steps
  - Add rollback procedures

- [ ] 23.3 Create VoicePay integration guide (`docs/VOICEPAY_INTEGRATION.md`)
  - Document API key creation
  - Document authentication
  - Document payment link creation
  - Document webhook setup
  - Include code examples

### 24. Deployment Preparation

- [ ] 24.1 Create deployment checklist
  - Generate INBOUND_WEBHOOK_SECRET
  - Verify secrets are unique
  - Run database migration
  - Test API key creation
  - Test webhook receiver
  - Verify rate limits
  - Check audit logging

- [ ] 24.2 Create rollback plan
  - Document feature flag disable procedure
  - Document database migration rollback
  - Document code revert procedure

---

## Completion Criteria

All tasks must be completed and verified before marking the feature complete:

### Phase Completion Gates

**Phase 1 Complete When:**
- [ ] All database migrations tested and approved
- [ ] All models implemented with 100% test coverage
- [ ] All authentication middleware integrated and tested
- [ ] Performance benchmarks meet targets (< 50ms API key validation)
- [ ] Security review completed and signed off
- [ ] Zero critical or high-severity bugs

**Phase 2 Complete When:**
- [ ] API key management UI fully functional
- [ ] All CRUD operations tested end-to-end
- [ ] Audit logging verified for all operations
- [ ] UI response times < 100ms at p95
- [ ] Cross-browser testing completed
- [ ] Accessibility audit passed (WCAG 2.1 AA)

**Phase 3 Complete When:**
- [ ] Webhook receiver processing webhooks successfully
- [ ] Replay protection verified with load testing
- [ ] Signature verification tested with 10K+ webhooks
- [ ] Performance targets met (< 200ms at p95)
- [ ] Security penetration testing completed
- [ ] Integration with VoicePay validated

**Phase 4 Complete When:**
- [ ] Rate limiting enforced correctly for both auth types
- [ ] Scope enforcement tested across all endpoints
- [ ] Load testing completed (1000+ concurrent users)
- [ ] Rate limit headers verified in all responses
- [ ] No scope bypass vulnerabilities found

**Phase 5 Complete When:**
- [ ] API versioning implemented and tested
- [ ] Health check endpoint operational
- [ ] Request ID tracing verified end-to-end
- [ ] OpenAPI documentation complete and accurate
- [ ] API documentation reviewed by technical writer

**Phase 6 Complete When:**
- [ ] All 24 correctness properties have passing tests (100+ iterations each)
- [ ] Unit test coverage > 90% (line coverage)
- [ ] Integration tests cover all critical paths
- [ ] Performance tests meet all targets
- [ ] Security tests pass (timing attacks, replay protection)
- [ ] Backward compatibility verified (existing tests pass)
- [ ] Load testing completed (100+ webhooks/second sustained)

**Phase 7 Complete When:**
- [ ] All documentation updated and reviewed
- [ ] Deployment runbook tested in staging
- [ ] Rollback procedure tested successfully
- [ ] Production deployment checklist completed
- [ ] Monitoring and alerting configured
- [ ] On-call runbook created

### Quality Gates

**Code Quality:**
- [ ] All code reviewed by senior engineer
- [ ] No code smells or technical debt introduced
- [ ] Consistent code style (passes linter)
- [ ] All functions documented with docstrings
- [ ] Complex logic has inline comments

**Testing Quality:**
- [ ] Unit tests: > 90% line coverage, > 85% branch coverage
- [ ] Integration tests: All critical paths covered
- [ ] Property-based tests: All 24 properties implemented
- [ ] Performance tests: All targets met
- [ ] Security tests: No vulnerabilities found
- [ ] Manual testing checklist 100% complete

**Security Quality:**
- [ ] Security review completed and approved
- [ ] Penetration testing completed (no critical/high findings)
- [ ] Constant-time operations verified
- [ ] No plaintext secrets in code or logs
- [ ] Audit logging comprehensive and tamper-evident
- [ ] Rate limiting prevents abuse

**Performance Quality:**
- [ ] API key validation: < 50ms at p95, < 100ms at p99
- [ ] Webhook processing: < 200ms at p95, < 500ms at p99
- [ ] Rate limit check: < 20ms at p95, < 50ms at p99
- [ ] Database queries: < 10ms at p95 for indexed lookups
- [ ] UI operations: < 100ms at p95
- [ ] Load testing: 1000+ concurrent users, 100+ webhooks/second

**Documentation Quality:**
- [ ] All requirements documented and traceable
- [ ] Architecture diagrams accurate and up-to-date
- [ ] API documentation complete (OpenAPI spec)
- [ ] Deployment runbook tested and validated
- [ ] User guide created for API key management
- [ ] Integration guide created for VoicePay

### Production Readiness Checklist

**Infrastructure:**
- [ ] Database migration tested on production-like dataset
- [ ] Monitoring dashboards created (Grafana/Datadog)
- [ ] Alerting rules configured (PagerDuty/Opsgenie)
- [ ] Log aggregation configured (ELK/Splunk)
- [ ] Backup and recovery tested
- [ ] Disaster recovery plan documented

**Security:**
- [ ] Secrets rotated and stored securely (Vault/AWS Secrets Manager)
- [ ] TLS certificates valid and auto-renewing
- [ ] Rate limiting configured at multiple layers
- [ ] DDoS protection enabled (Cloudflare/AWS Shield)
- [ ] Security headers configured (CSP, HSTS, etc.)
- [ ] Vulnerability scanning automated (Snyk/Dependabot)

**Operational:**
- [ ] On-call rotation established
- [ ] Incident response playbook created
- [ ] Rollback procedure tested in staging
- [ ] Feature flags configured for gradual rollout
- [ ] Capacity planning completed (6-month projection)
- [ ] Cost analysis completed and approved

**Compliance:**
- [ ] Data retention policy documented
- [ ] Privacy impact assessment completed
- [ ] Audit trail requirements met
- [ ] Compliance review completed (SOC 2/ISO 27001)
- [ ] Terms of service updated (if applicable)
- [ ] Privacy policy updated (if applicable)

---

## Risk Register

### High-Risk Items

**Risk 1: Database Migration Failure**
- **Probability:** Low
- **Impact:** Critical (production downtime)
- **Mitigation:** Extensive testing in staging, backup before migration, rollback plan tested
- **Owner:** Backend Lead
- **Status:** Mitigated

**Risk 2: Timing Attack Vulnerability**
- **Probability:** Medium
- **Impact:** High (API key compromise)
- **Mitigation:** Constant-time comparison, security review, penetration testing
- **Owner:** Security Team
- **Status:** Mitigated

**Risk 3: Webhook Replay Attack**
- **Probability:** Medium
- **Impact:** High (duplicate transactions)
- **Mitigation:** Signature caching, timestamp validation, comprehensive testing
- **Owner:** Backend Engineer
- **Status:** Mitigated

**Risk 4: Performance Degradation**
- **Probability:** Low
- **Impact:** Medium (user experience)
- **Mitigation:** Performance testing, load testing, database indexing, caching
- **Owner:** Backend Lead
- **Status:** Mitigated

**Risk 5: Backward Compatibility Break**
- **Probability:** Low
- **Impact:** Critical (existing users affected)
- **Mitigation:** Comprehensive backward compatibility testing, gradual rollout
- **Owner:** Product Owner
- **Status:** Mitigated

### Medium-Risk Items

**Risk 6: Scope Bypass Vulnerability**
- **Probability:** Low
- **Impact:** Medium (unauthorized access)
- **Mitigation:** Comprehensive scope testing, security review
- **Owner:** Security Team
- **Status:** Monitoring

**Risk 7: Rate Limit Bypass**
- **Probability:** Low
- **Impact:** Medium (resource exhaustion)
- **Mitigation:** Multi-layer rate limiting, load testing
- **Owner:** Backend Engineer
- **Status:** Monitoring

**Risk 8: Documentation Gaps**
- **Probability:** Medium
- **Impact:** Low (developer confusion)
- **Mitigation:** Technical writer review, user testing
- **Owner:** Technical Writer
- **Status:** Monitoring

---

## Notes

- **Task Granularity:** Each subtask designed for 15-30 minutes of focused work
- **Testing Philosophy:** Test-driven development (TDD) - write tests before implementation
- **Code Review:** All code requires review by senior engineer before merge
- **Security Review:** Security-sensitive code requires security team review
- **Performance Testing:** All performance targets must be met before production
- **Documentation:** All public APIs must be documented before release
- **Deployment:** Gradual rollout with feature flags and monitoring
- **Rollback:** Rollback procedure tested and ready for immediate use

---

## Appendix A: Task Dependencies Graph

```
Phase 1 (Foundation)
├── 1.1 Schema Design → 1.2 Migration → 1.3 Testing → 1.4 Validation
├── 2.1 Model Definition → 2.2 Helper Methods → 2.3 Unit Tests → 2.4 Integration
├── 3.1 Service Implementation → 3.2 Unit Tests → 3.3 Property Tests
├── 4.1 Middleware → 4.2 Integration → 4.3 Tests
├── 5.1 Auth Helpers → 5.2 Tests
└── 6.1 CSRF Bypass → 6.2 Tests

Phase 2 (UI) - Depends on Phase 1
├── 7.1 API Endpoints → 7.2 Tests
├── 8.1 UI Templates → 8.2 JavaScript → 8.3 Integration Tests
└── 9.1 Audit Logging → 9.2 Tests

Phase 3 (Webhooks) - Depends on Phase 1
├── 10.1 Secret Config → 10.2 Env Setup → 10.3 Tests
├── 11.1 Cache Service → 11.2 Tests
└── 12.1 Webhook Receiver → 12.2 Integration → 12.3 Tests → 12.4 Property Tests → 12.5 E2E Tests

Phase 4 (Rate Limiting) - Depends on Phase 1, 2, 3
├── 13.1 Config → 13.2 Implementation → 13.3 Headers → 13.4 Tests
└── 14.1 Scope Decorators → 14.2 Tests

Phase 5 (Versioning) - Depends on Phase 1-4
├── 15.1 Versioning Middleware → 15.2 Blueprint Registration → 15.3 Tests
├── 16.1 Health Check → 16.2 Tests
├── 17.1 Request ID → 17.2 Webhook Integration → 17.3 Tests
└── 18.1 OpenAPI Spec → 18.2 Docs Endpoint → 18.3 User Guide

Phase 6 (Testing) - Depends on Phase 1-5
├── 19.1 E2E Auth Tests
├── 19.2 E2E Webhook Tests
├── 19.3 Backward Compatibility Tests
├── 20.1 Performance Tests
├── 21.1 Security Tests
└── 22.1 Manual Testing Checklist

Phase 7 (Deployment) - Depends on Phase 1-6
├── 23.1 README → 23.2 Deployment Docs → 23.3 Integration Guide
└── 24.1 Deployment Checklist → 24.2 Rollback Plan
```

---

## Appendix B: Performance Benchmarks

| Operation | Target (p95) | Target (p99) | Measured | Status |
|-----------|--------------|--------------|----------|--------|
| API Key Validation | < 50ms | < 100ms | TBD | Pending |
| Webhook Processing | < 200ms | < 500ms | TBD | Pending |
| Rate Limit Check | < 20ms | < 50ms | TBD | Pending |
| Database Query (indexed) | < 10ms | < 20ms | TBD | Pending |
| UI API Key Creation | < 100ms | < 200ms | TBD | Pending |
| Scope Check | < 1ms | < 5ms | TBD | Pending |
| HMAC Verification | < 5ms | < 10ms | TBD | Pending |

---

## Appendix C: Security Test Matrix

| Test | Type | Status | Severity | Notes |
|------|------|--------|----------|-------|
| Timing Attack Resistance | Property-based | Pending | Critical | Constant-time comparison |
| Replay Attack Prevention | Integration | Pending | Critical | Signature caching |
| SQL Injection | Unit | Pending | Critical | Parameterized queries |
| XSS in UI | Manual | Pending | High | Input sanitization |
| CSRF Bypass Validation | Integration | Pending | High | API key vs session |
| Scope Bypass | Unit | Pending | High | Decorator enforcement |
| Rate Limit Bypass | Load | Pending | Medium | Multi-layer limiting |
| Secret Exposure | Code Review | Pending | Critical | No hardcoded secrets |
| Audit Log Tampering | Integration | Pending | Medium | Immutable logs |
| Cascade Delete | Unit | Pending | Medium | No orphaned data |

---

**END OF TASKS DOCUMENT**

**Total Tasks:** 200+ granular subtasks across 7 phases  
**Estimated Duration:** 35-40 developer-days  
**Last Updated:** 2026-03-30  
**Document Version:** 2.0 (Comprehensive WBS)
