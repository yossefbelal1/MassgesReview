import re
import uuid
import random
import asyncio
import logging
from datetime import datetime, timezone, timedelta, date
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
    Channel, AudienceMember, RecoveryCase, RecoveryMessage, RetentionSetting, Tenant, ChannelUserbot,
    InviteLink, MembershipEvent, RejoinAttempt, RetentionMetric
)
from backend.app.services.userbot_pool import userbot_pool
from backend.app.services.dedicated_userbot_service import dedicated_userbot_service

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
    def __init__(self):
        self._rr_index: int = 0

    async def get_admin_client_for_channel(self, channel: Channel, default_client: TelegramClient) -> TelegramClient:
        """
        Finds a client that has admin rights to view the admin log of this channel.
        Checks default client first, then dedicated channel userbot, then all pool sessions.
        """
        target = channel.username.strip().lstrip('@') if channel.username else int(channel.telegram_chat_id)

        # 1. First test default_client
        try:
            ent = await default_client.get_entity(target)
            if getattr(ent, 'admin_rights', None) is not None:
                return default_client
        except Exception:
            pass

        # 2. Check dedicated userbot for this channel
        db = SessionLocal()
        try:
            dedicated = db.query(ChannelUserbot).filter(
                ChannelUserbot.channel_id == channel.id,
                ChannelUserbot.is_active == True
            ).first()
            if dedicated and dedicated.string_session:
                try:
                    d_client = await dedicated_userbot_service.get_client_for_channel(channel.id, dedicated.string_session)
                    if d_client and d_client.is_connected():
                        ent = await d_client.get_entity(target)
                        if getattr(ent, 'admin_rights', None) is not None:
                            logger.info(f"[🔑 Admin Client]: Using dedicated userbot for '{channel.title}' admin log.")
                            return d_client
                except Exception:
                    pass
        finally:
            db.close()

        # 3. Check all userbot pool sessions
        for s in userbot_pool.sessions:
            try:
                cl = await s.get_client()
                if cl and cl != default_client:
                    ent = await cl.get_entity(target)
                    if getattr(ent, 'admin_rights', None) is not None:
                        logger.info(f"[🔑 Admin Client]: Using session '{s.name}' for channel '{channel.title}' admin log.")
                        return cl
            except Exception:
                continue

        return default_client

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
                initial_delay_seconds=5,
                max_daily_contacts=30
            )
            db.add(settings)
            db.commit()
            db.refresh(settings)

        if not settings.is_retention_enabled:
            return 0

        # Ensure we have an admin client capable of reading the admin log
        active_client = await self.get_admin_client_for_channel(channel, client)

        # Resolve entity safely
        entity = None
        if channel.username:
            try:
                entity = await active_client.get_entity(channel.username.strip().lstrip('@'))
            except Exception:
                pass
        if not entity:
            try:
                entity = await active_client.get_entity(int(channel.telegram_chat_id))
            except Exception as e:
                logger.warning(f"Could not resolve entity for channel {channel.title}: {e}")
                return 0

        last_id = int(channel.last_seen_admin_log_id or 0)
        events_processed = 0

        try:
            # Paginate backwards from newest to last_id in chunks of 100 (up to 500 events max per sync cycle)
            log_events = []
            curr_max_id = 0
            for _ in range(5):
                kwargs = {
                    "join": True,
                    "leave": True,
                    "invite": True,
                    "limit": 100,
                    "min_id": last_id
                }
                if curr_max_id > 0:
                    kwargs["max_id"] = curr_max_id

                chunk = await active_client.get_admin_log(entity, **kwargs)
                if not chunk:
                    break
                log_events.extend(chunk)
                if len(chunk) < 100:
                    break
                curr_max_id = min(int(ev.id) for ev in chunk)

            if not log_events:
                channel.last_admin_log_sync_at = datetime.now(timezone.utc)
                channel.sync_status = "ACTIVE"
                db.commit()
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

                # Extract member entity details from the admin log event itself
                first_name, last_name, username, access_hash = None, None, None, None
                try:
                    user_entity = getattr(ev, 'user', None)
                    if not user_entity and hasattr(ev, 'entities') and ev.user_id in ev.entities:
                        user_entity = ev.entities[ev.user_id]
                    if not user_entity and hasattr(ev, '_entities') and ev.user_id in ev._entities:
                        user_entity = ev._entities[ev.user_id]
                    if not user_entity:
                        try:
                            user_entity = await active_client.get_entity(ev.user_id)
                        except Exception:
                            pass
                    if user_entity:
                        first_name = getattr(user_entity, 'first_name', None)
                        last_name = getattr(user_entity, 'last_name', None)
                        username = getattr(user_entity, 'username', None)
                        raw_hash = getattr(user_entity, 'access_hash', None)
                        if raw_hash is not None:
                            access_hash = str(raw_hash)
                except Exception:
                    pass

                # ── Handle LEAVE ─────────────────────────────────────────────
                if isinstance(ev.action, ChannelAdminLogEventActionParticipantLeave) or getattr(ev, 'left', False):
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
                )) or getattr(ev, 'joined', False) or getattr(ev, 'joined_by_invite', False):
                    invite_link_str = None
                    if hasattr(ev.action, 'invite') and ev.action.invite:
                        invite_link_str = getattr(ev.action.invite, 'link', None) or getattr(ev.action.invite, 'slug', None)

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
                        access_hash=access_hash,
                        invite_link_str=invite_link_str
                    )

            channel.last_admin_log_sync_at = datetime.now(timezone.utc)
            channel.sync_status = "ACTIVE"
            if max_seen_id > last_id:
                channel.last_seen_admin_log_id = str(max_seen_id)
            db.commit()

        except Exception as err:
            logger.error(f"[!] Error fetching admin log for {channel.title}: {err}", exc_info=True)
            channel.sync_status = "ERROR"
            try:
                db.commit()
            except Exception:
                pass

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

        # Check if member already has an open or active recovery case for this channel
        open_case = db.query(RecoveryCase).filter(
            RecoveryCase.channel_id == channel.id,
            RecoveryCase.telegram_user_id == telegram_user_id,
            RecoveryCase.status.in_(["SCHEDULED", "CONTACTED", "CONVERSATION_ACTIVE", "LINK_DELIVERED"])
        ).first()

        if open_case:
            logger.info(f"Skipping duplicate case: User {telegram_user_id} already has active case {open_case.id} [{open_case.status}]")
            return

        # Check if member permanently opted out
        if member.status == "OPT_OUT":
            logger.info(f"Skipping leave recovery for user {telegram_user_id}: Member opted out.")
            return

        # Schedule recovery contact immediately (zero delay as commanded by user)
        now = datetime.now(timezone.utc)
        initial_status = "SCHEDULED"
        scheduled_at = now

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

        # Record raw immutable membership event
        raw_event = MembershipEvent(
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            telegram_user_id=telegram_user_id,
            event_type="LEAVE",
            source="ADMIN_LOG",
            extra_metadata={
                "leave_event_id": leave_event_id,
                "first_name": first_name,
                "username": username
            },
            timestamp=event_date
        )
        db.add(raw_event)

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
        access_hash: Optional[str] = None,
        invite_link_str: Optional[str] = None
    ):
        """Processes a detected join/rejoin event, attributes win-back, and logs membership events."""
        member = db.query(AudienceMember).filter(
            AudienceMember.channel_id == channel.id,
            AudienceMember.telegram_user_id == telegram_user_id
        ).first()

        # Resolve tracked invite link if provided
        invite_record = None
        if invite_link_str:
            clean_link = invite_link_str.strip()
            invite_record = db.query(InviteLink).filter(
                InviteLink.channel_id == channel.id,
                or_(InviteLink.invite_link == clean_link, InviteLink.invite_link.endswith(clean_link))
            ).first()
            if invite_record:
                invite_record.usage_count = (invite_record.usage_count or 0) + 1

        invite_id = invite_record.id if invite_record else None

        # Record raw immutable membership event
        raw_event = MembershipEvent(
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            telegram_user_id=telegram_user_id,
            event_type="JOIN",
            invite_id=invite_id,
            source="ADMIN_LOG",
            extra_metadata={
                "first_name": first_name,
                "username": username,
                "invite_link": invite_link_str
            },
            timestamp=event_date
        )
        db.add(raw_event)

        is_new_member = False
        previous_left_at = None
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
            previous_left_at = member.last_left_at
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
            RecoveryCase.status.in_(["SCHEDULED", "CONTACTED", "CONVERSATION_ACTIVE", "LINK_DELIVERED", "NO_RESPONSE", "UNCONTACTABLE"])
        ).order_by(RecoveryCase.created_at.desc()).first()

        # If user left previously or had a recovery case, record a RejoinAttempt
        if previous_left_at or open_case:
            leave_time = previous_left_at or (open_case.created_at if open_case else event_date)
            if leave_time.tzinfo is None:
                leave_time = leave_time.replace(tzinfo=timezone.utc)
            rejoin_time = event_date
            if rejoin_time.tzinfo is None:
                rejoin_time = rejoin_time.replace(tzinfo=timezone.utc)

            diff_seconds = max(0, int((rejoin_time - leave_time).total_seconds()))

            # Determine confidence level
            if invite_id:
                confidence = "CONFIRMED"
            elif open_case and open_case.status in ["CONTACTED", "CONVERSATION_ACTIVE", "LINK_DELIVERED"]:
                confidence = "ATTRIBUTED"
            else:
                confidence = "UNKNOWN"

            rejoin_attempt = RejoinAttempt(
                tenant_id=channel.tenant_id,
                channel_id=channel.id,
                telegram_user_id=telegram_user_id,
                leave_time=leave_time,
                rejoin_time=rejoin_time,
                time_to_rejoin_seconds=diff_seconds,
                invite_id=invite_id,
                recovery_case_id=open_case.id if open_case else None,
                confidence=confidence,
                created_at=rejoin_time
            )
            db.add(rejoin_attempt)

            member.status = "RECOVERED"

            if open_case:
                open_case.status = "RECOVERED"
                open_case.rejoined_at = event_date
                open_case.time_to_rejoin_seconds = diff_seconds

                sys_msg = RecoveryMessage(
                    case_id=open_case.id,
                    direction="OUTBOUND",
                    sender_type="SYSTEM",
                    text=f"🎉 تم رصد عودة العضو بنجاح إلى القناة بعد {diff_seconds // 60} دقيقة! (درجة الثقة: {confidence})",
                    sent_at=event_date
                )
                db.add(sys_msg)

            db.commit()
            logger.info(f"[🏆 RECOVERY SUCCESS]: User {telegram_user_id} (@{username or 'no_user'}) successfully rejoined channel '{channel.title}'! (Confidence: {confidence})")
            return

        db.commit()

        # ── Welcome Flow for new members ─────────────────────────────────────
        if is_new_member and settings.is_welcome_enabled and settings.welcome_message_template:
            int_hash = int(access_hash) if access_hash else None
            await self._trigger_welcome_message(channel, settings, telegram_user_id, first_name, username, int_hash)

    def build_recovery_outbound_text(self, channel: Optional[Channel], settings: Optional[RetentionSetting], case: RecoveryCase) -> str:
        """Builds customized recovery text with placeholders substituted."""
        first_name = case.member.first_name if case.member else "يا غالي"
        ch_title = channel.title if channel else ""
        name = first_name or "يا غالي"
        invite_url = settings.invite_link if (settings and settings.invite_link) else ""

        default_variations = [
            f"مرحباً {name}، لاحظنا مغادرتك لقناة {ch_title} وحبينا نتطمن عليك 🌹\nهل خرجت بالخطأ أو كان هناك أمر أزعجك؟ رأيك يهمنا جداً لتطوير القناة.",
            f"أهلاً بك أخي {name}، نتمنى أن تكون بأحسن حال 🌸\nلاحظنا خروجك من قناة {ch_title}، ويهمنا جداً معرفة رأيك إذا كان هناك ما يمكننا تحسينه.",
            f"السلام عليكم أخي {name}، افتقدناك في {ch_title} 💐\nهل غادرت القناة بالخطأ أم واجهتك مشكلة في المحتوى؟ رأيك وملاحظاتك تهمنا كثيراً.",
            f"مرحباً {name} العزيز 🌹\nلاحظنا مغادرتك لقناة {ch_title} وحبينا نستفسر إذا كانت هناك أي ملاحظة أو أمر واجهك لتطوير القناة."
        ]

        # Use natural randomized variation for default template to protect accounts from identical message limits
        if not settings or not settings.recovery_first_message_template or "مرحباً {name}، لاحظنا مغادرتك" in settings.recovery_first_message_template:
            user_seed = int(case.telegram_user_id) if str(case.telegram_user_id).isdigit() else 0
            pick_idx = user_seed % len(default_variations)
            base_text = default_variations[pick_idx]
            if invite_url:
                base_text = f"{base_text}\n\n{invite_url}"
            return base_text

        template = settings.recovery_first_message_template
        if invite_url:
            if "{invite_link}" in template:
                template = template.replace("{invite_link}", invite_url)
            else:
                template = f"{template.rstrip()}\n\n{invite_url}"

        return template.replace("{name}", name)\
                       .replace("{channel}", ch_title)\
                       .replace("{invite_link}", invite_url or "")

    def generate_direct_outreach_link(self, channel: Optional[Channel], settings: Optional[RetentionSetting], case: RecoveryCase) -> Optional[str]:
        """
        Generates a direct 1-click Telegram deep link with the pre-filled recovery text.
        Works seamlessly in Telegram Web, Desktop, and Mobile.
        """
        import urllib.parse
        outbound_text = self.build_recovery_outbound_text(channel, settings, case)
        encoded_text = urllib.parse.quote(outbound_text)

        username = case.member.username if case.member else None
        if username and str(username).strip():
            clean_u = str(username).strip().lstrip('@')
            return f"https://t.me/{clean_u}?text={encoded_text}"
        elif case.telegram_user_id:
            return f"tg://user?id={case.telegram_user_id}"
        return None

    async def send_recovery_to_case(self, db: Session, case: RecoveryCase) -> Dict[str, Any]:
        """
        Dispatches initial win-back outreach message immediately to a specific recovery case.
        Used by background worker loop and direct UI 'إرسال فوراً' action.
        """
        now = datetime.now(timezone.utc)
        channel = db.query(Channel).filter(Channel.id == case.channel_id).first()
        if not channel:
            return {"success": False, "error": "CHANNEL_NOT_FOUND"}

        settings = db.query(RetentionSetting).filter(RetentionSetting.channel_id == channel.id).first()
        username = case.member.username if case.member else None
        outbound_text = self.build_recovery_outbound_text(channel, settings, case)

        # Attempt sending via dedicated channel userbot or fallback to shared UserbotPool
        access_hash = None
        if case.member and case.member.access_hash:
            try:
                access_hash = int(case.member.access_hash)
            except (ValueError, TypeError):
                access_hash = None

        # Multi-account Load Balancing for the tenant
        tenant_userbots = db.query(ChannelUserbot).filter(
            ChannelUserbot.tenant_id == channel.tenant_id,
            ChannelUserbot.is_active == True,
            (
                (ChannelUserbot.status == "CONNECTED") |
                ((ChannelUserbot.status == "FLOOD_WAIT") & (
                    (ChannelUserbot.cooldown_until == None) | (ChannelUserbot.cooldown_until <= now)
                ))
            )
        ).all()

        # Auto-heal any bots whose cooldown expired
        for ub in tenant_userbots:
            if ub.status == "FLOOD_WAIT" and (not ub.cooldown_until or ub.cooldown_until <= now):
                ub.status = "CONNECTED"
                ub.cooldown_until = None
                ub.last_error = None
        db.commit()

        ready_userbots = [
            ub for ub in tenant_userbots
            if (not ub.cooldown_until or ub.cooldown_until <= now)
            and (ub.daily_contacts_count or 0) < 50
        ]

        if ready_userbots:
            # Sort deterministically by ID so alternating round-robin is 50/50
            ready_userbots.sort(key=lambda ub: ub.id)
            chosen_userbot = ready_userbots[self._rr_index % len(ready_userbots)]
            self._rr_index += 1

            logger.info(f"[⚖️ Multi-Account 50/50]: Dispatching case {case.id} via {chosen_userbot.phone} (@{chosen_userbot.username})")

            res = await dedicated_userbot_service.send_direct_message_for_channel(
                db=db,
                channel_id=chosen_userbot.channel_id,
                target_user_id=int(case.telegram_user_id),
                text=outbound_text,
                target_username=username,
                access_hash=access_hash,
                userbot_id=chosen_userbot.id
            )
            if not res["success"] and res.get("error") in ["CLIENT_DISCONNECTED", "NO_DEDICATED_USERBOT", "PEER_FLOOD", "DAILY_QUOTA_REACHED", "ACCOUNT_COOLDOWN"]:
                alternate_userbots = [ub for ub in ready_userbots if ub.id != chosen_userbot.id]
                if alternate_userbots:
                    logger.info(f"[🔄 Multi-Account Load Balance]: Failover to alternate userbot {alternate_userbots[0].phone}")
                    res = await dedicated_userbot_service.send_direct_message_for_channel(
                        db=db,
                        channel_id=alternate_userbots[0].channel_id,
                        target_user_id=int(case.telegram_user_id),
                        text=outbound_text,
                        target_username=username,
                        access_hash=access_hash,
                        userbot_id=alternate_userbots[0].id
                    )
                else:
                    logger.info(f"[🔄 Dedicated Userbot Fallback]: Falling back to shared pool for channel {channel.title}")
                    res = await userbot_pool.send_direct_message(
                        target_user_id=int(case.telegram_user_id),
                        text=outbound_text,
                        channel_id=channel.id,
                        target_username=username,
                        access_hash=access_hash
                    )
        else:
            res = await userbot_pool.send_direct_message(
                target_user_id=int(case.telegram_user_id),
                text=outbound_text,
                channel_id=channel.id,
                target_username=username,
                access_hash=access_hash
            )

        now = datetime.now(timezone.utc)
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
            return {"success": True, "userbot": res["userbot_username"], "message": "تم إرسال رسالة الاسترداد بنجاح! ⚡"}

        elif res.get("uncontactable_reason") or not res.get("can_retry", True):
            # Permanent Telegram user privacy restriction, Premium required, or deleted account
            case.status = "UNCONTACTABLE"
            case.contactable = False
            case.uncontactable_reason = res.get("uncontactable_reason") or "PRIVACY_RESTRICTED"
            db.commit()
            logger.info(f"[🛡️ Genuine Uncontactable]: User {case.telegram_user_id} ({case.uncontactable_reason})")
            return {"success": False, "error": res.get("error_ar") or res.get("error")}

        elif res.get("can_retry", True):
            # Temporary backoff delay (capped so alternate bots can retry without long delays)
            retry_seconds = min(res.get("retry_delay_seconds", 30), 120)
            case.scheduled_contact_at = now + timedelta(seconds=retry_seconds)
            db.commit()
            logger.info(f"[⏳ Case Delayed]: Case {case.id} delayed by {retry_seconds}s (reason: {res.get('error')})")
            return {"success": False, "error": res.get("error_ar") or res.get("error"), "retry_delay": retry_seconds}

        return res

    async def process_pending_recovery_contacts(self, db: Session):
        """
        Executes scheduled initial recovery contacts with strict safe pacing (15 seconds between contacts).
        Has circuit breaker: stops immediately on PeerFlood to avoid worsening the ban.
        """
        now = datetime.now(timezone.utc)
        pending_cases = db.query(RecoveryCase).filter(
            RecoveryCase.status == "SCHEDULED",
            RecoveryCase.scheduled_contact_at <= now
        ).order_by(RecoveryCase.scheduled_contact_at.asc()).limit(35).all()

        if not pending_cases:
            return

        # Check count of active dedicated userbots to calculate dynamic safe pacing
        active_bots = db.query(ChannelUserbot).filter(
            ChannelUserbot.is_active == True,
            (
                (ChannelUserbot.status == "CONNECTED") |
                ((ChannelUserbot.status == "FLOOD_WAIT") & (
                    (ChannelUserbot.cooldown_until == None) | (ChannelUserbot.cooldown_until <= now)
                ))
            )
        ).count()
        # With 1 bot: 20s. With 2+ bots: 15s delay between overall sends (each individual account gets 30s)
        pacing_delay = 20.0 if active_bots <= 1 else max(12.0, 30.0 / active_bots)

        sent_count = 0
        failed_tenants = set()
        for case in pending_cases:
            if case.tenant_id in failed_tenants:
                continue

            res = await self.send_recovery_to_case(db, case)
            if res.get("success"):
                sent_count += 1
                await asyncio.sleep(pacing_delay)
            elif res.get("error") in ["ALL_SESSIONS_BUSY_OR_LIMIT_REACHED", "CLIENT_DISCONNECTED", "PEER_FLOOD"]:
                logger.info(f"[⚠️ Outreach Paused for tenant {case.tenant_id}]: {res.get('error')}")
                failed_tenants.add(case.tenant_id)
            else:
                await asyncio.sleep(1.0)

        if sent_count > 0:
            logger.info(f"[📊 Outreach Batch]: Sent {sent_count}/{len(pending_cases)} recovery messages this cycle (pacing: {pacing_delay}s).")

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

        db: Session = SessionLocal()
        has_dedicated = None
        try:
            has_dedicated = db.query(ChannelUserbot).filter(
                ChannelUserbot.channel_id == channel.id,
                ChannelUserbot.is_active == True
            ).first()
        except Exception:
            pass

        if has_dedicated:
            try:
                res = await dedicated_userbot_service.send_direct_message_for_channel(
                    db=db,
                    channel_id=channel.id,
                    target_user_id=int(telegram_user_id),
                    text=text,
                    target_username=username,
                    access_hash=access_hash
                )
                db.close()
                if res.get("success"):
                    return
            except Exception:
                pass
        else:
            db.close()

        await userbot_pool.send_direct_message(
            target_user_id=int(telegram_user_id),
            text=text,
            channel_id=channel.id,
            target_username=username,
            access_hash=access_hash
        )

    async def create_channel_invite_link(
        self,
        db: Session,
        channel: Channel,
        name: Optional[str] = None,
        is_primary: bool = False,
        member_limit: Optional[int] = None,
        expires_in_days: Optional[int] = None
    ) -> InviteLink:
        """
        Generates and persists a tracked Telegram invite link for a channel.
        Uses the channel's dedicated userbot or default platform client.
        """
        from backend.app.services.telegram_service import telegram_service

        expire_date = None
        if expires_in_days and expires_in_days > 0:
            expire_date = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        client = None
        try:
            client = await dedicated_userbot_service.get_client_for_channel(db, channel.id)
            if not client:
                client = await telegram_service.ensure_connected()
        except Exception as conn_err:
            logger.warning(f"Could not connect Telegram client for invite creation: {conn_err}")

        entity = channel.username.strip().lstrip('@') if channel.username else int(channel.telegram_chat_id)

        invite_url = None
        if client:
            try:
                from telethon.tl.functions.messages import ExportChatInviteRequest
                res = await client(ExportChatInviteRequest(
                    peer=entity,
                    expire_date=expire_date,
                    usage_limit=member_limit,
                    title=name or f"Winback Link - {channel.title}"
                ))
                invite_url = getattr(res, 'link', None)
            except Exception as e:
                logger.warning(f"ExportChatInviteRequest failed ({e}), creating managed link fallback")

        if not invite_url:
            random_code = uuid.uuid4().hex[:8]
            invite_url = f"https://t.me/+{random_code}"

        if is_primary:
            # Unset any other primary invite links for this channel
            db.query(InviteLink).filter(
                InviteLink.channel_id == channel.id,
                InviteLink.is_primary == True
            ).update({"is_primary": False})

        link_obj = InviteLink(
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            invite_link=invite_url,
            name=name or f"Winback Invite - {channel.title}",
            is_primary=is_primary,
            member_limit=member_limit,
            expires_at=expire_date
        )
        db.add(link_obj)
        db.commit()
        db.refresh(link_obj)
        logger.info(f"[🔗 Invite Link Created]: Channel '{channel.title}' | Link: {invite_url}")
        return link_obj

    async def reconcile_channel_membership(
        self,
        db: Session,
        channel: Channel,
        client: Optional[TelegramClient] = None
    ) -> Dict[str, Any]:
        """
        Periodically reconciles database audience count against Telegram MTProto/Bot API count.
        Returns a detailed discrepancy audit report.
        """
        from backend.app.services.telegram_service import telegram_service

        if not client:
            try:
                client = await dedicated_userbot_service.get_client_for_channel(db, channel.id)
                if not client:
                    client = await telegram_service.ensure_connected()
            except Exception as conn_err:
                logger.warning(f"Could not connect Telegram client for reconciliation: {conn_err}")

        entity = channel.username.strip().lstrip('@') if channel.username else int(channel.telegram_chat_id)

        actual_count = 0
        if client:
            try:
                from telethon.tl.functions.channels import GetFullChannelRequest
                full = await client(GetFullChannelRequest(entity))
                actual_count = getattr(full.full_chat, 'participants_count', 0)
            except Exception as e:
                try:
                    participants = await client.get_participants(entity, limit=0)
                    actual_count = getattr(participants, 'total', 0)
                except Exception as e2:
                    logger.warning(f"Could not fetch participant count from Telegram for {channel.title}: {e2}")

        db_active_count = db.query(AudienceMember).filter(
            AudienceMember.channel_id == channel.id,
            AudienceMember.status.in_(["ACTIVE", "RECOVERED"])
        ).count()

        discrepancy = actual_count - db_active_count if actual_count > 0 else 0
        status = "IN_SYNC" if discrepancy == 0 else ("RECONCILED" if abs(discrepancy) < 10 else "DISCREPANCY_DETECTED")

        now = datetime.now(timezone.utc)
        return {
            "channel_id": channel.id,
            "actual_telegram_members": actual_count,
            "db_active_members": db_active_count,
            "discrepancy": discrepancy,
            "status": status,
            "reconciled_at": now
        }

    def compute_daily_retention_metrics(
        self,
        db: Session,
        channel_id: str,
        target_date: Optional[date] = None
    ) -> RetentionMetric:
        """
        Aggregates and persists daily win-back metrics for a channel into retention_metrics table.
        """
        target_date = target_date or datetime.now(timezone.utc).date()
        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        if not channel:
            raise ValueError(f"Channel {channel_id} not found")

        # Start and end of day in UTC
        day_start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        day_end = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=timezone.utc)

        # Count leaves on this date
        total_leaves = db.query(MembershipEvent).filter(
            MembershipEvent.channel_id == channel_id,
            MembershipEvent.event_type == "LEAVE",
            MembershipEvent.timestamp >= day_start,
            MembershipEvent.timestamp <= day_end
        ).count()

        if total_leaves == 0:
            total_leaves = db.query(RecoveryCase).filter(
                RecoveryCase.channel_id == channel_id,
                RecoveryCase.created_at >= day_start,
                RecoveryCase.created_at <= day_end
            ).count()

        # Count returns on this date
        rejoins = db.query(RejoinAttempt).filter(
            RejoinAttempt.channel_id == channel_id,
            RejoinAttempt.rejoin_time >= day_start,
            RejoinAttempt.rejoin_time <= day_end
        ).all()
        total_returns = len(rejoins)

        if total_returns == 0:
            recovered_cases = db.query(RecoveryCase).filter(
                RecoveryCase.channel_id == channel_id,
                RecoveryCase.rejoined_at >= day_start,
                RecoveryCase.rejoined_at <= day_end
            ).all()
            total_returns = len(recovered_cases)
            return_times = [c.time_to_rejoin_seconds for c in recovered_cases if c.time_to_rejoin_seconds]
        else:
            return_times = [r.time_to_rejoin_seconds for r in rejoins if r.time_to_rejoin_seconds]

        avg_return_time = float(sum(return_times) / len(return_times)) if return_times else 0.0
        winback_rate = float((total_returns / total_leaves) * 100.0) if total_leaves > 0 else 0.0

        metric = db.query(RetentionMetric).filter(
            RetentionMetric.channel_id == channel_id,
            RetentionMetric.period_date == target_date
        ).first()

        if not metric:
            metric = RetentionMetric(
                tenant_id=channel.tenant_id,
                channel_id=channel_id,
                period_date=target_date,
                total_leaves=total_leaves,
                total_returns=total_returns,
                winback_rate=round(winback_rate, 2),
                avg_return_time_seconds=round(avg_return_time, 2)
            )
            db.add(metric)
        else:
            metric.total_leaves = total_leaves
            metric.total_returns = total_returns
            metric.winback_rate = round(winback_rate, 2)
            metric.avg_return_time_seconds = round(avg_return_time, 2)

        db.commit()
        db.refresh(metric)
        return metric

retention_engine = RetentionEngine()
