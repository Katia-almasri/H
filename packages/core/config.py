from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "Harvest"
    DEBUG: bool = False
    API_VERSION: str = "v1"
    
    # Database
    DATABASE_URL: str
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40
    
    # Redis
    REDIS_URL: str
    
    # JWT
    JWT_ALGORITHM: str = "RS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    JWT_PRIVATE_KEY: str = ""
    JWT_PUBLIC_KEY: str = ""
    
    # Password hashing (Argon2id)
    ARGON2_TIME_COST: int = 2
    ARGON2_MEMORY_COST: int = 65536  # 64MB
    ARGON2_PARALLELISM: int = 2
    
    # Security
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    COOKIE_SECURE: bool = True
    COOKIE_HTTPONLY: bool = True
    COOKIE_SAMESITE: str = "strict"
    
    # Rate limiting
    LOGIN_RATE_LIMIT: str = "10/minute"
    LOGIN_LOCKOUT_THRESHOLD: int = 5
    LOGIN_LOCKOUT_DURATION_MINUTES: int = 30
    
    # Email (AWS SES)
    AWS_REGION: str = "me-south-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    SES_FROM_EMAIL: str = "noreply@shard.ae"
    
    # Multi-tenancy
    DEFAULT_TENANT_ID: str = "harvest-uae"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
