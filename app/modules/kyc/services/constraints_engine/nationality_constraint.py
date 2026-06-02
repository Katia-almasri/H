"""Nationality eligibility constraint."""

from typing import Tuple

from app.modules.kyc.enums.restricted_nationality import RestrictedNationality


def get_restricted_nationalities() -> list[str]:
    """Return list of restricted nationality codes."""
    return [n.value for n in RestrictedNationality]


def check_nationality(nationality_code: str) -> Tuple[bool, str]:
    """
    Check if the investor's nationality is allowed.

    Args:
        nationality_code: ISO 3166-1 alpha-2 country code (e.g., "AE", "US").

    Returns:
        Tuple of (is_allowed, message).
    """
    code_upper = nationality_code.upper().strip()
    restricted = get_restricted_nationalities()

    if code_upper in restricted:
        return False, (
            f"Nationality '{code_upper}' is restricted due to sanctions or regulatory requirements. "
            f"Investment is not permitted for nationals of sanctioned countries."
        )

    # Basic format validation
    if len(code_upper) < 2 or len(code_upper) > 5:
        return False, "Invalid nationality code format. Use ISO 3166-1 alpha-2 (e.g., 'AE', 'US')."

    return True, f"Nationality {code_upper} is eligible."
