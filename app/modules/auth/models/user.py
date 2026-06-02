"""User model for authentication."""

from sqlalchemy import Column, String, Boolean, DateTime
from datetime import datetime

from app.database import Base
from app.modules.auth.enums import UserRole, AccountStatus


class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = "users"

    id = Column(String, primary_key=True)  # UUID
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    
    # Profile
    full_name = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    
    # Status — stored as plain strings matching enum .value
    role = Column(String, default=UserRole.INVESTOR.value, nullable=False)
    account_status = Column(String, default=AccountStatus.NEEDS_EMAIL_VERIFICATION.value, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_email_verified = Column(Boolean, default=False, nullable=False)
    
    # Security
    failed_login_attempts = Column(String, default="0", nullable=False)
    locked_until = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
