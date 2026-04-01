# VoicePay Webhook Guide

## Overview

OnePay sends webhook notifications to VoicePay when payment confirmations are received from KoraPay.

## Webhook Flow

```
1. User transfers money to virtual account
2. KoraPay detects payment
3. KoraPay sends webhook to OnePay
4. OnePay verifies payment
5. OnePay sends webhook to VoicePay
```

## Webhook Endpoint

VoicePay must provide a webhook endpoint:

```
POST https://voicepay.ng/api/webhooks/onepay
```

## Webhook Payload

### Payment Verified Event

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

### Field Descriptions

- `event` - Event type (always "payment.verified")
- `tx_ref` - Transaction reference from payment link creation
- `amount` - Payment amount in Naira
- `currency` - Currency code (always "NGN")
- `status` - Payment status (always "verified" for this event)
- `verified_at` - ISO 8601 timestamp of payment confirmation
- `customer_email` - Customer email address
- `description` - Payment description

## Security

### HMAC Signature Verification

Every webhook includes an HMAC-SHA256 signature in the `X-OnePay-Signature` header.

**Verification Steps:**

1. Extract signature from header
2. Serialize payload with sorted keys
3. Compute HMAC-SHA256 with shared secret
4. Compare signatures using constant-time comparison

**Python Example:**

```python
import hmac
import hashlib
import json
from flask import request, jsonify

@app.route('/api/webhooks/onepay', methods=['POST'])
def receive_onepay_webhook():
    # Get signature from header
    signature = request.headers.get('X-OnePay-Signature', '')
    
    # Get payload
    payload = request.get_json()
    
    # Verify signature
    if not verify_signature(payload, signature):
        return jsonify({'error': 'Invalid signature'}), 401
    
    # Process webhook
    process_payment_confirmation(payload)
    
    return jsonify({'success': True, 'tx_ref': payload['tx_ref']})

def verify_signature(payload: dict, signature: str) -> bool:
    # Serialize with sorted keys
    message = json.dumps(payload, sort_keys=True)
    
    # Compute expected signature
    expected = hmac.new(
        ONEPAY_WEBHOOK_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    # Constant-time comparison
    return hmac.compare_digest(signature, expected)
```

**Node.js Example:**

```javascript
const crypto = require('crypto');
const express = require('express');
const app = express();

app.post('/api/webhooks/onepay', express.json(), (req, res) => {
  const signature = req.headers['x-onepay-signature'];
  const payload = req.body;
  
  // Verify signature
  if (!verifySignature(payload, signature)) {
    return res.status(401).json({ error: 'Invalid signature' });
  }
  
  // Process webhook
  processPaymentConfirmation(payload);
  
  res.json({ success: true, tx_ref: payload.tx_ref });
});

function verifySignature(payload, signature) {
  // Serialize with sorted keys
  const message = JSON.stringify(payload, Object.keys(payload).sort());
  
  // Compute expected signature
  const expected = crypto
    .createHmac('sha256', process.env.ONEPAY_WEBHOOK_SECRET)
    .update(message)
    .digest('hex');
  
  // Constant-time comparison
  return crypto.timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(expected)
  );
}
```

### IP Whitelisting (Optional)

For additional security, whitelist OnePay's server IPs. Contact OnePay support for current IP addresses.

## Retry Logic

OnePay retries failed webhook deliveries:

- Maximum retries: 3
- Retry delay: Exponential backoff (2^n seconds + random jitter)
- Timeout: 10 seconds per attempt
- Retry conditions: Server errors (5xx), timeouts, connection errors
- No retry: Client errors (4xx)

## Response Requirements

VoicePay webhook endpoint should:

1. Respond within 10 seconds
2. Return HTTP 200 for success
3. Return 4xx/5xx for errors (triggers retry)

**Success Response:**

```json
{
  "success": true,
  "tx_ref": "VP-BILL-123-1234567890"
}
```

## Idempotency

Webhooks may be delivered multiple times. VoicePay should:

1. Use `tx_ref` as idempotency key
2. Ignore duplicate webhooks
3. Return success for duplicates

**Example:**

```python
def process_payment_confirmation(payload):
    tx_ref = payload['tx_ref']
    
    # Check if already processed
    if is_already_processed(tx_ref):
        logger.info(f"Duplicate webhook ignored: {tx_ref}")
        return
    
    # Process payment
    mark_payment_as_confirmed(tx_ref)
    notify_user(payload)
    
    # Mark as processed
    mark_as_processed(tx_ref)
```

## Testing

### Webhook Signature Generator

Use this script to generate test signatures:

```python
import hmac
import hashlib
import json

def generate_test_signature(payload, secret):
    message = json.dumps(payload, sort_keys=True)
    signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return signature

# Example
payload = {
    "event": "payment.verified",
    "tx_ref": "VP-BILL-TEST-123",
    "amount": 9000.00,
    "currency": "NGN",
    "status": "verified"
}
secret = "your-webhook-secret"

signature = generate_test_signature(payload, secret)
print(f"X-OnePay-Signature: {signature}")
```

### Test Webhook Delivery

```bash
curl -X POST https://sandbox.voicepay.ng/api/webhooks/onepay \
  -H "Content-Type: application/json" \
  -H "X-OnePay-Signature: YOUR_SIGNATURE" \
  -d '{
    "event": "payment.verified",
    "tx_ref": "VP-BILL-TEST-123",
    "amount": 9000.00,
    "currency": "NGN",
    "status": "verified",
    "verified_at": "2026-04-01T10:30:00+00:00",
    "customer_email": "test@voicepay.ng",
    "description": "Test payment"
  }'
```

## Monitoring

Monitor webhook delivery:

- Success rate (target: >99%)
- Latency (target: <2s p95)
- Retry rate
- Error rate

## Troubleshooting

### Webhook Not Received

1. Check VoicePay webhook URL is configured in OnePay
2. Verify webhook endpoint is accessible
3. Check firewall rules
4. Review OnePay logs for delivery attempts

### Signature Verification Fails

1. Verify shared secret matches
2. Check payload serialization (sorted keys)
3. Ensure UTF-8 encoding
4. Use constant-time comparison

### Duplicate Webhooks

1. Implement idempotency using `tx_ref`
2. Log duplicate deliveries
3. Return success for duplicates

### High Latency

1. Optimize webhook endpoint processing
2. Process asynchronously if possible
3. Return 200 immediately, process in background

## Support

- Technical Support: support@onepay.ng
- Webhook Issues: webhooks@onepay.ng
