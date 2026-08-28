from typing import List
from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.models.models import Automation, AutomationStep, Channel, MessageLibrary, User, AuditLog, Job
from backend.app.schemas.schemas import AutomationCreate, AutomationOut
from backend.app.api.deps import get_current_active_customer

router = APIRouter()

@router.get("/", response_model=List[AutomationOut])
def get_automations(
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db)
):
    automations = db.query(Automation).filter(
        Automation.tenant_id == current_user.tenant_id
    ).order_by(Automation.created_at.desc()).all()
    return automations

@router.post("/", response_model=AutomationOut)
def create_automation(
    data: AutomationCreate,
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db)
):
    # 1. Check plan limits
    tenant = current_user.tenant
    if tenant and tenant.subscription and tenant.subscription.plan:
        max_allowed = tenant.subscription.plan.max_automations
        current_count = db.query(Automation).filter(Automation.tenant_id == tenant.id).count()
        if current_count >= max_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Automations limit reached ({max_allowed} max). Please upgrade your plan."
            )

    # 2. Verify channel belongs to tenant
    channel = db.query(Channel).filter(
        Channel.id == data.channel_id,
        Channel.tenant_id == current_user.tenant_id
    ).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # 3. Create Automation
    auto = Automation(
        tenant_id=current_user.tenant_id,
        channel_id=data.channel_id,
        name=data.name,
        trigger_type=data.trigger_type,
        trigger_value=data.trigger_value.strip(),
        reviews_count=data.reviews_count,
        initial_delay_seconds=data.initial_delay_seconds,
        delay_seconds=data.delay_seconds,
        is_active=data.is_active
    )
    db.add(auto)
    db.flush()

    # 4. Create Sequence Steps (if any provided)
    if data.steps:
        for step_data in data.steps:
            msg = db.query(MessageLibrary).filter(
                MessageLibrary.id == step_data.message_id,
                MessageLibrary.tenant_id == current_user.tenant_id
            ).first()
            if not msg:
                continue
            
            step = AutomationStep(
                automation_id=auto.id,
                message_id=step_data.message_id,
                step_order=step_data.step_order,
                delay_seconds=step_data.delay_seconds
            )
            db.add(step)

    db.add(AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="AUTOMATION_CREATED",
        entity_type="Automation",
        entity_id=auto.id,
        details={"name": auto.name, "trigger": auto.trigger_value, "reviews_count": auto.reviews_count, "initial_delay": auto.initial_delay_seconds, "delay": auto.delay_seconds}
    ))

    db.commit()
    db.refresh(auto)
    return auto

from pydantic import BaseModel
from typing import Optional

class AutomationUpdate(BaseModel):
    name: Optional[str] = None
    trigger_value: Optional[str] = None
    trigger_type: Optional[str] = "contains"
    reviews_count: Optional[int] = 2
    initial_delay_seconds: Optional[float] = 5.0
    delay_seconds: Optional[float] = 4.0
    is_active: Optional[bool] = None

@router.put("/{automation_id}", response_model=AutomationOut)
def update_automation(
    automation_id: str,
    data: AutomationUpdate,
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db)
):
    auto = db.query(Automation).filter(
        Automation.id == automation_id,
        Automation.tenant_id == current_user.tenant_id
    ).first()

    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found")

    if data.name is not None:
        auto.name = data.name.strip()
    if data.trigger_value is not None:
        auto.trigger_value = data.trigger_value.strip()
    if data.trigger_type is not None:
        auto.trigger_type = data.trigger_type
    if data.reviews_count is not None:
        auto.reviews_count = max(1, min(5, data.reviews_count))
    if data.initial_delay_seconds is not None:
        auto.initial_delay_seconds = max(0.0, data.initial_delay_seconds)
    if data.delay_seconds is not None:
        auto.delay_seconds = max(1.0, data.delay_seconds)
    if data.is_active is not None:
        auto.is_active = data.is_active

    db.commit()
    db.refresh(auto)
    return auto

@router.patch("/{automation_id}/toggle")
def toggle_automation(
    automation_id: str,
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db)
):
    auto = db.query(Automation).filter(
        Automation.id == automation_id,
        Automation.tenant_id == current_user.tenant_id
    ).first()

    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found")

    auto.is_active = not auto.is_active
    db.commit()
    return {"message": f"Automation is now {'Active' if auto.is_active else 'Paused'}", "is_active": auto.is_active}

@router.post("/{automation_id}/run-now")
def run_automation_manually(
    automation_id: str,
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db)
):
    import uuid

    auto = db.query(Automation).filter(
        Automation.id == automation_id,
        Automation.tenant_id == current_user.tenant_id
    ).first()

    if not auto:
        raise HTTPException(status_code=404, detail="الأتمتة غير موجودة")

    channel = auto.channel
    if not channel:
        raise HTTPException(status_code=404, detail="القناة غير مرتبطة")

    now = datetime.now(timezone.utc)
    idempotency_key = f"manual_{auto.id}_{int(now.timestamp())}_{uuid.uuid4().hex[:6]}"

    job = Job(
        tenant_id=current_user.tenant_id,
        automation_id=auto.id,
        channel_id=auto.channel_id,
        idempotency_key=idempotency_key,
        trigger_text="[تجربة فورية من لوحة التحكم]",
        current_step=1,
        total_steps=auto.reviews_count or 2,
        status="PENDING",
        execute_at=now
    )
    db.add(job)

    auto.total_executions += 1
    auto.last_executed_at = now
    db.commit()

    return {"message": f"تم إطلاق تجربة الأتمتة '{auto.name}' على قناة '{channel.title}' بنجاح! جاري إرسال {auto.reviews_count} تقييمات فوراً."}

@router.delete("/{automation_id}")
def delete_automation(
    automation_id: str,
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db)
):
    auto = db.query(Automation).filter(
        Automation.id == automation_id,
        Automation.tenant_id == current_user.tenant_id
    ).first()

    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found")

    db.delete(auto)
    db.commit()
    return {"message": "Automation deleted successfully"}
