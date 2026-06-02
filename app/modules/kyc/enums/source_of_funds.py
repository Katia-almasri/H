"""Source of funds enumeration."""

import enum


class SourceOfFunds(str, enum.Enum):
    EMPLOYMENT_INCOME = "employment_income"
    BUSINESS_INCOME = "business_income"
    INVESTMENTS = "investments"
    INHERITANCE = "inheritance"
    SAVINGS = "savings"
    PROPERTY_SALE = "property_sale"
    GIFT = "gift"
    PENSION = "pension"
    OTHER = "other"
