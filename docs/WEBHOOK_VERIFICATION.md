# OnePay Webhook Signature Verification

All OnePay webhooks include an `X-OnePay-Signature` header for security verification. This ensures that webhook requests are genuinely from OnePay and haven't been tampered with.

## Signature Format

```
X-OnePay-Signature: sha256=<hex_digest>
```

The signature is an HMAC-SHA256 hash of the raw request body, signed with your webhook secret.

## How to Verify Webhooks

### Python Example

```python
import hmac
import hashlib
from flask import Flask, request

app = Flask(__name__)

# Your webhook secret from OnePay dashboard
WEBHOOK_SECRET = "your_webhook_secret_here"

def verify_webhook_signature(payload_bytes, signature_header, webhook_secret):
    """
    Verify the webhook signature using constant-time comparison.
    
    Args:
        payload_bytes: Raw request body as bytes
        signature_header: Value of X-OnePay-Signature header
        webhook_secret: Your webhook secret from OnePay
    
    Returns:
        True if signature is valid, False otherwise
    """
    # Calculate expected signature
    expected = hmac.new(
        webhook_secret.encode('utf-8'),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    # Remove 'sha256=' prefix from header
    received = signature_header.removeprefix('sha256=')
    
    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected, received)


@app.route('/webhook', methods=['POST'])
def handle_onepay_webhook():
    # Get signature from header
    signature = request.headers.get('X-OnePay-Signature')
    if not signature:
        return 'Missing signature', 401
    
    # Get raw request body
    payload = request.get_data()
    
    # Verify signature
    if not verify_webhook_signature(payload, signature, WEBHOOK_SECRET):
        return 'Invalid signature', 401
    
    # Signature is valid - process webhook
    data = request.get_json()
    
    if data['event'] == 'payment.confirmed':
        tx_ref = data['tx_ref']
        amount = data['amount']
        # Update your database, send confirmation email, etc.
        print(f"Payment confirmed: {tx_ref} for {amount}")
    
    return 'OK', 200
```

### Node.js Example

```javascript
const express = require('express');
const crypto = require('crypto');

const app = express();

// Your webhook secret from OnePay dashboard
const WEBHOOK_SECRET = 'your_webhook_secret_here';

function verifyWebhookSignature(payload, signatureHeader, webhookSecret) {
    // Calculate expected signature
    const expected = crypto
        .createHmac('sha256', webhookSecret)
        .update(payload)
        .digest('hex');
    
    // Remove 'sha256=' prefix from header
    const received = signatureHeader.replace('sha256=', '');
    
    // Use constant-time comparison
    return crypto.timingSafeEqual(
        Buffer.from(expected),
        Buffer.from(received)
    );
}

app.post('/webhook', express.raw({ type: 'application/json' }), (req, res) => {
    const signature = req.headers['x-onepay-signature'];
    
    if (!signature) {
        return res.status(401).send('Missing signature');
    }
    
    // Verify signature using raw body
    if (!verifyWebhookSignature(req.body, signature, WEBHOOK_SECRET)) {
        return res.status(401).send('Invalid signature');
    }
    
    // Signature is valid - process webhook
    const data = JSON.parse(req.body);
    
    if (data.event === 'payment.confirmed') {
        console.log(`Payment confirmed: ${data.tx_ref} for ${data.amount}`);
        // Update your database, send confirmation email, etc.
    }
    
    res.status(200).send('OK');
});
```

### PHP Example

```php
<?php

// Your webhook secret from OnePay dashboard
$webhookSecret = 'your_webhook_secret_here';

function verifyWebhookSignature($payload, $signatureHeader, $webhookSecret) {
    // Calculate expected signature
    $expected = hash_hmac('sha256', $payload, $webhookSecret);
    
    // Remove 'sha256=' prefix from header
    $received = str_replace('sha256=', '', $signatureHeader);
    
    // Use constant-time comparison
    return hash_equals($expected, $received);
}

// Get raw request body
$payload = file_get_contents('php://input');

// Get signature from header
$signature = $_SERVER['HTTP_X_ONEPAY_SIGNATURE'] ?? '';

if (empty($signature)) {
    http_response_code(401);
    die('Missing signature');
}

// Verify signature
if (!verifyWebhookSignature($payload, $signature, $webhookSecret)) {
    http_response_code(401);
    die('Invalid signature');
}

// Signature is valid - process webhook
$data = json_decode($payload, true);

if ($data['event'] === 'payment.confirmed') {
    $txRef = $data['tx_ref'];
    $amount = $data['amount'];
    // Update your database, send confirmation email, etc.
    error_log("Payment confirmed: $txRef for $amount");
}

http_response_code(200);
echo 'OK';
```

## Webhook Payload Structure

```json
{
  "event": "payment.confirmed",
  "tx_ref": "ONEPAY-ABC123...",
  "amount": "1000.00",
  "currency": "NGN",
  "description": "Payment for order #123",
  "status": "verified",
  "verified_at": "2024-01-15T10:30:00+00:00",
  "timestamp": "2024-01-15T10:30:05+00:00"
}
```

## Security Best Practices

1. **Always verify signatures** - Never process webhooks without signature verification
2. **Use constant-time comparison** - Prevents timing attacks (use `hmac.compare_digest()` in Python, `crypto.timingSafeEqual()` in Node.js, `hash_equals()` in PHP)
3. **Use raw request body** - Calculate signature on the raw bytes, not parsed JSON
4. **Keep secrets secure** - Store webhook secret in environment variables, never in code
5. **Use HTTPS** - Only accept webhooks over HTTPS
6. **Implement idempotency** - Handle duplicate webhook deliveries gracefully
7. **Return 200 quickly** - Acknowledge receipt within 10 seconds, process asynchronously if needed
8. **Log failures** - Log signature verification failures for security monitoring

## Webhook Retry Policy

OnePay will retry failed webhook deliveries:
- Maximum 3 attempts
- Exponential backoff (1s, 2s, 4s between attempts)
- 10 second timeout per attempt
- Webhooks are considered successful on HTTP 2xx response

## Testing Webhooks

You can test your webhook endpoint using curl:

```bash
# Generate test signature
PAYLOAD='{"event":"payment.confirmed","tx_ref":"TEST-123","amount":"100.00"}'
SECRET="your_webhook_secret_here"
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/^.* //')

# Send test webhook
curl -X POST https://your-domain.com/webhook \
  -H "Content-Type: application/json" \
  -H "X-OnePay-Signature: sha256=$SIGNATURE" \
  -d "$PAYLOAD"
```

## Troubleshooting

### "Invalid signature" errors

1. Ensure you're using the raw request body, not parsed JSON
2. Verify you're using the correct webhook secret
3. Check that you're removing the 'sha256=' prefix before comparison
4. Ensure you're using constant-time comparison functions

### Webhooks not received

1. Check your webhook URL is publicly accessible over HTTPS
2. Verify your endpoint returns 200 status within 10 seconds
3. Check OnePay dashboard for webhook delivery logs
4. Ensure your firewall allows incoming requests from OnePay

## Support

For webhook issues, contact support@onepay.com with:
- Transaction reference
- Webhook URL
- Timestamp of failed delivery
- Error logs from your endpoint
