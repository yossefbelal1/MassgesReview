import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_

from backend.app.core.database import get_db
from backend.app.api.deps import get_current_user, get_current_tenant_id
from backend.app.models.models import (
    User, Channel, AudienceMember, RecoveryCase, RecoveryMessage, RetentionSetting, ChannelUserbot
)
from backend.app.schemas.schemas import (
    RecoveryCaseOut, RecoveryCaseDetailOut, RecoveryMessageOut, RecoveryMessageCreate,
    RetentionSettingOut, RetentionSettingUpdate, AudienceMemberOut, RetentionSummaryOut,
    UserbotSendCodeRequest, UserbotSendCodeResponse, UserbotVerifyCodeRequest, UserbotVerifyCodeResponse,
    ChannelUserbotOut
)
from backend.app.services.userbot_pool import userbot_pool
from backend.app.services.dedicated_userbot_service import dedicated_userbot_service
from backend.app.services.retention_engine import retention_engine

logger = logging.getLogger("reviewflow.retention")
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
    total_scheduled = base_query.filter(RecoveryCase.status.in_(["SCHEDULED", "DETECTED"])).count()
    total_opt_out = base_query.filter(RecoveryCase.status == "OPT_OUT").count()

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
        "total_scheduled_pending": total_scheduled,
        "total_opt_out": total_opt_out,
        "win_back_rate_percent": win_back_rate,
        "uncontactable_count": uncontactable_count,
        "average_rejoin_hours": avg_rejoin_hours,
        "reasons_breakdown": reasons_breakdown,
        "daily_trend": daily_trend,
        "funnel_reconciled": True
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

    # Pre-cache retention settings and dedicated userbots for fast mapping
    channel_ids = {c.channel_id for c in cases}
    settings_map = {
        s.channel_id: s for s in db.query(RetentionSetting).filter(RetentionSetting.channel_id.in_(channel_ids)).all()
    } if channel_ids else {}
    dedicated_set = {
        u.channel_id for u in db.query(ChannelUserbot.channel_id).filter(
            ChannelUserbot.channel_id.in_(channel_ids),
            ChannelUserbot.is_active == True
        ).all()
    } if channel_ids else set()

    result = []
    for c in cases:
        channel_title = c.channel.title if c.channel else "Unknown"
        user_name = None
        user_username = None
        if c.member:
            parts = [c.member.first_name or "", c.member.last_name or ""]
            user_name = " ".join(p for p in parts if p).strip() or None
            user_username = c.member.username

        ch_settings = settings_map.get(c.channel_id)
        direct_link = retention_engine.generate_direct_outreach_link(c.channel, ch_settings, c)

        queue_reason = None
        if c.status in ["SCHEDULED", "DETECTED"]:
            if c.channel_id in dedicated_set:
                queue_reason = "مجدول للإرسال التلقائي عبر يوزربوت القناة المخصص"
            else:
                queue_reason = "في طابور الإرسال (يعمل عبر حساب المنصة المشترك - يوصى بربط يوزربوت القناة)"
        elif c.status == "UNCONTACTABLE":
            queue_reason = "حساب المستخدم مقيد الخصوصية أو محذوف"

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
            created_at=c.created_at,
            direct_telegram_link=direct_link,
            queue_delay_reason=queue_reason
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

    settings = db.query(RetentionSetting).filter(RetentionSetting.channel_id == case.channel_id).first()
    direct_link = retention_engine.generate_direct_outreach_link(case.channel, settings, case)

    queue_reason = None
    if case.status in ["SCHEDULED", "DETECTED"]:
        has_dedicated = db.query(ChannelUserbot).filter(
            ChannelUserbot.channel_id == case.channel_id,
            ChannelUserbot.is_active == True
        ).first()
        if not has_dedicated:
            queue_reason = "في طابور الإرسال (يعمل عبر حساب المنصة المشترك - يوصى بربط يوزربوت القناة)"
        else:
            queue_reason = "مجدول للإرسال التلقائي عبر يوزربوت القناة المخصص"
    elif case.status == "UNCONTACTABLE":
        queue_reason = "حساب المستخدم مقيد الخصوصية أو محذوف"

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
        direct_telegram_link=direct_link,
        queue_delay_reason=queue_reason,
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
async def retry_single_recovery_case(
    case_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Resets a specific recovery case back to SCHEDULED for immediate outreach,
    and proactively triggers background worker dispatch.
    """
    case = db.query(RecoveryCase).filter(
        RecoveryCase.id == case_id,
        RecoveryCase.tenant_id == tenant_id
    ).first()

    if not case:
        raise HTTPException(status_code=404, detail="حالة الاستعادة غير موجودة")

    now = datetime.now(timezone.utc)
    case.status = "SCHEDULED"
    case.contactable = True
    case.uncontactable_reason = None
    case.scheduled_contact_at = now
    db.commit()
    db.refresh(case)

    # Immediately trigger processing in background
    try:
        asyncio.create_task(retention_engine.process_pending_recovery_contacts(db))
    except Exception as e:
        logger.warning(f"Error triggering immediate dispatch for case {case_id}: {e}")

    return case


@router.post("/cases/{case_id}/send-now")
async def send_case_now_direct(
    case_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Directly dispatches the win-back outreach message to a specific member right now.
    """
    case = db.query(RecoveryCase).filter(
        RecoveryCase.id == case_id,
        RecoveryCase.tenant_id == tenant_id
    ).first()

    if not case:
        raise HTTPException(status_code=404, detail="حالة الاستعادة غير موجودة")

    res = await retention_engine.send_recovery_to_case(db, case)
    db.refresh(case)
    return {
        "success": res.get("success", False),
        "status": case.status,
        "userbot": case.assigned_userbot,
        "message": res.get("message") or res.get("error_ar") or res.get("error") or "تمت المحاولة."
    }


@router.post("/cases/reset-all")
async def reset_all_uncontactable_cases(
    channel_id: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Immediately resets and dispatches all uncontacted, pending, or failed cases.
    Targets SCHEDULED, DETECTED, UNCONTACTABLE, and NO_RESPONSE cases without any delay.
    """
    query = db.query(RecoveryCase).filter(
        RecoveryCase.tenant_id == tenant_id,
        RecoveryCase.status.in_(["SCHEDULED", "DETECTED", "UNCONTACTABLE", "NO_RESPONSE"])
    )
    if channel_id:
        query = query.filter(RecoveryCase.channel_id == channel_id)

    cases = query.all()
    now = datetime.now(timezone.utc)
    for c in cases:
        c.status = "SCHEDULED"
        c.contactable = True
        c.uncontactable_reason = None
        c.scheduled_contact_at = now  # Send NOW without delay!

    db.commit()

    # Trigger background worker dispatch immediately
    try:
        asyncio.create_task(retention_engine.process_pending_recovery_contacts(db))
    except Exception as e:
        logger.warning(f"Error triggering batch dispatch: {e}")

    return {
        "reset_count": len(cases),
        "message": f"تم إطلاق الإرسال الفوري لـ {len(cases)} عضواً بنجاح ⚡"
    }


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


# ── Dedicated Per-Channel Userbot Endpoints ─────────────────────────────────

@router.post("/userbot/request-code", response_model=UserbotSendCodeResponse)
async def request_userbot_login_code(
    payload: UserbotSendCodeRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Step 1: Sends login code (OTP) via Telegram MTProto to channel owner's phone.
    """
    return await dedicated_userbot_service.send_login_code(
        db=db,
        tenant_id=tenant_id,
        channel_id=payload.channel_id,
        api_id=payload.api_id,
        api_hash=payload.api_hash,
        phone=payload.phone
    )


@router.post("/userbot/verify-code", response_model=UserbotVerifyCodeResponse)
async def verify_userbot_login_code(
    payload: UserbotVerifyCodeRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Step 2: Verifies code (and optional 2FA password) and establishes persistent StringSession.
    Immediately resets and releases all pending scheduled cases for this channel.
    """
    result = await dedicated_userbot_service.verify_login_code(
        db=db,
        tenant_id=tenant_id,
        login_attempt_id=payload.login_attempt_id,
        code=payload.code,
        password=payload.password
    )

    if isinstance(result, dict) and result.get("success") and not result.get("needs_2fa") and result.get("userbot"):
        try:
            channel_id = result["userbot"].get("channel_id") if isinstance(result["userbot"], dict) else getattr(result["userbot"], "channel_id", None)
            if channel_id:
                now = datetime.now(timezone.utc)
                # Reset all scheduled cases for this channel to send immediately!
                db.query(RecoveryCase).filter(
                    RecoveryCase.channel_id == channel_id,
                    RecoveryCase.status.in_(["SCHEDULED", "DETECTED", "UNCONTACTABLE"])
                ).update({
                    "scheduled_contact_at": now,
                    "status": "SCHEDULED",
                    "contactable": True,
                    "uncontactable_reason": None
                })
                db.commit()
                logger.info(f"[🚀 Dedicated Bot Connected]: Reset all pending recovery cases for channel {channel_id} to NOW.")
                # Trigger immediate background dispatch
                asyncio.create_task(retention_engine.process_pending_recovery_contacts(db))
        except Exception as e:
            logger.warning(f"Error resetting cases upon userbot connect: {e}")

    return result


@router.get("/userbot/{channel_id}", response_model=Optional[ChannelUserbotOut])
def get_channel_dedicated_userbot(
    channel_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Returns active dedicated userbot details for the channel if connected.
    """
    userbot = db.query(ChannelUserbot).filter(
        ChannelUserbot.channel_id == channel_id,
        ChannelUserbot.tenant_id == tenant_id
    ).first()
    return userbot


@router.delete("/userbot/{channel_id}")
async def disconnect_channel_dedicated_userbot(
    channel_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Disconnects and removes dedicated userbot for the channel.
    Channel will immediately revert to using the shared userbot pool.
    """
    return await dedicated_userbot_service.disconnect_userbot(
        db=db,
        tenant_id=tenant_id,
        channel_id=channel_id
    )


@router.post("/userbot/{channel_id}/avatar")
async def update_channel_userbot_avatar(
    channel_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Uploads a new profile picture to Telegram for the channel's dedicated userbot.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="يرجى رفع ملف صورة صالح (JPEG أو PNG)")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="حجم الصورة كبير جداً (الحد الأقصى 10 ميجابايت)")

    return await dedicated_userbot_service.upload_userbot_avatar(db, channel_id, contents)


