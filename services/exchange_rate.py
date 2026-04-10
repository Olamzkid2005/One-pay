"""
Exchange Rate Service

Handles fetching and caching exchange rates for multi-currency support.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal

import requests

from config import Config
from database import get_db
from models.exchange_rate import ExchangeRate

logger = logging.getLogger(__name__)


def fetch_exchange_rate_from_api(from_currency: str, to_currency: str) -> Decimal:
    """
    Fetch exchange rate from external API.

    Uses a mock implementation for demonstration.
    In production, integrate with
    a real exchange rate API like Fixer.io, Open Exchange Rates, or Central Bank API.

    Args:
        from_currency: Source currency code (e.g., 'USD')
        to_currency: Target currency code (e.g., 'NGN')

    Returns:
        Exchange rate as Decimal

    Raises:
        ValueError: If unable to fetch rate
    """
    # Mock exchange rates for demonstration
    # In production, replace with actual API call
    mock_rates = {
        ("USD", "NGN"): Decimal("1550.50"),
        ("EUR", "NGN"): Decimal("1680.75"),
        ("NGN", "USD"): Decimal("0.000645"),
        ("NGN", "EUR"): Decimal("0.000595"),
        ("USD", "EUR"): Decimal("0.92"),
        ("EUR", "USD"): Decimal("1.09"),
    }

    key = (from_currency.upper(), to_currency.upper())

    if key in mock_rates:
        logger.info(f"Using mock exchange rate | {from_currency}->{to_currency}={mock_rates[key]}")
        return mock_rates[key]

    # If no mock rate, try to reverse
    reverse_key = (to_currency.upper(), from_currency.upper())
    if reverse_key in mock_rates:
        rate = Decimal("1") / mock_rates[reverse_key]
        logger.info(f"Calculated reverse exchange rate | {from_currency}->{to_currency}={rate}")
        return rate

    # Default to 1.0 if same currency
    if from_currency.upper() == to_currency.upper():
        return Decimal("1")

    raise ValueError(f"No exchange rate available for {from_currency} to {to_currency}")


def get_exchange_rate(from_currency: str, to_currency: str) -> Decimal:
    """
    Get exchange rate between currencies with caching.

    Args:
        from_currency: Source currency code (e.g., 'USD')
        to_currency: Target currency code (e.g., 'NGN')

    Returns:
        Exchange rate as Decimal
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    # Same currency
    if from_currency == to_currency:
        return Decimal("1")

    with get_db() as db:
        rate = db.query(ExchangeRate).filter(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency
        ).first()

        if not rate:
            # Fetch from external API and cache
            try:
                new_rate = fetch_exchange_rate_from_api(from_currency, to_currency)
                exchange_rate = ExchangeRate(
                    from_currency=from_currency,
                    to_currency=to_currency,
                    rate=new_rate
                )
                db.add(exchange_rate)
                db.commit()
                logger.info(f"Cached new exchange rate | {from_currency}->{to_currency}={new_rate}")
                return new_rate
            except ValueError as e:
                logger.error(f"Failed to fetch exchange rate | {from_currency}->{to_currency} | error={e}")
                raise

        # Update if stale (older than cache TTL)
        ttl_seconds = Config.EXCHANGE_RATE_CACHE_TTL
        if rate.updated_at:
            age_seconds = (datetime.now(timezone.utc) - rate.updated_at).total_seconds()
            if age_seconds > ttl_seconds:
                try:
                    new_rate = fetch_exchange_rate_from_api(from_currency, to_currency)
                    rate.rate = new_rate
                    rate.updated_at = datetime.now(timezone.utc)
                    db.commit()
                    logger.info(f"Updated stale exchange rate | {from_currency}->{to_currency}={new_rate}")
                except ValueError as e:
                    logger.warning(f"Failed to update stale exchange rate, using cached | {from_currency}->{to_currency} | error={e}")

        return rate.rate


def convert_currency(amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
    """
    Convert amount from one currency to another.

    Args:
        amount: Amount to convert
        from_currency: Source currency code
        to_currency: Target currency code

    Returns:
        Converted amount as Decimal
    """
    if from_currency == to_currency:
        return amount

    rate = get_exchange_rate(from_currency, to_currency)
    return (amount * rate).quantize(Decimal("0.01"))


def get_supported_currencies() -> list[str]:
    """Get list of supported currency codes."""
    return Config.SUPPORTED_CURRENCIES


def get_currency_symbol(currency: str) -> str:
    """
    Get currency symbol for a currency code.

    Args:
        currency: Currency code (e.g., 'NGN', 'USD', 'EUR')

    Returns:
        Currency symbol (e.g., '₦', '$', '€')
    """
    return Config.CURRENCY_SYMBOLS.get(currency.upper(), currency)
