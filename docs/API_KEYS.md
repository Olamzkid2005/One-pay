# API Keys Documentation

OnePay supports machine-to-machine (M2M) API access using API keys for authentication. This enables programmatic integration with external services like VoicePay.

## Overview

API keys provide a secure way to authenticate API requests without requiring user sessions or cookies. They are ideal for:

- Server-to-server integrations
- Automated payment processing
- Third-party service integrations
- Webhook receivers

## Generating API Keys

### Via Web UI

1. Log in to your OnePay account
2. Navigate to Settings → API Keys
3. Click "Generate New API Key"
4. Provide a descriptive name (e.g., "Production VoicePay Integration")
5. Copy the API key immediately - **it will only be shown once**
6. Store the API key securely (use environment variables, never commit to code)

### API Key Format

API keys follow this format:
```
onepay_live_<64_hexadecimal_characters>
```

Example:
```
onepay_live_a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456
```

- Prefix: `onepay_live_` (12 characters)
- Secret: 64 hexadecimal characters
- Total length: 76 characters

## Using API Keys

### Authentication

Include the API key in the `Authorization` header using Bearer authentication:

```http
POST /api/v1/payments/link HTTP/1.1
Host: your-onepay-instance.com
Authorization: Bearer onepay_live_a1b2c3d4e5f6...
Content-Type: application/json

{
  "amount": "1000.00",
  "currency": "NGN",
  "description": "Payment for services"
}
```

### Example: Create Payment Link (cURL)

```bash
curl -X POST https://your-onepay-instance.com/api/v1/payments/link \
  -H "Authorization: Bearer onepay_live_a1b2c3d4e5f6..." \
  -H "Content-Type: application/json" \
  -d '{
    "amount": "1000.00",
    "currency": "NGN",
    "description": "Payment for services",
    "customer_email": "customer@example.com",
    "return_url": "https://yourapp.com/payment/success",
    "webhook_url": "https://yourapp.com/webhooks/payment"
  }'
```

### Example: Create Payment Link (Python)

```python
import requests

API_KEY = "onepay_live_a1b2c3d4e5f6..."
BASE_URL = "https://your-onepay-instance.com"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

payload = {
    "amount": "1000.00",
    "currency": "NGN",
    "description": "Payment for services",
    "customer_email": "customer@example.com"
}

response = requests.post(
    f"{BASE_URL}/api/v1/payments/link",
    headers=headers,
    json=payload
)

if response.status_code == 201:
    data = response.json()
    print(f"Payment URL: {data['payment_url']}")
    print(f"Transaction Ref: {data['tx_ref']}")
else:
    print(f"Error: {response.json()}")
```

### Example: Create Payment Link (Node.js)

```javascript
const axios = require('axios');

const API_KEY = 'onepay_live_a1b2c3d4e5f6...';
const BASE_URL = 'https://your-onepay-instance.com';

async function createPaymentLink() {
  try {
    const response = await axios.post(
      `${BASE_URL}/api/v1/payments/link`,
      {
        amount: '1000.00',
        currency: 'NGN',
        description: 'Payment for services',
        customer_email: 'customer@example.com'
      },
      {
        headers: {
          'Authorization': `Bearer ${API_KEY}`,
          'Content-Type': 'application/json'
        }
      }
    );

    console.log('Payment URL:', response.data.payment_url);
    console.log('Transaction Ref:', response.data.tx_ref);
  } catch (error) {
    console.error('Error:', error.response.data);
  }
}

createPaymentLink();
```

## Rate Limits

API key authenticated requests have higher rate limits than web UI requests:

| Endpoint | Web UI Limit | API Key Limit |
|----------|--------------|---------------|
| Create Payment Link | 10 per minute | 100 per minute |
| Check Payment Status | 50 per minute | 500 per minute |

Rate limit headers are included in responses:
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1617235200
```

When rate limited, you'll receive a `429 Too Many Requests` response:
```json
{
  "success": false,
  "error": "Rate limit exceeded",
  "error_code": "RATE_LIMIT_EXCEEDED"
}
```

## CSRF Protection

API key authenticated requests automatically bypass CSRF validation. You do NOT need to include CSRF tokens when using API keys.

## Security Best Practices

### 1. Store API Keys Securely

**DO:**
- Store in environment variables
- Use secret management services (AWS Secrets Manager, HashiCorp Vault)
- Encrypt at rest in databases
- Use separate keys for development/staging/production

**DON'T:**
- Commit API keys to version control
- Include in client-side code
- Share via email or chat
- Log API keys in application logs

### 2. Rotate API Keys Regularly

- Generate new API keys every 90 days
- Revoke old keys after rotation
- Use multiple keys for different services to limit blast radius

### 3. Use HTTPS Only

- Always use HTTPS for API requests
- Never send API keys over unencrypted connections
- Validate SSL certificates

### 4. Monitor API Key Usage

- Review "Last Used" timestamps in the API Keys dashboard
- Revoke unused or suspicious keys immediately
- Set up alerts for unusual activity

### 5. Principle of Least Privilege

- Create separate API keys for each integration
- Revoke keys when services are decommissioned
- Use descriptive names to track key usage

## API Key Management

### List API Keys

```bash
curl -X GET https://your-onepay-instance.com/api/v1/api-keys \
  -H "Authorization: Bearer onepay_live_a1b2c3d4e5f6..."
```

Response:
```json
{
  "success": true,
  "api_keys": [
    {
      "id": 1,
      "name": "Production VoicePay Integration",
      "key_prefix": "onepay_live_a1b2c3d4",
      "created_at": "2026-03-15T10:30:00Z",
      "last_used_at": "2026-04-01T08:45:00Z",
      "is_active": true
    }
  ]
}
```

**Note:** Full API keys are never returned after creation. Only the prefix is shown for identification.

### Revoke API Key

```bash
curl -X DELETE https://your-onepay-instance.com/api/v1/api-keys/1 \
  -H "Authorization: Bearer onepay_live_a1b2c3d4e5f6..."
```

Response:
```json
{
  "success": true,
  "message": "API key revoked"
}
```

Revoked keys:
- Cannot be used for authentication
- Are marked as inactive (not deleted)
- Can be viewed in the dashboard for audit purposes

## Error Handling

### Common Error Responses

**401 Unauthorized - Invalid API Key**
```json
{
  "success": false,
  "error": "Invalid or expired API key",
  "error_code": "UNAUTHORIZED"
}
```

**401 Unauthorized - Missing API Key**
```json
{
  "success": false,
  "error": "Authentication required",
  "error_code": "UNAUTHORIZED"
}
```

**403 Forbidden - Inactive API Key**
```json
{
  "success": false,
  "error": "API key has been revoked",
  "error_code": "FORBIDDEN"
}
```

**400 Bad Request - Validation Error**
```json
{
  "success": false,
  "error": "amount is required",
  "error_code": "VALIDATION_ERROR"
}
```

## API Documentation

For complete API documentation including all endpoints, request/response schemas, and examples:

- **OpenAPI Specification:** `/static/openapi.json`
- Import into Postman, Insomnia, or any OpenAPI-compatible tool
- View with online tools like [Swagger Editor](https://editor.swagger.io/)

## Webhook Integration

When creating payment links, you can specify a `webhook_url` to receive payment status updates:

```json
{
  "amount": "1000.00",
  "currency": "NGN",
  "webhook_url": "https://yourapp.com/webhooks/payment"
}
```

OnePay will send POST requests to your webhook URL when payment status changes. See the main documentation for webhook signature verification details.

## Support

For API integration support:
- Review the OpenAPI specification at `/static/openapi.json`
- Check the main documentation at `docs/README.md`
- Contact your OnePay administrator

## Changelog

- **2026-04-01:** Initial API keys documentation
- **2026-03-31:** API keys feature released
