import pytest
import re

PREFIX = "g" + "hp_"
FORBIDDEN_SECRET_PATTERNS = [
    rf"{PREFIX}[A-Za-z0-9_]{{36}}",
    r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
    r"6448299ee7fb91c63cbc82511b435594", # Exposed Telegram Hash
    r"31925523",                          # Exposed Telegram App ID
    r"Admin@123456",                      # Default Admin password
    r"reviewflow_password",               # Hardcoded DB password
]

def test_secret_scanner_detects_secrets():
    test_leak = f"API_KEY = {PREFIX}" + "A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8"
    matched = False
    for pat in FORBIDDEN_SECRET_PATTERNS:
        if re.search(pat, test_leak):
            matched = True
            break
    assert matched is True

def test_clean_source_has_no_secrets():
    clean_code = "SECRET_KEY = os.getenv('SECRET_KEY')\nTELEGRAM_API_ID = int(os.getenv('TELEGRAM_API_ID', 0))"
    matched = False
    for pat in FORBIDDEN_SECRET_PATTERNS:
        if re.search(pat, clean_code):
            matched = True
            break
    assert matched is False
