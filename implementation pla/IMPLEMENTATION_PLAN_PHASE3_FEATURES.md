# OnePay Implementation Plan - Phase 3: Features & Functionality

**Version:** 1.0  
**Created:** April 10, 2026  
**Status:** Active  
**Estimated Effort:** ~78 hours

---

## Overview

This document covers Phase 3 of the OnePay implementation plan: Features & Functionality. This phase includes 6 tasks focused on adding new features to enhance the application's capabilities.

**Tasks in this phase:** 6
- FEAT-001: Implement Refund Management UI (12h)
- FEAT-002: Add Payment Analytics Dashboard (16h)
- FEAT-003: Implement Multi-Currency Support (16h)
- FEAT-004: Add Invoice Template Customization (10h)
- FEAT-005: Implement Invoice Scheduling (16h)
- FEAT-006: Add Invoice Payment Reminders (8h)

---

## FEAT-001: Implement Refund Management UI

**Files:** `blueprints/payments.py`, `templates/refund.html`, `static/js/refund.js`, `services/korapay.py`  
**Estimated Effort:** 12 hours  
**Dependencies:** None  
**Risk:** Medium

### Implementation Steps

1. Add refund routes in `blueprints/payments.py`:
   ```python
   @app.route("/refunds")
   @login_required
   def refunds():
       """List all refunds for current user"""
       with get_db() as db:
           refunds = db.query(Refund).join(Transaction).filter(
               Transaction.user_id == current_user.id
           ).order_by(Refund.created_at.desc()).all()
       return render_template("refund.html", refunds=refunds)
   
   @app.route("/refunds/create", methods=["POST"])
   @login_required
   def create_refund():
       """Create a new refund"""
       tx_ref = request.form.get("tx_ref")
       amount = Decimal(request.form.get("amount"))
       reason = request.form.get("reason")
       
       with get_db() as db:
           tx = db.query(Transaction).filter_by(tx_ref=tx_ref).first()
           if not tx or tx.user_id != current_user.id:
               flash("Transaction not found", "error")
               return redirect(url_for("payments.refunds"))
           
           if tx.status != TransactionStatus.VERIFIED:
               flash("Can only refund verified transactions", "error")
               return redirect(url_for("payments.refunds"))
           
           refund = Refund(
               transaction_id=tx.id,
               amount=amount,
               currency=tx.currency,
               reason=reason
           )
           db.add(refund)
           
           # Call KoraPay refund API
           try:
               result = initiate_refund(
                   merchant_reference=tx.korapay_merchant_ref,
                   amount=amount,
                   reason=reason
               )
               refund.provider_refund_id = result.get("reference")
               refund.status = RefundStatus.PROCESSING
           except Exception as e:
               refund.status = RefundStatus.FAILED
               refund.failure_reason = str(e)
           
           db.commit()
           flash("Refund initiated successfully", "success")
           return redirect(url_for("payments.refunds"))
   ```
2. Create refund template `templates/refund.html`
3. Add refund service in `services/korapay.py`:
   ```python
   def initiate_refund(merchant_reference: str, amount: Decimal, reason: str) -> dict:
       """Initiate refund via KoraPay API"""
       url = f"{Config.KORAPAY_BASE_URL}/merchant/api/v1/refunds"
       headers = {
           "Authorization": f"Bearer {Config.KORAPAY_SECRET_KEY}",
           "Content-Type": "application/json"
       }
       payload = {
           "merchant_reference": merchant_reference,
           "amount": float(amount),
           "reason": reason
       }
       response = requests.post(url, json=payload, headers=headers, timeout=30)
       response.raise_for_status()
       return response.json()
   ```

### Acceptance Criteria
- [ ] Refund list page displays all user refunds
- [ ] Refund creation form validates input
- [ ] Refund API called successfully
- [ ] Refund status tracked in database
- [ ] Error handling for failed refunds

### Testing
- Unit test: Refund service integration
- Integration test: Refund creation flow
- UI test: Refund form validation

### Checkpoint Test
```bash
# Test refund routes
curl http://localhost:5000/refunds -i
# Expected: 302 redirect to login (if not authenticated)

# Test refund creation (after login)
curl -X POST http://localhost:5000/refunds/create \
  -d "tx_ref=TEST-REF&amount=100&reason=Test" \
  -i
# Expected: 302 redirect to refunds page

# Run unit tests
pytest tests/unit/test_refund.py -v

# Run integration tests
pytest tests/integration/test_refund_flow.py -v
```

---

## FEAT-002: Add Payment Analytics Dashboard

**Files:** `blueprints/payments.py`, `templates/analytics.html`, `static/js/analytics.js`  
**Estimated Effort:** 16 hours  
**Dependencies:** None  
**Risk:** Medium

### Implementation Steps

1. Add analytics route in `blueprints/payments.py` with aggregated queries:
   ```python
   @app.route("/analytics")
   @login_required
   def analytics():
       """Display payment analytics dashboard"""
       with get_db() as db:
           # Revenue by day (last 30 days)
           revenue_by_day = db.query(
               func.date(Transaction.created_at).label('date'),
               func.sum(Transaction.amount).label('revenue')
           ).filter(
               Transaction.user_id == current_user.id,
               Transaction.status == TransactionStatus.VERIFIED,
               Transaction.created_at >= datetime.now(timezone.utc) - timedelta(days=30)
           ).group_by(func.date(Transaction.created_at)).all()
           
           # Transaction status distribution
           status_distribution = db.query(
               Transaction.status,
               func.count(Transaction.id).label('count')
           ).filter(
               Transaction.user_id == current_user.id
           ).group_by(Transaction.status).all()
           
           # Top payment amounts
           top_payments = db.query(Transaction).filter(
               Transaction.user_id == current_user.id,
               Transaction.status == TransactionStatus.VERIFIED
           ).order_by(Transaction.amount.desc()).limit(10).all()
           
           # Conversion rate
           total_pending = db.query(Transaction).filter(
               Transaction.user_id == current_user.id,
               Transaction.status == TransactionStatus.PENDING
           ).count()
           total_verified = db.query(Transaction).filter(
               Transaction.user_id == current_user.id,
               Transaction.status == TransactionStatus.VERIFIED
           ).count()
           conversion_rate = (total_verified / (total_pending + total_verified) * 100) if (total_pending + total_verified) > 0 else 0
       
       return render_template("analytics.html",
           revenue_by_day=revenue_by_day,
           status_distribution=status_distribution,
           top_payments=top_payments,
           conversion_rate=conversion_rate
       )
   ```
2. Create analytics template with Chart.js
3. Create analytics JavaScript for chart rendering

### Acceptance Criteria
- [ ] Revenue chart displays 30-day trend
- [ ] Status distribution chart shown
- [ ] Top payments table displays
- [ ] Conversion rate calculated correctly
- [ ] Charts responsive on mobile

### Checkpoint Test
```bash
# Test analytics route
curl http://localhost:5000/analytics -i
# Expected: 302 redirect to login (if not authenticated)

# Run unit tests
pytest tests/unit/test_analytics.py -v
```

---

## FEAT-003: Implement Multi-Currency Support (USD, EUR)

**Files:** models (ExchangeRate), `config.py`, `services/exchange_rate.py` (new), `blueprints/payments.py`, `services/korapay.py`  
**Estimated Effort:** 16 hours  
**Dependencies:** None  
**Risk:** High

### Implementation Steps

1. Add supported currencies to config:
   ```python
   SUPPORTED_CURRENCIES: list[str] = ["NGN", "USD", "EUR"]
   DEFAULT_CURRENCY: str = os.getenv("DEFAULT_CURRENCY", "NGN")
   CURRENCY_SYMBOLS: dict[str, str] = {
       "NGN": "₦",
       "USD": "$",
       "EUR": "€"
   }
   ```
2. Create ExchangeRate model (migration):
   ```python
   # models/exchange_rate.py
   class ExchangeRate(Base):
       __tablename__ = 'exchange_rates'
       
       id = Column(Integer, primary_key=True)
       from_currency = Column(String(3), nullable=False)
       to_currency = Column(String(3), nullable=False)
       rate = Column(Numeric(10, 6), nullable=False)
       updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
       
       __table_args__ = (
           UniqueConstraint('from_currency', 'to_currency', name='uix_currency_pair'),
       )
   ```
3. Add exchange rate service:
   ```python
   # services/exchange_rate.py
   def get_exchange_rate(from_currency: str, to_currency: str) -> Decimal:
       """Get exchange rate between currencies"""
       with get_db() as db:
           rate = db.query(ExchangeRate).filter(
               ExchangeRate.from_currency == from_currency,
               ExchangeRate.to_currency == to_currency
           ).first()
           
           if not rate:
               # Fetch from external API
               rate = fetch_exchange_rate_from_api(from_currency, to_currency)
               # Cache in database
               new_rate = ExchangeRate(
                   from_currency=from_currency,
                   to_currency=to_currency,
                   rate=rate
               )
               db.add(new_rate)
               db.commit()
               return rate
           
           # Update if stale (older than 1 hour)
           if (datetime.now(timezone.utc) - rate.updated_at).total_seconds() > 3600:
               new_rate = fetch_exchange_rate_from_api(from_currency, to_currency)
               rate.rate = new_rate
               rate.updated_at = datetime.now(timezone.utc)
               db.commit()
           
           return rate
   ```
4. Update payment link creation to accept currency

### Acceptance Criteria
- [ ] Payment links can be created in USD, EUR, NGN
- [ ] Exchange rates fetched and cached
- [ ] Currency conversion accurate
- [ ] KoraPay receives NGN amounts

### Checkpoint Test
```bash
# Test exchange rate service
python -c "
from services.exchange_rate import get_exchange_rate
rate = get_exchange_rate('USD', 'NGN')
print(f'USD to NGN rate: {rate}')
# Expected: Decimal value > 0
"

# Test multi-currency payment link creation
curl -X POST http://localhost:5000/api/payments/link \
  -H "Content-Type: application/json" \
  -d '{"amount": "100.00", "currency": "USD"}' \
  -i
# Expected: 201 with payment link
```

---

## FEAT-004: Add Invoice Template Customization

**Files:** models (InvoiceTemplate), `services/invoice.py`, `templates/invoice_template_editor.html`  
**Estimated Effort:** 10 hours  
**Dependencies:** None  
**Risk:** Medium

### Implementation Steps

1. Add InvoiceTemplate model (migration)
2. Add template CRUD routes
3. Create template editor UI
4. Update invoice rendering to use custom templates

### Acceptance Criteria
- [ ] Users can create custom invoice templates
- [ ] Templates support HTML and CSS
- [ ] Preview available during editing
- [ ] PDF generation works with custom templates

### Checkpoint Test
```bash
# Test template routes
curl http://localhost:5000/invoice-templates -i
# Expected: 302 redirect to login

# Run unit tests
pytest tests/unit/test_invoice_templates.py -v
```

---

## FEAT-005: Implement Invoice Scheduling and Recurring Invoices

**Files:** models (RecurringInvoice), `services/task_queue.py`, `services/invoice.py`  
**Estimated Effort:** 16 hours  
**Dependencies:** None  
**Risk:** High

### Implementation Steps

1. Add RecurringInvoice model (migration)
2. Add recurring invoice CRUD routes
3. Add background task for generating invoices
4. Add invoice creation service

### Acceptance Criteria
- [ ] Users can create recurring invoice schedules
- [ ] Invoices generated automatically on schedule
- [ ] Multiple frequency options available
- [ ] End date support

### Checkpoint Test
```bash
# Test recurring invoice creation
curl -X POST http://localhost:5000/recurring-invoices/create \
  -d "customer_email=test@example.com&amount=1000&frequency=monthly" \
  -i
# Expected: 302 redirect

# Test periodic task
python -c "
from services.task_queue import generate_recurring_invoices
generate_recurring_invoices()
print('Recurring invoice generation executed')
"

# Run unit tests
pytest tests/unit/test_recurring_invoices.py -v
```

---

## FEAT-006: Add Invoice Payment Reminder Automation

**Files:** `services/task_queue.py`, `services/email.py`, models (InvoiceSettings)  
**Estimated Effort:** 8 hours  
**Dependencies:** FEAT-005 (invoice scheduling)  
**Risk:** Medium

### Implementation Steps

1. Add reminder settings to InvoiceSettings model (migration)
2. Add background task for payment reminders
3. Add reminder email templates
4. Add settings UI for reminders

### Acceptance Criteria
- [ ] Reminders sent before due date
- [ ] Reminders sent for overdue invoices
- [ ] Reminder timing configurable
- [ ] Reminders can be disabled

### Checkpoint Test
```bash
# Test reminder task
python -c "
from services.task_queue import send_invoice_reminders
send_invoice_reminders()
print('Reminder task executed')
"

# Run unit tests
pytest tests/unit/test_invoice_reminders.py -v
```

---

## Phase 3 Checkpoint Test

```bash
#!/bin/bash
# Phase 3 Features Checkpoint Test

echo "=== Phase 3 Features Checkpoint Test ==="
echo ""

echo "1. Testing Refund Management..."
curl -s http://localhost:5000/refunds | grep -q "Refund" && echo "✓ Refund page accessible" || echo "✗ Refund page not accessible"

echo "2. Testing Analytics Dashboard..."
curl -s http://localhost:5000/analytics | grep -q "Analytics" && echo "✓ Analytics page accessible" || echo "✗ Analytics page not accessible"

echo "3. Testing Multi-Currency..."
python -c "from services.exchange_rate import get_exchange_rate; print('✓ Exchange rate service available')" 2>/dev/null || echo "⚠ Exchange rate service not yet implemented"

echo "4. Testing Invoice Templates..."
curl -s http://localhost:5000/invoice-templates | grep -q "Template" && echo "✓ Invoice templates accessible" || echo "✗ Invoice templates not accessible"

echo "5. Testing Recurring Invoices..."
curl -s http://localhost:5000/recurring-invoices | grep -q "Recurring" && echo "✓ Recurring invoices accessible" || echo "✗ Recurring invoices not accessible"

echo "6. Testing Invoice Reminders..."
python -c "from services.task_queue import send_invoice_reminders; print('✓ Reminder task available')" 2>/dev/null || echo "⚠ Reminder task not yet implemented"

echo ""
echo "=== Phase 3 Checkpoint Complete ==="
```

---

## Phase 3 Summary

**Total Tasks:** 6  
**Total Estimated Effort:** ~78 hours  
**Risk Profile:** 3 Low, 2 Medium, 1 High  
**Dependencies:** 1 internal (FEAT-006 depends on FEAT-005)

**Completion Criteria:**
- All 6 checkpoint tests pass
- Refund management functional
- Analytics dashboard operational
- Multi-currency support working
- Invoice templates customizable
- Recurring invoices scheduling functional
- Payment reminders automated

**Next Phase:** Phase 4 - Testing & Quality
