# Payment Methods and QR Codes - Design Document

## Overview

This design extends OnePay's payment verification platform to support multiple payment methods (bank transfer and card payments) and QR code generation for easy payment detail sharing. Currently, OnePay only supports bank transfers via Quickteller Dynamic Transfer API. This enhancement enables merchants to offer customers payment method choice while maintaining the existing secure, time-bound payment link architecture.

The design maintains backward compatibility with existing payment links, follows OnePay's established patterns for security and error handling, and integrates seamlessly with the existing polling-based verification flow.

## Architecture

### High-Level Architecture

The system extends the existing three-tier architecture:

1. **Presentation Layer** (Flask templates + JavaScript)
   - Payment page displays available payment methods
   - Dynamic UI switches between bank transfer and card payment forms
   - QR code displayed as base64-encoded PNG embedded in HTML
   - Existing polling mechanism extended to handle card payment status

2. **Application Layer** (Flask blueprints + services)
   - Payment method selection logic in transaction creation
   - QR code generation service (new)
   - Card payment service integrating with Quickteller Card Payment API (new)
   - Fee calculation engine (new)
   - Existing webhook delivery extended to include payment method info

3. **Data Layer** (SQLAlchemy models + SQLite/PostgreSQL)
   - Transaction model extended with payment method fields
   - Database migration for schema changes
   - Backward-compatible defaults for existing records

### Integration Points

**Existing Systems:**
- Quickteller Dynamic Transfer API (bank transfers) - unchanged
- Webhook delivery system - extended with new fields
- Polling mechanism - extended to handle card payments
- HMAC-based link security - unchanged
- Rate limiting - extended to card payment endpoints

**New Systems:**
- Quickteller Card Payment API - new integration
- QR code generation library (qrcode Python package)
- Fee calculation engine

### Design Principles

1. **Backward Compatibility**: Existing payment links continue working as bank-transfer-only
2. **Security First**: Card data never stored, PCI-DSS compliance measures throughout
3. **Mock Mode Support**: Full testing without real API credentials
4. **Fail-Safe Defaults**: Missing configuration defaults to bank transfer only
5. **Audit Trail**: All payment attempts logged for security and debugging

## Components and Interfaces

### 1. Database Schema Extensions

**Transaction Model Changes:**

```python
# New columns in transactions table
allowed_payment_methods = Column(JSON, nullable=True)  # ['bank_transfer', 'card_payment']
selected_payment_method = Column(String(20), nullable=True)  # 'bank_transfer' or 'card_payment'
processing_fee = Column(Numeric(12, 2), default=0)  # Fee amount in currency units
total_amount = Column(Numeric(12, 2), nullable=True)  # Original amount + processing fee
card_last_four = Column(String(4), nullable=True)  # Last 4 digits for display
card_brand = Column(String(20), nullable=True)  # 'visa', 'mastercard', etc.
```

**Migration Strategy:**
- Alembic migration adds columns with nullable=True
- Default values for existing records:
  - `allowed_payment_methods = ['bank_transfer']`
  - `selected_payment_method = 'bank_transfer'`
  - `processing_fee = 0`
  - `total_amount = amount`
- New transactions require `allowed_payment_methods` in API request

**Data Types:**
- JSON for `allowed_payment_methods`: Flexible array storage, easy validation
- Numeric(12, 2) for monetary values: Precise decimal arithmetic, no floating-point errors
- String(20) for payment method: Enum-like values, indexed for queries

### 2. API Endpoints

**Modified Endpoints:**

**POST /api/payments/link** (Extended)
```python
# Request body (new fields)
{
  "amount": "1000.00",
  "currency": "NGN",
  "description": "Product purchase",
  "allowed_payment_methods": ["bank_transfer", "card_payment"],  # NEW - optional, defaults to ["bank_transfer"]
  "customer_email": "customer@example.com",
  "webhook_url": "https://merchant.com/webhook"
}

# Response (new fields)
{
  "success": true,
  "tx_ref": "ONEPAY-...",
  "payment_url": "https://onepay.com/pay/ONEPAY-...",
  "amount": "1000.00",
  "currency": "NGN",
  "allowed_payment_methods": ["bank_transfer", "card_payment"],  # NEW
  "expires_at": "2024-01-01T12:30:00Z",
  "virtual_account_number": "1234567890",  # Only if bank_transfer allowed
  "virtual_bank_name": "Wema Bank",
  "virtual_account_name": "OnePay Payment"
}
```

**GET /api/payments/preview/<tx_ref>** (Extended)
```python
# Response (new fields)
{
  "success": true,
  "tx_ref": "ONEPAY-...",
  "amount": "1000.00",
  "currency": "NGN",
  "allowed_payment_methods": ["bank_transfer", "card_payment"],  # NEW
  "processing_fee": "15.00",  # NEW - only if card_payment selected
  "total_amount": "1015.00",  # NEW - only if card_payment selected
  "description": "Product purchase",
  "expires_at": "2024-01-01T12:30:00Z",
  "is_expired": false,
  "is_used": false,
  "status": "pending",
  "virtual_account_number": "1234567890",  # Only if bank_transfer allowed
  "virtual_bank_name": "Wema Bank",
  "virtual_account_name": "OnePay Payment"
}
```

**New Endpoints:**

**POST /api/payments/select-method/<tx_ref>**
```python
# Purpose: Customer selects payment method and gets fee calculation
# Request body
{
  "payment_method": "card_payment"  # or "bank_transfer"
}

# Response
{
  "success": true,
  "payment_method": "card_payment",
  "original_amount": "1000.00",
  "processing_fee": "15.00",
  "total_amount": "1015.00",
  "currency": "NGN"
}

# Validation:
# - tx_ref must be valid and not expired
# - payment_method must be in allowed_payment_methods
# - Updates transaction.selected_payment_method
# - Calculates and stores processing_fee and total_amount
```

**POST /api/payments/card-payment/<tx_ref>**
```python
# Purpose: Process card payment
# Request body
{
  "card_number": "4111111111111111",
  "expiry_month": "12",
  "expiry_year": "2025",
  "cvv": "123",
  "cardholder_name": "John Doe"
}

# Response (success)
{
  "success": true,
  "status": "verified",
  "tx_ref": "ONEPAY-...",
  "amount": "1015.00",
  "message": "Payment successful"
}

# Response (failure)
{
  "success": false,
  "status": "failed",
  "error": "PAYMENT_DECLINED",
  "message": "Card payment was declined. Please try another card."
}

# Security:
# - Rate limited: 5 attempts per 15 minutes per IP
# - CSRF token required
# - Card data validated before transmission
# - Card details never logged or stored (except last 4 digits)
# - Transmitted to Quickteller over HTTPS only
# - Audit log records attempt with outcome (no card details)
```

**GET /api/payments/qr-code/<tx_ref>**
```python
# Purpose: Generate QR code image for payment details
# Response: PNG image (image/png)
# - QR code contains JSON with payment details
# - Cached for transaction lifetime
# - Returns 404 if transaction expired or verified
# - Rate limited: 20 requests per minute per IP
```

### 3. QR Code Implementation

**Library Selection:**
- **qrcode** Python package (version 7.4.2 or higher)
- Mature, well-maintained, pure Python implementation
- Supports error correction, custom sizing, PNG output
- No external dependencies beyond Pillow for image generation

**QR Code Data Format:**
```json
{
  "tx_ref": "ONEPAY-ABC123",
  "amount": "1000.00",
  "currency": "NGN",
  "description": "Product purchase",
  "merchant_name": "Merchant Username",
  "payment_url": "https://onepay.com/pay/ONEPAY-ABC123",
  "expires_at": "2024-01-01T12:30:00Z",
  "allowed_payment_methods": ["bank_transfer", "card_payment"],
  "virtual_account_number": "1234567890",
  "virtual_bank_name": "Wema Bank",
  "virtual_account_name": "OnePay Payment"
}
```

**Size Optimization:**
- Maximum QR code capacity (version 10, error correction M): ~1000 characters
- If data exceeds capacity, omit optional fields in order:
  1. `description` (if > 50 chars, truncate to 50)
  2. `merchant_name`
  3. `description` (remove entirely)
- Core fields always included: `tx_ref`, `amount`, `currency`, `payment_url`, `expires_at`

**Generation Parameters:**
```python
import qrcode

qr = qrcode.QRCode(
    version=None,  # Auto-size based on data
    error_correction=qrcode.constants.ERROR_CORRECT_M,  # 15% recovery
    box_size=10,  # 10 pixels per box
    border=4,  # 4 boxes border (QR spec minimum)
)
qr.add_data(json_data)
qr.make(fit=True)
img = qr.make_image(fill_color="black", back_color="white")
```

**Delivery Method:**
- Base64-encoded PNG embedded in HTML as data URL
- Avoids separate HTTP request for image
- Cached in memory for transaction lifetime (keyed by tx_ref)
- Cache cleared when transaction expires or is verified

**Service Interface:**
```python
# services/qr_code.py

def generate_qr_code(transaction: Transaction, base_url: str) -> str:
    """
    Generate QR code for transaction as base64-encoded PNG data URL.
    
    Args:
        transaction: Transaction ORM object
        base_url: Base URL for payment_url (e.g., "https://onepay.com")
    
    Returns:
        Base64-encoded data URL: "data:image/png;base64,iVBORw0KG..."
    
    Raises:
        QRCodeError: If generation fails
    """
    pass

def get_qr_data(transaction: Transaction, base_url: str) -> dict:
    """
    Build QR code data dict from transaction.
    Optimizes size by omitting optional fields if needed.
    """
    pass
```

### 4. Card Payment Integration

**Quickteller Card Payment API:**
- Endpoint: `POST {QUICKTELLER_BASE_URL}/paymentgateway/api/v1/card/payment`
- Authentication: OAuth Bearer token (same as Dynamic Transfer)
- Request format: JSON with card details and transaction info
- Response codes:
  - `00`: Success (payment approved)
  - `06`: Declined (insufficient funds, invalid card, etc.)
  - `91`: Timeout (retry later)
  - Other: Various error conditions

**Service Interface:**
```python
# services/quickteller.py (extended)

class QuicktellerService:
    def process_card_payment(
        self,
        transaction_reference: str,
        amount_kobo: int,
        card_number: str,
        expiry_month: str,
        expiry_year: str,
        cvv: str,
        cardholder_name: str,
    ) -> dict:
        """
        Process card payment via Quickteller Card Payment API.
        
        Args:
            transaction_reference: Unique tx_ref
            amount_kobo: Amount in kobo (₦1,000 = 100000 kobo)
            card_number: 13-19 digit card number
            expiry_month: 2-digit month (01-12)
            expiry_year: 4-digit year
            cvv: 3-4 digit CVV
            cardholder_name: Name on card
        
        Returns:
            {
                "responseCode": "00",  # or error code
                "responseMessage": "Approved",
                "transactionReference": "ONEPAY-...",
                "cardBrand": "visa",  # visa, mastercard, verve, etc.
                "last4": "1111"
            }
        
        Raises:
            QuicktellerError: If API call fails
        """
        pass
    
    def is_card_configured(self) -> bool:
        """True if card payment credentials are set."""
        return bool(
            Config.QUICKTELLER_CARD_MERCHANT_ID and
            Config.QUICKTELLER_CARD_API_KEY and
            Config.QUICKTELLER_CARD_TERMINAL_ID
        )
```

**Mock Mode Implementation:**
```python
def _mock_process_card_payment(self, card_number: str, amount_kobo: int, transaction_reference: str) -> dict:
    """
    Mock card payment for testing without real credentials.
    - Even last digit → success (00)
    - Odd last digit → declined (06)
    """
    last_digit = int(card_number[-1])
    if last_digit % 2 == 0:
        return {
            "responseCode": "00",
            "responseMessage": "Approved (Mock)",
            "transactionReference": transaction_reference,
            "cardBrand": "visa",
            "last4": card_number[-4:]
        }
    else:
        return {
            "responseCode": "06",
            "responseMessage": "Declined (Mock)",
            "transactionReference": transaction_reference
        }
```

**Configuration:**
```python
# config.py (new environment variables)

QUICKTELLER_CARD_MERCHANT_ID = os.getenv("QUICKTELLER_CARD_MERCHANT_ID", "")
QUICKTELLER_CARD_API_KEY = os.getenv("QUICKTELLER_CARD_API_KEY", "")
QUICKTELLER_CARD_TERMINAL_ID = os.getenv("QUICKTELLER_CARD_TERMINAL_ID", "")
```

### 5. Payment Method Selection Logic

**Merchant Configuration (Link Creation):**
```python
# In create_payment_link endpoint
allowed_methods = data.get("allowed_payment_methods", ["bank_transfer"])

# Validation
if not allowed_methods or not isinstance(allowed_methods, list):
    return error("allowed_payment_methods must be a non-empty array", "VALIDATION_ERROR", 400)

valid_methods = {"bank_transfer", "card_payment"}
if not all(m in valid_methods for m in allowed_methods):
    return error("Invalid payment method", "INVALID_PAYMENT_METHOD", 400)

transaction.allowed_payment_methods = allowed_methods
```

**Customer Selection (Payment Page):**
```python
# In select_method endpoint
selected_method = data.get("payment_method")

if selected_method not in transaction.allowed_payment_methods:
    return error("Payment method not allowed for this transaction", "METHOD_NOT_ALLOWED", 400)

transaction.selected_payment_method = selected_method

# Calculate fees if card payment
if selected_method == "card_payment":
    transaction.processing_fee = calculate_processing_fee(transaction.amount)
    transaction.total_amount = transaction.amount + transaction.processing_fee
else:
    transaction.processing_fee = Decimal("0")
    transaction.total_amount = transaction.amount
```

**UI Display Logic:**
```javascript
// In verify.js
if (data.allowed_payment_methods.length === 1) {
    // Single method - show directly without selection UI
    showPaymentMethod(data.allowed_payment_methods[0]);
} else {
    // Multiple methods - show selection tabs/radio buttons
    showPaymentMethodSelector(data.allowed_payment_methods);
}
```

### 6. Fee Calculation Engine

**Fee Structure:**
- Bank transfer: 0% (no fee)
- Card payment: 1.5% of transaction amount

**Implementation:**
```python
# services/fees.py (new file)

from decimal import Decimal, ROUND_HALF_UP

CARD_PAYMENT_FEE_RATE = Decimal("0.015")  # 1.5%

def calculate_processing_fee(amount: Decimal, payment_method: str) -> Decimal:
    """
    Calculate processing fee for a payment method.
    
    Args:
        amount: Transaction amount
        payment_method: 'bank_transfer' or 'card_payment'
    
    Returns:
        Fee amount rounded to 2 decimal places (ROUND_HALF_UP)
    """
    if payment_method == "card_payment":
        fee = amount * CARD_PAYMENT_FEE_RATE
        return fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Decimal("0")

def calculate_total_amount(amount: Decimal, payment_method: str) -> Decimal:
    """Calculate total amount including processing fee."""
    fee = calculate_processing_fee(amount, payment_method)
    return amount + fee
```

**Display Format:**
```python
# In API responses and UI
{
    "original_amount": "1000.00",
    "processing_fee": "15.00",
    "total_amount": "1015.00",
    "fee_breakdown": {
        "rate": "1.5%",
        "description": "Card processing fee"
    }
}
```

## Data Models

### Transaction Model (Extended)

```python
class Transaction(Base):
    __tablename__ = "transactions"
    
    # ... existing fields ...
    
    # Payment method fields
    allowed_payment_methods = Column(JSON, nullable=True)
    selected_payment_method = Column(String(20), nullable=True)
    processing_fee = Column(Numeric(12, 2), default=0)
    total_amount = Column(Numeric(12, 2), nullable=True)
    
    # Card payment fields (minimal storage for display only)
    card_last_four = Column(String(4), nullable=True)
    card_brand = Column(String(20), nullable=True)
    
    def to_dict(self):
        """Extended to include payment method fields."""
        base = {
            # ... existing fields ...
        }
        
        # Add payment method fields
        if self.allowed_payment_methods:
            base["allowed_payment_methods"] = self.allowed_payment_methods
        if self.selected_payment_method:
            base["selected_payment_method"] = self.selected_payment_method
        if self.processing_fee:
            base["processing_fee"] = str(self.processing_fee)
        if self.total_amount:
            base["total_amount"] = str(self.total_amount)
        if self.card_last_four:
            base["card_last_four"] = self.card_last_four
        if self.card_brand:
            base["card_brand"] = self.card_brand
            
        return base
```

### Database Migration

```python
# alembic/versions/YYYYMMDDHHMMSS_add_payment_methods.py

def upgrade():
    # Add new columns
    op.add_column('transactions', sa.Column('allowed_payment_methods', sa.JSON(), nullable=True))
    op.add_column('transactions', sa.Column('selected_payment_method', sa.String(20), nullable=True))
    op.add_column('transactions', sa.Column('processing_fee', sa.Numeric(12, 2), server_default='0'))
    op.add_column('transactions', sa.Column('total_amount', sa.Numeric(12, 2), nullable=True))
    op.add_column('transactions', sa.Column('card_last_four', sa.String(4), nullable=True))
    op.add_column('transactions', sa.Column('card_brand', sa.String(20), nullable=True))
    
    # Set defaults for existing records
    op.execute("""
        UPDATE transactions 
        SET allowed_payment_methods = '["bank_transfer"]',
            selected_payment_method = 'bank_transfer',
            processing_fee = 0,
            total_amount = amount
        WHERE allowed_payment_methods IS NULL
    """)
    
    # Add indexes for common queries
    op.create_index('ix_transactions_selected_method', 'transactions', ['selected_payment_method'])

def downgrade():
    op.drop_index('ix_transactions_selected_method', 'transactions')
    op.drop_column('transactions', 'card_brand')
    op.drop_column('transactions', 'card_last_four')
    op.drop_column('transactions', 'total_amount')
    op.drop_column('transactions', 'processing_fee')
    op.drop_column('transactions', 'selected_payment_method')
    op.drop_column('transactions', 'allowed_payment_methods')
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: QR Code Round-Trip Preservation

*For any* valid transaction, encoding the transaction data into a QR code and then decoding it should produce equivalent payment data with matching tx_ref, amount, currency, and payment_url.

**Validates: Requirements 1.3, 15.3, 15.4, 15.5, 15.6**

### Property 2: QR Code Contains Required Fields

*For any* transaction, the QR code data should include all required fields: tx_ref, amount, currency, payment_url, expires_at, and allowed_payment_methods.

**Validates: Requirements 1.2, 9.2, 9.4**

### Property 3: QR Code Visibility Based on Transaction State

*For any* transaction, QR codes should be displayed only when the transaction status is pending, and should not be displayed when the transaction is expired or verified.

**Validates: Requirements 1.5, 1.6, 1.7**

### Property 4: Payment Method Array Validation

*For any* payment link creation request, the system should accept only arrays containing "bank_transfer" and/or "card_payment", and should reject arrays containing any other values.

**Validates: Requirements 2.1, 2.2, 2.6**

### Property 5: Payment Method Storage Round-Trip

*For any* transaction created with allowed payment methods, retrieving the transaction should return the same payment methods that were specified during creation.

**Validates: Requirements 2.5, 7.1**

### Property 6: Payment Method UI Display

*For any* transaction, the payment page should display UI elements for all payment methods in the allowed_payment_methods array.

**Validates: Requirements 3.1, 3.4**

### Property 7: Card Number Luhn Validation

*For any* card number submitted for payment, the system should accept only card numbers that pass the Luhn algorithm check and should reject those that fail.

**Validates: Requirements 4.3**

### Property 8: Expiry Date Future Validation

*For any* card expiry date submitted for payment, the system should accept only dates in the future and should reject dates in the past or present.

**Validates: Requirements 4.4**

### Property 9: CVV Format Validation

*For any* CVV submitted for payment, the system should accept only strings of 3 or 4 digits and should reject all other formats.

**Validates: Requirements 4.5**

### Property 10: Successful Card Payment Updates Status

*For any* card payment that receives response code "00" from the payment API, the transaction status should be updated to "verified".

**Validates: Requirements 4.7, 7.3**

### Property 11: Failed Card Payment Updates Status

*For any* card payment that receives a non-"00" response code from the payment API, the transaction status should be updated to "failed" and an error message should be displayed.

**Validates: Requirements 4.8, 7.4**

### Property 12: Card Data Not Stored

*For any* completed card payment, the database should not contain the full card number, CVV, or full expiry date, but should contain only the last 4 digits and card brand.

**Validates: Requirements 4.9, 4.10, 8.3**

### Property 13: Card Processing Fee Calculation

*For any* transaction amount, when card_payment is selected, the processing fee should be exactly 1.5% of the amount, rounded to 2 decimal places using ROUND_HALF_UP.

**Validates: Requirements 5.1, 5.7**

### Property 14: Fee Breakdown Display

*For any* card payment, the system should display the original amount, processing fee, and total amount to the customer before payment submission.

**Validates: Requirements 5.2, 5.3, 14.4**

### Property 15: Fee Storage Round-Trip

*For any* card payment, after completion, retrieving the transaction should return the original amount, processing fee, and total amount that were calculated.

**Validates: Requirements 5.4**

### Property 16: Payment Method in Exports and Webhooks

*For any* completed transaction, the selected payment method should be included in transaction history API responses, CSV exports, and webhook payloads.

**Validates: Requirements 7.5, 7.6, 7.7**

### Property 17: Card Data Not Logged

*For any* card payment attempt, application logs should not contain card numbers, CVV, or expiry dates.

**Validates: Requirements 8.2**

### Property 18: Card Payment Rate Limiting

*For any* IP address, after 5 card payment attempts within 15 minutes, the 6th attempt should be rejected with a rate limit error.

**Validates: Requirements 8.5**

### Property 19: Card Payment Audit Logging

*For any* card payment attempt, an audit log entry should be created containing the transaction reference and outcome, but not containing card details.

**Validates: Requirements 8.6**

### Property 20: Card Payment Error Messages

*For any* failed card payment, the error message returned to the customer should not expose detailed error information that could aid attackers.

**Validates: Requirements 8.7**

### Property 21: CSRF Protection on Card Payments

*For any* card payment submission, requests without a valid CSRF token should be rejected.

**Validates: Requirements 8.8**

### Property 22: QR Code JSON Format

*For any* generated QR code, the encoded data should be valid JSON that can be parsed without errors.

**Validates: Requirements 9.1**

### Property 23: QR Code Conditional Bank Fields

*For any* transaction where bank_transfer is in allowed_payment_methods, the QR code data should include virtual_account_number, virtual_bank_name, and virtual_account_name.

**Validates: Requirements 9.3**

### Property 24: QR Code Size Optimization

*For any* transaction with data exceeding QR code capacity, the system should omit optional fields (description, merchant_name) to reduce size while preserving required fields.

**Validates: Requirements 9.5, 9.6**

### Property 25: QR Code Image Format

*For any* generated QR code, the output should be a PNG image with dimensions of at least 200x200 pixels.

**Validates: Requirements 9.7**

### Property 26: Mock Mode Card Number Handling

*For any* valid card number in mock mode, the system should return success (response code "00") for card numbers ending in even digits and failure (response code "06") for card numbers ending in odd digits.

**Validates: Requirements 10.2, 10.3, 10.4**

### Property 27: Mock Mode Logging

*For any* card payment operation in mock mode, the system should log clearly that mock mode is active.

**Validates: Requirements 10.6**

### Property 28: Legacy Transaction Backward Compatibility

*For any* transaction created before the payment methods feature (with null allowed_payment_methods), the system should treat it as having allowed_payment_methods = ["bank_transfer"] and selected_payment_method = "bank_transfer".

**Validates: Requirements 11.1, 11.3**

### Property 29: QR Code Base64 Delivery

*For any* QR code served to a customer, it should be delivered as a base64-encoded data URL in the format "data:image/png;base64,..."

**Validates: Requirements 12.4**

### Property 30: QR Code Caching

*For any* transaction, generating the QR code multiple times should return the same cached result without regenerating the image.

**Validates: Requirements 12.5**

### Property 31: QR Code Generation Error Handling

*For any* QR code generation failure, the system should log the error and display the payment page without the QR code rather than failing completely.

**Validates: Requirements 12.6**

### Property 32: Fee Information Display

*For any* payment page with multiple payment methods, the system should display fee information for each method (showing "No additional fees" for bank_transfer and "1.5% processing fee" for card_payment).

**Validates: Requirements 14.1, 14.2, 14.3**

### Property 33: Dynamic Total Amount Update

*For any* payment method selection change, the displayed total amount should update to reflect the fees associated with the newly selected method.

**Validates: Requirements 14.5**

### Property 34: Amount Formatting

*For any* amount displayed to customers or merchants, it should be formatted in the transaction currency with exactly 2 decimal places.

**Validates: Requirements 14.6**

## Error Handling

### Card Payment Errors

**Client-Side Validation:**
- Card number format (Luhn algorithm)
- Expiry date format and future date check
- CVV format (3-4 digits)
- Cardholder name presence
- Display inline validation errors before submission

**Server-Side Validation:**
- Re-validate all client-side checks (never trust client)
- Check transaction not expired or already used
- Verify payment method is allowed
- Rate limit enforcement

**API Error Handling:**
```python
# Quickteller response codes
RESPONSE_CODES = {
    "00": "Approved",
    "06": "Declined",
    "91": "Timeout - please try again",
    "96": "System error",
    # ... other codes
}

# Map to user-friendly messages
def get_user_message(response_code: str) -> str:
    if response_code == "00":
        return "Payment successful"
    elif response_code == "06":
        return "Card payment was declined. Please try another card."
    elif response_code == "91":
        return "Payment timed out. Please try again."
    else:
        return "Payment could not be processed. Please try again or use bank transfer."
```

**Error States:**
- Transaction expired: Show expired page, offer to request new link
- Transaction already used: Show already verified page
- Rate limit exceeded: Show "Too many attempts" message with retry time
- Network error: Show "Connection error" with retry button
- Invalid card: Show inline validation error
- Declined payment: Show generic decline message, don't expose reason

### QR Code Generation Errors

**Failure Scenarios:**
- Data too large even after optimization: Log error, show payment page without QR
- Image generation failure: Log error, show payment page without QR
- Encoding error: Log error, show payment page without QR

**Graceful Degradation:**
- QR code is a convenience feature, not critical
- Payment page must work without QR code
- Log all QR generation failures for monitoring
- Don't block page load on QR generation

### Payment Method Selection Errors

**Validation Errors:**
- Invalid payment method: Return 400 with INVALID_PAYMENT_METHOD code
- Method not allowed: Return 400 with METHOD_NOT_ALLOWED code
- Empty methods array: Return 400 with VALIDATION_ERROR code
- Transaction expired: Return 400 with TRANSACTION_EXPIRED code

**User Experience:**
- Show validation errors inline on payment page
- Preserve form data on validation failure
- Highlight invalid fields
- Provide clear guidance on how to fix

## Security Architecture

### Card Data Handling

**PCI-DSS Compliance Measures:**

1. **No Storage of Sensitive Data:**
   - Never store full card number (store only last 4 digits)
   - Never store CVV
   - Never store full expiry date
   - Never log card details

2. **Transmission Security:**
   - All card data transmitted over HTTPS (TLS 1.2+)
   - Direct transmission to Quickteller API (no intermediate storage)
   - No card data in URL parameters or query strings
   - No card data in error messages or logs

3. **Input Validation:**
   - Luhn algorithm validation for card numbers
   - Format validation for expiry dates
   - Length validation for CVV (3-4 digits)
   - Sanitization of cardholder name

4. **Rate Limiting:**
   - 5 card payment attempts per 15 minutes per IP
   - Prevents brute force attacks on card numbers
   - Prevents abuse of payment endpoint

5. **CSRF Protection:**
   - CSRF token required on all card payment submissions
   - Token validated server-side
   - Prevents cross-site request forgery attacks

6. **Audit Logging:**
   - Log all card payment attempts (without card details)
   - Log transaction reference, outcome, timestamp, IP
   - Enables security monitoring and incident response

**Security Checklist:**
- [ ] Card data never stored in database
- [ ] Card data never logged
- [ ] HTTPS enforced for all card payment endpoints
- [ ] Rate limiting active on card payment endpoint
- [ ] CSRF protection enabled
- [ ] Input validation on all card fields
- [ ] Audit logging for all payment attempts
- [ ] Error messages don't expose sensitive details

### QR Code Security

**Data Exposure:**
- QR codes contain payment details (amount, account number)
- This is intentional - QR codes are for sharing payment info
- No sensitive merchant data in QR codes
- No authentication tokens or secrets in QR codes

**Access Control:**
- QR codes only generated for valid, non-expired transactions
- QR code endpoint rate limited (20 requests/minute per IP)
- QR codes not generated for already-verified transactions

**Data Integrity:**
- QR code data includes hash token for link validation
- Customers can verify payment URL matches expected domain
- Expiry time included to prevent stale QR code usage

## Testing Strategy

### Unit Tests

**Payment Method Selection:**
- Test valid payment method arrays accepted
- Test invalid payment methods rejected
- Test empty array rejected
- Test default to bank_transfer when not specified
- Test payment method stored correctly in database

**Fee Calculation:**
- Test 1.5% fee calculated correctly for various amounts
- Test rounding to 2 decimal places (ROUND_HALF_UP)
- Test zero fee for bank transfers
- Test fee calculation with edge case amounts (very small, very large)

**Card Validation:**
- Test Luhn algorithm with valid/invalid card numbers
- Test expiry date validation (past, present, future)
- Test CVV format validation (2, 3, 4, 5 digits)
- Test cardholder name validation

**QR Code Generation:**
- Test QR code contains all required fields
- Test QR code data is valid JSON
- Test QR code size optimization when data too large
- Test QR code not generated for expired transactions
- Test QR code caching

**Database Migration:**
- Test migration adds all new columns
- Test migration sets correct defaults for existing records
- Test migration is reversible (downgrade works)

### Property-Based Tests

**Configuration:**
- Use Hypothesis library for Python property-based testing
- Minimum 100 iterations per property test
- Each test tagged with feature name and property number

**Test Structure:**
```python
from hypothesis import given, strategies as st
import pytest

@given(
    amount=st.decimals(min_value=1, max_value=1000000, places=2),
    payment_method=st.sampled_from(["bank_transfer", "card_payment"])
)
def test_property_13_card_processing_fee_calculation(amount, payment_method):
    """
    Feature: payment-methods-and-qr-codes, Property 13
    For any transaction amount, when card_payment is selected, 
    the processing fee should be exactly 1.5% of the amount, 
    rounded to 2 decimal places using ROUND_HALF_UP.
    """
    fee = calculate_processing_fee(amount, payment_method)
    
    if payment_method == "card_payment":
        expected_fee = (amount * Decimal("0.015")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        assert fee == expected_fee
    else:
        assert fee == Decimal("0")
```

**Property Test Coverage:**
- All 34 correctness properties implemented as property tests
- Generators for: transactions, card numbers, amounts, dates
- Strategies for: payment methods, transaction states, API responses

### Integration Tests

**Card Payment Flow:**
- Test full card payment flow (mock mode)
- Test card payment with Quickteller API (if credentials available)
- Test card payment failure handling
- Test card payment rate limiting
- Test card payment audit logging

**QR Code Flow:**
- Test QR code generation and display
- Test QR code round-trip (encode/decode)
- Test QR code with various transaction states
- Test QR code caching behavior

**Payment Method Selection:**
- Test payment page with single method
- Test payment page with multiple methods
- Test method selection and fee calculation
- Test method selection persistence

**Backward Compatibility:**
- Test legacy transactions (no payment methods) still work
- Test legacy transactions default to bank_transfer
- Test legacy transactions in dashboard and exports

### Mock Mode Testing

**Card Payment Mock:**
- Test even-ending card numbers succeed
- Test odd-ending card numbers fail
- Test mock mode banner displayed
- Test mock mode logging

**Configuration:**
- Test system detects missing credentials
- Test system switches to mock mode automatically
- Test mock mode clearly indicated in UI and logs

### Security Tests

**Card Data Protection:**
- Test card numbers not stored in database
- Test card numbers not in logs
- Test CVV not stored or logged
- Test only last 4 digits stored

**Rate Limiting:**
- Test card payment rate limit enforced
- Test rate limit per IP address
- Test rate limit reset after window

**CSRF Protection:**
- Test card payment requires CSRF token
- Test invalid CSRF token rejected
- Test missing CSRF token rejected

**Input Validation:**
- Test SQL injection attempts rejected
- Test XSS attempts sanitized
- Test invalid card formats rejected
- Test malformed requests rejected

### End-to-End Tests

**Complete Payment Flows:**
1. Merchant creates link with both payment methods
2. Customer accesses payment page
3. Customer sees both payment options
4. Customer selects card payment
5. Customer sees fee breakdown
6. Customer submits card details
7. Payment processed successfully
8. Transaction marked as verified
9. Webhook delivered to merchant
10. Transaction appears in merchant dashboard with payment method

**QR Code Flow:**
1. Merchant creates payment link
2. Customer accesses payment page
3. QR code displayed
4. Customer scans QR code
5. QR code contains correct payment details
6. Customer can share QR code
7. Another device can scan and access payment page

## UI/UX Changes

### Payment Page Modifications

**Single Payment Method:**
```html
<!-- No selection UI, just show the payment method directly -->
<div class="payment-section">
  <h3>Payment Method</h3>
  <!-- Bank transfer details OR card payment form -->
</div>
```

**Multiple Payment Methods:**
```html
<!-- Tab-based selection UI -->
<div class="payment-method-selector">
  <div class="tabs">
    <button class="tab active" data-method="bank_transfer">
      Bank Transfer
      <span class="fee-badge">No fees</span>
    </button>
    <button class="tab" data-method="card_payment">
      Card Payment
      <span class="fee-badge">1.5% fee</span>
    </button>
  </div>
  
  <div class="tab-content active" data-method="bank_transfer">
    <!-- Bank transfer details -->
  </div>
  
  <div class="tab-content" data-method="card_payment">
    <!-- Card payment form -->
  </div>
</div>
```

**Card Payment Form:**
```html
<form id="card-payment-form">
  <div class="form-group">
    <label>Card Number</label>
    <input type="text" id="card-number" maxlength="19" 
           placeholder="1234 5678 9012 3456" autocomplete="cc-number">
    <span class="error" id="card-number-error"></span>
  </div>
  
  <div class="form-row">
    <div class="form-group">
      <label>Expiry Date</label>
      <input type="text" id="expiry" placeholder="MM/YY" 
             maxlength="5" autocomplete="cc-exp">
      <span class="error" id="expiry-error"></span>
    </div>
    
    <div class="form-group">
      <label>CVV</label>
      <input type="text" id="cvv" maxlength="4" 
             placeholder="123" autocomplete="cc-csc">
      <span class="error" id="cvv-error"></span>
    </div>
  </div>
  
  <div class="form-group">
    <label>Cardholder Name</label>
    <input type="text" id="cardholder-name" 
           placeholder="John Doe" autocomplete="cc-name">
    <span class="error" id="cardholder-error"></span>
  </div>
  
  <div class="fee-breakdown">
    <div class="fee-row">
      <span>Amount</span>
      <span id="original-amount">₦1,000.00</span>
    </div>
    <div class="fee-row">
      <span>Processing Fee (1.5%)</span>
      <span id="processing-fee">₦15.00</span>
    </div>
    <div class="fee-row total">
      <span>Total</span>
      <span id="total-amount">₦1,015.00</span>
    </div>
  </div>
  
  <button type="submit" class="btn-primary">
    Pay ₦1,015.00
  </button>
</form>
```

**QR Code Display:**
```html
<div class="qr-code-section">
  <h4>Scan to Pay</h4>
  <img src="data:image/png;base64,..." alt="Payment QR Code" 
       class="qr-code-image">
  <p class="qr-code-hint">
    Scan this code with your phone to access payment details
  </p>
</div>
```

**Mock Mode Banner:**
```html
<div class="mock-mode-banner">
  <span class="icon">⚠️</span>
  <span>Demo mode active - payments will be simulated</span>
</div>
```

### JavaScript Changes

**Payment Method Selection:**
```javascript
// In verify.js

function showPaymentMethodSelector(allowedMethods) {
  const selector = document.getElementById('payment-method-selector');
  selector.classList.remove('hidden');
  
  // Create tabs for each method
  allowedMethods.forEach(method => {
    const tab = createMethodTab(method);
    tab.addEventListener('click', () => selectPaymentMethod(method));
  });
}

async function selectPaymentMethod(method) {
  // Call API to select method and get fee calculation
  const response = await fetch(`/api/payments/select-method/${TX_REF}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken()
    },
    body: JSON.stringify({ payment_method: method })
  });
  
  const data = await response.json();
  
  // Update UI with fee breakdown
  updateFeeBreakdown(data);
  
  // Show appropriate payment form
  showPaymentForm(method);
}
```

**Card Payment Submission:**
```javascript
async function submitCardPayment(event) {
  event.preventDefault();
  
  // Client-side validation
  if (!validateCardForm()) {
    return;
  }
  
  const cardData = {
    card_number: document.getElementById('card-number').value.replace(/\s/g, ''),
    expiry_month: document.getElementById('expiry').value.split('/')[0],
    expiry_year: '20' + document.getElementById('expiry').value.split('/')[1],
    cvv: document.getElementById('cvv').value,
    cardholder_name: document.getElementById('cardholder-name').value
  };
  
  try {
    const response = await fetch(`/api/payments/card-payment/${TX_REF}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify(cardData)
    });
    
    const data = await response.json();
    
    if (data.success) {
      showSuccess();
    } else {
      showCardError(data.message);
    }
  } catch (error) {
    showCardError('Network error. Please try again.');
  }
}
```

**Card Number Formatting:**
```javascript
// Format card number with spaces as user types
document.getElementById('card-number').addEventListener('input', (e) => {
  let value = e.target.value.replace(/\s/g, '');
  let formatted = value.match(/.{1,4}/g)?.join(' ') || value;
  e.target.value = formatted;
});

// Format expiry date as MM/YY
document.getElementById('expiry').addEventListener('input', (e) => {
  let value = e.target.value.replace(/\D/g, '');
  if (value.length >= 2) {
    value = value.slice(0, 2) + '/' + value.slice(2, 4);
  }
  e.target.value = value;
});
```

### Dashboard Changes

**Transaction History:**
- Add "Payment Method" column to transaction table
- Show "Bank Transfer" or "Card Payment" with icon
- Show card brand and last 4 digits for card payments
- Filter transactions by payment method

**CSV Export:**
- Add "Payment Method" column
- Add "Card Brand" column
- Add "Card Last 4" column
- Add "Processing Fee" column
- Add "Total Amount" column

**Transaction Detail View:**
- Show payment method used
- Show fee breakdown for card payments
- Show card brand and last 4 for card payments
- Show QR code if transaction is still pending

## Deployment Considerations

### Environment Variables

**New Configuration:**
```bash
# Card Payment API Credentials
QUICKTELLER_CARD_MERCHANT_ID=your_merchant_id
QUICKTELLER_CARD_API_KEY=your_api_key
QUICKTELLER_CARD_TERMINAL_ID=your_terminal_id

# Optional: Leave empty for mock mode during development
```

### Database Migration

**Migration Steps:**
1. Backup database before migration
2. Run migration: `alembic upgrade head`
3. Verify new columns added: `SELECT * FROM transactions LIMIT 1`
4. Verify existing records have defaults set
5. Test creating new transactions with payment methods

**Rollback Plan:**
```bash
# If issues occur, rollback migration
alembic downgrade -1

# Restore from backup if needed
```

### Feature Flags

**Gradual Rollout:**
```python
# config.py
ENABLE_CARD_PAYMENTS = os.getenv("ENABLE_CARD_PAYMENTS", "false").lower() == "true"
ENABLE_QR_CODES = os.getenv("ENABLE_QR_CODES", "true").lower() == "true"

# Use in code
if Config.ENABLE_CARD_PAYMENTS and quickteller.is_card_configured():
    # Show card payment option
```

### Monitoring

**Metrics to Track:**
- Card payment success rate
- Card payment failure rate by error code
- Average processing time for card payments
- QR code generation success rate
- Payment method selection distribution
- Fee revenue from card payments

**Alerts:**
- Card payment success rate < 90%
- QR code generation failure rate > 5%
- Card payment API errors > 10/minute
- Rate limit triggers > 100/hour

### Performance Considerations

**QR Code Caching:**
- Cache QR codes in memory (keyed by tx_ref)
- Clear cache when transaction expires or is verified
- Monitor cache size (limit to 10,000 entries)

**Database Indexes:**
- Index on `selected_payment_method` for filtering
- Index on `card_brand` for analytics
- Existing indexes on `tx_ref`, `user_id`, `status` sufficient

**API Response Times:**
- Card payment: < 5 seconds (external API call)
- QR code generation: < 100ms (cached after first generation)
- Payment method selection: < 200ms (database update + fee calculation)

## Backward Compatibility

### Existing Payment Links

**Behavior:**
- Links created before this feature have `allowed_payment_methods = NULL`
- System treats NULL as `["bank_transfer"]`
- Payment page shows only bank transfer (no selection UI)
- Polling mechanism unchanged
- Webhook format unchanged (no payment method field for legacy transactions)

### API Compatibility

**Link Creation:**
- `allowed_payment_methods` is optional in request
- Defaults to `["bank_transfer"]` if not provided
- Existing integrations continue working without changes

**Transaction Status:**
- Existing status polling endpoints unchanged
- New fields added to responses (ignored by old clients)
- Old clients see only fields they expect

### Database Compatibility

**Migration:**
- New columns nullable or have defaults
- Existing records get sensible defaults
- No data loss during migration
- Rollback possible if needed

## Future Enhancements

**Potential Extensions:**
1. Additional payment methods (USSD, mobile money)
2. Multiple currency support for card payments
3. Recurring payments / subscriptions
4. Split payments (partial card, partial transfer)
5. Dynamic fee configuration per merchant
6. Card tokenization for repeat customers
7. 3D Secure authentication for card payments
8. QR code customization (colors, logos)
9. Payment method analytics dashboard
10. A/B testing for payment method presentation

**Not in Scope:**
- Refunds or chargebacks
- Saved payment methods
- Multi-currency transactions
- Installment payments
- Cryptocurrency payments
