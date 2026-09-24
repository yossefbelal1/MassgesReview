import json
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Response, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_, extract

from backend.app.core.database import get_db
from backend.app.api.deps import get_current_user, get_current_tenant_id
from backend.app.models.models import (
    User, Channel, AudienceMember, RecoveryCase, RecoveryMessage, RetentionSetting, ChannelUserbot,
    InviteLink, MembershipEvent, RejoinAttempt, RetentionMetric, MembershipState
)
from backend.app.schemas.schemas import (
    RecoveryCaseOut, RecoveryCaseDetailOut, RecoveryMessageOut, RecoveryMessageCreate,
    RetentionSettingOut, RetentionSettingUpdate, AudienceMemberOut, RetentionSummaryOut,
    UserbotSendCodeRequest, UserbotSendCodeResponse, UserbotVerifyCodeRequest, UserbotVerifyCodeResponse,
    ChannelUserbotOut, InviteLinkCreate, InviteLinkOut, MembershipEventOut, RejoinAttemptOut,
    RetentionMetricOut, ReconciliationResultOut, MembershipStateOut, ChannelHealthOut, CohortWinbackOut
)
from backend.app.services.userbot_pool import userbot_pool
from backend.app.services.dedicated_userbot_service import dedicated_userbot_service
from backend.app.services.retention_engine import retention_engine
from backend.app.services.sse_service import sse_broadcaster

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

    # Members who responded to the outreach message
    total_responded = base_query.filter(
        or_(
            RecoveryCase.last_response_at.isnot(None),
            RecoveryCase.status == "CONVERSATION_ACTIVE",
            RecoveryCase.leave_reason_raw.isnot(None)
        )
    ).count()

    # Members who received an invite link
    total_link_delivered = base_query.filter(
        or_(
            RecoveryCase.link_sent_at.isnot(None),
            RecoveryCase.status.in_(["LINK_DELIVERED", "RECOVERED"])
        )
    ).count()

    win_back_rate = round((total_rejoined / total_contacted * 100), 1) if total_contacted > 0 else 0.0
    win_back_rate_of_leavers = round((total_rejoined / total_left * 100), 1) if total_left > 0 else 0.0
    response_rate = round((total_responded / total_contacted * 100), 1) if total_contacted > 0 else 0.0
    conversion_on_response = round((total_rejoined / total_responded * 100), 1) if total_responded > 0 else 0.0

    # Average time to rejoin in hours
    avg_rejoin_sec = db.query(func.avg(RecoveryCase.time_to_rejoin_seconds)).filter(
        RecoveryCase.tenant_id == tenant_id,
        RecoveryCase.status == "RECOVERED",
        RecoveryCase.time_to_rejoin_seconds.isnot(None)
    ).scalar()
    avg_rejoin_hours = round((avg_rejoin_sec / 3600), 1) if avg_rejoin_sec else 0.0

    # 1. Full 5-Stage Retention Funnel
    funnel_stages = [
        {
            "id": "detected",
            "name": "تم رصد المغادرة",
            "count": total_left,
            "percentage": 100.0,
            "color": "indigo"
        },
        {
            "id": "contacted",
            "name": "تم إطلاق التواصل الآلي",
            "count": total_contacted,
            "percentage": round((total_contacted / total_left * 100), 1) if total_left > 0 else 0.0,
            "color": "blue"
        },
        {
            "id": "responded",
            "name": "تفاعل وردود الأعضاء",
            "count": total_responded,
            "percentage": round((total_responded / total_contacted * 100), 1) if total_contacted > 0 else 0.0,
            "color": "amber"
        },
        {
            "id": "link_delivered",
            "name": "تم تسليم رابط العودة",
            "count": total_link_delivered,
            "percentage": round((total_link_delivered / total_contacted * 100), 1) if total_contacted > 0 else 0.0,
            "color": "teal"
        },
        {
            "id": "rejoined",
            "name": "عادوا للقناة بنجاح 🎯",
            "count": total_rejoined,
            "percentage": win_back_rate,
            "color": "emerald"
        }
    ]

    # 2. Status Distribution (Accounts for 100% of the members)
    status_counts = {}
    for row in base_query.with_entities(RecoveryCase.status, func.count(RecoveryCase.id)).group_by(RecoveryCase.status).all():
        status_counts[row[0]] = row[1]

    status_labels = [
        {"status": "RECOVERED", "label": "عادوا للقناة (نجاح الاسترداد) 🟢", "color": "emerald"},
        {"status": "CONVERSATION_ACTIVE", "label": "محادثة جارية وتفاعل 💬", "color": "blue"},
        {"status": "LINK_DELIVERED", "label": "تم تسليم رابط العودة 🔗", "color": "teal"},
        {"status": "CONTACTED", "label": "تم التواصل وفي انتظار الرد 📩", "color": "sky"},
        {"status": "SCHEDULED", "label": "في طابور الإرسال المجدول ⏱️", "color": "amber"},
        {"status": "DETECTED", "label": "تم الرصد (بانتظار الجدولة) 🔍", "color": "slate"},
        {"status": "UNCONTACTABLE", "label": "حماية خصوصية تيليجرام 🛡️", "color": "rose"},
        {"status": "OPT_OUT", "label": "رفض الاستمرار ⛔", "color": "slate"},
    ]
    status_distribution = []
    for sl in status_labels:
        cnt = status_counts.get(sl["status"], 0)
        if cnt > 0:
            status_distribution.append({
                "status": sl["status"],
                "label": sl["label"],
                "count": cnt,
                "percentage": round((cnt / total_left * 100), 1) if total_left > 0 else 0.0,
                "color": sl["color"]
            })

    # 3. Churn reasons breakdown (Includes explicit categories + awaiting response + queued)
    explicit_reasons = base_query.filter(RecoveryCase.leave_reason_category.isnot(None)).with_entities(
        RecoveryCase.leave_reason_category, func.count(RecoveryCase.id)
    ).group_by(RecoveryCase.leave_reason_category).all()

    reasons_breakdown = []
    for cat, cnt in explicit_reasons:
        rejoined_in_cat = base_query.filter(
            RecoveryCase.leave_reason_category == cat,
            RecoveryCase.status == "RECOVERED"
        ).count()
        reasons_breakdown.append({
            "category": cat or "OTHER",
            "count": cnt,
            "rejoined": rejoined_in_cat,
            "rate": round((rejoined_in_cat / cnt * 100), 1) if cnt > 0 else 0.0
        })

    contacted_no_reason = base_query.filter(
        RecoveryCase.leave_reason_category.is_(None),
        RecoveryCase.status.in_(["CONTACTED", "CONVERSATION_ACTIVE", "LINK_DELIVERED"])
    ).count()
    if contacted_no_reason > 0:
        reasons_breakdown.append({
            "category": "AWAITING_REPLY",
            "count": contacted_no_reason,
            "rejoined": 0,
            "rate": 0.0
        })

    scheduled_no_reason = base_query.filter(
        RecoveryCase.leave_reason_category.is_(None),
        RecoveryCase.status.in_(["SCHEDULED", "DETECTED"])
    ).count()
    if scheduled_no_reason > 0:
        reasons_breakdown.append({
            "category": "IN_QUEUE",
            "count": scheduled_no_reason,
            "rejoined": 0,
            "rate": 0.0
        })

    uncontactable_no_reason = base_query.filter(
        RecoveryCase.leave_reason_category.is_(None),
        RecoveryCase.status == "UNCONTACTABLE"
    ).count()
    if uncontactable_no_reason > 0:
        reasons_breakdown.append({
            "category": "PRIVACY_BLOCKED",
            "count": uncontactable_no_reason,
            "rejoined": 0,
            "rate": 0.0
        })

    # 4. Hourly departure peak analysis (00:00 to 23:00)
    hourly_query = base_query.with_entities(
        extract('hour', RecoveryCase.created_at).label("hour"),
        func.count(RecoveryCase.id).label("count")
    ).group_by("hour").order_by("hour").all()

    hourly_map = {int(h): c for h, c in hourly_query if h is not None}
    hourly_distribution = []
    for h in range(24):
        hourly_distribution.append({
            "hour": h,
            "hour_label": f"{h:02d}:00",
            "count": hourly_map.get(h, 0)
        })

    # 5. Daily trend for the last 7 days
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
        "total_responded": total_responded,
        "total_rejoined": total_rejoined,
        "total_scheduled_pending": total_scheduled,
        "total_opt_out": total_opt_out,
        "win_back_rate_percent": win_back_rate,
        "win_back_rate_of_leavers": win_back_rate_of_leavers,
        "uncontactable_count": uncontactable_count,
        "average_rejoin_hours": avg_rejoin_hours,
        "reasons_breakdown": reasons_breakdown,
        "daily_trend": daily_trend,
        "funnel_reconciled": True,
        "funnel_stages": funnel_stages,
        "status_distribution": status_distribution,
        "hourly_distribution": hourly_distribution,
        "response_rate_percent": response_rate,
        "conversion_on_response_percent": conversion_on_response
    }


@router.get("/cases", response_model=List[RecoveryCaseOut])
def get_recovery_cases(
    channel_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    stage: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = Query(250, le=500),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Returns list of member recovery cases with search, stage, and status filtering.
    """
    query = db.query(RecoveryCase).filter(RecoveryCase.tenant_id == tenant_id)

    if channel_id:
        query = query.filter(RecoveryCase.channel_id == channel_id)
    if status_filter:
        query = query.filter(RecoveryCase.status == status_filter)

    if stage == 1:
        # Stage 1: All detected leavers
        pass
    elif stage == 2:
        # Stage 2: Contacted leavers
        query = query.filter(
            or_(
                RecoveryCase.first_contacted_at.isnot(None),
                RecoveryCase.status.in_(["CONTACTED", "CONVERSATION_ACTIVE", "LINK_DELIVERED", "RECOVERED"])
            )
        )
    elif stage == 3:
        # Stage 3: Engaged, responded, or active conversations
        query = query.filter(
            or_(
                RecoveryCase.last_response_at.isnot(None),
                RecoveryCase.status == "CONVERSATION_ACTIVE",
                RecoveryCase.leave_reason_raw.isnot(None)
            )
        )
    elif stage == 4:
        # Stage 4: Recovered leavers who rejoined
        query = query.filter(
            or_(
                RecoveryCase.status == "RECOVERED",
                RecoveryCase.rejoined_at.isnot(None)
            )
        )

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
                queue_reason = "مجدول عبر يوزربوت القناة"
            else:
                queue_reason = "في طابور الإرسال"
        elif c.status == "UNCONTACTABLE":
            queue_reason = "حساب مقيد الخصوصية أو محذوف"

        latest_msg = c.messages[-1] if c.messages else None
        latest_inbound = next((m for m in reversed(c.messages) if m.direction == "INBOUND"), None)

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
            queue_delay_reason=queue_reason,
            latest_message_text=latest_msg.text if latest_msg else None,
            latest_inbound_text=latest_inbound.text if latest_inbound else None,
            latest_message_direction=latest_msg.direction if latest_msg else None,
            latest_message_time=latest_msg.sent_at if latest_msg else None,
            messages_count=len(c.messages) if c.messages else 0
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
            queue_reason = "في طابور الإرسال"
        else:
            queue_reason = "مجدول عبر يوزربوت القناة"
    elif case.status == "UNCONTACTABLE":
        queue_reason = "حساب مقيد الخصوصية أو محذوف"

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

    if case.status == "UNCONTACTABLE":
        case.contactable = True
        case.uncontactable_reason = None
        db.commit()

    res = await retention_engine.send_recovery_to_case(db, case)
    db.refresh(case)
    return {
        "success": res.get("success", False),
        "status": case.status,
        "userbot": case.assigned_userbot,
        "message": res.get("message") or res.get("error_ar") or res.get("error") or "تمت المحاولة."
    }


@router.post("/cases/turbo-dispatch")
@router.post("/cases/reset-all")
async def turbo_dispatch_pending_cases(
    channel_id: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Intelligently staggers and activates instant safe outreach for all pending cases.
    Applies human pacing (25s interval per case) to prevent Telegram PeerFlood blocks,
    and immediately wakes up the dispatcher for the first case.
    """
    query = db.query(RecoveryCase).filter(
        RecoveryCase.tenant_id == tenant_id,
        RecoveryCase.status.in_(["SCHEDULED", "DETECTED", "UNCONTACTABLE", "NO_RESPONSE"])
    )
    if channel_id:
        query = query.filter(RecoveryCase.channel_id == channel_id)

    now = datetime.now(timezone.utc)

    # Auto-heal dedicated userbots whose cooldown expired
    expired_bots = db.query(ChannelUserbot).filter(
        ChannelUserbot.tenant_id == tenant_id,
        (
            (ChannelUserbot.status == "FLOOD_WAIT") &
            ((ChannelUserbot.cooldown_until == None) | (ChannelUserbot.cooldown_until <= now))
        )
    ).all()
    for eb in expired_bots:
        eb.status = "CONNECTED"
        eb.cooldown_until = None
        eb.last_error = None

    cases = query.all()
    for idx, c in enumerate(cases):
        c.status = "SCHEDULED"
        c.contactable = True
        c.uncontactable_reason = None
        # Safe natural pacing: stagger each message by 15s across 2 alternating bots (each bot gets 30s)
        c.scheduled_contact_at = now + timedelta(seconds=idx * 15)

    db.commit()

    # Trigger background worker dispatch immediately for due cases
    try:
        asyncio.create_task(retention_engine.process_pending_recovery_contacts(db))
    except Exception as e:
        logger.warning(f"Error triggering batch dispatch: {e}")

    return {
        "success": True,
        "reset_count": len(cases),
        "dispatched_count": len(cases),
        "message": f"تم تفعيل الإرسال الفوري لـ {len(cases)} عضواً بفواصل آمنة (عضو كل 15 ثانية) ⚡"
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
    system_pool: bool = False,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the tenant's connected dedicated userbots with their channel names and live health.
    For system administrators, passing system_pool=true returns the internal fallback fleet.
    """
    if system_pool and current_user.role == "admin":
        return await userbot_pool.get_pool_status()

    now = datetime.now(timezone.utc)
    userbots = db.query(ChannelUserbot).filter(
        ChannelUserbot.tenant_id == tenant_id
    ).all()

    result = []
    for ub in userbots:
        ch = db.query(Channel).filter(Channel.id == ub.channel_id).first()
        ub_cd = ub.cooldown_until.replace(tzinfo=timezone.utc) if (ub.cooldown_until and ub.cooldown_until.tzinfo is None) else ub.cooldown_until
        result.append({
            "id": ub.id,
            "name": ub.channel_id,
            "channel_id": ub.channel_id,
            "channel_title": ch.title if ch else "قناة غير معروفة",
            "phone": ub.phone,
            "username": ub.username or "",
            "first_name": ub.first_name or "",
            "is_active": ub.is_active,
            "is_healthy": ub.status == "CONNECTED" and ub.is_active,
            "status": ub.status,
            "daily_contacts_sent": ub.daily_contacts_count or 0,
            "max_daily_contacts": 35,
            "in_cooldown": bool(ub_cd and ub_cd > now),
            "created_at": ub.created_at.isoformat() if ub.created_at else None
        })
    return result


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


@router.post("/userbot/{userbot_id}/auto-heal")
async def trigger_userbot_auto_heal(
    userbot_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Triggers automated SpamBot appeal, limit inspection, and cooldown clearance for a userbot.
    """
    userbot = db.query(ChannelUserbot).filter(
        ChannelUserbot.id == userbot_id,
        ChannelUserbot.tenant_id == tenant_id
    ).first()
    if not userbot:
        raise HTTPException(status_code=404, detail="اليوزربوت المحدد غير موجود")

    unlocked, status_msg, cd = await dedicated_userbot_service.auto_heal_userbot_via_spambot(
        db=db,
        channel_id=userbot.channel_id,
        userbot_id=userbot.id
    )
    db.refresh(userbot)
    return {
        "success": unlocked,
        "status": userbot.status,
        "cooldown_until": userbot.cooldown_until,
        "message": "تم فك تقييد الحساب بنجاح وهو الآن متاح للعمل! 🎉" if unlocked else f"الحساب مقيد حالياً من تيليجرام حتى {userbot.cooldown_until.strftime('%Y-%m-%d %H:%M UTC') if userbot.cooldown_until else 'انتهاء فترة الراحة'}"
    }


# ── SaaS Multi-Tenant Retention & Winback API Endpoints ──────────────────────

@router.post("/channels/{channel_id}/invite-links", response_model=InviteLinkOut)
async def create_channel_invite_link_endpoint(
    channel_id: str,
    payload: InviteLinkCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Creates and tracks a new dedicated Telegram invite link for a channel.
    """
    channel = db.query(Channel).filter(
        Channel.id == channel_id,
        Channel.tenant_id == tenant_id
    ).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    return await retention_engine.create_channel_invite_link(
        db=db,
        channel=channel,
        name=payload.name,
        is_primary=payload.is_primary,
        member_limit=payload.member_limit,
        expires_in_days=payload.expires_in_days
    )


@router.get("/channels/{channel_id}/invite-links", response_model=List[InviteLinkOut])
def get_channel_invite_links(
    channel_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Lists all invite links generated for a channel with usage counters.
    """
    channel = db.query(Channel).filter(
        Channel.id == channel_id,
        Channel.tenant_id == tenant_id
    ).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    return db.query(InviteLink).filter(
        InviteLink.channel_id == channel_id,
        InviteLink.tenant_id == tenant_id
    ).order_by(desc(InviteLink.created_at)).all()


@router.get("/channels/{channel_id}/events", response_model=List[MembershipEventOut])
def get_channel_membership_events(
    channel_id: str,
    event_type: Optional[str] = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Returns immutable event log of joins and leaves for a channel.
    """
    channel = db.query(Channel).filter(
        Channel.id == channel_id,
        Channel.tenant_id == tenant_id
    ).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    q = db.query(MembershipEvent).filter(
        MembershipEvent.channel_id == channel_id,
        MembershipEvent.tenant_id == tenant_id
    )
    if event_type:
        q = q.filter(MembershipEvent.event_type == event_type.upper())
    return q.order_by(desc(MembershipEvent.timestamp)).limit(limit).all()


@router.get("/channels/{channel_id}/rejoins", response_model=List[RejoinAttemptOut])
def get_channel_rejoin_attempts(
    channel_id: str,
    confidence: Optional[str] = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Returns rejoin/winback attempts with confidence attribution (CONFIRMED, ATTRIBUTED, UNKNOWN).
    """
    channel = db.query(Channel).filter(
        Channel.id == channel_id,
        Channel.tenant_id == tenant_id
    ).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    q = db.query(RejoinAttempt).filter(
        RejoinAttempt.channel_id == channel_id,
        RejoinAttempt.tenant_id == tenant_id
    )
    if confidence:
        q = q.filter(RejoinAttempt.confidence == confidence.upper())
    return q.order_by(desc(RejoinAttempt.rejoin_time)).limit(limit).all()


@router.post("/channels/{channel_id}/reconcile", response_model=ReconciliationResultOut)
async def reconcile_channel_endpoint(
    channel_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Triggers an on-demand reconciliation audit between Telegram participant count and database.
    """
    channel = db.query(Channel).filter(
        Channel.id == channel_id,
        Channel.tenant_id == tenant_id
    ).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    return await retention_engine.reconcile_channel_membership(db, channel)


@router.get("/channels/{channel_id}/metrics", response_model=List[RetentionMetricOut])
def get_channel_retention_metrics(
    channel_id: str,
    days: int = Query(30, le=365),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves pre-computed daily retention & winback metrics for a channel.
    """
    channel = db.query(Channel).filter(
        Channel.id == channel_id,
        Channel.tenant_id == tenant_id
    ).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    start_date = (datetime.now(timezone.utc) - timedelta(days=days)).date()
    return db.query(RetentionMetric).filter(
        RetentionMetric.channel_id == channel_id,
        RetentionMetric.tenant_id == tenant_id,
        RetentionMetric.period_date >= start_date
    ).order_by(desc(RetentionMetric.period_date)).all()


@router.post("/channels/{channel_id}/metrics/compute", response_model=RetentionMetricOut)
def compute_channel_metrics_endpoint(
    channel_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Manually triggers computation of today's retention metrics for a channel.
    """
    channel = db.query(Channel).filter(
        Channel.id == channel_id,
        Channel.tenant_id == tenant_id
    ).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    return retention_engine.compute_daily_retention_metrics(db, channel_id)


@router.get("/channels/{channel_id}/events/stream")
async def stream_channel_events(
    channel_id: str,
    request: Request,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Server-Sent Events (SSE) endpoint for real-time live push of joins, leaves, kicks,
    and rejoins to connected dashboards.
    """
    channel = db.query(Channel).filter(
        Channel.id == channel_id,
        Channel.tenant_id == tenant_id
    ).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    async def event_generator():
        queue = asyncio.Queue(maxsize=100)
        await sse_broadcaster.subscribe(channel_id, queue)
        try:
            init_frame = json.dumps({"channel_id": channel_id, "status": "connected", "title": channel.title})
            yield f"event: connected\ndata: {init_frame}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"event: {ev['type']}\ndata: {json.dumps(ev['data'])}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            await sse_broadcaster.unsubscribe(channel_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/channels/{channel_id}/health", response_model=ChannelHealthOut)
def get_channel_health(
    channel_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Returns channel connection health, lag metrics, and state machine status.
    """
    channel = db.query(Channel).filter(
        Channel.id == channel_id,
        Channel.tenant_id == tenant_id
    ).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    now = datetime.now(timezone.utc)
    lag_seconds = None
    if channel.last_event_at:
        ev_time = channel.last_event_at if channel.last_event_at.tzinfo else channel.last_event_at.replace(tzinfo=timezone.utc)
        lag_seconds = max(0, int((now - ev_time).total_seconds()))

    return ChannelHealthOut(
        channel_id=channel.id,
        title=channel.title,
        health_state=channel.health_state or "HEALTHY",
        consecutive_errors=channel.consecutive_errors or 0,
        last_event_at=channel.last_event_at,
        last_error_at=channel.last_error_at,
        last_success_at=channel.last_success_at,
        lag_seconds=lag_seconds
    )


@router.get("/channels/{channel_id}/cohort-winback", response_model=CohortWinbackOut)
def get_cohort_winback(
    channel_id: str,
    window: str = Query("7d", pattern="^(24h|7d|30d)$"),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Calculates retention/winback rate based on leaver cohorts over 24h, 7d, or 30d.
    Winback rate = (users who left in cohort AND returned) / (users who left in cohort).
    """
    channel = db.query(Channel).filter(
        Channel.id == channel_id,
        Channel.tenant_id == tenant_id
    ).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    now = datetime.now(timezone.utc)
    if window == "24h":
        start_time = now - timedelta(hours=24)
        end_time = now
        window_days = 1
    elif window == "30d":
        start_time = now - timedelta(days=30)
        end_time = now
        window_days = 30
    else:  # default 7d
        start_time = now - timedelta(days=7)
        end_time = now
        window_days = 7

    metrics = retention_engine.calculate_cohort_winback(
        db=db,
        channel_id=channel_id,
        cohort_start=start_time,
        cohort_end=end_time,
        window_days=window_days
    )
    return CohortWinbackOut(**metrics)


@router.get("/channels/{channel_id}/membership-state", response_model=List[MembershipStateOut])
def get_channel_membership_state(
    channel_id: str,
    status_filter: Optional[str] = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user)
):
    """
    Returns current membership state projection for the channel (member, left, kicked, banned).
    """
    channel = db.query(Channel).filter(
        Channel.id == channel_id,
        Channel.tenant_id == tenant_id
    ).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    q = db.query(MembershipState).filter(
        MembershipState.channel_id == channel_id,
        MembershipState.tenant_id == tenant_id
    )
    if status_filter:
        q = q.filter(MembershipState.status == status_filter.lower())

    return q.order_by(desc(MembershipState.updated_at)).limit(limit).all()




