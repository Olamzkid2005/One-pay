"""
OnePay — PDF Receipt Generation Service
Generates PDF receipts for transactions using xhtml2pdf (pure Python, Windows compatible).
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from decimal import Decimal

from xhtml2pdf import pisa
from io import BytesIO

logger = logging.getLogger(__name__)


def generate_receipt_html(transaction) -> str:
    """
    Generate HTML receipt for a transaction.
    
    Args:
        transaction: Transaction object
        
    Returns:
        HTML string for receipt
    """
    from flask import render_template
    
    try:
        html = render_template(
            'receipt.html',
            tx=transaction,
            current_date=datetime.now(timezone.utc)
        )
        return html
    except Exception as e:
        logger.error(f"Failed to generate receipt HTML: {e}")
        raise


def generate_receipt_pdf(transaction) -> bytes:
    """
    Generate PDF receipt from transaction using xhtml2pdf (pure Python, Windows compatible).
    
    Args:
        transaction: Transaction object
        
    Returns:
        PDF binary data
        
    Raises:
        Exception: If PDF generation fails
    """
    try:
        # Generate HTML content
        html_content = generate_receipt_html(transaction)
        
        # Create PDF buffer
        pdf_buffer = BytesIO()
        
        # Generate PDF from HTML
        pisa_status = pisa.CreatePDF(
            html_content,
            dest=pdf_buffer,
            encoding='utf-8'
        )
        
        # Check for errors
        if pisa_status.err:
            raise Exception(f"PDF generation error: {pisa_status.err} errors occurred")
        
        # Get PDF bytes
        pdf_bytes = pdf_buffer.getvalue()
        pdf_buffer.close()
        
        logger.info(
            "Receipt PDF generated successfully | tx_ref=%s size=%.2fKB",
            transaction.tx_ref, len(pdf_bytes) / 1024
        )
        
        return pdf_bytes
        
    except Exception as e:
        logger.error(
            "Receipt PDF generation failed | tx_ref=%s error=%s",
            transaction.tx_ref, e
        )
        raise
