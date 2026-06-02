"""Admin profile model — linked to User table."""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from datetime import datetime

from app.database import Base


class Admin(Base):
    """Admin-specific profile. One-to-one with User."""
    __tablename__ = "admins"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    # Admin metadata
    department = Column(String, nullable=True)
    position = Column(String, nullable=True)

    # RBAC — nullable for future use (FK will be added when roles table exists)
    role_id = Column(String, nullable=True)
    permissions_override = Column(String, nullable=True)  # JSON string of extra permissions

    # Status
    is_super_admin = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
