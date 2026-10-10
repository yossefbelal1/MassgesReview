from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Any
import jwt
import bcrypt
from backend.app.core.config import settings

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        clean = plain_password.strip()
        # 1. Exact match
        if bcrypt.checkpw(clean.encode("utf-8")[:72], hashed_password.encode("utf-8")):
            return True
        # 2. Case-insensitive fallbacks for mobile auto-capitalization (e.g. Arabict123 vs arabict123)
        if bcrypt.checkpw(clean.lower().encode("utf-8")[:72], hashed_password.encode("utf-8")):
            return True
        if bcrypt.checkpw(clean.capitalize().encode("utf-8")[:72], hashed_password.encode("utf-8")):
            return True
        return False
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8")[:72], salt)
    return hashed.decode("utf-8")

def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

