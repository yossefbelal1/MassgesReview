from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.core.database import get_db
from backend.app.core.security import get_password_hash
from backend.app.models.models import (
    Tenant, User, Plan, Subscription, Channel, Automation, MessageLibrary, Job, PublishingHistory, AuditLog
)
from backend.app.schemas.schemas import (
    AdminStats, PlanCreate, PlanOut, SubscriptionUpdateAdmin, AdminResetPassword, AutomationUpdateAdmin
)
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
        automations = db.query(Automation).filter(Automation.tenant_id == t.id).all()
        sub = t.subscription
        
        days_left = 0
        if sub and sub.expires_at:
            exp_at = sub.expires_at
            if exp_at.tzinfo is None:
                exp_at = exp_at.replace(tzinfo=timezone.utc)
            days_left = max(0, (exp_at - now).days)

        auto_list = []
        keywords = []
        for a in automations:
            auto_list.append({
                "id": a.id,
                "name": a.name,
                "trigger_value": a.trigger_value,
                "trigger_type": a.trigger_type,
                "channel_id": a.channel_id,
                "channel_title": a.channel.title if a.channel else "N/A",
                "reviews_count": a.reviews_count or 2,
                "initial_delay_seconds": a.initial_delay_seconds or 5.0,
                "delay_seconds": a.delay_seconds or 4.0,
                "is_active": a.is_active,
                "total_executions": a.total_executions or 0,
                "last_executed_at": a.last_executed_at.isoformat() if a.last_executed_at else None
            })
            if a.trigger_value and a.trigger_value not in keywords:
                keywords.append(a.trigger_value)

        result.append({
            "id": t.id,
            "name": t.name,
            "slug": t.slug,
            "is_active": t.is_active,
            "owner_email": owner.email if owner else "N/A",
            "owner_name": owner.full_name if owner else "N/A",
            "owner_id": owner.id if owner else None,
            "channels_count": len(channels),
            "automations_count": len(automations),
            "keywords": keywords,
            "automations": auto_list,
            "channels": [
                {
                    "id": c.id, 
                    "title": c.title, 
                    "chat_id": c.telegram_chat_id, 
                    "is_connected": c.is_connected,
                    "bot_is_admin": c.bot_is_admin,
                    "backup_bot_is_admin": c.backup_bot_is_admin,
                    "automations_count": len([a for a in automations if a.channel_id == c.id])
                } for c in channels
            ],
            "plan_name": sub.plan.name if sub and sub.plan else "None",
            "plan_slug": sub.plan.slug if sub and sub.plan else "starter",
            "plan_price": sub.plan.price_monthly if sub and sub.plan else 0,
            "max_channels": sub.plan.max_channels if sub and sub.plan else 1,
            "max_automations": sub.plan.max_automations if sub and sub.plan else 5,
            "subscription_status": sub.status if sub else "expired",
            "expires_at": sub.expires_at.isoformat() if sub and sub.expires_at else None,
            "starts_at": sub.starts_at.isoformat() if sub and sub.starts_at else None,
            "days_remaining": days_left,
            "created_at": t.created_at.isoformat() if t.created_at else None
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
            "created_at": tenant.created_at.isoformat() if tenant.created_at else None
        },
        "owner": {
            "id": owner.id if owner else None,
            "email": owner.email if owner else None,
            "full_name": owner.full_name if owner else None,
            "role": owner.role if owner else None
        },
        "subscription": {
            "status": tenant.subscription.status if tenant.subscription else "none",
            "plan_name": tenant.subscription.plan.name if tenant.subscription and tenant.subscription.plan else "None",
            "plan_slug": tenant.subscription.plan.slug if tenant.subscription and tenant.subscription.plan else "starter",
            "price_monthly": tenant.subscription.plan.price_monthly if tenant.subscription and tenant.subscription.plan else 0,
            "max_channels": tenant.subscription.plan.max_channels if tenant.subscription and tenant.subscription.plan else 1,
            "max_automations": tenant.subscription.plan.max_automations if tenant.subscription and tenant.subscription.plan else 5,
            "starts_at": tenant.subscription.starts_at.isoformat() if tenant.subscription and tenant.subscription.starts_at else None,
            "expires_at": tenant.subscription.expires_at.isoformat() if tenant.subscription and tenant.subscription.expires_at else None
        },
        "channels": [
            {
                "id": c.id, 
                "title": c.title, 
                "chat_id": c.telegram_chat_id, 
                "is_connected": c.is_connected, 
                "bot_is_admin": c.bot_is_admin,
                "backup_bot_is_admin": c.backup_bot_is_admin,
                "automations_count": len([a for a in automations if a.channel_id == c.id])
            } for c in channels
        ],
        "automations": [
            {
                "id": a.id, 
                "name": a.name,
                "trigger_value": a.trigger_value,
                "trigger_type": a.trigger_type,
                "channel_id": a.channel_id,
                "channel_title": a.channel.title if a.channel else "N/A",
                "reviews_count": a.reviews_count or 2,
                "initial_delay_seconds": a.initial_delay_seconds or 5.0,
                "delay_seconds": a.delay_seconds or 4.0,
                "is_active": a.is_active,
                "total_executions": a.total_executions or 0,
                "last_executed_at": a.last_executed_at.isoformat() if a.last_executed_at else None
            } for a in automations
        ],
        "messages_count": len(messages),
        "recent_jobs": [{"id": j.id, "status": j.status, "trigger": j.trigger_text, "created_at": j.created_at.isoformat() if j.created_at else None} for j in jobs],
        "recent_history": [{"id": h.id, "status": h.status, "message": h.message_title, "published_at": h.published_at.isoformat() if h.published_at else None} for h in history]
    }

@router.post("/customers/{tenant_id}/automations")
def create_customer_automation_admin(
    tenant_id: str,
    data: AutomationUpdateAdmin,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    channel_id = data.channel_id
    if not channel_id:
        first_ch = db.query(Channel).filter(Channel.tenant_id == tenant.id).first()
        if not first_ch:
            raise HTTPException(status_code=400, detail="Customer has no connected channels")
        channel_id = first_ch.id

    auto = Automation(
        tenant_id=tenant.id,
        channel_id=channel_id,
        name=data.name or data.trigger_value or "أتمتة جديدة",
        trigger_value=data.trigger_value or "هدف",
        trigger_type=data.trigger_type or "contains",
        reviews_count=data.reviews_count or 2,
        initial_delay_seconds=data.initial_delay_seconds if data.initial_delay_seconds is not None else 5.0,
        delay_seconds=data.delay_seconds if data.delay_seconds is not None else 4.0,
        is_active=data.is_active if data.is_active is not None else True
    )
    db.add(auto)
    db.commit()
    db.refresh(auto)
    return {
        "id": auto.id,
        "name": auto.name,
        "trigger_value": auto.trigger_value,
        "trigger_type": auto.trigger_type,
        "channel_id": auto.channel_id,
        "channel_title": auto.channel.title if auto.channel else "N/A",
        "reviews_count": auto.reviews_count,
        "initial_delay_seconds": auto.initial_delay_seconds,
        "delay_seconds": auto.delay_seconds,
        "is_active": auto.is_active
    }

@router.put("/automations/{auto_id}")
def update_automation_admin(
    auto_id: str,
    data: AutomationUpdateAdmin,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    auto = db.query(Automation).filter(Automation.id == auto_id).first()
    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found")

    if data.name is not None:
        auto.name = data.name
    if data.trigger_value is not None:
        auto.trigger_value = data.trigger_value
    if data.trigger_type is not None:
        auto.trigger_type = data.trigger_type
    if data.channel_id is not None:
        auto.channel_id = data.channel_id
    if data.reviews_count is not None:
        auto.reviews_count = data.reviews_count
    if data.initial_delay_seconds is not None:
        auto.initial_delay_seconds = data.initial_delay_seconds
    if data.delay_seconds is not None:
        auto.delay_seconds = data.delay_seconds
    if data.is_active is not None:
        auto.is_active = data.is_active

    db.commit()
    db.refresh(auto)
    return {
        "id": auto.id,
        "name": auto.name,
        "trigger_value": auto.trigger_value,
        "trigger_type": auto.trigger_type,
        "channel_id": auto.channel_id,
        "channel_title": auto.channel.title if auto.channel else "N/A",
        "reviews_count": auto.reviews_count,
        "initial_delay_seconds": auto.initial_delay_seconds,
        "delay_seconds": auto.delay_seconds,
        "is_active": auto.is_active
    }

@router.delete("/automations/{auto_id}")
def delete_automation_admin(
    auto_id: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    auto = db.query(Automation).filter(Automation.id == auto_id).first()
    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found")

    db.delete(auto)
    db.commit()
    return {"message": "تم حذف الأتمتة بنجاح"}

@router.post("/automations/{auto_id}/toggle")
def toggle_automation_admin(
    auto_id: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    auto = db.query(Automation).filter(Automation.id == auto_id).first()
    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found")

    auto.is_active = not auto.is_active
    db.commit()
    return {"id": auto.id, "is_active": auto.is_active, "name": auto.name}

@router.post("/customers/{tenant_id}/subscription/update")
def update_customer_subscription_full(
    tenant_id: str,
    data: SubscriptionUpdateAdmin,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Comprehensive subscription management: Change Plan, Change Status, Set Custom Expiry Date or Add Days.
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Customer not found")

    sub = tenant.subscription
    now = datetime.now(timezone.utc)

    # If subscription doesn't exist, create one
    if not sub:
        plan = db.query(Plan).filter(Plan.slug == (data.plan_slug or "starter")).first()
        if not plan:
            plan = db.query(Plan).first()
        sub = Subscription(
            tenant_id=tenant.id,
            plan_id=plan.id,
            status="active",
            starts_at=now,
            expires_at=now + timedelta(days=30)
        )
        db.add(sub)
        db.flush()

    # 1. Update Plan if provided
    if data.plan_slug:
        target_plan = db.query(Plan).filter(Plan.slug == data.plan_slug).first()
        if not target_plan:
            raise HTTPException(status_code=400, detail=f"Plan '{data.plan_slug}' not found")
        sub.plan_id = target_plan.id

    # 2. Update Status if provided
    if data.status:
        sub.status = data.status

    # 3. Update Expiry
    if data.expires_at:
        exp = data.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        sub.expires_at = exp
    elif data.days_to_add:
        base_date = sub.expires_at if sub.expires_at and sub.expires_at > now else now
        sub.expires_at = base_date + timedelta(days=data.days_to_add)

    # If subscription was expired/suspended but has future expiry and status active, ensure active
    if sub.status == "expired" and sub.expires_at > now:
        sub.status = "active"

    db.add(AuditLog(
        tenant_id=tenant.id,
        user_id=admin.id,
        action="SUBSCRIPTION_UPDATED_BY_ADMIN",
        details={
            "plan_slug": data.plan_slug,
            "status": sub.status,
            "new_expiry": sub.expires_at.isoformat() if sub.expires_at else None
        }
    ))

    db.commit()
    db.refresh(sub)
    return {
        "message": "تم تحديث بيانات اشتراك العميل بنجاح",
        "status": sub.status,
        "plan_name": sub.plan.name if sub.plan else "None",
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None
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
    return {"message": f"تم تمديد الاشتراك بنجاح لمدة {days} يوم إضافي", "new_expires_at": sub.expires_at}

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
    return {"message": "تم إيقاف اشتراك العميل مؤقتاً"}

@router.post("/customers/{tenant_id}/subscription/resume")
def resume_customer_subscription(
    tenant_id: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant or not tenant.subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    now = datetime.now(timezone.utc)
    if tenant.subscription.expires_at and tenant.subscription.expires_at <= now:
        tenant.subscription.expires_at = now + timedelta(days=30)
    tenant.subscription.status = "active"

    db.add(AuditLog(
        tenant_id=tenant.id,
        user_id=admin.id,
        action="SUBSCRIPTION_RESUMED_BY_ADMIN",
        details={"tenant_name": tenant.name}
    ))
    db.commit()
    return {"message": "تم استئناف وتفعيل اشتراك العميل بنجاح"}

@router.post("/customers/{tenant_id}/reset-password")
def admin_reset_customer_password(
    tenant_id: str,
    data: AdminResetPassword,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    owner = db.query(User).filter(User.tenant_id == tenant_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Customer user not found")

    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="كلمة المرور يجب أن لا تقل عن 6 خانات")

    owner.hashed_password = get_password_hash(data.new_password)
    db.add(AuditLog(
        tenant_id=tenant_id,
        user_id=admin.id,
        action="PASSWORD_RESET_BY_ADMIN",
        details={"owner_email": owner.email}
    ))
    db.commit()
    return {"message": f"تم تغيير كلمة مرور العميل ({owner.email}) بنجاح"}

@router.delete("/customers/{tenant_id}")
def delete_customer_tenant(
    tenant_id: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Delete dependent entities
    db.query(PublishingHistory).filter(PublishingHistory.tenant_id == tenant_id).delete()
    db.query(Job).filter(Job.tenant_id == tenant_id).delete()
    db.query(Automation).filter(Automation.tenant_id == tenant_id).delete()
    db.query(MessageLibrary).filter(MessageLibrary.tenant_id == tenant_id).delete()
    db.query(Channel).filter(Channel.tenant_id == tenant_id).delete()
    db.query(Subscription).filter(Subscription.tenant_id == tenant_id).delete()
    db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id).delete()
    db.query(User).filter(User.tenant_id == tenant_id).delete()
    db.delete(tenant)
    db.commit()
    return {"message": "تم حذف المشترك وكافة بياناته بنجاح"}

@router.get("/plans", response_model=List[PlanOut])
def get_plans(db: Session = Depends(get_db)):
    plans = db.query(Plan).order_by(Plan.price_monthly.asc()).all()
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
