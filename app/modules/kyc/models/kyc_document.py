"""KYC document model."""

from sqlalchemy import Column, String, Integer, DateTime
from datetime import datetime

from app.database import Base


class KYCDocument(Base):
    """Uploaded KYC document metadata."""
    __tablename__ = "kyc_documents"

    id = Column(String, primary_key=True)
    submission_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)

    # File info
    document_type = Column(String, nullable=False)  # DocumentType enum value
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)  # Local storage path
    file_size = Column(Integer, nullable=False)  # Bytes
    content_type = Column(String, nullable=False)  # MIME type

    # Timestamps
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
