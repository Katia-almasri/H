import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, SQLModel


class AppBaseModel(SQLModel):
    """
    Base model for all database tables.
    Provides UUID primary key, tenant_id, and timestamps.
    """
    
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False
    )
    
    tenant_id: str = Field(
        index=True,
        nullable=False,
        description="Tenant identifier for multi-tenancy"
    )
    
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_column_kwargs={"onupdate": lambda: datetime.now(timezone.utc)}
    )
    
    class Config:
        from_attributes = True
