from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.core.database import get_db
from backend.app.models.models import (
    Tenant, User, Plan, Subscription, Channel, Automation, MessageLibrary, Job, PublishingHistory, AuditLog
)
from backend.app.schemas.schemas import AdminStats, PlanCreate, PlanOut
from backend.app.api.deps import get_current_admin

router = APIRouter()

@router.get("/stats", response_model=AdminStats)
def get_admin_dashboard_stats(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    total_customers = db.query(Tenant).count()
    active_subscriptions = db.query(Subscription).filter(Subscription.status == "active").count()
    
    now = datetime.now(timezone.utc)
    expiring_soon = db.query(Subscription).filter(
        Subscription.status == "active",
        Subscription.expires_at <= now + timedelta(days=7),
        Subscription.expires_at >= now
    ).count()

    expired_subscriptions = db.query(Subscription).filter(
        Subscription.expires_at < now
    ).count()

    connected_channels = db.query(Channel).filter(Channel.is_connected == True).count()
    active_automations = db.query(Automation).filter(Automation.is_active == True).count()

    # Jobs today
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    jobs_today = db.query(Job).filter(Job.created_at >= today_start).count()
    successful_jobs = db.query(Job).filter(Job.created_at >= today_start, Job.status == "COMPLETED").count()
    failed_jobs = db.query(Job).filter(Job.created_at >= today_start, Job.status == "FAILED").count()

    return {
        "total_customers": total_customers,
        "active_subscriptions": active_subscriptions,
        "expiring_soon": expiring_soon,
        "expired_subscriptions": expired_subscriptions,
        "connected_channels": connected_channels,
        "active_automations": active_automations,
        "jobs_today": jobs_today,
        "successful_jobs_today": successful_jobs,
        "failed_jobs_today": failed_jobs,
        "services_status": {
            "worker": "healthy",
            "database": "healthy",
            "redis": "healthy",
            "telegram": "healthy"
        }
    }

@router.get("/customers")
def get_all_customers(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    tenants = db.query(Tenant).order_by(Tenant.created_at.desc()).all()
    result = []
    now = datetime.now(timezone.utc)
    for t in tenants:
        owner = db.query(User).filter(User.tenant_id == t.id).first()
        channels = db.query(Channel).filter(Channel.tenant_id == t.id).all()
        sub = t.subscription
        
        days_left = 0
        if sub and sub.expires_at:
            exp_at = sub.expires_at
            if exp_at.tzinfo is None:
                exp_at = exp_at.replace(tzinfo=timezone.utc)
            days_left = max(0, (exp_at - now).days)

        result.append({
            "id": t.id,
            "name": t.name,
            "slug": t.slug,
            "owner_email": owner.email if owner else "N/A",
            "owner_name": owner.full_name if owner else "N/A",
            "channels_count": len(channels),
            "channels": [{"title": c.title, "chat_id": c.telegram_chat_id} for c in channels],
            "plan_name": sub.plan.name if sub and sub.plan else "None",
            "subscription_status": sub.status if sub else "expired",
            "expires_at": sub.expires_at if sub else None,
            "days_remaining": days_left,
            "created_at": t.created_at
        })
    return result

@router.get("/customers/{tenant_id}")
def get_customer_details(
    tenant_id: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Customer not found")

    owner = db.query(User).filter(User.tenant_id == tenant.id).first()
    channels = db.query(Channel).filter(Channel.tenant_id == tenant.id).all()
    automations = db.query(Automation).filter(Automation.tenant_id == tenant.id).all()
    messages = db.query(MessageLibrary).filter(MessageLibrary.tenant_id == tenant.id).all()
    jobs = db.query(Job).filter(Job.tenant_id == tenant.id).order_by(Job.created_at.desc()).limit(20).all()
    history = db.query(PublishingHistory).filter(PublishingHistory.tenant_id == tenant.id).order_by(PublishingHistory.published_at.desc()).limit(20).all()

    return {
        "tenant": {
            "id": tenant.id,
            "name": tenant.name,
            "slug": tenant.slug,
            "is_active": tenant.is_active,
            "created_at": tenant.created_at
        },
        "owner": {
            "id": owner.id if owner else None,
            "email": owner.email if owner else None,
            "full_name": owner.full_name if owner else None
        },
        "subscription": {
            "status": tenant.subscription.status if tenant.subscription else "none",
            "plan": tenant.subscription.plan.name if tenant.subscription and tenant.subscription.plan else "None",
            "expires_at": tenant.subscription.expires_at if tenant.subscription else None
        },
        "channels": [{"id": c.id, "title": c.title, "chat_id": c.telegram_chat_id, "is_connected": c.is_connected} for c in channels],
        "automations_count": len(automations),
        "messages_count": len(messages),
        "recent_jobs": [{"id": j.id, "status": j.status, "trigger": j.trigger_text, "created_at": j.created_at} for j in jobs],
        "recent_history": [{"id": h.id, "status": h.status, "message": h.message_title, "published_at": h.published_at} for h in history]
    }

@router.post("/customers/{tenant_id}/subscription/extend")
def extend_customer_subscription(
    tenant_id: str,
    days: int = 30,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant or not tenant.subscription:
        raise HTTPException(status_code=404, detail="Subscription not found for customer")

    sub = tenant.subscription
    now = datetime.now(timezone.utc)
    base_date = sub.expires_at if sub.expires_at and sub.expires_at > now else now
    sub.expires_at = base_date + timedelta(days=days)
    sub.status = "active"
    
    db.add(AuditLog(
        tenant_id=tenant.id,
        user_id=admin.id,
        action="SUBSCRIPTION_EXTENDED_BY_ADMIN",
        details={"days_added": days, "new_expiry": sub.expires_at.isoformat()}
    ))

    db.commit()
    return {"message": f"Subscription successfully extended by {days} days", "new_expires_at": sub.expires_at}

@router.post("/customers/{tenant_id}/subscription/suspend")
def suspend_customer_subscription(
    tenant_id: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant or not tenant.subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    tenant.subscription.status = "suspended"
    db.add(AuditLog(
        tenant_id=tenant.id,
        user_id=admin.id,
        action="SUBSCRIPTION_SUSPENDED_BY_ADMIN",
        details={"tenant_name": tenant.name}
    ))
    db.commit()
    return {"message": "Customer subscription suspended"}

@router.get("/plans", response_model=List[PlanOut])
def get_plans(db: Session = Depends(get_db)):
    plans = db.query(Plan).all()
    return plans

@router.post("/plans", response_model=PlanOut)
def create_plan(
    data: PlanCreate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    plan = Plan(**data.dict())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan
