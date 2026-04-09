---
inclusion: auto
---

# Webhook Handler Skill

Debug and test webhook integrations (KoraPay and VoicePay).

## When to Use
- User reports webhook not working
- Testing payment notification flow
- Adding new webhook endpoint

## Webhook Types
1. **Inbound (KoraPay)**: KoraPay calls `/webhooks/korapay` to notify payment
2. **Outbound (VoicePay)**: OnePay forwards to VoicePay after payment verified

## Testing Webhooks
```bash
# Test KoraPay webhook signature verification
pytest tests/unit/test_webhook_signature.py -v

# Test inbound webhook endpoint
curl -X POST http://localhost:5000/webhooks/korapay \
  -H "Content-Type: application/json" \
  -d '{"event":"transfer.success","data":{"reference":"TEST"}}'

# Test VoicePay forwarding
pytest tests/integration/test_webhook_endpoint.py -v
```

## Signature Verification
- KoraPay: HMAC-SHA256 with `KORAPAY_WEBHOOK_SECRET`
- VoicePay outbound: HMAC-SHA256 with `WEBHOOK_SECRET`

## Key Files
- `blueprints/webhooks.py` - Webhook endpoints
- `services/webhook.py` - Outbound webhook forwarding
- `services/voicepay_webhook.py` - VoicePay-specific logic
- `services/korapay.py` - KoraPay API and webhook verification

## Debug Tips
- Check webhook blacklist: `models/webhook_blacklist.py`
- View recent webhook attempts in logs
- Verify HMAC secret matches dashboard
