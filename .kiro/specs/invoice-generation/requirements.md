# Requirements Document: Invoice Generation

## Introduction

The Invoice Generation feature extends OnePay's payment link system to generate professional PDF invoices for merchants. This feature enables merchants to create branded invoices linked to payment transactions, providing professional documentation for business operations and record-keeping. Invoices will include merchant branding, sequential numbering, itemized details, and integration with the existing payment verification workflow.

## Glossary

- **Invoice_Generator**: The system component responsible for creating PDF invoices from transaction data
- **Invoice**: A professional business document containing merchant details, customer information, itemized charges, payment terms, and a unique invoice number
- **Merchant**: A registered OnePay user who creates payment links and invoices
- **Transaction**: A payment link record in the database with associated payment details
- **Invoice_Number**: A unique, sequential identifier for each invoice (format: INV-YYYY-NNNNNN)
- **Invoice_Template**: The HTML/CSS layout used to render invoice content before PDF conversion
- **PDF_Renderer**: The component that converts HTML invoice templates to PDF format
- **Invoice_Record**: A database entry tracking invoice metadata and linking to transactions
- **Payment_Link**: A secure, time-bound URL for customers to complete payment
- **Pretty_Printer**: A component that formats invoice data into human-readable HTML
- **Round_Trip**: The property that parsing an invoice and printing it produces an equivalent invoice

## Requirements

### Requirement 1: Invoice Creation

**User Story:** As a merchant, I want to create invoices linked to payment links, so that I can provide professional documentation to my customers.

#### Acceptance Criteria

1. WHEN a merchant creates a payment link, THE Invoice_Generator SHALL create an associated invoice with a unique Invoice_Number
2. THE Invoice_Generator SHALL assign Invoice_Numbers in sequential order starting from INV-2026-000001
3. THE Invoice_Generator SHALL store invoice metadata in the Invoice_Record table with transaction reference, creation timestamp, and invoice status
4. THE Invoice SHALL include merchant business name, customer email, customer phone, amount, currency, description, and payment terms
5. WHERE a merchant provides optional business details (address, tax ID, logo), THE Invoice SHALL include these details in the invoice header

### Requirement 2: Invoice Numbering System

**User Story:** As a merchant, I want invoices to have unique sequential numbers, so that I can track and reference them easily.

#### Acceptance Criteria

1. THE Invoice_Generator SHALL generate Invoice_Numbers in the format INV-YYYY-NNNNNN where YYYY is the current year and NNNNNN is a zero-padded sequential number
2. THE Invoice_Generator SHALL ensure Invoice_Numbers are unique across all merchants and years
3. WHEN the calendar year changes, THE Invoice_Generator SHALL continue sequential numbering without resetting
4. THE Invoice_Generator SHALL handle concurrent invoice creation without generating duplicate Invoice_Numbers
5. IF Invoice_Number generation fails due to database constraint violation, THEN THE Invoice_Generator SHALL retry with the next available number

### Requirement 3: Invoice PDF Generation

**User Story:** As a merchant, I want to download invoices as PDF files, so that I can send them to customers and maintain records.

#### Acceptance Criteria

1. WHEN a merchant requests an invoice download, THE PDF_Renderer SHALL generate a PDF from the Invoice_Template
2. THE PDF_Renderer SHALL include all invoice details: Invoice_Number, merchant information, customer information, itemized charges, subtotal, tax (if applicable), total amount, payment terms, and payment link
3. THE PDF_Renderer SHALL format currency values with two decimal places and the appropriate currency symbol
4. THE PDF_Renderer SHALL generate PDFs with consistent formatting across different browsers and operating systems
5. THE PDF_Renderer SHALL complete PDF generation within 5 seconds for standard invoices

### Requirement 4: Invoice Template Rendering

**User Story:** As a merchant, I want invoices to look professional and branded, so that they reflect well on my business.

#### Acceptance Criteria

1. THE Pretty_Printer SHALL format Invoice_Records into valid HTML using the Invoice_Template
2. THE Invoice_Template SHALL include OnePay branding in the header and merchant branding in the invoice body
3. THE Invoice_Template SHALL use responsive CSS that renders correctly in PDF format
4. THE Invoice_Template SHALL display payment status with visual indicators (pending, verified, failed, expired)
5. WHEN an invoice includes a merchant logo, THE Pretty_Printer SHALL embed the logo image in the HTML output

### Requirement 5: Invoice-Transaction Linking

**User Story:** As a merchant, I want invoices to be linked to payment transactions, so that I can track payment status for each invoice.

#### Acceptance Criteria

1. THE Invoice_Generator SHALL create a one-to-one relationship between Invoice_Records and Transactions
2. WHEN a transaction status changes to verified, THE Invoice_Record SHALL update its status to paid
3. WHEN a transaction expires, THE Invoice_Record SHALL update its status to expired
4. THE Invoice_Generator SHALL include the payment link URL in the generated invoice
5. THE Invoice_Generator SHALL include the QR code for payment in the PDF invoice

### Requirement 6: Invoice Retrieval and History

**User Story:** As a merchant, I want to view all my invoices in my dashboard, so that I can manage and track them easily.

#### Acceptance Criteria

1. THE Invoice_Generator SHALL provide an API endpoint that returns paginated invoice history for the authenticated merchant
2. THE Invoice_Generator SHALL return invoices sorted by creation date in descending order (newest first)
3. THE Invoice_Generator SHALL include invoice metadata: Invoice_Number, customer email, amount, status, creation date, and transaction reference
4. THE Invoice_Generator SHALL filter invoices by status when a status filter parameter is provided
5. THE Invoice_Generator SHALL limit invoice history queries to 100 records per page

### Requirement 7: Invoice Access Control

**User Story:** As a merchant, I want only authorized users to access my invoices, so that my business information remains secure.

#### Acceptance Criteria

1. WHEN an unauthenticated user requests an invoice, THE Invoice_Generator SHALL return an authentication error
2. WHEN a merchant requests an invoice, THE Invoice_Generator SHALL verify the merchant owns the associated transaction
3. IF a merchant requests an invoice they do not own, THEN THE Invoice_Generator SHALL return a not found error
4. THE Invoice_Generator SHALL rate-limit invoice generation requests to 20 requests per minute per merchant
5. THE Invoice_Generator SHALL log all invoice access attempts with merchant ID, invoice number, and timestamp

### Requirement 8: Invoice Data Validation

**User Story:** As a merchant, I want invoice data to be validated before generation, so that invoices contain accurate information.

#### Acceptance Criteria

1. WHEN creating an invoice, THE Invoice_Generator SHALL validate that the transaction amount is greater than zero
2. THE Invoice_Generator SHALL validate that customer email follows RFC 5322 email format if provided
3. THE Invoice_Generator SHALL validate that customer phone matches the pattern ^\+?[0-9\s\-\(\)]{7,20}$ if provided
4. THE Invoice_Generator SHALL sanitize all text fields to prevent HTML injection in the PDF output
5. IF validation fails, THEN THE Invoice_Generator SHALL return a descriptive error message indicating which field failed validation

### Requirement 9: Invoice Parser and Round-Trip Property

**User Story:** As a developer, I want to parse invoice data from various sources, so that I can ensure data integrity and enable invoice import functionality.

#### Acceptance Criteria

1. THE Invoice_Parser SHALL parse invoice data from JSON format into Invoice_Record objects
2. THE Invoice_Parser SHALL validate all required fields are present: Invoice_Number, merchant_id, transaction_reference, amount, currency
3. WHEN invalid invoice data is provided, THE Invoice_Parser SHALL return a descriptive error message
4. THE Pretty_Printer SHALL format Invoice_Records into JSON representation
5. FOR ALL valid Invoice_Records, parsing the JSON output then printing it SHALL produce an equivalent Invoice_Record (round-trip property)

### Requirement 10: Invoice Email Delivery

**User Story:** As a merchant, I want to automatically email invoices to customers, so that they receive professional documentation without manual effort.

#### Acceptance Criteria

1. WHERE a merchant enables automatic invoice delivery, WHEN an invoice is created, THE Invoice_Generator SHALL send the invoice PDF to the customer email address
2. THE Invoice_Generator SHALL use the existing email service to send invoice emails
3. THE Invoice_Generator SHALL include the invoice PDF as an email attachment
4. THE Invoice_Generator SHALL include the payment link URL in the email body
5. IF email delivery fails, THEN THE Invoice_Generator SHALL log the error and allow manual invoice download

### Requirement 11: Invoice Customization Settings

**User Story:** As a merchant, I want to configure invoice settings, so that invoices reflect my business branding and preferences.

#### Acceptance Criteria

1. THE Invoice_Generator SHALL allow merchants to configure business name, address, tax ID, and logo URL in their account settings
2. THE Invoice_Generator SHALL allow merchants to configure default payment terms (e.g., "Payment due upon receipt")
3. THE Invoice_Generator SHALL allow merchants to enable or disable automatic invoice email delivery
4. WHEN a merchant updates invoice settings, THE Invoice_Generator SHALL apply the new settings to future invoices only
5. THE Invoice_Generator SHALL validate logo URLs are accessible and return valid image formats (PNG, JPG, SVG)

### Requirement 12: Invoice Status Tracking

**User Story:** As a merchant, I want to see the current status of each invoice, so that I can track which invoices have been paid.

#### Acceptance Criteria

1. THE Invoice_Record SHALL maintain a status field with values: draft, sent, paid, expired, cancelled
2. WHEN an invoice is created, THE Invoice_Record SHALL set status to draft
3. WHEN an invoice email is successfully delivered, THE Invoice_Record SHALL update status to sent
4. WHEN the associated transaction is verified, THE Invoice_Record SHALL update status to paid
5. WHEN the associated transaction expires, THE Invoice_Record SHALL update status to expired
