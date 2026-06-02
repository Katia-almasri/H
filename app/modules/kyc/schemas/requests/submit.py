"""KYC submit request schema."""

from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class KYCSubmitRequest(BaseModel):
    full_legal_name: str = Field(..., min_length=2, max_length=200)
    date_of_birth: date
    nationality: str = Field(..., min_length=2, max_length=100)
    country_of_residence: str = Field(..., min_length=2, max_length=100)
    residential_address: str = Field(..., min_length=5, max_length=500)
    source_of_funds: str = Field(..., description="Value from SourceOfFunds enum")
    source_of_funds_details: Optional[str] = Field(None, max_length=1000)
    is_pep: bool = Field(default=False, description="Politically Exposed Person self-declaration")
