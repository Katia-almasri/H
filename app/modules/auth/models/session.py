"""User session model for refresh token management."""

from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
from datetime import datetime

from app.database import Base


class UserSession(Base):
    """User session for refresh token tracking."""
    __tablename__ = "user_sessions"

    id = Column(String, primary_key=True)  # UUID
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Token
    refresh_token_hash = Column(String, nullable=False)
    
    # Device info
    device_fingerprint = Column(String, nullable=True, index=True)  # SHA-256 hash
    device_name = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    last_used_at = Column(DateTime, default=datetime.utcnow, nullable=False)
