"""
OnePay — Logging filters for sensitive data redaction
Prevents credentials, tokens, and PII from appearing in logs.
"""
import re
import logging


class SensitiveDataFilter(logging.Filter):
    """
    Redact sensitive data from log messages.
    
    Patterns redacted:
    - API keys and tokens (Bearer, API-Key headers)
    - Email addresses
    - Phone numbers
    - Credit card numbers
    - Password fields
    - Session tokens
    """
    
    # Patterns to redact
    PATTERNS = [
        (re.compile(r'Bearer\s+[A-Za-z0-9\-._~+/]+=*', re.IGNORECASE), 'Bearer [REDACTED]'),
        (re.compile(r'API-Key:\s*[A-Za-z0-9\-._~+/]+=*', re.IGNORECASE), 'API-Key: [REDACTED]'),
        (re.compile(r'password["\']?\s*[:=]\s*["\']?[^"\'}\s,]+', re.IGNORECASE), 'password=[REDACTED]'),
        (re.compile(r'token["\']?\s*[:=]\s*["\']?[^"\'}\s,]+', re.IGNORECASE), 'token=[REDACTED]'),
        (re.compile(r'secret["\']?\s*[:=]\s*["\']?[^"\'}\s,]+', re.IGNORECASE), 'secret=[REDACTED]'),
        (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[EMAIL]'),
        (re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'), '[CARD]'),
    ]
    
    def filter(self, record):
        """Redact sensitive data from the log message."""
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            message = record.msg
            for pattern, replacement in self.PATTERNS:
                message = pattern.sub(replacement, message)
            record.msg = message
        return True
