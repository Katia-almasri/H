"""KYC document response schema."""

from datetime import datetime
from pydantic import BaseModel


class KYCDocumentResponse(BaseModel):
    id: str
    submission_id: str
    document_type: str
    file_name: str
    file_size: int
    content_type: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}
