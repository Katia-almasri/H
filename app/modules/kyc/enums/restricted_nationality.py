"""Restricted nationalities — sanctioned or high-risk countries."""

import enum


class RestrictedNationality(str, enum.Enum):
    """Nationalities restricted from investing due to sanctions or regulatory requirements."""
    NORTH_KOREA = "KP"
    IRAN = "IR"
    SYRIA = "SY"
    CUBA = "CU"
    CRIMEA = "UA-43"  # Crimea region
    MYANMAR = "MM"
    SUDAN = "SD"
    SOUTH_SUDAN = "SS"
