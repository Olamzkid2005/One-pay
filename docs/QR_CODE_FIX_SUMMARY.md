# QR Code Display Fix - Complete Summary

## Issue
QR codes were not displaying on the payment verification page when users clicked the "QR Code" toggle button. The "SCAN TO PAY" section appeared but was empty.

## Root Causes Identified

### 1. Variable Scope Error in Backend (Primary Issue)
**Location:** `blueprints/payments.py` line 358-362

**Problem:** The `payment_url` variable was used in QR code generation BEFORE it was defined:
```python
# QR code generation tried to use payment_url here (line 358)
transaction.qr_code_payment_url = qr_service.generate_payment_qr(
    payment_url=payment_url,  # ← UNDEFINED!
    ...
)

# But payment_url was only defined later (line 387)
payment_url = f"{base_url}/pay/{tx_ref}"
```

**Impact:** QR code generation failed silently (caught by exception handler), resulting in `NULL` values in database.

**Fix:** Moved `payment_url` definition before QR code generation and added `db.flush()` to save QR codes.

### 2. Auto-Loading QR Codes on Page Load
**Location:** `static/js/verify.js` line 164

**Problem:** `showQRCodes()` was called automatically when page loaded, causing QR section to appear even when "Bank Transfer" was selected.

**Fix:** Removed automatic call. QR codes now only load when user clicks "QR Code" button.

### 3. Duplicate QR Codes
**Location:** `templates/verify.html`

**Problem:** Both payment URL QR and virtual account QR were displayed, appearing as duplicates.

**Fix:** Removed virtual account QR code section, keeping only payment URL QR code.

## Changes Made

### Backend Changes
**File:** `blueprints/payments.py`
- Moved `payment_url` definition before QR code generation
- Added `db.flush()` after QR code generation to persist to database
- QR codes now generate correctly for all new payments

### Frontend Changes
**File:** `static/js/verify.js`
- Removed automatic `showQRCodes()` call on page load
- QR codes only load when user explicitly clicks "QR Code" button

**File:** `templates/verify.html`
- Removed virtual account QR code container
- Kept only payment URL QR code
- Removed `mb-6` margin from payment QR container

## Testing

### Verification Steps
1. Create new payment through dashboard
2. Open payment link
3. Verify "Bank Transfer" section shows by default
4. Click "QR Code" button
5. Verify single QR code appears
6. Click "Bank Transfer" button
7. Verify QR section hides and bank details show

### Expected Behavior
- ✅ Bank details visible by default
- ✅ QR section hidden by default
- ✅ Clicking "QR Code" shows single QR code
- ✅ Clicking "Bank Transfer" hides QR section
- ✅ Toggle buttons change color to indicate active state
- ✅ No JavaScript errors in console

## Technical Details

### QR Code Generation Flow
```
1. User creates payment → Backend generates tx_ref
2. Backend builds payment_url = f"{base_url}/pay/{tx_ref}"
3. Backend calls qr_service.generate_payment_qr(payment_url, ...)
4. QR code data (base64 PNG) stored in transaction.qr_code_payment_url
5. Backend calls db.flush() to persist
6. Frontend receives QR data via Jinja2 template variable
7. User clicks "QR Code" button → showPaymentMethod('qr') called
8. showPaymentMethod('qr') calls showQRCodes(window.ONEPAY_QR_PAYMENT_URL, ...)
9. showQRCodes() sets img.src and removes 'hidden' class
10. QR code displays
```

### Why Old Payments Don't Have QR Codes
Payments created before this fix have `NULL` values in `qr_code_payment_url` column because:
1. The variable scope error caused generation to fail
2. Exception was caught and logged but not raised
3. Transaction was saved with `NULL` QR code fields

**Solution:** Create new payments. Old payments cannot be retroactively fixed without regenerating QR codes.

## Files Modified
- `blueprints/payments.py` - Fixed QR code generation
- `static/js/verify.js` - Removed auto-load
- `templates/verify.html` - Removed duplicate QR code

## Deployment Notes
- No database migration required (columns already exist)
- No configuration changes needed
- Restart Flask server to apply changes
- Old payment links will continue to work but won't have QR codes
- New payment links will have QR codes

## Future Improvements
- Add fallback UI when QR codes are missing ("QR code not available")
- Add retry mechanism for failed QR generation
- Consider background job for regenerating QR codes for old payments
- Add QR code preview in merchant dashboard

---

**Fixed:** March 27, 2026
**Version:** 1.1.0
