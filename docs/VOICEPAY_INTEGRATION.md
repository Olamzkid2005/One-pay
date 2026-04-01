# VoicePay Integration Guide

## Overview

OnePay serves as the merchant payment gateway for VoicePay, handling bill payments (DSTV, electricity, airtime) and invoice generation through virtual bank accounts.

## Architecture

```
VoicePay → OnePay API → KoraPay → Bank Transfer → KoraPay Webhook → OnePay → VoicePay Webhook
```

## Authentication

VoicePay authenticates with OnePay using API key authentication:

```bash
Authorization: Bearer YOUR_API_KEY
```

### Obtaining API Key

Contact OnePay support to generate a dedicated API key for your VoicePay integration.

## API Endpoints

### 1. Create Payment Link

**Endpoint:** `POST /api/v1/payment-links`

**Headers:**
```
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
```

**Request:**
```json
{
  "amount": 9000.00,
  "description": "DSTV Premium Subscription",
  "customer_email": "user@voicepay.ng",
  "customer_name": "John Doe",
  "tx_ref": "VP-BILL-123-1234567890",
  "metadata": {
    "source": "voicepay",
    "user_id": "123",
    "bill_type": "dstv",
    "package": "premium"
  }
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "payment_url": "https://onepay.ng/pay/abc123",
    "tx_ref": "VP-BILL-123-1234567890",
    "virtual_account_number": "1234567890",
    "virtual_bank_name": "Wema Bank",
    "account_name": "OnePay - John Doe",
    "qr_code_url": "https://onepay.ng/qr/abc123.png",
    "amount": 9000.00,
    "expires_at": "2026-04-01T12:00:00Z"
  }
}
```

### 2. Check Payment Status

**Endpoint:** `GET /api/v1/payment-links/{tx_ref}`

**Headers:**
```
Authorization: Bearer YOUR_API_KEY
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "tx_ref": "VP-BILL-123-1234567890",
    "status": "VERIFIED",
    "amount": 9000.00,
    "verified_at": "2026-04-01T10:30:00Z",
    "customer_email": "user@voicepay.ng",
    "description": "DSTV Premium Subscription"
  }
}
```

**Status Values:**
- `PENDING` - Payment link created, awaiting payment
- `VERIFIED` - Payment confirmed
- `EXPIRED` - Payment link expired
- `FAILED` - Payment failed

## Webhook Notifications

OnePay sends webhook notifications to VoicePay when payments are confirmed.

### Webhook Payload

```json
{
  "event": "payment.verified",
  "tx_ref": "VP-BILL-123-1234567890",
  "amount": 9000.00,
  "currency": "NGN",
  "status": "verified",
  "verified_at": "2026-04-01T10:30:00+00:00",
  "customer_email": "user@voicepay.ng",
  "description": "DSTV Premium Subscription"
}
```

### Webhook Security

Webhooks include an HMAC-SHA256 signature in the `X-OnePay-Signature` header.

**Verification (Python):**
```python
import hmac
import hashlib
import json

def verify_onepay_webhook(payload: dict, signature: str, secret: str) -> bool:
    message = json.dumps(payload, sort_keys=True)
    expected_signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected_signature)
```

**Verification (Node.js):**
```javascript
const crypto = require('crypto');

function verifySignature(payload, signature, secret) {
  const message = JSON.stringify(payload, Object.keys(payload).sort());
  const expected = crypto
    .createHmac('sha256', secret)
    .update(message)
    .digest('hex');
  return crypto.timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(expected)
  );
}
```

## Metadata Fields

VoicePay should include these metadata fields:

```json
{
  "source": "voicepay",
  "user_id": "123",
  "whatsapp_id": "2348012345678",
  "bill_type": "dstv",
  "package": "premium",
  "biometric_score": 0.92,
  "voice_verified": true
}
```

## Transaction Reference Format

VoicePay transaction references must follow this format:

```
VP-BILL-{user_id}-{timestamp}
Example: VP-BILL-123-1711958400
```

This prefix is used by OnePay to identify VoicePay transactions for webhook forwarding.

## Rate Limits

- Payment link creation: 100 requests/minute
- Status checks: 500 requests/minute

## Error Handling

### Error Response Format

```json
{
  "success": false,
  "error": "ERROR_CODE",
  "message": "Human-readable error message"
}
```

### Common Error Codes

- `UNAUTHORIZED` - Invalid or missing API key
- `VALIDATION_ERROR` - Invalid request parameters
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `NOT_FOUND` - Transaction not found
- `EXPIRED` - Payment link expired

## Testing

### Sandbox Environment

- Base URL: `https://sandbox.onepay.ng`
- Use sandbox API key
- Virtual accounts are simulated

### Production Environment

- Base URL: `https://api.onepay.ng`
- Use production API key
- Real bank transfers

## Support

- Technical Support: support@onepay.ng
- Documentation: https://docs.onepay.ng
