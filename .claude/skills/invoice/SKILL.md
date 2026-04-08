# Invoice Generation Skill

Generate and manage invoices for the OnePay platform.

## When to Use
- User wants to test invoice generation
- User reports invoice PDF issues
- User wants to customize invoice format

## How to Invoices Work
1. Invoice created when payment verified (auto) or manually
2. Invoice number format: `INV-{year}{month}{sequence}`
3. PDF generated via `services/pdf_receipt.py` using xhtml2pdf
4. Can email invoice via `services/email.py`
5. Invoice statuses: DRAFT → SENT → PAID → EXPIRED/CANCELLED

## Test Invoice Generation
```bash
# Run invoice tests
pytest tests/ -k invoice -v

# Generate test PDF manually
python -c "
from services.pdf_receipt import generate_receipt_pdf
from models.invoice import Invoice
# Create test invoice and generate PDF
"
```

## Key Files
- `models/invoice.py` - Invoice model and status
- `services/pdf_receipt.py` - PDF generation
- `services/invoice.py` - Invoice business logic
- `blueprints/invoices.py` - Invoice routes

## Invoice Number Format
```
INV-20260407001  (INV-{YYYY}{MM}{sequence})
```

## Template Location
Templates stored in `templates/invoices/`
