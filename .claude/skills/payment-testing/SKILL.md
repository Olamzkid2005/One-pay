---
inclusion: auto
---

# Payment Testing Skill

Test KoraPay and VoicePay payment integration end-to-end.

## When to Use
- User wants to test payment flows
- User reports payment-related bugs
- User wants to verify KoraPay integration works

## How to Use
1. Check KoraPay mock mode status (empty secret key = mock mode)
2. Run relevant payment tests:
   ```bash
   pytest tests/unit/test_korapay_*.py -v
   pytest tests/integration/test_korapay_flow.py -v
   ```
3. Test specific scenarios:
   - Virtual account creation
   - Transfer confirmation with polling
   - Refund initiation and status
   - Webhook handling

## Payment Flow
1. Create payment link → generates virtual account
2. Customer pays into virtual account
3. KoraPay calls webhook or customer polls status
4. confirm_transfer() returns success after 3 polls
5. Transaction marked as verified

## Mock Mode
- `KORAPAY_SECRET_KEY` empty or < 32 chars activates mock mode
- Mock mode simulates KoraPay responses locally
- Virtual accounts use deterministic formula based on tx_ref
- Transfer confirmation succeeds after 4 polls
