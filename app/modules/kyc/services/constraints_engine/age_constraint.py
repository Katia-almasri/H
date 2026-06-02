from datetime import date


def check_investor_eligibility(date_of_birth: date) -> bool:
    """Check if an investor is eligible based on age (must be at least 21 years old)."""
    today = date.today()
    age = today.year - date_of_birth.year - (
        (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
    )
    return age >= 21
