import os
from typing import List, Union
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    PROJECT_NAME: str = "ReviewFlow SaaS"
    API_V1_STR: str = "/api/v1"
    
    # JWT & Auth (Must be explicitly set in production)
    SECRET_KEY: str = os.getenv("SECRET_KEY", "" if os.getenv("ENVIRONMENT") == "production" else "dev-secret-key-reviewflow-2026-super-secure-32chars")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24 * 7))  # 7 days
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./reviewflow.db")
    
    # Telegram MTProto Credentials
    TELEGRAM_API_ID: int = int(os.getenv("TELEGRAM_API_ID", os.getenv("API_ID", "0")))
    TELEGRAM_API_HASH: str = os.getenv("TELEGRAM_API_HASH", os.getenv("API_HASH", ""))
    TELEGRAM_SESSION_PATH: str = os.getenv("SESSION_PATH", "sessions/multi_tenant_userbot")
    TELEGRAM_STRING_SESSION: str = os.getenv("TELEGRAM_STRING_SESSION", "")
    
    # Redis Queue & Caching
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Global Central Reviews Bank (Managed by SaaS Admin)
    DEFAULT_REVIEW_BANK_ID: str = os.getenv("DEFAULT_REVIEW_BANK_ID", "-1003969850866")
    DEFAULT_REVIEW_BANK_TITLE: str = "MassgesReviews Central Bank"

    # CORS Allowed Origins
    CORS_ORIGINS: List[str] = [
        origin.strip() for origin in os.getenv(
            "CORS_ORIGINS", 
            "http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:5173,http://127.0.0.1:3000"
        ).split(",") if origin.strip()
    ]

    # Rate Limiting (requests per minute)
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", 120))

    def validate_production(self):
        """Ensures that in production, required secrets are strictly provided and not defaulted."""
        if self.ENVIRONMENT == "production":
            if not self.SECRET_KEY or self.SECRET_KEY.startswith("dev-"):
                raise ValueError("CRITICAL SECURITY ERROR: SECRET_KEY must be set to a strong unique secret in production!")
            if not self.TELEGRAM_API_ID or not self.TELEGRAM_API_HASH:
                raise ValueError("CRITICAL CONFIG ERROR: TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in production!")
            if not self.TELEGRAM_STRING_SESSION and not os.path.exists(self.TELEGRAM_SESSION_PATH):
                raise ValueError("CRITICAL CONFIG ERROR: TELEGRAM_STRING_SESSION or valid session file is required in production!")

settings = Settings()
if settings.ENVIRONMENT == "production":
    settings.validate_production()
