"""KYC lookup services — nationalities, residence countries, source of funds, document types."""

from app.modules.kyc.enums.document_type import DocumentType
from app.modules.kyc.enums.restricted_nationality import RestrictedNationality
from app.modules.kyc.enums.allowed_residence_country import AllowedResidenceCountry
from app.modules.kyc.enums.source_of_funds import SourceOfFunds
from app.modules.kyc.enums.kyc_status import KYCStatus
from app.modules.kyc.enums.kyc_tier import KYCTier
from packages.core.i18n import t

# ── ISO 3166-1 alpha-2 full country list ──────────────────────────────────────
# Static map: code → country name. Used to derive allowed nationalities.
COUNTRY_MAP: dict[str, str] = {
    "AF": "Afghanistan",
    "AL": "Albania",
    "DZ": "Algeria",
    "AS": "American Samoa",
    "AD": "Andorra",
    "AO": "Angola",
    "AG": "Antigua and Barbuda",
    "AR": "Argentina",
    "AM": "Armenia",
    "AU": "Australia",
    "AT": "Austria",
    "AZ": "Azerbaijan",
    "BS": "Bahamas",
    "BH": "Bahrain",
    "BD": "Bangladesh",
    "BB": "Barbados",
    "BY": "Belarus",
    "BE": "Belgium",
    "BZ": "Belize",
    "BJ": "Benin",
    "BT": "Bhutan",
    "BO": "Bolivia",
    "BA": "Bosnia and Herzegovina",
    "BW": "Botswana",
    "BR": "Brazil",
    "BN": "Brunei",
    "BG": "Bulgaria",
    "BF": "Burkina Faso",
    "BI": "Burundi",
    "CV": "Cabo Verde",
    "KH": "Cambodia",
    "CM": "Cameroon",
    "CA": "Canada",
    "CF": "Central African Republic",
    "TD": "Chad",
    "CL": "Chile",
    "CN": "China",
    "CO": "Colombia",
    "KM": "Comoros",
    "CG": "Congo",
    "CD": "Congo (DRC)",
    "CR": "Costa Rica",
    "CI": "Côte d'Ivoire",
    "HR": "Croatia",
    "CU": "Cuba",
    "CY": "Cyprus",
    "CZ": "Czech Republic",
    "DK": "Denmark",
    "DJ": "Djibouti",
    "DM": "Dominica",
    "DO": "Dominican Republic",
    "EC": "Ecuador",
    "EG": "Egypt",
    "SV": "El Salvador",
    "GQ": "Equatorial Guinea",
    "ER": "Eritrea",
    "EE": "Estonia",
    "SZ": "Eswatini",
    "ET": "Ethiopia",
    "FJ": "Fiji",
    "FI": "Finland",
    "FR": "France",
    "GA": "Gabon",
    "GM": "Gambia",
    "GE": "Georgia",
    "DE": "Germany",
    "GH": "Ghana",
    "GR": "Greece",
    "GD": "Grenada",
    "GT": "Guatemala",
    "GN": "Guinea",
    "GW": "Guinea-Bissau",
    "GY": "Guyana",
    "HT": "Haiti",
    "HN": "Honduras",
    "HU": "Hungary",
    "IS": "Iceland",
    "IN": "India",
    "ID": "Indonesia",
    "IR": "Iran",
    "IQ": "Iraq",
    "IE": "Ireland",
    "IL": "Israel",
    "IT": "Italy",
    "JM": "Jamaica",
    "JP": "Japan",
    "JO": "Jordan",
    "KZ": "Kazakhstan",
    "KE": "Kenya",
    "KI": "Kiribati",
    "KP": "North Korea",
    "KR": "South Korea",
    "KW": "Kuwait",
    "KG": "Kyrgyzstan",
    "LA": "Laos",
    "LV": "Latvia",
    "LB": "Lebanon",
    "LS": "Lesotho",
    "LR": "Liberia",
    "LY": "Libya",
    "LI": "Liechtenstein",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "MG": "Madagascar",
    "MW": "Malawi",
    "MY": "Malaysia",
    "MV": "Maldives",
    "ML": "Mali",
    "MT": "Malta",
    "MH": "Marshall Islands",
    "MR": "Mauritania",
    "MU": "Mauritius",
    "MX": "Mexico",
    "FM": "Micronesia",
    "MD": "Moldova",
    "MC": "Monaco",
    "MN": "Mongolia",
    "ME": "Montenegro",
    "MA": "Morocco",
    "MZ": "Mozambique",
    "MM": "Myanmar",
    "NA": "Namibia",
    "NR": "Nauru",
    "NP": "Nepal",
    "NL": "Netherlands",
    "NZ": "New Zealand",
    "NI": "Nicaragua",
    "NE": "Niger",
    "NG": "Nigeria",
    "MK": "North Macedonia",
    "NO": "Norway",
    "OM": "Oman",
    "PK": "Pakistan",
    "PW": "Palau",
    "PA": "Panama",
    "PG": "Papua New Guinea",
    "PY": "Paraguay",
    "PE": "Peru",
    "PH": "Philippines",
    "PL": "Poland",
    "PT": "Portugal",
    "QA": "Qatar",
    "RO": "Romania",
    "RU": "Russia",
    "RW": "Rwanda",
    "KN": "Saint Kitts and Nevis",
    "LC": "Saint Lucia",
    "VC": "Saint Vincent and the Grenadines",
    "WS": "Samoa",
    "SM": "San Marino",
    "ST": "São Tomé and Príncipe",
    "SA": "Saudi Arabia",
    "SN": "Senegal",
    "RS": "Serbia",
    "SC": "Seychelles",
    "SL": "Sierra Leone",
    "SG": "Singapore",
    "SK": "Slovakia",
    "SI": "Slovenia",
    "SB": "Solomon Islands",
    "SO": "Somalia",
    "ZA": "South Africa",
    "SS": "South Sudan",
    "ES": "Spain",
    "LK": "Sri Lanka",
    "SD": "Sudan",
    "SR": "Suriname",
    "SE": "Sweden",
    "CH": "Switzerland",
    "SY": "Syria",
    "TW": "Taiwan",
    "TJ": "Tajikistan",
    "TZ": "Tanzania",
    "TH": "Thailand",
    "TL": "Timor-Leste",
    "TG": "Togo",
    "TO": "Tonga",
    "TT": "Trinidad and Tobago",
    "TN": "Tunisia",
    "TR": "Turkey",
    "TM": "Turkmenistan",
    "TV": "Tuvalu",
    "UG": "Uganda",
    "UA": "Ukraine",
    "AE": "United Arab Emirates",
    "GB": "United Kingdom",
    "US": "United States",
    "UY": "Uruguay",
    "UZ": "Uzbekistan",
    "VU": "Vanuatu",
    "VE": "Venezuela",
    "VN": "Vietnam",
    "YE": "Yemen",
    "ZM": "Zambia",
    "ZW": "Zimbabwe",
}

# Set of restricted nationality codes for fast O(1) lookup
_RESTRICTED_CODES: frozenset[str] = frozenset(r.value for r in RestrictedNationality)


# ── Lookup functions ──────────────────────────────────────────────────────────

def _humanize_enum_value(value: str) -> str:
    return value.replace("_", " ").title()


def _enum_lookup(enum_class, translation_prefix: str) -> list[dict[str, str]]:
    return [
        {
            "value": item.value,
            "label": t(
                f"{translation_prefix}.{item.value}",
                default=_humanize_enum_value(item.value),
            ),
        }
        for item in enum_class
    ]


def get_document_types() -> list[dict[str, str]]:
    """Return all supported KYC document types.

    Returns a list of ``{"value": <enum value>, "label": <human-readable label>}``
    dicts suitable for driving a dropdown in the client.
    """
    return _enum_lookup(DocumentType, "kyc.document_type")


def get_allowed_residence_countries() -> list[dict[str, str]]:
    """Return allowed residence countries with their ISO code and full name.

    Returns a list of ``{"code": <ISO alpha-2>, "name": <country name>}`` dicts,
    derived from ``AllowedResidenceCountry`` enum values cross-referenced against
    the full ``COUNTRY_MAP``.
    """
    return [
        {
            "code": country.value,
            "name": t(
                f"country.{country.value}",
                default=COUNTRY_MAP.get(country.value, country.value),
            ),
        }
        for country in AllowedResidenceCountry
    ]


def get_source_of_funds() -> list[dict[str, str]]:
    """Return all accepted source-of-funds options.

    Returns a list of ``{"value": <enum value>, "label": <human-readable label>}``
    dicts suitable for driving a dropdown in the client.
    """
    return _enum_lookup(SourceOfFunds, "kyc.source_of_funds")


def get_allowed_nationalities() -> list[dict[str, str]]:
    """Return nationalities that are not restricted (i.e. eligible to invest).

    Derives the list by filtering ``COUNTRY_MAP`` to exclude all codes present
    in ``RestrictedNationality``.  Returns ``{"code": ..., "name": ...}`` dicts.
    """
    return [
        {"code": code, "name": t(f"country.{code}", default=name)}
        for code, name in COUNTRY_MAP.items()
        if code not in _RESTRICTED_CODES
    ]


def get_kyc_status() -> list[dict[str, str]]:
    """Return all available KYC submission statuses."""
    return _enum_lookup(KYCStatus, "kyc.status")


def get_kyc_tiers() -> list[dict[str, str]]:
    """Return all available KYC verification tiers."""
    return _enum_lookup(KYCTier, "kyc.tier")
