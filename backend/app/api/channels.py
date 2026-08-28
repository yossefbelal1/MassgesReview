from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.models.models import Channel, User, AuditLog, MessageLibrary, Automation, AutomationStep
from backend.app.schemas.schemas import ChannelCreate, ChannelOut
from backend.app.api.deps import get_current_active_customer
from backend.app.services.telegram_service import telegram_service

router = APIRouter()

@router.get("/", response_model=List[ChannelOut])
def get_channels(
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db)
):
    channels = db.query(Channel).filter(Channel.tenant_id == current_user.tenant_id).all()
    return channels

@router.post("/join")
async def auto_join_channel(
    data: ChannelCreate,
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db)
):
    """
    Step 1: Bot automatically joins the customer's channel using their link.
    """
    tenant = current_user.tenant
    if tenant and tenant.subscription and tenant.subscription.plan:
        max_allowed = tenant.subscription.plan.max_channels
        current_count = db.query(Channel).filter(Channel.tenant_id == tenant.id).count()
        if current_count >= max_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"وصلت للحد الأقصى المسموح به في باقتك ({max_allowed} قنوات). يرجى ترقية الباقة لربط قنوات إضافية."
            )

    res = await telegram_service.join_channel(data.telegram_chat_id)
    if not res.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=res.get("error", "تعذر العثور على القناة أو الانضمام إليها.")
        )
    return res

@router.post("/verify", response_model=ChannelOut)
async def verify_and_add_channel(
    data: ChannelCreate,
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db)
):
    # 1. Check subscription channel limits
    tenant = current_user.tenant
    if tenant and tenant.subscription and tenant.subscription.plan:
        max_allowed = tenant.subscription.plan.max_channels
        current_count = db.query(Channel).filter(Channel.tenant_id == tenant.id).count()
        if current_count >= max_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Plan limit reached ({max_allowed} channels max). Please upgrade your plan."
            )

    # 2. Check Telegram Verification
    res = await telegram_service.verify_channel(data.telegram_chat_id)
    if not res.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=res.get("error", "Could not verify channel with Telegram")
        )

    # 3. Prevent duplicate channels within tenant
    existing = db.query(Channel).filter(
        Channel.tenant_id == current_user.tenant_id,
        Channel.telegram_chat_id == res["chat_id"]
    ).first()

    if existing:
        existing.title = res["title"]
        existing.username = res["username"]
        existing.bot_is_admin = res["bot_is_admin"]
        existing.can_post = res["can_post"]
        existing.can_forward = res["can_forward"]
        db.commit()
        db.refresh(existing)
        return existing

    new_channel = Channel(
        tenant_id=current_user.tenant_id,
        telegram_chat_id=res["chat_id"],
        title=res["title"],
        username=res["username"],
        is_connected=True,
        bot_is_admin=res["bot_is_admin"],
        can_post=res["can_post"],
        can_forward=res["can_forward"]
    )
    db.add(new_channel)
    db.flush()

    # 4. Auto-Seed Central Review Bank & Default Preset Automations (Zero Effort for Customer)
    existing_messages = db.query(MessageLibrary).filter(MessageLibrary.tenant_id == current_user.tenant_id).all()
    if not existing_messages:
        # Seed default references from central bank
        default_msg1 = MessageLibrary(
            tenant_id=current_user.tenant_id,
            title="VIP Member Profit Proof (+$850)",
            source_chat_id="-1003969850866",
            source_message_id=2,
            text_preview="VIP Member Gold Trade Profit +$850 🔥",
            category="Results"
        )
        default_msg2 = MessageLibrary(
            tenant_id=current_user.tenant_id,
            title="VIP Community Feedback (+120 Pips)",
            source_chat_id="-1003969850866",
            source_message_id=3,
            text_preview="الحمد لله الصفقة جابت الأهداف كاملة بفضل الله 🚀",
            category="Reviews"
        )
        db.add_all([default_msg1, default_msg2])
        db.flush()

        # Create Default Preset Automations
        auto1 = Automation(
            tenant_id=current_user.tenant_id,
            channel_id=new_channel.id,
            name="🎯 الهدف الأول TP1 (افتراضي)",
            trigger_type="contains",
            trigger_value="TP1",
            reviews_count=2,
            delay_seconds=4.0,
            is_active=True
        )
        auto2 = Automation(
            tenant_id=current_user.tenant_id,
            channel_id=new_channel.id,
            name="🚀 الهدف الثاني TP2 (افتراضي)",
            trigger_type="contains",
            trigger_value="TP2",
            reviews_count=3,
            delay_seconds=5.0,
            is_active=True
        )
        db.add_all([auto1, auto2])
        db.flush()

        step1 = AutomationStep(
            automation_id=auto1.id,
            message_id=default_msg1.id,
            step_order=1,
            delay_seconds=3
        )
        step3 = AutomationStep(
            automation_id=auto2.id,
            message_id=default_msg2.id,
            step_order=1,
            delay_seconds=5
        )
        db.add_all([step1, step3])

    # Audit log
    db.add(AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="CHANNEL_CONNECTED",
        entity_type="Channel",
        entity_id=new_channel.id,
        details={"chat_id": new_channel.telegram_chat_id, "title": new_channel.title}
    ))

    db.commit()
    db.refresh(new_channel)
    return new_channel

@router.delete("/{channel_id}")
def delete_channel(
    channel_id: str,
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db)
):
    from backend.app.models.models import Job, PublishingHistory

    channel = db.query(Channel).filter(
        Channel.id == channel_id,
        Channel.tenant_id == current_user.tenant_id
    ).first()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    try:
        # 1. Clean jobs referencing this channel
        db.query(Job).filter(Job.channel_id == channel_id).delete(synchronize_session=False)

        # 2. Nullify channel references in history
        db.query(PublishingHistory).filter(PublishingHistory.channel_id == channel_id).update(
            {PublishingHistory.channel_id: None},
            synchronize_session=False
        )

        # 3. Delete automations and their steps
        automations = db.query(Automation).filter(Automation.channel_id == channel_id).all()
        for auto in automations:
            db.delete(auto)

        # 4. Delete channel
        db.delete(channel)

        db.add(AuditLog(
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            action="CHANNEL_DELETED",
            entity_type="Channel",
            entity_id=channel_id,
            details={"title": channel.title}
        ))
        db.commit()
        return {"message": "تم حذف وإلغاء ربط القناة بنجاح"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"فشل حذف القناة: {str(e)}")
