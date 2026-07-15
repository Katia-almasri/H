"""Minimal request-local translation support."""

from contextvars import ContextVar, Token
from typing import Optional

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = frozenset({DEFAULT_LANGUAGE})

_current_language: ContextVar[str] = ContextVar(
    "current_language",
    default=DEFAULT_LANGUAGE,
)

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "api.kyc.lookups.document_types.retrieved": "Document types retrieved.",
        "api.kyc.lookups.residence_countries.retrieved": "Allowed residence countries retrieved.",
        "api.kyc.lookups.source_of_funds.retrieved": "Source of funds options retrieved.",
        "api.kyc.lookups.nationalities.retrieved": "Allowed nationalities retrieved.",
        "api.kyc.lookups.statuses.retrieved": "KYC statuses retrieved.",
        "api.kyc.lookups.tiers.retrieved": "KYC tiers retrieved.",
        "kyc.document_type.government_id_front": "Government ID (Front)",
        "kyc.document_type.government_id_back": "Government ID (Back)",
        "kyc.document_type.proof_of_address": "Proof of Address",
        "kyc.document_type.selfie": "Selfie / Liveness Photo",
        "kyc.source_of_funds.employment_income": "Employment Income",
        "kyc.source_of_funds.business_income": "Business Income",
        "kyc.source_of_funds.investments": "Investments",
        "kyc.source_of_funds.inheritance": "Inheritance",
        "kyc.source_of_funds.savings": "Savings",
        "kyc.source_of_funds.property_sale": "Property Sale",
        "kyc.source_of_funds.gift": "Gift",
        "kyc.source_of_funds.pension": "Pension",
        "kyc.source_of_funds.other": "Other",
        "kyc.status.not_submitted": "Not Submitted",
        "kyc.status.pending": "Pending",
        "kyc.status.under_review": "Under Review",
        "kyc.status.approved": "Approved",
        "kyc.status.rejected": "Rejected",
        "kyc.tier.unverified": "Unverified",
        "kyc.tier.basic": "Basic",
        "kyc.tier.full": "Full",
    }
}


def normalize_language(header_value: Optional[str]) -> str:
    """Return the best supported language for an Accept-Language header."""
    if not header_value:
        return DEFAULT_LANGUAGE

    candidates: list[tuple[float, int, str]] = []
    for index, raw_part in enumerate(header_value.split(",")):
        part = raw_part.strip()
        if not part:
            continue

        language_range, *params = part.split(";")
        language = language_range.strip().lower()
        quality = 1.0

        for param in params:
            key, separator, value = param.strip().partition("=")
            if key == "q" and separator:
                try:
                    quality = float(value)
                except ValueError:
                    quality = 0.0

        if quality <= 0:
            continue

        candidates.append((quality, index, language))

    for _, _, language in sorted(candidates, key=lambda item: (-item[0], item[1])):
        if language == "*":
            return DEFAULT_LANGUAGE

        base_language = language.split("-", 1)[0]
        if language in SUPPORTED_LANGUAGES:
            return language
        if base_language in SUPPORTED_LANGUAGES:
            return base_language

    return DEFAULT_LANGUAGE


def set_current_language(header_value: Optional[str]) -> Token[str]:
    """Set the request-local language and return a reset token."""
    return _current_language.set(normalize_language(header_value))


def reset_current_language(token: Token[str]) -> None:
    """Reset the request-local language after a request finishes."""
    _current_language.reset(token)


def get_current_language() -> str:
    """Return the active request language."""
    return _current_language.get()


def translate(
    key: str,
    *,
    language: Optional[str] = None,
    default: Optional[str] = None,
    **params: object,
) -> str:
    """Translate a key using the active request language."""
    active_language = normalize_language(language) if language else get_current_language()
    text = (
        TRANSLATIONS.get(active_language, {}).get(key)
        or TRANSLATIONS[DEFAULT_LANGUAGE].get(key)
        or default
        or key
    )

    if not params:
        return text

    try:
        return text.format(**params)
    except (KeyError, ValueError):
        return text


t = translate
