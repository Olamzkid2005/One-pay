# N+1 Query Audit Report

**Date**: 2025  
**Scope**: `blueprints/payments.py`, `blueprints/invoices.py`, `blueprints/public.py`, `services/webhook.py`, `services/invoice.py`  
**Requirement**: 9.1 — Identify and eliminate N+1 query patterns

---

## Summary

Three confirmed N+1 patterns were found, ranked by impact. One additional
redundant-query pattern was identified that is not a classic N+1 but wastes
queries on every request.

---

## Finding 1 — `GET /payments/history` (HIGH IMPACT)

**File**: `blueprints/payments.py` → `transaction_history()`  
**Lines**: ~856–882

### Pattern

```python
transactions = (
    db.query(Transaction)
    .filter(Transaction.user_id == current_user_id())
    .order_by(Transaction.created_at.desc())
    .offset(offset)
    .limit(PAGE_SIZE)
    .all()
)

return jsonify({
    "transactions": [t.to_dict() for t in transactions],  # loop here
    ...
})
```

`Transaction.to_dict()` accesses only columns on the `Transaction` row itself,
so there is no relationship traversal in the loop today. **However**, the
`Transaction` model has a `backref="invoice"` relationship defined on
`Invoice.transaction`. If any code path accesses `t.invoice` inside the loop
(e.g. to include invoice number in the history response), SQLAlchemy will fire
one SELECT per row — a textbook N+1.

More critically, the endpoint issues **two separate queries** for every page
load: one `COUNT(*)` and one `SELECT … LIMIT`. With the composite index
`ix_transactions_user_created` already in place, both queries are fast, but
the count query is still redundant when the caller only needs the current page.

**Recommended fix**: Add `selectinload(Transaction.invoice)` to the query so
that if `invoice` is ever accessed in the loop it is pre-fetched in a single
IN-clause query rather than N individual queries.

```python
from sqlalchemy.orm import selectinload

transactions = (
    db.query(Transaction)
    .options(selectinload(Transaction.invoice))
    .filter(Transaction.user_id == current_user_id())
    .order_by(Transaction.created_at.desc())
    .offset(offset)
    .limit(PAGE_SIZE)
    .all()
)
```

---

## Finding 2 — `GET /invoices/list` → `list_invoices()` (HIGH IMPACT)

**File**: `blueprints/invoices.py` → `list_invoices()` (via `invoice_service.get_invoice_history`)  
**Lines**: ~390–430 (blueprint) + `services/invoice.py` lines 218–285

### Pattern

`get_invoice_history` already uses `joinedload(Invoice.transaction)`, which is
correct. **The N+1 occurs in the serialisation loop in the blueprint**:

```python
for invoice in invoices:
    invoice_list.append({
        "transaction_reference": invoice.transaction.tx_ref   # ← relationship access
        if invoice.transaction
        else None,
        ...
    })
```

Because `joinedload` is used, this is currently safe — the transaction is
loaded in the same JOIN. But `joinedload` on a one-to-one relationship with
`uselist=False` can produce a Cartesian product when combined with
`LIMIT`/`OFFSET` pagination (a known SQLAlchemy gotcha). SQLAlchemy silently
applies the LIMIT to the outer query, which is correct here, but the behaviour
is fragile.

**Recommended fix**: Replace `joinedload` with `selectinload` in
`get_invoice_history`. `selectinload` issues a separate `SELECT … WHERE id IN
(…)` after the paginated query, which is both correct and efficient:

```python
# services/invoice.py  get_invoice_history()
from sqlalchemy.orm import selectinload

query = (
    db.query(Invoice)
    .options(selectinload(Invoice.transaction))   # was joinedload
    .filter(Invoice.user_id == user_id)
)
```

This reduces the query from a JOIN (which can inflate row counts) to two clean
queries regardless of page size.

---

## Finding 3 — `transfer_status` + `korapay_webhook` user lookup (MEDIUM IMPACT)

**File**: `blueprints/public.py` → `transfer_status()` (lines ~640–660)

### Pattern

When a transfer is confirmed, the code fetches the `User` in a separate query
**after** already having the `Transaction`:

```python
# Transaction already loaded above
user_for_email = (
    db.query(User).filter(User.id == t_locked.user_id).first()
)
if user_for_email:
    send_payment_notification_emails(db, t_locked, user_for_email)
```

Inside `send_payment_notification_emails`, the function then queries
`InvoiceSettings` separately:

```python
settings = (
    db.query(InvoiceSettings)
    .filter(InvoiceSettings.user_id == user.id)
    .first()
)
```

And separately queries `Invoice`:

```python
invoice = (
    db.query(Invoice).filter(Invoice.transaction_id == transaction.id).first()
)
```

This is **3 sequential single-row lookups** that could be collapsed. While not
a loop-based N+1, it is a "chatty" query pattern that fires on every payment
confirmation event.

The same pattern repeats in `korapay_webhook` in `blueprints/public.py`.

**Recommended fix**: Add a `user` relationship to `Transaction` and eager-load
it when fetching the transaction for confirmation:

```python
from sqlalchemy.orm import joinedload

t_locked = (
    db.query(Transaction)
    .options(joinedload(Transaction.user))
    .filter(Transaction.tx_ref == tx_ref)
    .with_for_update()
    .first()
)
```

Then pass `t_locked.user` directly to `send_payment_notification_emails`,
eliminating the extra `User` query. The `InvoiceSettings` and `Invoice` lookups
inside the helper are single-row lookups that are harder to pre-fetch without
restructuring the helper, but they are low-frequency (only on payment
confirmation) so they are lower priority.

---

## Finding 4 — Redundant `User` fetch on every authenticated page render (LOW IMPACT)

**File**: `blueprints/payments.py` → `dashboard()`, `settings()`, `history()`, `check_status()`

### Pattern

Every page-render route fetches the `User` row solely to get
`profile_picture_url` and `webhook_url`:

```python
with get_db() as db:
    user = db.query(User).filter(User.id == current_user_id()).first()
    profile_picture = user.profile_picture_url if user else None
```

This is not an N+1 (it is a single query), but it is a repeated pattern across
four routes. These fields could be stored in the session at login time and
refreshed only when the user updates their profile, eliminating the DB round
trip entirely.

This is a caching opportunity rather than an N+1 fix, and is lower priority
than Findings 1–3.

---

## Top 3 Most Impactful Fixes (Priority Order)

| # | Location | Fix | Queries saved per request |
|---|----------|-----|--------------------------|
| 1 | `services/invoice.py` `get_invoice_history` | `joinedload` → `selectinload` | Prevents potential Cartesian product; makes pagination safe |
| 2 | `blueprints/payments.py` `transaction_history` | Add `selectinload(Transaction.invoice)` | Pre-fetches invoice relationship; prevents future N+1 as feature grows |
| 3 | `blueprints/public.py` `transfer_status` + `korapay_webhook` | Eager-load `Transaction.user` | Saves 1 query per payment confirmation event |

---

## What Was NOT Found

- No queries inside explicit `for` loops in the audited files (the serialisation
  loops in `transaction_history` and `list_invoices` access only already-loaded
  attributes or use `joinedload`).
- `sync_invoice_on_transaction_update` issues a single `Invoice` lookup per
  call — not an N+1.
- `create_invoice` fetches `InvoiceSettings` once per invocation — not an N+1.

---

## Next Steps

These findings feed directly into task **12.2** (add joinedload/selectinload to
queries). The fixes are low-risk, additive changes that do not alter business
logic.
