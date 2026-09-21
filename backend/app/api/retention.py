from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_

from backend.app.core.database import get_db
from backend.app.api.deps import get_current_user, get_current_tenant_id
from backend.app.models.models import (
    User, Channel, AudienceMember, RecoveryCase, RecoveryMessage, RetentionSetting
)
from backend.app.schemas.schemas import (
    RecoveryCaseOut, RecoveryCaseDetailOut, RecoveryMessageOut, RecoveryMessageCreate,
    RetentionSettingOut, RetentionSettingUpdate, AudienceMemberOut, RetentionSummaryOut
)
from backend.app.services.userbot_pool import userbot_pool

router = APIRouter()

@router.get("/summary", response_model=RetentionSummaryOut)
def get_retention_summary(
    channel_id: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Returns executive KPI retention metrics, win-back rate, and reason distribution.
    """
    base_query = db.query(RecoveryCase).filter(RecoveryCase.tenant_id == tenant_id)
    if channel_id:
        base_query = base_query.filter(RecoveryCase.channel_id == channel_id)

    total_left = base_query.count()
    total_rejoined = base_query.filter(RecoveryCase.status == "RECOVERED").count()
    total_contacted = base_query.filter(RecoveryCase.first_contacted_at.isnot(None)).count()
    total_in_conversation = base_query.filter(RecoveryCase.status == "CONVERSATION_ACTIVE").count()
    uncontactable_count = base_query.filter(RecoveryCase.status == "UNCONTACTABLE").count()

    win_back_rate = round((total_rejoined / total_left * 100), 1) if total_left > 0 else 0.0

    # Average time to rejoin in hours
    avg_rejoin_sec = db.query(func.avg(RecoveryCase.time_to_rejoin_seconds)).filter(
        RecoveryCase.tenant_id == tenant_id,
        RecoveryCase.status == "RECOVERED",
        RecoveryCase.time_to_rejoin_seconds.isnot(None)
    ).scalar()
    avg_rejoin_hours = round((avg_rejoin_sec / 3600), 1) if avg_rejoin_sec else 0.0

    # Churn reasons breakdown
    reasons_query = db.query(
        RecoveryCase.leave_reason_category,
        func.count(RecoveryCase.id).label("count")
    ).filter(
        RecoveryCase.tenant_id == tenant_id,
        RecoveryCase.leave_reason_category.isnot(None)
    )
    if channel_id:
        reasons_query = reasons_query.filter(RecoveryCase.channel_id == channel_id)
    reasons_rows = reasons_query.group_by(RecoveryCase.leave_reason_category).all()

    reasons_breakdown = []
    for r in reasons_rows:
        cat = r.leave_reason_category or "OTHER"
        rejoined_in_cat = base_query.filter(
            RecoveryCase.leave_reason_category == cat,
            RecoveryCase.status == "RECOVERED"
        ).count()
        reasons_breakdown.append({
            "category": cat,
            "count": r.count,
            "rejoined": rejoined_in_cat,
            "rate": round((rejoined_in_cat / r.count * 100), 1) if r.count > 0 else 0.0
        })

    # Daily trend for the last 7 days
    daily_trend = []
    now = datetime.now(timezone.utc)
    for i in range(6, -1, -1):
        day_date = (now - timedelta(days=i)).date()
        start_day = datetime(day_date.year, day_date.month, day_date.day, tzinfo=timezone.utc)
        end_day = start_day + timedelta(days=1)

        day_leaves = base_query.filter(
            RecoveryCase.created_at >= start_day,
            RecoveryCase.created_at < end_day
        ).count()

        day_rejoins = base_query.filter(
            RecoveryCase.rejoined_at >= start_day,
            RecoveryCase.rejoined_at < end_day,
            RecoveryCase.status == "RECOVERED"
        ).count()

        daily_trend.append({
            "date": day_date.strftime("%Y-%m-%d"),
            "leaves": day_leaves,
            "rejoins": day_rejoins
        })

    return {
        "total_left_detected": total_left,
        "total_contact_attempted": total_contacted + uncontactable_count,
        "total_contacted": total_contacted,
        "total_in_conversation": total_in_conversation,
        "total_rejoined": total_rejoined,
        "win_back_rate_percent": win_back_rate,
        "uncontactable_count": uncontactable_count,
        "average_rejoin_hours": avg_rejoin_hours,
        "reasons_breakdown": reasons_breakdown,
        "daily_trend": daily_trend
    }


@router.get("/cases", response_model=List[RecoveryCaseOut])
def get_recovery_cases(
    channel_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Returns list of member recovery cases with search and status filtering.
    """
    query = db.query(RecoveryCase).filter(RecoveryCase.tenant_id == tenant_id)

    if channel_id:
        query = query.filter(RecoveryCase.channel_id == channel_id)
    if status_filter:
        query = query.filter(RecoveryCase.status == status_filter)

    query = query.order_by(desc(RecoveryCase.created_at))
    cases = query.limit(limit).all()

    # Hydrate user details and channel titles
    result = []
    for c in cases:
        channel_title = c.channel.title if c.channel else "Unknown"
        user_name = None
        user_username = None
        if c.member:
            parts = [c.member.first_name or "", c.member.last_name or ""]
            user_name = " ".join(p for p in parts if p).strip() or None
            user_username = c.member.username

        item = RecoveryCaseOut(
            id=c.id,
            tenant_id=c.tenant_id,
            channel_id=c.channel_id,
            channel_title=channel_title,
            member_id=c.member_id,
            telegram_user_id=c.telegram_user_id,
            user_full_name=user_name,
            user_username=user_username,
            status=c.status,
            contactable=c.contactable,
            uncontactable_reason=c.uncontactable_reason,
            assigned_userbot=c.assigned_userbot,
            leave_reason_category=c.leave_reason_category,
            leave_reason_raw=c.leave_reason_raw,
            scheduled_contact_at=c.scheduled_contact_at,
            first_contacted_at=c.first_contacted_at,
            last_response_at=c.last_response_at,
            link_sent_at=c.link_sent_at,
            rejoined_at=c.rejoined_at,
            time_to_rejoin_seconds=c.time_to_rejoin_seconds,
            created_at=c.created_at
        )
        if search:
            s = search.lower()
            match_name = user_name and s in user_name.lower()
            match_user = user_username and s in user_username.lower()
            match_id = s in c.telegram_user_id
            if not (match_name or match_user or match_id):
                continue
        result.append(item)

    return result


@router.get("/cases/{case_id}", response_model=RecoveryCaseDetailOut)
def get_case_detail(
    case_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Returns full details and message history for a specific recovery case.
    """
    case = db.query(RecoveryCase).filter(
        RecoveryCase.id == case_id,
        RecoveryCase.tenant_id == tenant_id
    ).first()

    if not case:
        raise HTTPException(status_code=404, detail="Recovery case not found")

    channel_title = case.channel.title if case.channel else "Unknown"
    user_name = None
    user_username = None
    if case.member:
        parts = [case.member.first_name or "", case.member.last_name or ""]
        user_name = " ".join(p for p in parts if p).strip() or None
        user_username = case.member.username

    messages = [
        RecoveryMessageOut(
            id=m.id,
            case_id=m.case_id,
            direction=m.direction,
            sender_type=m.sender_type,
            userbot_username=m.userbot_username,
            text=m.text,
            intent_detected=m.intent_detected,
            sent_at=m.sent_at
        ) for m in case.messages
    ]

    return RecoveryCaseDetailOut(
        id=case.id,
        tenant_id=case.tenant_id,
        channel_id=case.channel_id,
        channel_title=channel_title,
        member_id=case.member_id,
        telegram_user_id=case.telegram_user_id,
        user_full_name=user_name,
        user_username=user_username,
        status=case.status,
        contactable=case.contactable,
        uncontactable_reason=case.uncontactable_reason,
        assigned_userbot=case.assigned_userbot,
        leave_reason_category=case.leave_reason_category,
        leave_reason_raw=case.leave_reason_raw,
        scheduled_contact_at=case.scheduled_contact_at,
        first_contacted_at=case.first_contacted_at,
        last_response_at=case.last_response_at,
        link_sent_at=case.link_sent_at,
        rejoined_at=case.rejoined_at,
        time_to_rejoin_seconds=case.time_to_rejoin_seconds,
        created_at=case.created_at,
        messages=messages
    )


@router.post("/cases/{case_id}/message", response_model=RecoveryMessageOut)
async def send_manual_case_message(
    case_id: str,
    payload: RecoveryMessageCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Sends a direct message from the userbot to the member in an active recovery case.
    Allows manual intervention even if previously marked uncontactable.
    """
    case = db.query(RecoveryCase).filter(
        RecoveryCase.id == case_id,
        RecoveryCase.tenant_id == tenant_id
    ).first()

    if not case:
        raise HTTPException(status_code=404, detail="حالة الاستعادة غير موجودة")

    username = case.member.username if case.member else None
    access_hash = None
    if case.member and case.member.access_hash:
        try:
            access_hash = int(case.member.access_hash)
        except (ValueError, TypeError):
            access_hash = None

    res = await userbot_pool.send_direct_message(
        target_user_id=int(case.telegram_user_id),
        text=payload.text,
        channel_id=case.channel_id,
        preferred_session=case.assigned_userbot,
        target_username=username,
        access_hash=access_hash
    )

    if not res["success"]:
        detail_msg = res.get("error_ar") or f"فشل إرسال الرسالة: {res.get('error', 'Unknown error')}"
        raise HTTPException(
            status_code=400,
            detail=detail_msg
        )

    now = datetime.now(timezone.utc)
    case.status = "CONVERSATION_ACTIVE"
    case.contactable = True
    case.uncontactable_reason = None
    case.assigned_userbot = res["userbot_username"]

    msg = RecoveryMessage(
        case_id=case.id,
        direction="OUTBOUND",
        sender_type="USERBOT",
        userbot_username=res["userbot_username"],
        text=payload.text,
        sent_at=now
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    return msg


@router.post("/cases/{case_id}/retry", response_model=RecoveryCaseOut)
def retry_single_recovery_case(
    case_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Resets a specific recovery case back to SCHEDULED for outreach.
    """
    case = db.query(RecoveryCase).filter(
        RecoveryCase.id == case_id,
        RecoveryCase.tenant_id == tenant_id
    ).first()

    if not case:
        raise HTTPException(status_code=404, detail="حالة الاستعادة غير موجودة")

    case.status = "SCHEDULED"
    case.contactable = True
    case.uncontactable_reason = None
    case.scheduled_contact_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(case)
    return case


@router.post("/cases/reset-all")
def reset_all_uncontactable_cases(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Resets all false UNCONTACTABLE cases back to SCHEDULED with staggered delays.
    """
    cases = db.query(RecoveryCase).filter(
        RecoveryCase.tenant_id == tenant_id,
        RecoveryCase.status == "UNCONTACTABLE"
    ).all()

    now = datetime.now(timezone.utc)
    for idx, c in enumerate(cases):
        c.status = "SCHEDULED"
        c.contactable = True
        c.uncontactable_reason = None
        # Stagger by 35 seconds to maintain anti-spam safety
        c.scheduled_contact_at = now + timedelta(seconds=(idx * 35))

    db.commit()
    return {"reset_count": len(cases), "message": f"تمت إعادة جدولة {len(cases)} حالة بأمان بفارق زمني لتفادي الحظر."}


@router.get("/members", response_model=List[AudienceMemberOut])
def get_channel_members(
    channel_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Returns channel audience members directory with lifecycle status.
    """
    query = db.query(AudienceMember).filter(AudienceMember.tenant_id == tenant_id)
    if channel_id:
        query = query.filter(AudienceMember.channel_id == channel_id)
    if status_filter:
        query = query.filter(AudienceMember.status == status_filter)

    return query.order_by(desc(AudienceMember.first_joined_at)).limit(limit).all()


@router.get("/settings/{channel_id}", response_model=RetentionSettingOut)
def get_channel_retention_settings(
    channel_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves retention and welcome automation settings for a channel.
    """
    channel = db.query(Channel).filter(
        Channel.id == channel_id,
        Channel.tenant_id == tenant_id
    ).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    settings = db.query(RetentionSetting).filter(
        RetentionSetting.channel_id == channel_id,
        RetentionSetting.tenant_id == tenant_id
    ).first()

    if not settings:
        settings = RetentionSetting(
            tenant_id=tenant_id,
            channel_id=channel_id,
            is_retention_enabled=True,
            initial_delay_seconds=5,
            max_daily_contacts=30
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return settings


@router.put("/settings/{channel_id}", response_model=RetentionSettingOut)
def update_channel_retention_settings(
    channel_id: str,
    payload: RetentionSettingUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Updates retention delays, message templates, invite links, and welcome rules.
    """
    settings = db.query(RetentionSetting).filter(
        RetentionSetting.channel_id == channel_id,
        RetentionSetting.tenant_id == tenant_id
    ).first()

    if not settings:
        settings = RetentionSetting(
            tenant_id=tenant_id,
            channel_id=channel_id,
            **payload.model_dump()
        )
        db.add(settings)
    else:
        for k, v in payload.model_dump().items():
            setattr(settings, k, v)

    db.commit()
    db.refresh(settings)
    return settings


@router.get("/userbots")
async def get_userbots_status(
    current_user: User = Depends(get_current_user)
):
    """
    Returns real-time operational status, quotas, and health for the Userbot pool.
    """
    return await userbot_pool.get_pool_status()


@router.get("/userbots/{session_name}/avatar")
async def get_userbot_avatar(
    session_name: str
):
    """
    Fetches and serves the profile picture of the userbot directly from Telegram.
    """
    photo_bytes = await userbot_pool.get_userbot_avatar(session_name)
    if not photo_bytes:
        raise HTTPException(status_code=404, detail="لا توجد صورة بروفايل محددة لهذا الحساب")
    return Response(content=photo_bytes, media_type="image/jpeg")


@router.post("/userbots/{session_name}/avatar")
async def update_userbot_avatar(
    session_name: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Uploads a new profile picture to Telegram for the specified userbot.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="يرجى رفع ملف صورة صالح (JPEG أو PNG)")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="حجم الصورة كبير جداً (الحد الأقصى 10 ميجابايت)")

    try:
        success = await userbot_pool.update_userbot_avatar(session_name, contents, filename=file.filename or "avatar.jpg")
        if not success:
            raise HTTPException(status_code=500, detail="فشل تحديث الصورة عبر تيليجرام")
        return {"success": True, "message": "تم تحديث صورة بروفايل اليوزربوت على تيليجرام بنجاح! 🎉"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"خطأ أثناء رفع الصورة لتيليجرام: {str(e)}")

