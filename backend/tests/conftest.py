import os
import sys
import pytest
import httpx
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup test environment
os.environ["ENVIRONMENT"] = "testing"
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest-execution-only-32chars"
os.environ["DATABASE_URL"] = "sqlite:///./test_reviewflow.db"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.main import app
from backend.app.core.database import Base, get_db
from backend.app.core.security import get_password_hash, create_access_token
from backend.app.models.models import User, Tenant, Plan, Subscription, Channel, Automation

TEST_DATABASE_URL = "sqlite:///./test_reviewflow.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = TestingSessionLocal()
    # Seed Starter and Pro Plans
    starter_plan = Plan(name="Starter", slug="starter", price_monthly=20.0, max_channels=1, max_automations=5, max_messages=100)
    pro_plan = Plan(name="Pro", slug="pro", price_monthly=49.0, max_channels=5, max_automations=20, max_messages=500)
    db.add_all([starter_plan, pro_plan])
    db.commit()
    db.close()
    
    yield
    
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test_reviewflow.db"):
        try:
            os.remove("./test_reviewflow.db")
        except Exception:
            pass

@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

class SyncASGIClient:
    def __init__(self, app, base_url="http://testserver"):
        self.app = app
        self.base_url = base_url
        self.transport = httpx.ASGITransport(app=app)

    def request(self, method, url, **kwargs):
        import asyncio
        async def _run():
            async with httpx.AsyncClient(transport=self.transport, base_url=self.base_url) as ac:
                return await ac.request(method, url, **kwargs)
        return asyncio.run(_run())

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self.request("PUT", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)

    def patch(self, url, **kwargs):
        return self.request("PATCH", url, **kwargs)

@pytest.fixture
def client(db) -> Generator:
    def override_get_db():
        try:
            yield db
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    yield SyncASGIClient(app)
    app.dependency_overrides.clear()

@pytest.fixture
def tenant_a(db):
    tenant = Tenant(name="Tenant Alpha", slug="tenant-alpha")
    db.add(tenant)
    db.flush()
    
    user = User(
        tenant_id=tenant.id,
        email="tenant_a@example.com",
        full_name="User Alpha",
        hashed_password=get_password_hash("AlphaPassword123!"),
        role="customer"
    )
    db.add(user)
    db.flush()
    
    starter_plan = db.query(Plan).filter(Plan.slug == "starter").first()
    from datetime import datetime, timedelta, timezone
    sub = Subscription(
        tenant_id=tenant.id,
        plan_id=starter_plan.id,
        status="active",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30)
    )
    db.add(sub)
    db.commit()
    
    token = create_access_token(user.id)
    return {"tenant": tenant, "user": user, "token": token}

@pytest.fixture
def tenant_b(db):
    tenant = Tenant(name="Tenant Beta", slug="tenant-beta")
    db.add(tenant)
    db.flush()
    
    user = User(
        tenant_id=tenant.id,
        email="tenant_b@example.com",
        full_name="User Beta",
        hashed_password=get_password_hash("BetaPassword123!"),
        role="customer"
    )
    db.add(user)
    db.flush()
    
    pro_plan = db.query(Plan).filter(Plan.slug == "pro").first()
    from datetime import datetime, timedelta, timezone
    sub = Subscription(
        tenant_id=tenant.id,
        plan_id=pro_plan.id,
        status="active",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30)
    )
    db.add(sub)
    db.commit()
    
    token = create_access_token(user.id)
    return {"tenant": tenant, "user": user, "token": token}

@pytest.fixture
def admin_user(db):
    tenant = Tenant(name="System Admin", slug="sys-admin")
    db.add(tenant)
    db.flush()
    
    admin = User(
        tenant_id=tenant.id,
        email="admin@example.com",
        full_name="Super Admin",
        hashed_password=get_password_hash("SuperAdmin123!"),
        role="admin"
    )
    db.add(admin)
    db.commit()
    
    token = create_access_token(admin.id)
    return {"user": admin, "token": token}
