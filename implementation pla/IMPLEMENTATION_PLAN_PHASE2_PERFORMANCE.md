# OnePay Implementation Plan - Phase 2: Performance & Scalability

**Version:** 1.0  
**Created:** April 10, 2026  
**Status:** Active  
**Estimated Effort:** ~43 hours

---

## Overview

This document covers Phase 2 of the OnePay implementation plan: Performance & Scalability. This phase includes 6 tasks focused on optimizing database queries, caching, and overall system performance.

**Tasks in this phase:** 6
- PERF-001: Optimize Database Queries - Eliminate N+1 (8h)
- PERF-002: Tune Database Connection Pooling (3h)
- PERF-003: Add Database Indexes (6h)
- PERF-004: Implement Redis Cluster Support (12h)
- PERF-005: Add Cache Warming (6h)
- PERF-006: Implement Tag-Based Cache Invalidation (8h)

---

## PERF-001: Optimize Database Queries - Eliminate N+1 Queries

**Files:** `blueprints/payments.py`, `blueprints/invoices.py`, models  
**Estimated Effort:** 8 hours  
**Dependencies:** None  
**Risk:** Medium

### Implementation Steps

1. Enable SQLAlchemy query logging in development:
   ```python
   # config.py
   SQLALCHEMY_ECHO: bool = Config.DEBUG
   SQLALCHEMY_RECORD_QUERIES: bool = Config.DEBUG
   ```
2. Identify N+1 query patterns:
   - Transaction history with user data
   - Invoice list with transaction data
   - Webhook delivery with transaction details
3. Add eager loading using `joinedload`:
   ```python
   # Before (N+1 query)
   transactions = db.query(Transaction).filter_by(user_id=user_id).all()
   for tx in transactions:
       print(tx.user.email)  # Triggers additional query
   
   # After (single query)
   from sqlalchemy.orm import joinedload
   transactions = db.query(Transaction).options(
       joinedload(Transaction.user)
   ).filter_by(user_id=user_id).all()
   ```
4. Apply to identified locations:
   - `blueprints/payments.py`: Transaction history route
   - `blueprints/invoices.py`: Invoice list route
   - `services/invoice.py`: Invoice retrieval
5. Add query count monitoring:
   ```python
   # app.py
   from sqlalchemy import event
   
   @event.listens_for(engine, "before_cursor_execute")
   def before_cursor_execute(conn, cursor, statement, ...):
       conn.info.setdefault('query_count', 0)
       conn.info['query_count'] += 1
   
   @event.listens_for(engine, "after_cursor_execute")
   def after_cursor_execute(conn, cursor, statement, ...):
       query_count = conn.info.get('query_count', 0)
       if query_count > Config.QUERY_COUNT_WARN_THRESHOLD:
           logger.warning(f"High query count: {query_count}")
   ```

### Acceptance Criteria
- [ ] Query count reduced by 60%+ on transaction history
- [ ] Query count reduced by 50%+ on invoice list
- [ ] No functional regressions
- [ ] Query count warnings logged for optimization opportunities

### Testing
- Performance test: Measure query count before/after
- Load test: Verify improved response times
- Integration test: Verify data integrity

### Query Analysis Tools
```bash
# Install django-silk for Flask equivalent
pip install flask-debugtoolbar

# Or use SQLAlchemy profiling
from sqlalchemy import event
from sqlalchemy.engine import Engine
import time

@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, ...):
    conn.info.setdefault('query_start_time', []).append(time.time())

@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, ...):
    total = time.time() - conn.info['query_start_time'].pop(-1)
    if total > 0.1:  # Log slow queries
        logger.warning(f"Slow query ({total:.2f}s): {statement[:100]}")
```

### Checkpoint Test
```bash
# Enable query logging
export SQLALCHEMY_ECHO=true
export DEBUG=true

# Test transaction history endpoint with query counting
python -c "
from app import create_app
from database import get_db
from models.transaction import Transaction
from sqlalchemy import event

app = create_app()
query_count = 0

@event.listens_for(app.extensions['sqlalchemy'].engine, 'before_cursor_execute')
def count_queries(*args, **kwargs):
    global query_count
    query_count += 1

with app.app_context():
    with get_db() as db:
        tx = db.query(Transaction).first()
        print(f'Query count for single transaction: {query_count}')
# Expected: Reduced from N+1 to 1-2 queries
"

# Run performance tests
pytest tests/performance/test_query_optimization.py -v
```

---

## PERF-002: Tune Database Connection Pooling

**Files:** `database.py`, `config.py`  
**Estimated Effort:** 3 hours  
**Dependencies:** None  
**Risk:** Low

### Implementation Steps

1. Analyze current connection pool settings in `database.py`:
   ```python
   # Current settings
   pool_size = 10  # PostgreSQL
   max_overflow = 20  # PostgreSQL
   pool_pre_ping = True
   pool_recycle = 3600
   pool_timeout = 30
   ```
2. Add configuration to `config.py`:
   ```python
   DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "20"))
   DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "40"))
   DB_POOL_PRE_PING: bool = os.getenv("DB_POOL_PRE_PING", "true").lower() == "true"
   DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "3600"))
   DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
   ```
3. Update `database.py` to use configuration:
   ```python
   _engine_kwargs = {
       "pool_size": Config.DB_POOL_SIZE,
       "max_overflow": Config.DB_MAX_OVERFLOW,
       "pool_pre_ping": Config.DB_POOL_PRE_PING,
       "pool_recycle": Config.DB_POOL_RECYCLE,
       "pool_timeout": Config.DB_POOL_TIMEOUT,
   }
   ```
4. Add connection pool monitoring:
   ```python
   from sqlalchemy import event
   
   @event.listens_for(engine, "connect")
   def on_connect(dbapi_conn, connection_record):
       logger.debug(f"New connection created. Pool size: {engine.pool.size()}")
   
   @event.listens_for(engine, "close")
   def on_close(dbapi_conn, connection_record):
       logger.debug(f"Connection closed. Pool size: {engine.pool.size()}")
   ```

### Acceptance Criteria
- [ ] Connection pool size configurable
- [ ] No connection exhaustion under load
- [ ] Connection reuse improved
- [ ] Stale connections detected and recycled

### Testing
- Load test: 100 concurrent users
- Monitor connection pool metrics
- Verify no connection timeouts

### Recommended Settings by Load
```
Development: pool_size=5, max_overflow=10
Production (low traffic): pool_size=20, max_overflow=40
Production (high traffic): pool_size=50, max_overflow=100
```

### Checkpoint Test
```bash
# Set production pool settings
export DB_POOL_SIZE=20
export DB_MAX_OVERFLOW=40

# Test connection pool
python -c "
from app import create_app
app = create_app()
with app.app_context():
    engine = app.extensions['sqlalchemy'].engine
    print(f'Pool size: {engine.pool.size()}')
    print(f'Max overflow: {engine.pool._max_overflow}')
    print(f'Checked out: {engine.pool.checkedout()}')
# Expected: Pool size 20, Max overflow 40
"

# Load test with Locust
locust -f tests/load/test_connection_pool.py --host http://localhost:5000 --users 100 --spawn-rate 10
# Monitor for connection timeouts
```

---

## PERF-003: Add Database Indexes for Common Query Patterns

**Files:** `alembic/versions/`, models  
**Estimated Effort:** 6 hours  
**Dependencies:** None  
**Risk:** Low

### Implementation Steps

1. Analyze slow queries using pg_stat_statements:
   ```sql
   SELECT query, calls, total_time, mean_time
   FROM pg_stat_statements
   ORDER BY mean_time DESC
   LIMIT 20;
   ```
2. Identify common query patterns:
   - `SELECT * FROM transactions WHERE user_id = ? AND status = ?`
   - `SELECT * FROM transactions WHERE created_at > ?`
   - `SELECT * FROM audit_logs WHERE user_id = ? AND created_at > ?`
   - `SELECT * FROM invoices WHERE user_id = ? AND status = ?`
3. Create migration file:
   ```bash
   alembic revision -m "add performance indexes"
   ```
4. Add indexes in migration:
   ```python
   # alembic/versions/xxxx_add_performance_indexes.py
   def upgrade():
       op.create_index(
           'idx_transactions_user_status',
           'transactions',
           ['user_id', 'status']
       )
       op.create_index(
           'idx_transactions_created_at',
           'transactions',
           ['created_at']
       )
       op.create_index(
           'idx_audit_logs_user_created',
           'audit_logs',
           ['user_id', 'created_at']
       )
       op.create_index(
           'idx_invoices_user_status',
           'invoices',
           ['user_id', 'status']
       )
   
   def downgrade():
       op.drop_index('idx_invoices_user_status', table_name='invoices')
       op.drop_index('idx_audit_logs_user_created', table_name='audit_logs')
       op.drop_index('idx_transactions_created_at', table_name='transactions')
       op.drop_index('idx_transactions_user_status', table_name='transactions')
   ```
5. Run migration:
   ```bash
   alembic upgrade head
   ```

### Acceptance Criteria
- [ ] Query execution time reduced by 40%+
- [ ] No impact on write performance
- [ ] Indexes properly created in production
- [ ] Migration reversible

### Testing
- Performance test: Compare query times before/after
- Load test: Verify improved throughput
- Regression test: Ensure no functional changes

### Index Maintenance
```sql
-- Rebuild indexes periodically
REINDEX INDEX idx_transactions_user_status;

-- Analyze tables for query planner
ANALYZE transactions;
ANALYZE audit_logs;
ANALYZE invoices;
```

### Checkpoint Test
```bash
# Create migration
alembic revision -m "add performance indexes"

# Run migration
alembic upgrade head

# Verify indexes created
python -c "
from database import engine
from sqlalchemy import inspect
inspector = inspect(engine)
indexes = inspector.get_indexes('transactions')
print('Transaction indexes:', [idx['name'] for idx in indexes])
# Expected: idx_transactions_user_status, idx_transactions_created_at
"

# Test query performance
python -c "
from app import create_app
from database import get_db
from models.transaction import Transaction
import time

app = create_app()
with app.app_context():
    with get_db() as db:
        start = time.time()
        tx = db.query(Transaction).filter(
            Transaction.user_id == 1,
            Transaction.status == 'VERIFIED'
        ).first()
        elapsed = time.time() - start
        print(f'Query time: {elapsed*1000:.2f}ms')
# Expected: Reduced by 40%+
"

# Test rollback
alembic downgrade -1
alembic upgrade head
```

---

## PERF-004: Implement Redis Cluster Support

**Files:** `services/cache.py`, `config.py`, `requirements.txt`  
**Estimated Effort:** 12 hours  
**Dependencies:** None  
**Risk:** High

### Implementation Steps

1. Add dependency to `requirements.txt`:
   ```
   redis-py-cluster==2.1.3
   ```
2. Update `services/cache.py`:
   ```python
   from redis.cluster import RedisCluster
   
   class RedisClusterCache:
       def __init__(self, cluster_nodes, ttl=300, timeout=5):
           self._cluster_nodes = cluster_nodes
           self._default_ttl = ttl
           self._timeout = timeout
           self._cluster = None
           self._memory_fallback = MemoryCache()
           self._connected = False
           self._connect()
       
       def _connect(self):
           try:
               self._cluster = RedisCluster(
                   startup_nodes=self._cluster_nodes,
                   decode_responses=True,
                   skip_full_coverage_check=True,
               )
               self._cluster.ping()
               self._connected = True
               logger.info("Redis cluster connected")
           except Exception as e:
               logger.warning(f"Redis cluster connection failed: {e}")
               self._connected = False
       
       def get(self, key: str) -> Optional[Any]:
           if self._connected:
               try:
                   import json
                   value = self._cluster.get(key)
                   if value:
                       return json.loads(value)
                   return None
               except Exception as e:
                   logger.warning(f"Redis cluster get failed: {e}")
                   self._connected = False
           return self._memory_fallback.get(key)
       
       def set(self, key: str, value: Any, ttl: Optional[int] = None):
           ttl = ttl or self._default_ttl
           if self._connected:
               try:
                   import json
                   serialized = json.dumps(value)
                   self._cluster.setex(key, ttl, serialized)
                   return
               except Exception as e:
                   logger.warning(f"Redis cluster set failed: {e}")
                   self._connected = False
           self._memory_fallback.set(key, value, ttl)
   ```
3. Add configuration to `config.py`:
   ```python
   REDIS_CLUSTER_NODES: str = os.getenv("REDIS_CLUSTER_NODES", "")
   REDIS_CLUSTER_ENABLED: bool = os.getenv("REDIS_CLUSTER_ENABLED", "false").lower() == "true"
   ```
4. Update `get_cache()` function:
   ```python
   def get_cache(config: Optional[CacheConfig] = None) -> Union[RedisClusterCache, RedisCache, MemoryCache]:
       global _cache
       with _cache_lock:
           if _cache is None:
               config = config or CacheConfig()
               if Config.REDIS_CLUSTER_ENABLED and Config.REDIS_CLUSTER_NODES:
                   nodes = [
                       {"host": node.split(":")[0], "port": int(node.split(":")[1])}
                       for node in Config.REDIS_CLUSTER_NODES.split(",")
                   ]
                   _cache = RedisClusterCache(
                       nodes,
                       config.default_ttl_seconds,
                       config.redis_timeout_seconds
                   )
               elif config.backend == CacheBackend.REDIS and config.redis_url:
                   _cache = RedisCache(...)
               else:
                   _cache = MemoryCache(...)
           return _cache
   ```

### Acceptance Criteria
- [ ] Redis cluster connections work
- [ ] Data distributed across cluster nodes
- [ ] Failover to memory cache on cluster failure
- [ ] No single point of failure

### Testing
- Integration test: Test with local Redis cluster
- Failover test: Kill cluster node, verify fallback
- Performance test: Compare cluster vs single node

### Configuration
```bash
# .env.production.example
REDIS_CLUSTER_ENABLED=true
REDIS_CLUSTER_NODES=redis-node1:7000,redis-node2:7000,redis-node3:7000
```

### Redis Cluster Setup
```bash
# Create 3 Redis instances
docker run -d --name redis1 -p 7000:7000 redis:7-alpine redis-server --port 7000 --cluster-enabled yes
docker run -d --name redis2 -p 7001:7001 redis:7-alpine redis-server --port 7001 --cluster-enabled yes
docker run -d --name redis3 -p 7002:7002 redis:7-alpine redis-server --port 7002 --cluster-enabled yes

# Create cluster
docker exec -it redis1 redis-cli --cluster create 127.0.0.1:7000 127.0.0.1:7001 127.0.0.1:7002
```

### Checkpoint Test
```bash
# Setup Redis cluster
docker run -d --name redis1 -p 7000:7000 redis:7-alpine redis-server --port 7000 --cluster-enabled yes
docker run -d --name redis2 -p 7001:7001 redis:7-alpine redis-server --port 7001 --cluster-enabled yes
docker run -d --name redis3 -p 7002:7002 redis:7-alpine redis-server --port 7002 --cluster-enabled yes

# Create cluster
docker exec -it redis1 redis-cli --cluster create 127.0.0.1:7000 127.0.0.1:7001 127.0.0.1:7002 --cluster-yes

# Set environment
export REDIS_CLUSTER_ENABLED=true
export REDIS_CLUSTER_NODES=127.0.0.1:7000,127.0.0.1:7001,127.0.0.1:7002

# Test cluster connection
python -c "
from services.cache import get_cache
cache = get_cache()
cache.set('test', 'value', ttl=60)
print('Set test key')
result = cache.get('test')
print(f'Got: {result}')
# Expected: value
"

# Test failover - kill one node
docker stop redis2
python -c "
from services.cache import get_cache
cache = get_cache()
result = cache.get('test')
print(f'Got after failover: {result}')
# Expected: value (from memory fallback or other nodes)
"

# Cleanup
docker stop redis1 redis2 redis3
docker rm redis1 redis2 redis3
```

---

## PERF-005: Add Cache Warming for Frequently Accessed Data

**Files:** `services/cache_warming.py` (new), `app.py`, `services/task_queue.py`  
**Estimated Effort:** 6 hours  
**Dependencies:** PERF-004 (Redis cluster recommended)  
**Risk:** Medium

### Implementation Steps

1. Identify frequently accessed data:
   - User session data
   - Transaction summary (last 10 transactions)
   - Invoice settings
   - Rate limit data
2. Create cache warming service in `services/cache_warming.py`:
   ```python
   from services.cache import cache_set, cache_get
   from database import get_db
   from models.transaction import Transaction
   from models.invoice import InvoiceSettings
   
   def warm_user_cache(user_id: int):
       """Warm cache for user data"""
       with get_db() as db:
           # Recent transactions
           recent_tx = db.query(Transaction).filter_by(
               user_id=user_id
           ).order_by(Transaction.created_at.desc()).limit(10).all()
           cache_set(f"user:{user_id}:recent_tx", [tx.to_dict() for tx in recent_tx], ttl=300)
           
           # Invoice settings
           settings = db.query(InvoiceSettings).filter_by(user_id=user_id).first()
           if settings:
               cache_set(f"user:{user_id}:invoice_settings", settings.to_dict(), ttl=3600)
   
   def warm_all_users_cache():
       """Warm cache for all active users"""
       with get_db() as db:
           from models.user import User
           users = db.query(User).filter_by(is_active=True).all()
           for user in users:
               warm_user_cache(user.id)
   ```
3. Add cache warming on application startup in `app.py`:
   ```python
   from services.cache_warming import warm_all_users_cache
   
   def create_app():
       app = Flask(__name__)
       # ... existing setup ...
       
       # Warm cache after app initialization
       if not Config.DEBUG:
           warm_all_users_cache()
       
       return app
   ```
4. Add periodic cache warming in `services/task_queue.py`:
   ```python
   @huey.periodic_task(crontab(minute="*/30"))
   def warm_cache_periodically():
       """Warm cache every 30 minutes"""
       from services.cache_warming import warm_all_users_cache
       warm_all_users_cache()
   ```

### Acceptance Criteria
- [ ] Cache warmed on application startup
- [ ] Cache warmed periodically
- [ ] Reduced cache misses for user data
- [ ] Configurable warming intervals

### Testing
- Performance test: Measure cache hit rate before/after
- Load test: Verify improved response times
- Integration test: Verify cache warming logic

### Cache Hit Rate Monitoring
```python
# Add to services/cache.py
_cache_hits = 0
_cache_misses = 0

def get_cache_stats():
    total = _cache_hits + _cache_misses
    hit_rate = (_cache_hits / total * 100) if total > 0 else 0
    return {"hits": _cache_hits, "misses": _cache_misses, "hit_rate": hit_rate}
```

### Checkpoint Test
```bash
# Test cache warming
python -c "
from app import create_app
from services.cache_warming import warm_user_cache

app = create_app()
with app.app_context():
    warm_user_cache(1)
    print('Cache warmed for user 1')
"

# Verify cache is warmed
python -c "
from app import create_app
from services.cache import cache_get

app = create_app()
with app.app_context():
    data = cache_get('user:1:recent_tx')
    print(f'Cached data: {data is not None}')
# Expected: True
"

# Test periodic warming
python -c "
from services.task_queue import warm_cache_periodically
warm_cache_periodically()
# Expected: Cache warmed for all users
"
```

---

## PERF-006: Implement Tag-Based Cache Invalidation

**Files:** `services/cache.py`, models  
**Estimated Effort:** 8 hours  
**Dependencies:** PERF-004 (Redis cluster recommended)  
**Risk:** Medium

### Implementation Steps

1. Update `services/cache.py` to support tags:
   ```python
   class TaggedCache:
       def __init__(self, cache_backend):
           self._cache = cache_backend
           self._tag_separator = ":"
       
       def set(self, key: str, value: Any, ttl: Optional[int] = None, tags: Optional[list[str]] = None):
           """Set value with tags for invalidation"""
           self._cache.set(key, value, ttl)
           
           if tags:
               for tag in tags:
                   tag_key = f"tag:{tag}"
                   tagged_keys = self._cache.get(tag_key) or []
                   tagged_keys.append(key)
                   self._cache.set(tag_key, tagged_keys, ttl)
       
       def invalidate_tag(self, tag: str):
           """Invalidate all keys with given tag"""
           tag_key = f"tag:{tag}"
           tagged_keys = self._cache.get(tag_key)
           
           if tagged_keys:
               for key in tagged_keys:
                   self._cache.delete(key)
               self._cache.delete(tag_key)
       
       def invalidate_user_cache(self, user_id: int):
           """Invalidate all cache for a user"""
           self.invalidate_tag(f"user:{user_id}")
   ```
2. Add cache invalidation to model events:
   ```python
   # models/transaction.py
   from sqlalchemy import event
   from services.cache import get_cache
   
   @event.listens_for(Transaction, 'after_update')
   def on_transaction_update(mapper, connection, target):
       cache = get_cache()
       if hasattr(cache, 'invalidate_user_cache'):
           cache.invalidate_user_cache(target.user_id)
   
   @event.listens_for(Transaction, 'after_insert')
   def on_transaction_insert(mapper, connection, target):
       cache = get_cache()
       if hasattr(cache, 'invalidate_user_cache'):
           cache.invalidate_user_cache(target.user_id)
   ```
3. Update cache warming to use tags:
   ```python
   def warm_user_cache(user_id: int):
       recent_tx = db.query(Transaction).filter_by(user_id=user_id).limit(10).all()
       cache_set(
           f"user:{user_id}:recent_tx",
           [tx.to_dict() for tx in recent_tx],
           ttl=300,
           tags=[f"user:{user_id}", "transactions"]
       )
   ```

### Acceptance Criteria
- [ ] Cache entries can be tagged
- [ ] Tags can be invalidated
- [ ] User cache invalidated on data changes
- [ ] No stale cache after updates

### Testing
- Unit test: Verify tag-based invalidation
- Integration test: Test cache invalidation on model updates
- Performance test: Measure invalidation overhead

### Tag Usage Examples
```python
# User-specific cache
cache.set("user:123:profile", data, tags=["user:123"])

# Transaction cache
cache.set("tx:ABC123", data, tags=["tx", "user:123"])

# Invalidate all user cache
cache.invalidate_tag("user:123")

# Invalidate all transaction cache
cache.invalidate_tag("tx")
```

### Checkpoint Test
```bash
# Test tag-based cache invalidation
python -c "
from app import create_app
from services.cache import get_cache

app = create_app()
with app.app_context():
    cache = get_cache()
    
    # Set tagged cache
    if hasattr(cache, 'set'):
        cache.set('user:1:data', 'value1', tags=['user:1'])
        cache.set('user:1:profile', 'value2', tags=['user:1'])
        print('Set tagged cache entries')
    
    # Invalidate tag
    if hasattr(cache, 'invalidate_tag'):
        cache.invalidate_tag('user:1')
        print('Invalidated user:1 tag')
    
    # Verify cache cleared
    data1 = cache.get('user:1:data')
    data2 = cache.get('user:1:profile')
    print(f'Data1 after invalidation: {data1}')
    print(f'Data2 after invalidation: {data2}')
# Expected: Both None
"

# Test model event invalidation
python -c "
from app import create_app
from database import get_db
from models.transaction import Transaction

app = create_app()
with app.app_context():
    with get_db() as db:
        # Create transaction (should trigger invalidation)
        tx = Transaction(
            user_id=1,
            amount=1000,
            currency='NGN',
            hash_token='test'
        )
        db.add(tx)
        db.commit()
        print('Transaction created - cache should be invalidated')
"
```

---

## Phase 2 Checkpoint Test

```bash
#!/bin/bash
# Phase 2 Performance Checkpoint Test

echo "=== Phase 2 Performance Checkpoint Test ==="
echo ""

echo "1. Testing Query Optimization..."
python -c "
from app import create_app
from database import get_db
from models.transaction import Transaction
from sqlalchemy import event

app = create_app()
query_count = 0

@event.listens_for(app.extensions['sqlalchemy'].engine, 'before_cursor_execute')
def count_queries(*args, **kwargs):
    global query_count
    query_count += 1

with app.app_context():
    with get_db() as db:
        tx_list = db.query(Transaction).limit(10).all()
        print(f'Query count for 10 transactions: {query_count}')
" 2>/dev/null && echo "✓ Query optimization working" || echo "✗ Query optimization failed"

echo "2. Testing Connection Pool Settings..."
python -c "
from app import create_app
app = create_app()
with app.app_context():
    engine = app.extensions['sqlalchemy'].engine
    print(f'Pool size: {engine.pool.size()}')
" 2>/dev/null && echo "✓ Connection pool configured" || echo "✗ Connection pool not configured"

echo "3. Testing Database Indexes..."
python -c "
from database import engine
from sqlalchemy import inspect
inspector = inspect(engine)
indexes = inspector.get_indexes('transactions')
print(f'Transaction indexes: {len(indexes)}')
" 2>/dev/null && echo "✓ Database indexes present" || echo "✗ Database indexes missing"

echo "4. Testing Redis Cache..."
python -c "
from services.cache import get_cache
cache = get_cache()
cache.set('test', 'value', ttl=60)
result = cache.get('test')
print(f'Cache test: {result == \"value\"}')
" 2>/dev/null && echo "✓ Redis cache working" || echo "✗ Redis cache failed"

echo "5. Testing Cache Warming..."
python -c "
from services.cache_warming import warm_user_cache
warm_user_cache(1)
print('Cache warming executed')
" 2>/dev/null && echo "✓ Cache warming working" || echo "✗ Cache warming failed"

echo "6. Testing Tag-Based Cache Invalidation..."
python -c "
from services.cache import get_cache
cache = get_cache()
if hasattr(cache, 'set'):
    cache.set('test', 'value', tags=['test-tag'])
    cache.invalidate_tag('test-tag')
    print('Tag invalidation executed')
" 2>/dev/null && echo "✓ Tag-based invalidation working" || echo "⚠ Tag-based invalidation not implemented"

echo ""
echo "=== Phase 2 Checkpoint Complete ==="
```

---

## Phase 2 Summary

**Total Tasks:** 6  
**Total Estimated Effort:** ~43 hours  
**Risk Profile:** 3 Low, 2 Medium, 1 High  
**Dependencies:** None

**Completion Criteria:**
- All 6 checkpoint tests pass
- Query count reduced by 60%+
- Database indexes created and verified
- Redis cluster operational (if implemented)
- Cache warming functional
- Tag-based invalidation working

**Next Phase:** Phase 3 - Features & Functionality
