import pytest
from backend.app.core.config import settings

def test_security_headers_present(client):
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert "strict-origin" in response.headers.get("referrer-policy", "").lower()

def test_production_config_validation_fails_on_missing_secrets():
    original_env = settings.ENVIRONMENT
    original_sec = settings.SECRET_KEY
    try:
        settings.ENVIRONMENT = "production"
        settings.SECRET_KEY = "dev-secret-key-reviewflow-2026-super-secure-32chars"
        # Must fail fast when insecure default secret is used in production
        with pytest.raises(ValueError, match="SECRET_KEY"):
            settings.validate_production()
    finally:
        settings.ENVIRONMENT = original_env
        settings.SECRET_KEY = original_sec
