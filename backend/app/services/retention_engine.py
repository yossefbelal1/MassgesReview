import re
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from telethon import TelegramClient
from telethon.tl.types import (
    ChannelAdminLogEventActionParticipantLeave,
    ChannelAdminLogEventActionParticipantJoin,
    ChannelAdminLogEventActionParticipantJoinByInvite,
    ChannelAdminLogEventActionParticipantJoinByRequest,
    ChannelAdminLogEvent
)

from backend.app.core.database import SessionLocal
from backend.app.models.models import (
    Channel, AudienceMember, RecoveryCase, RecoveryMessage, RetentionSetting, Tenant
)
from backend.app.services.userbot_pool import userbot_pool

logger = logging.getLogger("reviewflow.retention_engine")

# ── Intent Classifier ────────────────────────────────────────────────────────
INTENT_PATTERNS = {
    "MISTAKE_OR_LOST_LINK": [
        r"غلط", r"بالغلط", r"مسحت", r"حذفت", r"راحت", r"ضيعت", r"لينك", r"رابط", 
        r"ارجع", r"ضيفني", r"ممكن رابط", r"ابعت الرابط", r"فين القناة", r"mistake", 
        r"accidental", r"lost", r"link", r"rejoin", r"invite"
    ],
    "TOO_MANY_MESSAGES": [
        r"كتير", r"كثير", r"رسائل", r"رسايل", r"اشعارات", r"إشعارات", r"ازعاج", 
        r"إزعاج", r"دوشة", r"صداع", r"زحمة", r"spam", r"too many", r"notifications", 
        r"noise", r"loud"
    ],
    "CONTENT_CRITIQUE": [
        r"خسر", r"خسارة", r"خسرت", r"صفقات", r"تحليل", r"محتوى", r"مش عاجبني", 
        r"مش شغال", r"فاشل", r"بطلت", r"تداول", r"loss", r"bad", r"unprofitable", 
        r"stopped"
    ],
    "OPT_OUT": [
        r"فكك", r"متبعتش", r"stop", r"بلوك", r"كفاية", r"الغاء", r"إلغاء", 
        r"unsubscribe", r"leave me", r"don't message", r"dont message"
    ]
}

def classify_user_reply(text: str) -> Tuple[str, str]:
    """
    Multilingual intent and reason classifier for member replies.
    Returns (category, intent_code).
    """
    if not text:
        return "OTHER", "UNKNOWN"

    norm_text = text.lower().strip()

    # Check for OPT_OUT first
    for pattern in INTENT_PATTERNS["OPT_OUT"]:
        if re.search(pattern, norm_text):
            return "OPT_OUT", "REQUESTED_STOP"

    # Check for MISTAKE_OR_LOST_LINK
    for pattern in INTENT_PATTERNS["MISTAKE_OR_LOST_LINK"]:
        if re.search(pattern, norm_text):
            return "MISTAKE_OR_LOST_LINK", "WANTS_REJOIN_LINK"

    # Check for TOO_MANY_MESSAGES
    for pattern in INTENT_PATTERNS["TOO_MANY_MESSAGES"]:
        if re.search(pattern, norm_text):
            return "TOO_MANY_MESSAGES", "EXCESSIVE_NOTIFICATIONS"

    # Check for CONTENT_CRITIQUE
    for pattern in INTENT_PATTERNS["CONTENT_CRITIQUE"]:
        if re.search(pattern, norm_text):
            return "CONTENT_CRITIQUE", "CONTENT_FEEDBACK"

    return "OTHER", "GENERAL_RESPONSE"


# ── Retention Engine Core Service ───────────────────────────────────────────
class RetentionEngine:
    """
    Audience Retention, Leave Detection, and Conversational Win-back Engine.
    """

    async def sync_channel_admin_log(self, db: Session, channel: Channel, client: TelegramClient) -> int:
        """
        Polls channel Admin Log (Recent Actions) for member leaves and joins.
        Maintains persistent cursor last_seen_admin_log_id to prevent duplicates.
        """
        if not channel.is_connected or not channel.tenant or not channel.tenant.is_active:
            return 0

        # Ensure retention settings exist for this channel
        settings = db.query(RetentionSetting).filter(RetentionSetting.channel_id == channel.id).first()
        if not settings:
            settings = RetentionSetting(
                tenant_id=channel.tenant_id,
                channel_id=channel.id,
                is_retention_enabled=True,
                initial_delay_seconds=180,
                max_daily_contacts=30
            )
            db.add(settings)
            db.commit()
            db.refresh(settings)

        if not settings.is_retention_enabled:
            return 0

        chat_peer = int(channel.telegram_chat_id)
        try:
            entity = await client.get_entity(chat_peer)
        except Exception as e:
            logger.debug(f"Could not resolve entity for channel {channel.title}: {e}")
            return 0

        last_id = int(channel.last_seen_admin_log_id or 0)
        events_processed = 0

        try:
            # Fetch recent admin log events for joins, leaves, and invites
            log_events = await client.get_admin_log(
                entity,
                join=True,
                leave=True,
                invite=True,
                limit=30,
                min_id=last_id
            )

            if not log_events:
                return 0

            max_seen_id = last_id

            # Process in chronological order (oldest to newest)
            for ev in reversed(log_events):
                event_id = int(ev.id)
                if event_id > max_seen_id:
                    max_seen_id = event_id

                if event_id <= last_id:
                    continue

                user_id = str(ev.user_id)
                event_date = ev.date.replace(tzinfo=timezone.utc) if ev.date.tzinfo is None else ev.date

                # Fetch member entity details
                first_name, last_name, username, access_hash = None, None, None, None
                try:
                    user_entity = await client.get_entity(ev.user_id)
                    first_name = getattr(user_entity, 'first_name', None)
                    last_name = getattr(user_entity, 'last_name', None)
                    username = getattr(user_entity, 'username', None)
                    raw_hash = getattr(user_entity, 'access_hash', None)
                    if raw_hash is not None:
                        access_hash = str(raw_hash)
                except Exception:
                    pass

                # ── Handle LEAVE ─────────────────────────────────────────────
                if isinstance(ev.action, ChannelAdminLogEventActionParticipantLeave):
                    events_processed += 1
                    await self._handle_member_leave(
                        db=db,
                        channel=channel,
                        settings=settings,
                        telegram_user_id=user_id,
                        leave_event_id=str(ev.id),
                        event_date=event_date,
                        first_name=first_name,
                        last_name=last_name,
                        username=username,
                        access_hash=access_hash
                    )

                # ── Handle JOIN / REJOIN ─────────────────────────────────────
                elif isinstance(ev.action, (
                    ChannelAdminLogEventActionParticipantJoin,
                    ChannelAdminLogEventActionParticipantJoinByInvite,
                    ChannelAdminLogEventActionParticipantJoinByRequest
                )):
                    events_processed += 1
                    await self._handle_member_join(
                        db=db,
                        channel=channel,
                        settings=settings,
                        telegram_user_id=user_id,
                        event_date=event_date,
                        first_name=first_name,
                        last_name=last_name,
                        username=username,
                        access_hash=access_hash
                    )

            if max_seen_id > last_id:
                channel.last_seen_admin_log_id = str(max_seen_id)
                db.commit()

        except Exception as err:
            logger.error(f"[!] Error fetching admin log for {channel.title}: {err}", exc_info=True)

        return events_processed

    async def _handle_member_leave(
        self,
        db: Session,
        channel: Channel,
        settings: RetentionSetting,
        telegram_user_id: str,
        leave_event_id: str,
        event_date: datetime,
        first_name: Optional[str],
        last_name: Optional[str],
        username: Optional[str],
        access_hash: Optional[str] = None
    ):
        """Processes a detected member leave event with idempotency."""
        # Find or create AudienceMember
        member = db.query(AudienceMember).filter(
            AudienceMember.channel_id == channel.id,
            AudienceMember.telegram_user_id == telegram_user_id
        ).first()

        if not member:
            member = AudienceMember(
                tenant_id=channel.tenant_id,
                channel_id=channel.id,
                telegram_user_id=telegram_user_id,
                access_hash=access_hash,
                first_name=first_name,
                last_name=last_name,
                username=username,
                status="LEFT",
                first_joined_at=event_date,
                last_left_at=event_date
            )
            db.add(member)
            db.flush()
        else:
            member.status = "LEFT"
            member.last_left_at = event_date
            if access_hash: member.access_hash = access_hash
            if first_name: member.first_name = first_name
            if last_name: member.last_name = last_name
            if username: member.username = username
            db.flush()

        # Check if a case already exists for this exact leave event
        existing_case = db.query(RecoveryCase).filter(
            RecoveryCase.channel_id == channel.id,
            RecoveryCase.leave_event_id == leave_event_id
        ).first()

        if existing_case:
            return

        # Check if member permanently opted out
        if member.status == "OPT_OUT":
            logger.info(f"Skipping leave recovery for user {telegram_user_id}: Member opted out.")
            return

        # Schedule recovery contact with safe staggering
        now = datetime.now(timezone.utc)
        delay_sec = settings.initial_delay_seconds if settings.initial_delay_seconds is not None else 180

        # Check if leave happened in the past (e.g. historical admin log read)
        is_historical = (now - event_date).total_seconds() > (48 * 3600)

        if is_historical:
            # Historical events are tracked in directory and cases but not auto-blasted
            initial_status = "DETECTED"
            scheduled_at = None
        else:
            initial_status = "SCHEDULED"
            if event_date + timedelta(seconds=delay_sec) <= now:
                # Distribute outreach so cases don't fire concurrently
                from sqlalchemy import func
                max_sched = db.query(func.max(RecoveryCase.scheduled_contact_at)).filter(
                    RecoveryCase.channel_id == channel.id,
                    RecoveryCase.status == "SCHEDULED"
                ).scalar()
                base_time = max(now, max_sched if max_sched else now)
                scheduled_at = base_time + timedelta(seconds=30)
            else:
                scheduled_at = event_date + timedelta(seconds=delay_sec)

        case = RecoveryCase(
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            member_id=member.id,
            telegram_user_id=telegram_user_id,
            leave_event_id=leave_event_id,
            status=initial_status,
            contactable=True,
            scheduled_contact_at=scheduled_at,
            created_at=event_date
        )
        db.add(case)
        db.commit()
        logger.info(f"[🎯 Retention Case Created]: Channel '{channel.title}' | User {telegram_user_id} (@{username or 'no_user'}) [{initial_status}]")

    async def _handle_member_join(
        self,
        db: Session,
        channel: Channel,
        settings: RetentionSetting,
        telegram_user_id: str,
        event_date: datetime,
        first_name: Optional[str],
        last_name: Optional[str],
        username: Optional[str],
        access_hash: Optional[str] = None
    ):
        """Processes a detected join/rejoin event and attributes win-back."""
        member = db.query(AudienceMember).filter(
            AudienceMember.channel_id == channel.id,
            AudienceMember.telegram_user_id == telegram_user_id
        ).first()

        is_new_member = False
        if not member:
            is_new_member = True
            member = AudienceMember(
                tenant_id=channel.tenant_id,
                channel_id=channel.id,
                telegram_user_id=telegram_user_id,
                access_hash=access_hash,
                first_name=first_name,
                last_name=last_name,
                username=username,
                status="ACTIVE",
                first_joined_at=event_date
            )
            db.add(member)
            db.flush()
        else:
            member.status = "ACTIVE"
            member.last_rejoined_at = event_date
            if access_hash: member.access_hash = access_hash
            if first_name: member.first_name = first_name
            if last_name: member.last_name = last_name
            if username: member.username = username
            db.flush()

        # ── Rejoin Attribution ───────────────────────────────────────────────
        open_case = db.query(RecoveryCase).filter(
            RecoveryCase.channel_id == channel.id,
            RecoveryCase.telegram_user_id == telegram_user_id,
            RecoveryCase.status.in_(["SCHEDULED", "CONTACTED", "CONVERSATION_ACTIVE", "LINK_DELIVERED", "NO_RESPONSE"])
        ).order_by(RecoveryCase.created_at.desc()).first()

        if open_case:
            open_case.status = "RECOVERED"
            open_case.rejoined_at = event_date
            if open_case.created_at:
                diff = (event_date - open_case.created_at.replace(tzinfo=timezone.utc)).total_seconds()
                open_case.time_to_rejoin_seconds = max(0, int(diff))

            member.status = "RECOVERED"

            sys_msg = RecoveryMessage(
                case_id=open_case.id,
                direction="OUTBOUND",
                sender_type="SYSTEM",
                text=f"🎉 تم رصد عودة العضو بنجاح إلى القناة بعد {open_case.time_to_rejoin_seconds // 60} دقيقة!",
                sent_at=event_date
            )
            db.add(sys_msg)
            db.commit()
            logger.info(f"[🏆 RECOVERY SUCCESS]: User {telegram_user_id} (@{username or 'no_user'}) successfully rejoined channel '{channel.title}'!")
            return

        db.commit()

        # ── Welcome Flow for new members ─────────────────────────────────────
        if is_new_member and settings.is_welcome_enabled and settings.welcome_message_template:
            int_hash = int(access_hash) if access_hash else None
            await self._trigger_welcome_message(channel, settings, telegram_user_id, first_name, username, int_hash)

    async def process_pending_recovery_contacts(self, db: Session):
        """
        Executes scheduled initial recovery contacts that are due.
        Processes safely one case per loop with respectful anti-spam pacing.
        """
        now = datetime.now(timezone.utc)
        pending_case = db.query(RecoveryCase).filter(
            RecoveryCase.status == "SCHEDULED",
            RecoveryCase.scheduled_contact_at <= now
        ).order_by(RecoveryCase.scheduled_contact_at.asc()).first()

        if not pending_case:
            return

        case = pending_case
        channel = db.query(Channel).filter(Channel.id == case.channel_id).first()
        if not channel:
            return

        settings = db.query(RetentionSetting).filter(RetentionSetting.channel_id == channel.id).first()
        first_name = case.member.first_name if case.member else "يا غالي"
        username = case.member.username if case.member else None

        # Default empathetic, respectful recovery opener
        default_template = (
            f"مرحباً {first_name}، لاحظنا مغادرتك لقناة {channel.title} وحبينا نتطمن عليك 🌹\n"
            f"هل خرجت بالخطأ أو كان هناك أمر أزعجك؟ رأيك يهمنا جداً لتطوير القناة."
        )
        outbound_text = settings.recovery_first_message_template if (settings and settings.recovery_first_message_template) else default_template

        # Attempt sending via UserbotPool with access_hash if available
        access_hash = None
        if case.member and case.member.access_hash:
            try:
                access_hash = int(case.member.access_hash)
            except (ValueError, TypeError):
                access_hash = None

        res = await userbot_pool.send_direct_message(
            target_user_id=int(case.telegram_user_id),
            text=outbound_text,
            channel_id=channel.id,
            target_username=username,
            access_hash=access_hash
        )

        if res["success"]:
            case.status = "CONTACTED"
            case.contactable = True
            case.assigned_userbot = res["userbot_username"]
            case.first_contacted_at = now
            case.uncontactable_reason = None

            msg = RecoveryMessage(
                case_id=case.id,
                direction="OUTBOUND",
                sender_type="USERBOT",
                userbot_username=res["userbot_username"],
                text=outbound_text,
                sent_at=now
            )
            db.add(msg)
            db.commit()
            logger.info(f"[📬 Recovery Message Sent]: To user {case.telegram_user_id} (@{username or 'no_user'}) via {res['userbot_username']}")

        elif res.get("uncontactable_reason") and not res.get("can_retry", True):
            # STRICTLY for permanent Telegram user privacy restrictions or blocked/deleted accounts
            case.status = "UNCONTACTABLE"
            case.contactable = False
            case.uncontactable_reason = res["uncontactable_reason"]
            db.commit()
            logger.info(f"[🛡️ Genuine Uncontactable]: User {case.telegram_user_id} ({res['uncontactable_reason']})")

        elif res.get("can_retry", True):
            # Temporary bot quota, cooldown, or network delay -> POSTPONE, DO NOT mark uncontactable!
            retry_seconds = res.get("retry_delay_seconds", 900)
            case.scheduled_contact_at = now + timedelta(seconds=retry_seconds)
            db.commit()
            logger.info(f"[⏳ Case Delayed]: Case {case.id} delayed by {retry_seconds}s (reason: {res.get('error')})")

    async def handle_inbound_reply(self, event, active_client: TelegramClient, session_name: str):
        """
        Handles incoming private DMs from members and runs the conversational state machine.
        """
        sender = await event.get_sender()
        if not sender:
            return

        sender_id = str(sender.id)
        reply_text = event.raw_text or ""
        now = datetime.now(timezone.utc)

        db: Session = SessionLocal()
        try:
            # Find open recovery case for this member
            case = db.query(RecoveryCase).filter(
                RecoveryCase.telegram_user_id == sender_id,
                RecoveryCase.status.in_(["CONTACTED", "CONVERSATION_ACTIVE", "LINK_DELIVERED", "SCHEDULED"])
            ).order_by(RecoveryCase.created_at.desc()).first()

            if not case:
                return

            channel = db.query(Channel).filter(Channel.id == case.channel_id).first()
            settings = db.query(RetentionSetting).filter(RetentionSetting.channel_id == case.channel_id).first()

            # Classify user's reply
            category, intent_code = classify_user_reply(reply_text)
            case.leave_reason_category = category
            case.leave_reason_raw = reply_text[:500]
            case.last_response_at = now
            case.status = "CONVERSATION_ACTIVE"

            # Record inbound message
            inbound_msg = RecoveryMessage(
                case_id=case.id,
                direction="INBOUND",
                sender_type="MEMBER",
                text=reply_text,
                intent_detected=f"{category}:{intent_code}",
                sent_at=now
            )
            db.add(inbound_msg)
            db.commit()

            # ── Conversational Follow-up Logic ───────────────────────────────
            channel_link = (settings.invite_link if settings and settings.invite_link else None) or (f"https://t.me/{channel.username}" if channel and channel.username else None)

            response_text = None

            if category == "MISTAKE_OR_LOST_LINK":
                if channel_link:
                    response_text = f"ولا يهمك يا غالي، بتحصل دائماً! 🌟\nتقدر ترجع للقناة مباشرة من الرابط التالي:\n{channel_link}\nيسعدنا دائماً وجودك معنا!"
                    case.status = "LINK_DELIVERED"
                    case.link_sent_at = now
                else:
                    response_text = "ولا يهمك يا غالي! جاري إرسال رابط القناة لك حالاً، يسعدنا وجودك معنا دائماً 🌟"

            elif category == "TOO_MANY_MESSAGES":
                tips = "نصيحة سريعة: تقدر تكتم إشعارات القناة (Mute) وتفتحها وقت ما يناسبك عشان تستفيد من الصفقات بدون أي إزعاج 🔕"
                if channel_link:
                    response_text = f"نقدّر وقتك جداً ونعتذر عن أي إزعاج 🌹\n{tips}\nتقدر ترجع للقناة من هنا وقت ما تحب:\n{channel_link}"
                    case.status = "LINK_DELIVERED"
                    case.link_sent_at = now
                else:
                    response_text = f"نقدّر وقتك جداً ونعتذر عن أي إزعاج 🌹\n{tips}"

            elif category == "CONTENT_CRITIQUE":
                response_text = "شكراً جزيلاً لصراحتك ورأيك الثمين جداً! 📝 تم تسجيل ملاحظاتك وسنعمل على تحسين المحتوى والصفقات باستمرار. بابنا مفتوح لك دائماً 🌹"

            elif category == "OPT_OUT":
                case.status = "OPT_OUT"
                if case.member:
                    case.member.status = "OPT_OUT"
                response_text = "نعتذر بشدة يا غالي وتم إيقاف أي رسائل أخرى لك تماماً. نتمنى لك كل التوفيق! 🌹"

            # Send automated response if generated
            if response_text:
                await asyncio.sleep(2.0)  # Natural typing feel
                await event.respond(response_text)

                outbound_msg = RecoveryMessage(
                    case_id=case.id,
                    direction="OUTBOUND",
                    sender_type="USERBOT",
                    userbot_username=session_name,
                    text=response_text,
                    sent_at=datetime.now(timezone.utc)
                )
                db.add(outbound_msg)
                db.commit()

        except Exception as e:
            logger.error(f"[!] Error handling inbound reply from {sender_id}: {e}", exc_info=True)
        finally:
            db.close()

    async def _trigger_welcome_message(self, channel: Channel, settings: RetentionSetting, telegram_user_id: str, first_name: Optional[str], username: Optional[str] = None, access_hash: Optional[int] = None):
        """Delivers welcome message to new joiner."""
        name_display = first_name or "صديقنا العزيز"
        text = settings.welcome_message_template.replace("{name}", name_display).replace("{channel}", channel.title)
        await userbot_pool.send_direct_message(
            target_user_id=int(telegram_user_id),
            text=text,
            channel_id=channel.id,
            target_username=username,
            access_hash=access_hash
        )

retention_engine = RetentionEngine()
