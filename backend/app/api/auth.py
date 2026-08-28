from datetime import datetime, timedelta, timezone
import re
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import verify_password, get_password_hash, create_access_token
from backend.app.models.models import User, Tenant, Plan, Subscription, AuditLog
from backend.app.schemas.schemas import UserCreate, UserLogin, Token, UserOut
from backend.app.api.deps import get_current_user

router = APIRouter()

def slugify(text: str) -> str:
    slug = re.sub(r'[^\w\s-]', '', text.lower()).strip()
    return re.sub(r'[-\s]+', '-', slug) or "tenant"

@router.post("/register", response_model=Token)
def register_customer(data: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == data.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered"
        )
    
    # 1. Create Tenant
    company_name = data.company_name or data.full_name or "My Forex Channel"
    base_slug = slugify(company_name)
    slug = base_slug
    counter = 1
    while db.query(Tenant).filter(Tenant.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
        
    tenant = Tenant(name=company_name, slug=slug)
    db.add(tenant)
    db.flush()

    # 2. Create User
    user = User(
        tenant_id=tenant.id,
        email=data.email.lower(),
        full_name=data.full_name,
        hashed_password=get_password_hash(data.password),
        role="customer"
    )
    db.add(user)

    # 3. Assign Pro Trial Plan (14 Days)
    pro_plan = db.query(Plan).filter(Plan.slug == "pro").first()
    if not pro_plan:
        pro_plan = Plan(
            name="الباقة الاحترافية (Pro)",
            slug="pro",
            price_monthly=40.0,
            max_channels=3,
            max_automations=15,
            max_messages=500,
            max_daily_executions=1000,
            features=["ربط 3 قنوات تيليجرام", "حتى 15 هدف وكلمة مفتاحية", "خصم 33% (وفر $20 شهرياً)", "أولوية النشر الفوري 24/7"]
        )
        db.add(pro_plan)
        db.flush()

    now = datetime.now(timezone.utc)
    subscription = Subscription(
        tenant_id=tenant.id,
        plan_id=pro_plan.id,
        status="active",
        starts_at=now,
        expires_at=now + timedelta(days=14)
    )
    db.add(subscription)

    # Audit log
    db.add(AuditLog(
        tenant_id=tenant.id,
        user_id=user.id,
        action="USER_REGISTERED",
        entity_type="User",
        entity_id=user.id,
        details={"email": user.email, "company": company_name}
    ))

    db.commit()
    db.refresh(user)

    access_token = create_access_token(subject=user.id)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "tenant_id": user.tenant_id,
            "tenant_name": tenant.name
        }
    }

@router.post("/login", response_model=Token)
def login_form(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username.lower()).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="User account is deactivated")

    tenant_name = user.tenant.name if user.tenant else "System Admin"
    access_token = create_access_token(subject=user.id)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "tenant_id": user.tenant_id,
            "tenant_name": tenant_name
        }
    }

@router.post("/login-json", response_model=Token)
def login_json(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.lower()).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="User account is deactivated")

    tenant_name = user.tenant.name if user.tenant else "System Admin"
    access_token = create_access_token(subject=user.id)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "tenant_id": user.tenant_id,
            "tenant_name": tenant_name
        }
    }

@router.get("/me")
def get_current_user_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub_data = None
    if current_user.tenant and current_user.tenant.subscription:
        sub = current_user.tenant.subscription
        now = datetime.now(timezone.utc)
        
        # Ensure timezone-aware comparison
        exp_at = sub.expires_at
        if exp_at.tzinfo is None:
            exp_at = exp_at.replace(tzinfo=timezone.utc)
            
        days_left = max(0, (exp_at - now).days)
        sub_data = {
            "status": sub.status,
            "plan_name": sub.plan.name if sub.plan else "Pro",
            "expires_at": sub.expires_at,
            "days_remaining": days_left
        }
    
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "tenant_id": current_user.tenant_id,
        "tenant_name": current_user.tenant.name if current_user.tenant else "Admin",
        "subscription": sub_data
    }
