# VoicePay Bill Categories

## Overview

OnePay supports various bill payment categories through KoraPay integration. This document lists available categories and required metadata.

## Supported Categories

### Phase 1 (MVP)

#### 1. DSTV Subscriptions

**Bill Type:** `dstv`

**Packages:**
- Compact: ₦10,500/month
- Compact Plus: ₦16,600/month
- Premium: ₦24,500/month
- Premium Asia: ₦29,300/month

**Required Metadata:**
```json
{
  "bill_type": "dstv",
  "provider": "DSTV Nigeria",
  "package": "premium",
  "smartcard_number": "1234567890",
  "customer_name": "John Doe"
}
```

#### 2. Electricity Bills

**Bill Type:** `electricity`

**Providers:**
- EKEDC (Eko Electricity)
- IKEDC (Ikeja Electric)
- AEDC (Abuja Electricity)
- PHED (Port Harcourt Electricity)

**Required Metadata:**
```json
{
  "bill_type": "electricity",
  "provider": "EKEDC",
  "meter_number": "12345678901",
  "meter_type": "prepaid",
  "customer_name": "John Doe",
  "customer_address": "123 Main St, Lagos"
}
```

#### 3. Airtime Top-Up

**Bill Type:** `airtime`

**Providers:**
- MTN
- Airtel
- Glo
- 9mobile

**Required Metadata:**
```json
{
  "bill_type": "airtime",
  "provider": "MTN",
  "phone_number": "08012345678",
  "amount": 1000
}
```

### Phase 2 (Future)

#### 4. Water Bills

**Bill Type:** `water`

**Providers:**
- Lagos Water Corporation
- Abuja Water Board

**Required Metadata:**
```json
{
  "bill_type": "water",
  "provider": "Lagos Water Corporation",
  "account_number": "1234567890",
  "customer_name": "John Doe"
}
```

#### 5. Internet Subscriptions

**Bill Type:** `internet`

**Providers:**
- Spectranet
- Smile
- Swift

**Required Metadata:**
```json
{
  "bill_type": "internet",
  "provider": "Spectranet",
  "account_number": "1234567890",
  "package": "unlimited",
  "customer_name": "John Doe"
}
```

#### 6. Cable TV (Other)

**Bill Type:** `cable_tv`

**Providers:**
- GOtv
- Startimes

**Required Metadata:**
```json
{
  "bill_type": "cable_tv",
  "provider": "GOtv",
  "smartcard_number": "1234567890",
  "package": "max",
  "customer_name": "John Doe"
}
```

## Metadata Validation

### Required Fields (All Categories)

- `bill_type` - Category identifier
- `provider` - Service provider name
- `customer_name` - Customer name

### Optional Fields

- `customer_email` - Customer email
- `customer_phone` - Customer phone number
- `customer_address` - Customer address

## Amount Ranges

### Minimum Amounts

- DSTV: ₦2,000
- Electricity: ₦1,000
- Airtime: ₦100
- Water: ₦500
- Internet: ₦1,000
- Cable TV: ₦500

### Maximum Amounts

- All categories: ₦999,999

## Example Payment Link Creation

```json
{
  "amount": 24500.00,
  "description": "DSTV Premium Subscription - March 2026",
  "customer_email": "user@voicepay.ng",
  "customer_name": "John Doe",
  "tx_ref": "VP-BILL-123-1711958400",
  "metadata": {
    "source": "voicepay",
    "user_id": "123",
    "whatsapp_id": "2348012345678",
    "bill_type": "dstv",
    "provider": "DSTV Nigeria",
    "package": "premium",
    "smartcard_number": "1234567890",
    "customer_name": "John Doe",
    "voice_verified": true,
    "biometric_score": 0.95
  }
}
```

## Provider Codes

### DSTV Packages

- `compact` - DSTV Compact
- `compact_plus` - DSTV Compact Plus
- `premium` - DSTV Premium
- `premium_asia` - DSTV Premium Asia

### Electricity Providers

- `EKEDC` - Eko Electricity Distribution Company
- `IKEDC` - Ikeja Electric
- `AEDC` - Abuja Electricity Distribution Company
- `PHED` - Port Harcourt Electricity Distribution

### Meter Types

- `prepaid` - Prepaid meter
- `postpaid` - Postpaid meter

## Validation Rules

1. `bill_type` must be one of supported categories
2. `provider` must be valid for the bill type
3. `amount` must be within allowed range
4. Account/meter/smartcard numbers must be numeric
5. Phone numbers must be 11 digits (Nigerian format)

## Error Codes

- `INVALID_BILL_TYPE` - Unsupported bill category
- `INVALID_PROVIDER` - Unknown provider
- `INVALID_AMOUNT` - Amount outside allowed range
- `MISSING_METADATA` - Required metadata field missing
- `INVALID_ACCOUNT_NUMBER` - Invalid account/meter/smartcard number

## Support

For questions about bill categories:
- Email: billing@onepay.ng
