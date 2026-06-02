"""Currency helper — enums and conversion utilities."""

import enum
from decimal import Decimal


class Currency(str, enum.Enum):
    """Supported currencies."""
    AED = "AED"
    USD = "USD"


# Fixed exchange rates (update from external source in production)
_RATES_TO_AED: dict[Currency, Decimal] = {
    Currency.AED: Decimal("1.0"),
    Currency.USD: Decimal("3.6725"),  # 1 USD = 3.6725 AED (pegged)
}


def convert(amount: Decimal, from_currency: Currency, to_currency: Currency) -> Decimal:
    """
    Convert amount between supported currencies.

    Args:
        amount: The amount to convert.
        from_currency: Source currency.
        to_currency: Target currency.

    Returns:
        Converted amount rounded to 2 decimal places.
    """
    if from_currency == to_currency:
        return amount

    # Convert to AED first, then to target
    amount_in_aed = amount * _RATES_TO_AED[from_currency]

    if to_currency == Currency.AED:
        return amount_in_aed.quantize(Decimal("0.01"))

    result = amount_in_aed / _RATES_TO_AED[to_currency]
    return result.quantize(Decimal("0.01"))


def get_investment_limit(tier_value: str, currency: Currency = Currency.AED) -> Decimal | None:
    """
    Get investment limit per property for a given KYC tier.

    Returns:
        Limit in the requested currency, or None for unlimited.
    """
    from app.modules.kyc.enums import KYCTier

    if tier_value == KYCTier.UNVERIFIED.value:
        return Decimal("0")
    elif tier_value == KYCTier.BASIC.value:
        limit_aed = Decimal("10000")
        return convert(limit_aed, Currency.AED, currency)
    elif tier_value == KYCTier.FULL.value:
        return None  # Unlimited
    return Decimal("0")
