"""Residence country eligibility constraint."""

from typing import Tuple

from app.modules.kyc.enums.allowed_residence_country import AllowedResidenceCountry


def get_allowed_countries() -> list[str]:
    """Return list of allowed country codes."""
    return [c.value for c in AllowedResidenceCountry]


def get_allowed_countries_names() -> dict[str, str]:
    """Return mapping of country code to country name."""
    return {c.value: c.name.replace("_", " ").title() for c in AllowedResidenceCountry}


def check_residence_country(country_code: str) -> Tuple[bool, str]:
    """
    Check if the investor's country of residence is allowed.

    Args:
        country_code: ISO 3166-1 alpha-2 country code (e.g., "AE", "US").

    Returns:
        Tuple of (is_allowed, message).
    """
    allowed = get_allowed_countries()
    code_upper = country_code.upper().strip()

    if code_upper in allowed:
        return True, f"Country {code_upper} is eligible for investment."

    return False, (
        f"Country '{code_upper}' is not eligible. "
        f"Allowed countries: {', '.join(allowed)}"
    )


def validate_residential_address(address: str, country_code: str) -> Tuple[bool, str]:
    """
    Validate residential address details.

    Constraints:
    - Address must be at least 10 characters.
    - Address must not exceed 500 characters.
    - Country must be in the allowed list.
    - Address must contain at least a street indicator (number or common keywords).

    Args:
        address: Full residential address string.
        country_code: ISO 3166-1 alpha-2 country code.

    Returns:
        Tuple of (is_valid, message).
    """
    # Length checks
    if len(address.strip()) < 10:
        return False, "Address is too short. Minimum 10 characters required."

    if len(address.strip()) > 500:
        return False, "Address is too long. Maximum 500 characters allowed."

    # Country eligibility
    is_allowed, country_msg = check_residence_country(country_code)
    if not is_allowed:
        return False, country_msg

    # Basic structure check — must contain at least one digit (building/flat number)
    if not any(char.isdigit() for char in address):
        return False, "Address must include a building or flat number."

    return True, "Address is valid."
