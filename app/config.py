from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    app_name: str = "Harvest"
    debug: bool = True
    database_url: str
    redis_url: str
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"]
    frontend_base_url: str = "http://localhost:3000"
    
    class Config:
        env_file = ".env"

settings = Settings()
