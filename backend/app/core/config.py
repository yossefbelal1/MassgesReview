import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    PROJECT_NAME: str = "ReviewFlow SaaS"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "reviewflow-super-secret-jwt-key-2026-secure")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./reviewflow.db")
    
    # Telegram
    TELEGRAM_API_ID: int = int(os.getenv("API_ID", 31925523))
    TELEGRAM_API_HASH: str = os.getenv("API_HASH", "6448299ee7fb91c63cbc82511b435594")
    TELEGRAM_SESSION_PATH: str = os.getenv("SESSION_PATH", "sessions/multi_tenant_userbot")
    TELEGRAM_STRING_SESSION: str = os.getenv(
        "TELEGRAM_STRING_SESSION", 
        "1BJWap1sBuypZntEY2gXJ8hZJ_zjFLJk7aNKxe9fGNB4bxM21iHnh9iNz5SaChPEr58S5SnQGd9vVwbJAN2-zmMfDPoKGoWy9RLI1MIl5_yCB3pfC747Qo4SYdR3sNPnry2errpIN9Jqv0W4oGHd0Q5g9z54AtdNsG2fYH0U2fvNzF9VrDm32L5FhbuL9aREY92gA8wFmXE-4jYR1KA3bMg2Byoylvreu7gGoKv1xDU7par5kKvb8-KT3RbryACir2R2MxpHZrQ_4CBMbBF4UL0pE0H26jIRn4QqFbWFXAXYRep0lBQ_575T2YgRSrOuUL0MWvButjTZxr2W88l5arf8jcFF3Kkk="
    )
    
    # Redis Queue
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Global Central Reviews Bank (Managed by SaaS Owner)
    DEFAULT_REVIEW_BANK_ID: str = os.getenv("DEFAULT_REVIEW_BANK_ID", "-1003969850866")
    DEFAULT_REVIEW_BANK_TITLE: str = "MassgesReviews Central Bank"

settings = Settings()
