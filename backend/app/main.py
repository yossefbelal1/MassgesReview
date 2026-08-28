from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.core.database import Base, engine, SessionLocal
from backend.app.core.security import get_password_hash
from backend.app.models.models import User, Plan, Tenant, Subscription
from backend.app.api import auth, admin, channels, messages, automations, jobs, history, health

# Create database tables
Base.metadata.create_all(bind=engine)

# Seed default admin and plans
def seed_initial_data():
    db = SessionLocal()
    try:
        # 1. Admin User
        admin_user = db.query(User).filter(User.email == "admin@reviewflow.com").first()
        if not admin_user:
            admin_tenant = Tenant(name="ReviewFlow System", slug="system-admin")
            db.add(admin_tenant)
            db.flush()

            admin_user = User(
                tenant_id=admin_tenant.id,
                email="admin@reviewflow.com",
                full_name="ReviewFlow Admin",
                hashed_password=get_password_hash("Admin@123456"),
                role="admin"
            )
            db.add(admin_user)

        # 2. Default 3 Plans ($20, $30, $80)
        plans_data = [
            {
                "name": "الباقة الأساسية (Starter)",
                "slug": "starter",
                "price_monthly": 20.0,
                "max_channels": 1,
                "max_automations": 5,
                "max_messages": 100,
                "max_daily_executions": 300,
                "features": ["1 قناة تيليجرام واحدة", "حتى 5 أهداف وكلمات مفتاحية", "فواصل زمنية عشوائية ذكية", "تشغيل سحابي 24/7"]
            },
            {
                "name": "الباقة الاحترافية (Pro)",
                "slug": "pro",
                "price_monthly": 30.0,
                "max_channels": 3,
                "max_automations": 15,
                "max_messages": 500,
                "max_daily_executions": 1000,
                "features": ["3 قنوات تيليجرام", "حتى 15 هدف وكلمة مفتاحية", "فواصل زمنية عشوائية ذكية", "أولوية النشر الفوري 24/7"]
            },
            {
                "name": "باقة النخبة (VIP)",
                "slug": "vip",
                "price_monthly": 80.0,
                "max_channels": 10,
                "max_automations": 50,
                "max_messages": 2000,
                "max_daily_executions": 5000,
                "features": ["10 قنوات تيليجرام", "حتى 50 هدف وكلمة مفتاحية", "فواصل زمنية عشوائية ذكية", "دعم فني VIP مخصص 24/7"]
            }
        ]

        # Clean old obsolete slugs
        allowed_slugs = [p["slug"] for p in plans_data]
        db.query(Plan).filter(Plan.slug.notin_(allowed_slugs)).delete(synchronize_session=False)

        for p in plans_data:
            existing_p = db.query(Plan).filter(Plan.slug == p["slug"]).first()
            if not existing_p:
                db.add(Plan(**p))
            else:
                existing_p.name = p["name"]
                existing_p.price_monthly = p["price_monthly"]
                existing_p.max_channels = p["max_channels"]
                existing_p.max_automations = p["max_automations"]
                existing_p.features = p["features"]

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error seeding data: {e}")
    finally:
        db.close()

seed_initial_data()

app = FastAPI(
    title="ReviewFlow SaaS API",
    description="Multi-Tenant Telegram Automation SaaS for Forex Channel Owners",
    version="1.0.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Auth"])
app.include_router(admin.router, prefix=f"{settings.API_V1_STR}/admin", tags=["Admin"])
app.include_router(channels.router, prefix=f"{settings.API_V1_STR}/channels", tags=["Channels"])
app.include_router(messages.router, prefix=f"{settings.API_V1_STR}/messages", tags=["Messages"])
app.include_router(automations.router, prefix=f"{settings.API_V1_STR}/automations", tags=["Automations"])
app.include_router(jobs.router, prefix=f"{settings.API_V1_STR}/jobs", tags=["Jobs"])
app.include_router(history.router, prefix=f"{settings.API_V1_STR}/history", tags=["Publishing History"])
app.include_router(health.router, prefix=f"{settings.API_V1_STR}/health", tags=["Health"])

@app.get("/")
def root():
    return {
        "message": "Welcome to ReviewFlow SaaS API",
        "docs": "/docs",
        "health": f"{settings.API_V1_STR}/health"
    }
