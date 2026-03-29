# Design Document: Invoice Generation

## Overview

The Invoice Generation feature extends OnePay's payment link system to automatically generate professional PDF invoices for merchants. This feature integrates seamlessly with the existing transaction workflow, creating a one-to-one relationship between payment links and invoices. Each invoice receives a unique sequential number (format: INV-YYYY-NNNNNN), includes merchant branding, and can be delivered via email or downloaded as a PDF.

The system leverages OnePay's existing architecture: Flask blueprints for routing, SQLAlchemy ORM for data persistence, the existing email service for delivery, and WeasyPrint (already in dependencies) for PDF generation. The design follows OnePay's established patterns for security, rate limiting, and audit logging.

## Architecture

### High-Level Architecture

The invoice generation system consists of four primary layers:

1. **API Layer** (blueprints/invoices.py): REST endpoints for invoice creation, retrieval, download, and settings management
2. **Service Layer** (services/invoice.py): Business logic for invoice generation, PDF rendering, and email delivery
3. **Data Layer** (models/invoice.py): Invoice and InvoiceSettings models with SQLAlchemy ORM
4. **Template Layer** (templates/invoice.html): HTML/CSS template for PDF rendering

### Component Interaction Flow

```
Payment Link Creation → Invoice Auto-Creation → PDF Generation → Email Delivery (optional)
                                ↓
                        Invoice Record Stored
                                ↓
                    Transaction Status Updates → Invoice Status Sync
```

### Integration Points

- **Transaction Model**: One-to-one relationship via foreign key
- **Email Service**: Reuse existing services/email.py for invoice delivery
- **QR Code Service**: Include payment QR codes in invoice PDFs
- **Rate Limiter**: Apply existing rate limiting to invoice endpoints
- **Audit Log**: Track invoice access and generation events

## Components and Interfaces

### 1. Invoice Model (models/invoice.py)

**Purpose**: Represent invoice records in the database with metadata and status tracking.

**Schema**:
```python
class Invoice(Base):
    __tablename__ = "invoices"
    
    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(20), unique=True, nullable=False, index=True)
    
    # Relationships
    transaction_id = Column(Integer, ForeignKey("transactions.id", ondelete="CASCADE"), 
                           unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), 
                    nullable=True, index=True)
    
    # Invoice details (denormalized for historical accuracy)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="NGN")
    description = Column(String(255), nullable=True)
    customer_email = Column(String(255), nullable=True)
    customer_phone = Column(String(20), nullable=True)
    
    # Merchant branding (snapshot at creation time)
    business_name = Column(String(255), nullable=True)
    business_address = Column(Text, nullable=True)
    business_tax_id = Column(String(100), nullable=True)
    business_logo_url = Column(String(500), nullable=True)
    payment_terms = Column(Text, nullable=True)
    
    # Status tracking
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.DRAFT)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    sent_at = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    
    # Email delivery tracking
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime(timezone=True), nullable=True)
    email_attempts = Column(Integer, default=0)
    email_last_error = Column(Text, nullable=True)
```

**Indexes**:
- `ix_invoices_user_created`: (user_id, created_at) for history queries
- `ix_invoices_user_status`: (user_id, status) for filtering
- `ix_invoices_transaction`: (transaction_id) for lookups

### 2. InvoiceSettings Model (models/invoice.py)

**Purpose**: Store per-merchant invoice customization preferences.

**Schema**:
```python
class InvoiceSettings(Base):
    __tablename__ = "invoice_settings"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), 
                    unique=True, nullable=False, index=True)
    
    # Branding
    business_name = Column(String(255), nullable=True)
    business_address = Column(Text, nullable=True)
    business_tax_id = Column(String(100), nullable=True)
    business_logo_url = Column(String(500), nullable=True)
    
    # Defaults
    default_payment_terms = Column(Text, default="Payment due upon receipt")
    auto_send_email = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))
```

### 3. Invoice Service (services/invoice.py)

**Purpose**: Core business logic for invoice operations.

**Interface**:
```python
class InvoiceService:
    def generate_invoice_number() -> str:
        """Generate unique sequential invoice number: INV-YYYY-NNNNNN"""
        
    def create_invoice(transaction: Transaction, user: User) -> Invoice:
        """Create invoice from transaction with merchant settings"""
        
    def render_invoice_html(invoice: Invoice, transaction: Transaction) -> str:
        """Render invoice to HTML using template"""
        
    def generate_invoice_pdf(invoice: Invoice, transaction: Transaction) -> bytes:
        """Generate PDF from invoice HTML"""
        
    def send_invoice_email(invoice: Invoice, pdf_bytes: bytes) -> bool:
        """Send invoice PDF via email"""
        
    def sync_invoice_status(invoice: Invoice, transaction: Transaction) -> None:
        """Update invoice status based on transaction status"""
        
    def get_invoice_by_number(invoice_number: str, user_id: int) -> Invoice:
        """Retrieve invoice with ownership verification"""
        
    def get_invoice_history(user_id: int, status: str = None, 
                           page: int = 1, page_size: int = 20) -> List[Invoice]:
        """Get paginated invoice history with optional status filter"""
```

### 4. Invoice Blueprint (blueprints/invoices.py)

**Purpose**: REST API endpoints for invoice operations.

**Endpoints**:

```
POST   /api/invoices/create              - Create invoice for transaction
GET    /api/invoices                     - List invoices (paginated)
GET    /api/invoices/<invoice_number>    - Get invoice details
GET    /api/invoices/<invoice_number>/download - Download PDF
POST   /api/invoices/<invoice_number>/send     - Send via email
GET    /api/invoices/settings            - Get invoice settings
POST   /api/invoices/settings            - Update invoice settings
```

**Authentication**: All endpoints require authentication via `@login_required_redirect` or API equivalent.

**Rate Limiting**: 
- Invoice creation: 20 requests/minute (tied to payment link creation)
- Invoice download: 50 requests/minute
- Settings update: 10 requests/minute

### 5. Invoice Template (templates/invoice.html)

**Purpose**: HTML/CSS template for PDF rendering.

**Structure**:
- Header: OnePay branding + merchant logo
- Invoice metadata: Invoice number, date, status
- Merchant details: Business name, address, tax ID
- Customer details: Email, phone
- Itemized charges: Description, amount
- Payment information: Total, currency, payment link, QR code
- Footer: Payment terms, OnePay branding

**CSS Requirements**:
- Print-friendly styles (A4 page size)
- Professional typography
- Responsive layout for PDF rendering
- Status indicators with color coding

## Data Models

### Invoice Status Enum

```python
class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"      # Created but not sent
    SENT = "sent"        # Email delivered successfully
    PAID = "paid"        # Transaction verified
    EXPIRED = "expired"  # Transaction expired
    CANCELLED = "cancelled"  # Manually cancelled
```

### Invoice Number Generation

**Algorithm**:
1. Query database for highest invoice number
2. Extract sequence number from format INV-YYYY-NNNNNN
3. Increment sequence by 1
4. Format as INV-{current_year}-{sequence:06d}
5. Handle race conditions with database unique constraint + retry logic

**Concurrency Handling**:
- Use database-level unique constraint on invoice_number
- Implement retry logic (max 3 attempts) on constraint violation
- Use SELECT FOR UPDATE in transaction to prevent race conditions

### Data Denormalization Strategy

Invoice records denormalize transaction and merchant data to preserve historical accuracy:
- If merchant updates business name, old invoices retain original name
- If transaction is deleted, invoice retains amount/description
- Enables accurate invoice regeneration at any time

### Database Migration

**Migration file**: `alembic/versions/YYYYMMDDHHMMSS_add_invoice_tables.py`

**Operations**:
1. Create `invoices` table with indexes
2. Create `invoice_settings` table
3. Add foreign key constraints with CASCADE/SET NULL
4. Create unique constraint on invoice_number
5. Create composite indexes for query optimization


## API Specification

### POST /api/invoices/create

**Purpose**: Create invoice for an existing transaction.

**Request**:
```json
{
  "transaction_reference": "TXN-20260326-ABC123",
  "auto_send_email": false
}
```

**Response** (201 Created):
```json
{
  "success": true,
  "invoice": {
    "invoice_number": "INV-2026-000042",
    "transaction_reference": "TXN-20260326-ABC123",
    "amount": "5000.00",
    "currency": "NGN",
    "status": "draft",
    "created_at": "2026-03-26T10:30:00Z",
    "download_url": "/api/invoices/INV-2026-000042/download"
  }
}
```

**Error Cases**:
- 401: Unauthenticated
- 403: Transaction not owned by merchant
- 404: Transaction not found
- 409: Invoice already exists for transaction
- 429: Rate limit exceeded

### GET /api/invoices

**Purpose**: List invoices with pagination and filtering.

**Query Parameters**:
- `page`: Page number (default: 1)
- `page_size`: Results per page (default: 20, max: 100)
- `status`: Filter by status (draft|sent|paid|expired|cancelled)
- `sort`: Sort order (created_desc|created_asc|amount_desc|amount_asc)

**Response** (200 OK):
```json
{
  "success": true,
  "invoices": [
    {
      "invoice_number": "INV-2026-000042",
      "transaction_reference": "TXN-20260326-ABC123",
      "customer_email": "customer@example.com",
      "amount": "5000.00",
      "currency": "NGN",
      "status": "paid",
      "created_at": "2026-03-26T10:30:00Z",
      "paid_at": "2026-03-26T11:15:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_pages": 3,
    "total_count": 57
  }
}
```

### GET /api/invoices/<invoice_number>

**Purpose**: Get detailed invoice information.

**Response** (200 OK):
```json
{
  "success": true,
  "invoice": {
    "invoice_number": "INV-2026-000042",
    "transaction_reference": "TXN-20260326-ABC123",
    "amount": "5000.00",
    "currency": "NGN",
    "description": "Website development services",
    "customer_email": "customer@example.com",
    "customer_phone": "+2348012345678",
    "business_name": "Acme Corp",
    "status": "paid",
    "created_at": "2026-03-26T10:30:00Z",
    "sent_at": "2026-03-26T10:31:00Z",
    "paid_at": "2026-03-26T11:15:00Z",
    "payment_link": "https://onepay.com/verify/TXN-20260326-ABC123?token=...",
    "download_url": "/api/invoices/INV-2026-000042/download"
  }
}
```

**Error Cases**:
- 401: Unauthenticated
- 403: Invoice not owned by merchant
- 404: Invoice not found

### GET /api/invoices/<invoice_number>/download

**Purpose**: Download invoice as PDF.

**Response** (200 OK):
- Content-Type: application/pdf
- Content-Disposition: attachment; filename="INV-2026-000042.pdf"
- Body: PDF binary data

**Error Cases**:
- 401: Unauthenticated
- 403: Invoice not owned by merchant
- 404: Invoice not found
- 500: PDF generation failed

### POST /api/invoices/<invoice_number>/send

**Purpose**: Send invoice via email to customer.

**Request**:
```json
{
  "recipient_email": "customer@example.com"  // Optional, defaults to invoice customer_email
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Invoice sent successfully",
  "sent_to": "customer@example.com",
  "sent_at": "2026-03-26T10:31:00Z"
}
```

**Error Cases**:
- 401: Unauthenticated
- 403: Invoice not owned by merchant
- 404: Invoice not found
- 400: No recipient email available
- 500: Email delivery failed

### GET /api/invoices/settings

**Purpose**: Get merchant invoice settings.

**Response** (200 OK):
```json
{
  "success": true,
  "settings": {
    "business_name": "Acme Corp",
    "business_address": "123 Main St, Lagos, Nigeria",
    "business_tax_id": "12345678-0001",
    "business_logo_url": "https://example.com/logo.png",
    "default_payment_terms": "Payment due within 30 days",
    "auto_send_email": true
  }
}
```

### POST /api/invoices/settings

**Purpose**: Update merchant invoice settings.

**Request**:
```json
{
  "business_name": "Acme Corp",
  "business_address": "123 Main St, Lagos, Nigeria",
  "business_tax_id": "12345678-0001",
  "business_logo_url": "https://example.com/logo.png",
  "default_payment_terms": "Payment due within 30 days",
  "auto_send_email": true
}
```

**Validation**:
- business_name: Max 255 chars, sanitized
- business_address: Max 1000 chars, sanitized
- business_tax_id: Max 100 chars, alphanumeric + hyphens
- business_logo_url: Valid URL, accessible, image format (PNG/JPG/SVG)
- default_payment_terms: Max 500 chars, sanitized
- auto_send_email: Boolean

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Invoice settings updated successfully",
  "settings": { /* updated settings */ }
}
```

**Error Cases**:
- 401: Unauthenticated
- 400: Validation failed
- 429: Rate limit exceeded

## PDF Generation Approach

### Technology: WeasyPrint

**Rationale**: WeasyPrint is already in requirements.txt, provides excellent HTML/CSS to PDF conversion, supports modern CSS features, and handles complex layouts reliably.

**Advantages**:
- No additional dependencies
- Excellent CSS support (flexbox, grid)
- Handles embedded images and fonts
- Produces high-quality PDFs
- Open source and well-maintained

### PDF Generation Pipeline

1. **Load Invoice Data**: Fetch invoice and related transaction from database
2. **Render HTML**: Use Jinja2 template with invoice data
3. **Embed Assets**: Include QR code as base64 data URI, fetch logo if URL provided
4. **Generate PDF**: Pass HTML to WeasyPrint with CSS
5. **Return Binary**: Stream PDF bytes to response or email attachment

### Template Rendering

**Template Engine**: Jinja2 (Flask default)

**Template Location**: `templates/invoice.html`

**Context Variables**:
```python
{
    'invoice': invoice_object,
    'transaction': transaction_object,
    'qr_code_data_uri': 'data:image/png;base64,...',
    'logo_data_uri': 'data:image/png;base64,...',  # If logo URL provided
    'current_date': datetime.now(timezone.utc),
    'payment_url': full_payment_link_url
}
```

### CSS Considerations

**Print-Specific Styles**:
```css
@page {
    size: A4;
    margin: 2cm;
}

@media print {
    /* Prevent page breaks inside important sections */
    .invoice-header, .invoice-items, .invoice-footer {
        page-break-inside: avoid;
    }
}
```

**Color Coding**:
- Draft: Gray (#6c757d)
- Sent: Blue (#0969da)
- Paid: Green (#2da44e)
- Expired: Orange (#fb8500)
- Cancelled: Red (#cf222e)

### Performance Optimization

- **Caching**: Cache rendered HTML for 5 minutes (invoice data rarely changes)
- **Async Generation**: For email delivery, generate PDF asynchronously
- **Timeout**: Set 10-second timeout for PDF generation
- **Size Limit**: Warn if PDF exceeds 5MB (indicates issue with embedded assets)

## Email Integration

### Email Service Extension

**File**: `services/email.py` (extend existing service)

**New Function**:
```python
def send_invoice_email(to_email: str, invoice: Invoice, pdf_bytes: bytes) -> bool:
    """
    Send invoice PDF via email.
    
    Args:
        to_email: Recipient email address
        invoice: Invoice object
        pdf_bytes: PDF binary data
        
    Returns:
        True if sent successfully, False otherwise
    """
```

### Email Template

**Subject**: `Invoice {invoice_number} from {business_name}`

**Plain Text Body**:
```
Hello,

Please find attached invoice {invoice_number} for {amount} {currency}.

Description: {description}

You can pay online using this link:
{payment_link}

Payment Terms: {payment_terms}

Thank you for your business!

— {business_name}
Powered by OnePay
```

**HTML Body**: Professional HTML email with:
- Invoice summary table
- Payment link button
- QR code for quick payment
- Attached PDF notice
- OnePay branding footer

### Attachment Handling

**Filename**: `{invoice_number}.pdf` (e.g., "INV-2026-000042.pdf")

**MIME Type**: `application/pdf`

**Size Limit**: 10MB (WeasyPrint PDFs typically < 1MB)

### Delivery Tracking

**Fields in Invoice Model**:
- `email_sent`: Boolean flag
- `email_sent_at`: Timestamp of successful delivery
- `email_attempts`: Retry counter
- `email_last_error`: Last error message for debugging

**Retry Logic**:
- Max 3 attempts
- Exponential backoff: 1min, 5min, 15min
- Log all attempts to audit log
- Update invoice status to "sent" only on success

## Security Considerations

### Authentication and Authorization

**Authentication**: All invoice endpoints require valid session (existing Flask-Login integration)

**Authorization**: 
- Verify invoice ownership: `invoice.user_id == current_user_id()`
- Verify transaction ownership before invoice creation
- Return 403 Forbidden for unauthorized access attempts
- Log all authorization failures to audit log

### Input Validation

**Invoice Settings**:
- Sanitize all text fields with `_safe()` helper (existing in payments.py)
- Validate logo URL format and accessibility
- Validate email format with existing `_safe_email()` helper
- Validate phone format with existing `_safe_phone()` helper
- Prevent HTML injection in PDF output

**Invoice Number**:
- Validate format: `^INV-\d{4}-\d{6}$`
- Prevent SQL injection via parameterized queries (SQLAlchemy ORM)

### Rate Limiting

**Endpoints**:
- Invoice creation: 20/minute (prevents abuse)
- Invoice download: 50/minute (allows legitimate bulk downloads)
- Invoice email: 10/minute (prevents spam)
- Settings update: 10/minute (prevents abuse)

**Implementation**: Use existing `services/rate_limiter.py` with per-user keys

### Data Protection

**Sensitive Data**:
- Invoice PDFs may contain customer PII (email, phone)
- Business tax IDs are sensitive
- Enforce HTTPS in production (existing ENFORCE_HTTPS config)

**Access Logging**:
- Log all invoice access attempts with user_id, invoice_number, IP address
- Use existing `core/audit.py` for audit logging
- Log events: invoice.created, invoice.viewed, invoice.downloaded, invoice.emailed

### PDF Security

**Prevent Injection**:
- Escape all user input in HTML template (Jinja2 auto-escaping)
- Validate logo URLs before fetching (prevent SSRF)
- Set timeout on external resource fetching (5 seconds)
- Sanitize all text fields before rendering

**Resource Limits**:
- Max PDF generation time: 10 seconds
- Max PDF size: 10MB
- Max logo size: 2MB
- Timeout on logo fetching: 5 seconds

## Performance Considerations

### Database Optimization

**Indexes**:
- `(user_id, created_at)`: Optimize invoice history queries
- `(user_id, status)`: Optimize filtered queries
- `(transaction_id)`: Optimize invoice-transaction lookups
- `(invoice_number)`: Unique constraint + fast lookups

**Query Optimization**:
- Use pagination for list endpoints (max 100 per page)
- Eager load related transaction data with `joinedload()`
- Use `SELECT FOR UPDATE` for invoice number generation
- Add database connection pooling (already configured in database.py)

### PDF Generation Performance

**Benchmarks** (expected):
- Simple invoice: < 1 second
- Invoice with logo: < 2 seconds
- Invoice with QR code: < 1.5 seconds

**Optimization Strategies**:
- Cache rendered HTML for 5 minutes
- Generate PDFs asynchronously for email delivery
- Use connection pooling for logo fetching
- Implement timeout to prevent hanging

### Caching Strategy

**Invoice HTML Caching**:
- Key: `invoice:{invoice_number}:html`
- TTL: 5 minutes
- Invalidate on invoice update

**Invoice Settings Caching**:
- Key: `invoice_settings:{user_id}`
- TTL: 15 minutes
- Invalidate on settings update

**Implementation**: Use in-memory cache (functools.lru_cache) for MVP, Redis for production scale

### Scalability Considerations

**Current Scale**: Single-server deployment with SQLite/PostgreSQL

**Future Scale** (if needed):
- Move PDF generation to background queue (Celery)
- Store generated PDFs in object storage (S3)
- Implement CDN for PDF downloads
- Add read replicas for invoice history queries

## Transaction Status Synchronization

### Synchronization Strategy

**Trigger Points**:
1. Transaction status changes to "verified" → Invoice status to "paid"
2. Transaction status changes to "expired" → Invoice status to "expired"
3. Transaction status changes to "failed" → No invoice status change (keep as draft/sent)

**Implementation Approach**: Event-driven synchronization

### Webhook Integration

**Location**: `services/webhook.py` (extend existing webhook handler)

**New Function**:
```python
def sync_invoice_on_transaction_update(transaction: Transaction) -> None:
    """
    Synchronize invoice status when transaction status changes.
    Called from webhook handler after transaction update.
    """
    with get_db() as db:
        invoice = db.query(Invoice).filter(
            Invoice.transaction_id == transaction.id
        ).first()
        
        if not invoice:
            return  # No invoice for this transaction
        
        if transaction.status == TransactionStatus.VERIFIED:
            invoice.status = InvoiceStatus.PAID
            invoice.paid_at = datetime.now(timezone.utc)
        elif transaction.status == TransactionStatus.EXPIRED:
            invoice.status = InvoiceStatus.EXPIRED
        
        db.flush()
        log_event(db, "invoice.status_synced", 
                 detail={"invoice_number": invoice.invoice_number,
                        "new_status": invoice.status.value})
```

**Integration Point**: Add call to `sync_invoice_on_transaction_update()` in existing webhook handler after transaction status update.

### Manual Synchronization

**Endpoint**: `POST /api/invoices/<invoice_number>/sync`

**Purpose**: Allow manual status synchronization if webhook fails

**Implementation**:
```python
@invoices_bp.route("/api/invoices/<invoice_number>/sync", methods=["POST"])
def sync_invoice_status(invoice_number):
    """Manually sync invoice status with transaction status"""
    # Verify ownership, fetch invoice and transaction
    # Call sync logic
    # Return updated status
```

### Status Transition Rules

**Valid Transitions**:
- draft → sent (email delivered)
- draft → paid (direct payment without email)
- draft → expired (transaction expired)
- sent → paid (payment received)
- sent → expired (transaction expired)
- Any → cancelled (manual cancellation)

**Invalid Transitions**:
- paid → expired (payment is final)
- paid → draft (cannot unpay)
- expired → paid (cannot pay expired invoice)

## Integration with Existing System

### Payment Link Creation Flow

**Current Flow**:
1. Merchant creates payment link via `/api/payments/create`
2. Transaction record created
3. QR codes generated
4. Response returned with payment link

**Updated Flow**:
1. Merchant creates payment link via `/api/payments/create`
2. Transaction record created
3. QR codes generated
4. **Invoice automatically created** (if merchant has invoice settings)
5. **Invoice PDF generated** (if auto_send_email enabled)
6. **Invoice emailed to customer** (if customer_email provided and auto_send_email enabled)
7. Response returned with payment link + invoice_number

**Implementation**: Add invoice creation logic to `blueprints/payments.py` in the `/api/payments/create` endpoint after transaction creation.

### Dashboard Integration

**New Dashboard Section**: "Invoices"

**Location**: Add new route `/invoices` in `blueprints/payments.py`

**Template**: `templates/invoices.html` (new file)

**Features**:
- List all invoices with status badges
- Filter by status (draft, sent, paid, expired)
- Search by invoice number or customer email
- Download PDF button
- Resend email button
- View invoice details modal

**Navigation**: Add "Invoices" link to dashboard navigation in `templates/dashboard_base.html`

### Settings Page Integration

**Location**: Extend existing `/settings` route in `blueprints/payments.py`

**Template**: Extend `templates/settings.html`

**New Section**: "Invoice Settings"

**Fields**:
- Business Name (text input)
- Business Address (textarea)
- Tax ID (text input)
- Logo URL (text input with preview)
- Default Payment Terms (textarea)
- Auto-send Email (checkbox)

**Validation**: Client-side + server-side validation with existing patterns

### Audit Logging Integration

**Events to Log**:
- `invoice.created`: Invoice created with invoice_number, transaction_reference
- `invoice.viewed`: Invoice details viewed
- `invoice.downloaded`: PDF downloaded
- `invoice.emailed`: Email sent with recipient
- `invoice.settings_updated`: Settings changed
- `invoice.status_synced`: Status synchronized with transaction

**Implementation**: Use existing `core/audit.py` `log_event()` function


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Invoice Creation for Payment Links

*For any* payment link created by a merchant, the system shall create exactly one associated invoice with a unique invoice number.

**Validates: Requirements 1.1, 5.1**

### Property 2: Sequential Invoice Numbering

*For any* sequence of invoice creations, invoice numbers shall be assigned in strictly increasing sequential order, and all invoice numbers shall match the format `INV-YYYY-NNNNNN` where YYYY is a four-digit year and NNNNNN is a zero-padded six-digit sequence number.

**Validates: Requirements 1.2, 2.1, 2.2**

### Property 3: Invoice Data Completeness

*For any* invoice created, the invoice record shall contain all required fields: invoice_number, transaction_id, user_id, amount, currency, status, and created_at timestamp.

**Validates: Requirements 1.3, 1.4**

### Property 4: Optional Field Inclusion

*For any* invoice where the merchant has provided optional business details (address, tax_id, logo_url), those details shall be present in the invoice record and rendered in the PDF output.

**Validates: Requirements 1.5**

### Property 5: Concurrent Invoice Number Uniqueness

*For any* set of invoices created concurrently, all invoice numbers shall be unique with no duplicates, and if a constraint violation occurs, the system shall retry with the next available number.

**Validates: Requirements 2.4, 2.5**

### Property 6: PDF Generation Completeness

*For any* invoice, the generated PDF shall contain all required elements: invoice_number, merchant information, customer information, amount with currency symbol formatted to two decimal places, description, payment terms, payment link URL, and QR code.

**Validates: Requirements 3.1, 3.2, 3.3, 5.4, 5.5**

### Property 7: HTML Template Validity

*For any* invoice, the Pretty_Printer shall generate valid HTML that includes OnePay branding, merchant branding (if provided), and payment status indicators.

**Validates: Requirements 4.1, 4.2, 4.4**

### Property 8: Logo Embedding

*For any* invoice with a merchant logo URL, the Pretty_Printer shall embed the logo image as a base64 data URI in the HTML output.

**Validates: Requirements 4.5**

### Property 9: Transaction Status Synchronization

*For any* transaction whose status changes to verified or expired, the associated invoice status shall update to paid or expired respectively within the same transaction.

**Validates: Requirements 5.2, 5.3, 12.4, 12.5**

### Property 10: Invoice History Pagination

*For any* request to the invoice history API, the response shall return invoices sorted by creation date in descending order, limited to the specified page_size (max 100), and include complete pagination metadata.

**Validates: Requirements 6.1, 6.2, 6.5**

### Property 11: Invoice History Metadata

*For any* invoice returned in the history API, the response shall include all required metadata fields: invoice_number, customer_email, amount, status, created_at, and transaction_reference.

**Validates: Requirements 6.3**

### Property 12: Status Filtering

*For any* invoice history request with a status filter parameter, all returned invoices shall have the specified status.

**Validates: Requirements 6.4**

### Property 13: Authentication Required

*For any* invoice API endpoint request without valid authentication, the system shall return a 401 authentication error.

**Validates: Requirements 7.1**

### Property 14: Authorization Enforcement

*For any* invoice request by a merchant, the system shall verify the merchant owns the associated transaction, and if not, shall return a 403 or 404 error.

**Validates: Requirements 7.2, 7.3**

### Property 15: Rate Limiting

*For any* merchant making invoice generation requests, the system shall enforce a rate limit of 20 requests per minute, returning a 429 error when exceeded.

**Validates: Requirements 7.4**

### Property 16: Audit Logging

*For any* invoice access attempt (view, download, email), the system shall create an audit log entry containing merchant_id, invoice_number, action type, and timestamp.

**Validates: Requirements 7.5**

### Property 17: Input Validation

*For any* invoice creation request, the system shall validate that amount > 0, customer_email matches RFC 5322 format (if provided), customer_phone matches the pattern `^\+?[0-9\s\-\(\)]{7,20}$` (if provided), and all text fields are sanitized to prevent HTML injection.

**Validates: Requirements 8.1, 8.2, 8.3, 8.4**

### Property 18: Validation Error Messages

*For any* invoice creation request with invalid data, the system shall return a descriptive error message indicating which specific field failed validation.

**Validates: Requirements 8.5**

### Property 19: Invoice Serialization Round-Trip

*For any* valid invoice record, serializing to JSON then deserializing back shall produce an equivalent invoice record with all fields preserved.

**Validates: Requirements 9.5**

### Property 20: JSON Parsing Validation

*For any* JSON invoice data, the parser shall validate that all required fields are present (invoice_number, merchant_id, transaction_reference, amount, currency) and return a descriptive error message if validation fails.

**Validates: Requirements 9.1, 9.2, 9.3**

### Property 21: JSON Serialization

*For any* invoice record, the Pretty_Printer shall format it into valid JSON containing all invoice fields.

**Validates: Requirements 9.4**

### Property 22: Automatic Email Delivery

*For any* invoice created when the merchant has auto_send_email enabled and customer_email is provided, the system shall send an email containing the invoice PDF as an attachment and the payment link URL in the body.

**Validates: Requirements 10.1, 10.2, 10.3, 10.4**

### Property 23: Email Failure Handling

*For any* invoice email delivery failure, the system shall log the error with details and still allow manual invoice download.

**Validates: Requirements 10.5**

### Property 24: Invoice Settings Persistence

*For any* merchant invoice settings update (business_name, address, tax_id, logo_url, payment_terms, auto_send_email), the new settings shall be saved and applied to all future invoices created by that merchant.

**Validates: Requirements 11.1, 11.2, 11.3**

### Property 25: Settings Temporal Isolation

*For any* invoice created before a merchant updates their settings, the invoice shall retain the original settings values and not be affected by the update.

**Validates: Requirements 11.4**

### Property 26: Logo URL Validation

*For any* logo URL provided in invoice settings, the system shall validate that the URL is accessible and returns a valid image format (PNG, JPG, or SVG), rejecting invalid URLs with a descriptive error.

**Validates: Requirements 11.5**

### Property 27: Invoice Status Lifecycle

*For any* invoice, the status field shall only contain valid enum values (draft, sent, paid, expired, cancelled), and newly created invoices shall have status set to draft.

**Validates: Requirements 12.1, 12.2**

### Property 28: Email Delivery Status Update

*For any* invoice where email delivery succeeds, the invoice status shall update from draft to sent, and the sent_at timestamp shall be recorded.

**Validates: Requirements 12.3**

## Error Handling

### Error Categories

**Validation Errors (400 Bad Request)**:
- Invalid invoice data (missing required fields, invalid formats)
- Invalid email or phone format
- Invalid logo URL or inaccessible image
- Amount <= 0
- Invalid status filter parameter

**Authentication Errors (401 Unauthorized)**:
- Missing or invalid session
- Expired session token

**Authorization Errors (403 Forbidden)**:
- Accessing invoice owned by another merchant
- Insufficient permissions

**Not Found Errors (404 Not Found)**:
- Invoice number doesn't exist
- Transaction reference doesn't exist
- Attempting to access non-owned invoice (security through obscurity)

**Conflict Errors (409 Conflict)**:
- Invoice already exists for transaction
- Duplicate invoice number (should trigger retry)

**Rate Limit Errors (429 Too Many Requests)**:
- Exceeded rate limit for invoice creation (20/min)
- Exceeded rate limit for invoice download (50/min)
- Exceeded rate limit for email sending (10/min)

**Server Errors (500 Internal Server Error)**:
- PDF generation failure
- Database connection failure
- Email service unavailable
- External resource timeout (logo fetching)

### Error Response Format

All error responses follow OnePay's existing error format:

```json
{
  "success": false,
  "error": "Human-readable error message",
  "error_code": "MACHINE_READABLE_CODE",
  "details": {
    "field": "specific_field_name",
    "reason": "detailed_reason"
  }
}
```

### Error Recovery Strategies

**Invoice Number Collision**:
1. Catch unique constraint violation
2. Retry with next sequence number (max 3 attempts)
3. If all retries fail, return 500 error and log critical alert

**PDF Generation Failure**:
1. Log error with full context (invoice_number, user_id, error message)
2. Return 500 error to client
3. Allow retry via manual download endpoint
4. Set timeout of 10 seconds to prevent hanging

**Email Delivery Failure**:
1. Log error with details (recipient, error message)
2. Increment email_attempts counter
3. Store error in email_last_error field
4. Return success response (invoice created, email failed)
5. Allow manual resend via `/send` endpoint

**Logo Fetch Failure**:
1. Set 5-second timeout on HTTP request
2. If timeout or error, log warning
3. Generate invoice without logo (graceful degradation)
4. Include note in invoice: "Logo unavailable"

**Transaction Not Found**:
1. Validate transaction exists before invoice creation
2. Return 404 with clear message
3. Log attempt for security monitoring

**Database Connection Failure**:
1. Rely on SQLAlchemy connection pooling retry logic
2. If persistent failure, return 500 error
3. Log critical alert for monitoring

### Idempotency

**Invoice Creation**: Use transaction_id as natural idempotency key
- Check if invoice exists for transaction before creating
- If exists, return existing invoice (200 OK, not 409)
- Prevents duplicate invoices from retry requests

**Settings Update**: Last-write-wins semantics
- No idempotency key needed
- Each update overwrites previous values
- Timestamp recorded for audit trail

## Testing Strategy

### Dual Testing Approach

The invoice generation feature will be tested using both unit tests and property-based tests to ensure comprehensive coverage:

**Unit Tests**: Verify specific examples, edge cases, and error conditions
- Specific invoice number formats
- Status transition scenarios
- Error handling paths
- Integration points with existing services

**Property-Based Tests**: Verify universal properties across all inputs
- Invoice number uniqueness and sequencing
- Round-trip serialization
- Input validation across random inputs
- Concurrent invoice creation safety

### Property-Based Testing Configuration

**Library**: Use `hypothesis` for Python property-based testing

**Configuration**:
- Minimum 100 iterations per property test
- Each test tagged with comment referencing design property
- Tag format: `# Feature: invoice-generation, Property {number}: {property_text}`

**Example Property Test**:
```python
from hypothesis import given, strategies as st

# Feature: invoice-generation, Property 2: Sequential Invoice Numbering
@given(st.lists(st.integers(min_value=1, max_value=1000000), min_size=1, max_size=100))
def test_invoice_numbers_are_sequential(amounts):
    """For any sequence of invoice creations, numbers are strictly increasing"""
    invoices = []
    for amount in amounts:
        invoice = create_invoice(amount=amount)
        invoices.append(invoice)
    
    numbers = [extract_sequence(inv.invoice_number) for inv in invoices]
    assert numbers == sorted(numbers)
    assert len(numbers) == len(set(numbers))  # All unique
```

### Unit Test Coverage

**Models** (models/invoice.py):
- Invoice model field validation
- InvoiceSettings model field validation
- Status enum values
- Timestamp handling (timezone-aware)
- Relationship constraints (one-to-one with transaction)

**Services** (services/invoice.py):
- Invoice number generation (sequential, format, uniqueness)
- Invoice creation with settings application
- HTML rendering with template
- PDF generation with WeasyPrint
- Email delivery integration
- Status synchronization logic
- Authorization checks

**API Endpoints** (blueprints/invoices.py):
- POST /api/invoices/create (success, errors, validation)
- GET /api/invoices (pagination, filtering, sorting)
- GET /api/invoices/<number> (success, not found, unauthorized)
- GET /api/invoices/<number>/download (PDF generation, errors)
- POST /api/invoices/<number>/send (email delivery, errors)
- GET /api/invoices/settings (retrieve settings)
- POST /api/invoices/settings (update settings, validation)

**Integration Tests**:
- End-to-end invoice creation from payment link
- Transaction status change triggers invoice status update
- Email delivery with PDF attachment
- Settings update affects future invoices only
- Concurrent invoice creation (race condition testing)

### Edge Cases and Error Conditions

**Edge Cases**:
- Year boundary crossing (Dec 31 → Jan 1)
- First invoice ever created (sequence 000001)
- Invoice with no customer email (no auto-send)
- Invoice with no optional merchant details
- Very long descriptions (truncation)
- Special characters in text fields (sanitization)
- Large amounts (decimal precision)
- Zero-amount transactions (should be rejected)

**Error Conditions**:
- Duplicate invoice creation attempt
- Invalid transaction reference
- Unauthorized access attempt
- Rate limit exceeded
- PDF generation timeout
- Email delivery failure
- Logo URL inaccessible
- Invalid image format
- Database constraint violation
- Concurrent invoice number collision

### Test Data Generators

**Hypothesis Strategies**:
```python
# Generate valid invoice data
invoice_data = st.fixed_dictionaries({
    'amount': st.decimals(min_value='0.01', max_value='999999.99', places=2),
    'currency': st.sampled_from(['NGN', 'USD', 'EUR', 'GBP']),
    'description': st.text(min_size=1, max_size=255),
    'customer_email': st.emails(),
    'customer_phone': st.from_regex(r'^\+?[0-9\s\-\(\)]{7,20}$'),
})

# Generate invoice settings
settings_data = st.fixed_dictionaries({
    'business_name': st.text(min_size=1, max_size=255),
    'business_address': st.text(max_size=1000),
    'business_tax_id': st.from_regex(r'^[A-Z0-9\-]{5,100}$'),
    'payment_terms': st.text(max_size=500),
    'auto_send_email': st.booleans(),
})
```

### Performance Testing

**Benchmarks**:
- Invoice creation: < 100ms (database insert)
- PDF generation: < 2 seconds (with logo and QR code)
- Invoice list query: < 200ms (paginated, 20 records)
- Email delivery: < 5 seconds (including PDF generation)

**Load Testing**:
- 100 concurrent invoice creations (test uniqueness)
- 1000 invoices in database (test query performance)
- 50 simultaneous PDF downloads (test resource usage)

### Test Environment Setup

**Database**: Use SQLite in-memory for unit tests, PostgreSQL for integration tests

**Mocking**:
- Mock WeasyPrint for unit tests (test HTML generation separately)
- Mock email service for unit tests (test email logic separately)
- Mock external logo fetching (test with local test images)

**Fixtures**:
- Sample transactions with various statuses
- Sample merchant settings (with and without optional fields)
- Sample invoices in various states
- Test images for logo testing (PNG, JPG, SVG, invalid formats)

### Continuous Integration

**Pre-commit Checks**:
- Run all unit tests
- Run property-based tests (100 iterations)
- Check code coverage (target: 90%+)
- Run linter (flake8, black)
- Check for security issues (bandit)

**CI Pipeline**:
1. Run unit tests with coverage report
2. Run property-based tests with extended iterations (1000)
3. Run integration tests against PostgreSQL
4. Generate test report
5. Fail build if coverage < 90% or any test fails

