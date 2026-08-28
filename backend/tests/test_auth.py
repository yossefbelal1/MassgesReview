import pytest

def test_user_registration_success(client):
    payload = {
        "email": "newuser@example.com",
        "password": "SecurePassword123!",
        "full_name": "New SaaS User",
        "company_name": "Forex Trading Pro"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "newuser@example.com"

def test_duplicate_registration_rejected(client):
    payload = {
        "email": "dup@example.com",
        "password": "SecurePassword123!",
        "full_name": "Duplicate User",
        "company_name": "Forex Dup"
    }
    res1 = client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 200
    
    res2 = client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 400
    assert "already registered" in res2.json()["detail"].lower()

def test_login_success(client, tenant_a):
    response = client.post("/api/v1/auth/login", data={
        "username": "tenant_a@example.com",
        "password": "AlphaPassword123!"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "tenant_a@example.com"

def test_login_invalid_password_rejected(client, tenant_a):
    response = client.post("/api/v1/auth/login", data={
        "username": "tenant_a@example.com",
        "password": "WrongPassword123!"
    })
    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"].lower()

def test_unauthenticated_request_rejected(client):
    response = client.get("/api/v1/channels/")
    assert response.status_code == 401
