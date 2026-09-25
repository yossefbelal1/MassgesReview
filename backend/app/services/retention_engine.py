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
try:
    from telethon.tl.types import (
        ChannelAdminLogEventActionParticipantBan,
        ChannelAdminLogEventActionParticipantToggleBan
    )
except ImportError:
    ChannelAdminLogEventActionParticipantBan = tuple()
    ChannelAdminLogEventActionParticipantToggleBan = tuple()

from backend.app.core.database import SessionLocal
from backend.app.models.models import (
    Channel, AudienceMember, RecoveryCase, RecoveryMessage, RetentionSetting, Tenant, ChannelUserbot,
    InviteLink, MembershipEvent, RejoinAttempt, RetentionMetric, MembershipState
)
from backend.app.services.userbot_pool import userbot_pool
from backend.app.services.dedicated_userbot_service import dedicated_userbot_service
from backend.app.services.sse_service import sse_broadcaster

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

    @staticmethod
    def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

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

                # ── Handle KICK / BAN ────────────────────────────────────────
                elif (
                    (ChannelAdminLogEventActionParticipantBan and isinstance(ev.action, ChannelAdminLogEventActionParticipantBan)) or
                    (ChannelAdminLogEventActionParticipantToggleBan and isinstance(ev.action, ChannelAdminLogEventActionParticipantToggleBan)) or
                    getattr(ev, 'banned', False) or getattr(ev, 'kicked', False)
                ):
                    action_type = "BAN" if (getattr(ev, 'banned', False) or "ban" in ev.action.__class__.__name__.lower()) else "KICK"
                    events_processed += 1
                    await self._handle_member_kick_or_ban(
                        db=db,
                        channel=channel,
                        telegram_user_id=user_id,
                        event_date=event_date,
                        action_type=action_type,
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

                    via_join_request = (
                        isinstance(ev.action, ChannelAdminLogEventActionParticipantJoinByRequest) or
                        getattr(ev.action, 'via_join_request', False) or
                        getattr(ev, 'via_join_request', False)
                    )

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
                        invite_link_str=invite_link_str,
                        via_join_request=via_join_request
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
        # 1. Find or create AudienceMember
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

        # 2. Update or create MembershipState projection
        state = db.query(MembershipState).filter(
            MembershipState.channel_id == channel.id,
            MembershipState.telegram_user_id == telegram_user_id
        ).first()
        if not state:
            state = MembershipState(
                tenant_id=channel.tenant_id,
                channel_id=channel.id,
                telegram_user_id=telegram_user_id,
                status="left",
                first_join=event_date,
                last_leave=event_date
            )
            db.add(state)
        else:
            state.status = "left"
            state.last_leave = event_date

        # 3. Idempotent raw event log
        existing_event = db.query(MembershipEvent).filter(
            MembershipEvent.channel_id == channel.id,
            MembershipEvent.telegram_user_id == telegram_user_id,
            MembershipEvent.timestamp == event_date,
            MembershipEvent.event_type == "LEAVE"
        ).first()
        if not existing_event:
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

        # 4. Check if a case already exists for this exact leave event
        existing_case = db.query(RecoveryCase).filter(
            RecoveryCase.channel_id == channel.id,
            RecoveryCase.leave_event_id == leave_event_id
        ).first()

        if not existing_case:
            # Check if member already has an open or active recovery case for this channel
            open_case = db.query(RecoveryCase).filter(
                RecoveryCase.channel_id == channel.id,
                RecoveryCase.telegram_user_id == telegram_user_id,
                RecoveryCase.status.in_(["SCHEDULED", "CONTACTED", "CONVERSATION_ACTIVE", "LINK_DELIVERED"])
            ).first()

            if not open_case and member.status != "OPT_OUT":
                # Schedule recovery contact immediately
                now = datetime.now(timezone.utc)
                initial_status = "SCHEDULED"
                scheduled_at = now

                # Pre-bind previously assigned userbot to strictly guarantee single-messenger rule
                prev_assigned = db.query(RecoveryCase.assigned_userbot).filter(
                    RecoveryCase.tenant_id == channel.tenant_id,
                    RecoveryCase.telegram_user_id == telegram_user_id,
                    RecoveryCase.assigned_userbot != None
                ).order_by(RecoveryCase.created_at.desc()).first()

                assigned_bot = prev_assigned[0] if (prev_assigned and prev_assigned[0]) else None

                case = RecoveryCase(
                    tenant_id=channel.tenant_id,
                    channel_id=channel.id,
                    member_id=member.id,
                    telegram_user_id=telegram_user_id,
                    leave_event_id=leave_event_id,
                    status=initial_status,
                    contactable=True,
                    assigned_userbot=assigned_bot,
                    scheduled_contact_at=scheduled_at,
                    created_at=event_date
                )
                db.add(case)
                logger.info(f"[🎯 Retention Case Created]: Channel '{channel.title}' | User {telegram_user_id} (@{username or 'no_user'}) [{initial_status}] (Assigned: {assigned_bot or 'Pending Round-Robin'})")

        channel.last_event_at = event_date
        channel.last_success_at = datetime.now(timezone.utc)
        channel.consecutive_errors = 0
        channel.health_state = "HEALTHY"

        db.commit()

        # 5. Broadcast to SSE subscribers
        sse_broadcaster.broadcast(
            channel_id=channel.id,
            event_type="leave",
            data={
                "telegram_user_id": telegram_user_id,
                "username": username,
                "first_name": first_name,
                "timestamp": event_date.isoformat(),
                "event_type": "LEAVE",
                "source": "ADMIN_LOG"
            }
        )

    async def _handle_member_kick_or_ban(
        self,
        db: Session,
        channel: Channel,
        telegram_user_id: str,
        event_date: datetime,
        action_type: str = "KICK",
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        username: Optional[str] = None,
        access_hash: Optional[str] = None
    ):
        """Processes an involuntary kick or ban. Does NOT create a recovery outreach case."""
        action_status = "banned" if action_type.upper() == "BAN" else "kicked"

        # 1. Update/create AudienceMember
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
                status=action_status.upper(),
                first_joined_at=event_date,
                last_left_at=event_date
            )
            db.add(member)
        else:
            member.status = action_status.upper()
            member.last_left_at = event_date
            if access_hash: member.access_hash = access_hash
            if first_name: member.first_name = first_name
            if last_name: member.last_name = last_name
            if username: member.username = username

        # 2. Update/create MembershipState
        state = db.query(MembershipState).filter(
            MembershipState.channel_id == channel.id,
            MembershipState.telegram_user_id == telegram_user_id
        ).first()
        if not state:
            state = MembershipState(
                tenant_id=channel.tenant_id,
                channel_id=channel.id,
                telegram_user_id=telegram_user_id,
                status=action_status,
                first_join=event_date,
                last_leave=event_date
            )
            db.add(state)
        else:
            state.status = action_status
            state.last_leave = event_date

        # 3. Cancel any open recovery case for this member
        open_cases = db.query(RecoveryCase).filter(
            RecoveryCase.channel_id == channel.id,
            RecoveryCase.telegram_user_id == telegram_user_id,
            RecoveryCase.status.in_(["SCHEDULED", "DETECTED", "CONTACTED", "CONVERSATION_ACTIVE", "LINK_DELIVERED"])
        ).all()
        for oc in open_cases:
            oc.status = "OPT_OUT"
            oc.uncontactable_reason = f"INVOLUNTARY_{action_type}"

        # 4. Idempotent raw event log
        existing_event = db.query(MembershipEvent).filter(
            MembershipEvent.channel_id == channel.id,
            MembershipEvent.telegram_user_id == telegram_user_id,
            MembershipEvent.timestamp == event_date,
            MembershipEvent.event_type == action_type.upper()
        ).first()
        if not existing_event:
            raw_event = MembershipEvent(
                tenant_id=channel.tenant_id,
                channel_id=channel.id,
                telegram_user_id=telegram_user_id,
                event_type=action_type.upper(),
                source="ADMIN_LOG",
                extra_metadata={
                    "first_name": first_name,
                    "username": username,
                    "action_type": action_type
                },
                timestamp=event_date
            )
            db.add(raw_event)

        channel.last_event_at = event_date
        channel.last_success_at = datetime.now(timezone.utc)
        channel.consecutive_errors = 0
        channel.health_state = "HEALTHY"

        db.commit()

        # 5. Broadcast to SSE subscribers
        sse_broadcaster.broadcast(
            channel_id=channel.id,
            event_type=action_type.lower(),
            data={
                "telegram_user_id": telegram_user_id,
                "username": username,
                "first_name": first_name,
                "timestamp": event_date.isoformat(),
                "event_type": action_type.upper(),
                "source": "ADMIN_LOG"
            }
        )
        logger.info(f"[🚫 Involuntary {action_type} Logged]: Channel '{channel.title}' | User {telegram_user_id} (@{username or 'no_user'})")

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
        invite_link_str: Optional[str] = None,
        via_join_request: bool = False
    ):
        """Processes a detected join/rejoin event, attributes win-back, and logs membership events."""
        member = db.query(AudienceMember).filter(
            AudienceMember.channel_id == channel.id,
            AudienceMember.telegram_user_id == telegram_user_id
        ).first()

        # 1. Resolve tracked invite link if provided
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

        # 2. Check for active recovery case to determine attribution and confidence
        open_case = db.query(RecoveryCase).filter(
            RecoveryCase.channel_id == channel.id,
            RecoveryCase.telegram_user_id == telegram_user_id,
            RecoveryCase.status.in_(["SCHEDULED", "CONTACTED", "CONVERSATION_ACTIVE", "LINK_DELIVERED", "NO_RESPONSE", "UNCONTACTABLE"])
        ).order_by(RecoveryCase.created_at.desc()).first()

        # Strict attribution matrix
        if invite_id:
            source = "INVITE_LINK"
            confidence = "CONFIRMED"
        elif via_join_request:
            source = "JOIN_REQUEST"
            confidence = "ATTRIBUTED"
        elif open_case and open_case.status in ["CONTACTED", "CONVERSATION_ACTIVE", "LINK_DELIVERED"]:
            source = "DIRECT"
            confidence = "ATTRIBUTED"
        else:
            source = "DIRECT"
            confidence = "UNKNOWN"

        # 3. Idempotent raw membership event log
        existing_event = db.query(MembershipEvent).filter(
            MembershipEvent.channel_id == channel.id,
            MembershipEvent.telegram_user_id == telegram_user_id,
            MembershipEvent.timestamp == event_date,
            MembershipEvent.event_type == "JOIN"
        ).first()

        if not existing_event:
            raw_event = MembershipEvent(
                tenant_id=channel.tenant_id,
                channel_id=channel.id,
                telegram_user_id=telegram_user_id,
                event_type="JOIN",
                invite_id=invite_id,
                via_join_request=via_join_request,
                source=source,
                extra_metadata={
                    "first_name": first_name,
                    "username": username,
                    "invite_link": invite_link_str
                },
                timestamp=event_date
            )
            db.add(raw_event)

        # 4. Update or create MembershipState projection
        state = db.query(MembershipState).filter(
            MembershipState.channel_id == channel.id,
            MembershipState.telegram_user_id == telegram_user_id
        ).first()
        if not state:
            state = MembershipState(
                tenant_id=channel.tenant_id,
                channel_id=channel.id,
                telegram_user_id=telegram_user_id,
                status="member",
                first_join=event_date,
                last_join=event_date
            )
            db.add(state)
        else:
            state.status = "member"
            state.last_join = event_date
            if not state.first_join:
                state.first_join = event_date

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

        # 5. Rejoin Attribution
        if previous_left_at or open_case:
            leave_time = previous_left_at or (open_case.created_at if open_case else event_date)
            if leave_time.tzinfo is None:
                leave_time = leave_time.replace(tzinfo=timezone.utc)
            rejoin_time = event_date
            if rejoin_time.tzinfo is None:
                rejoin_time = rejoin_time.replace(tzinfo=timezone.utc)

            diff_seconds = max(0, int((rejoin_time - leave_time).total_seconds()))

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
                    text=f"🎉 تم رصد عودة العضو بنجاح إلى القناة بعد {diff_seconds // 60} دقيقة! (المصدر: {source} | درجة الثقة: {confidence})",
                    sent_at=event_date
                )
                db.add(sys_msg)

            logger.info(f"[🏆 RECOVERY SUCCESS]: User {telegram_user_id} (@{username or 'no_user'}) successfully rejoined channel '{channel.title}'! (Source: {source} | Confidence: {confidence})")

        channel.last_event_at = event_date
        channel.last_success_at = datetime.now(timezone.utc)
        channel.consecutive_errors = 0
        channel.health_state = "HEALTHY"

        db.commit()

        # 6. Broadcast to SSE subscribers
        sse_broadcaster.broadcast(
            channel_id=channel.id,
            event_type="join",
            data={
                "telegram_user_id": telegram_user_id,
                "username": username,
                "first_name": first_name,
                "timestamp": event_date.isoformat(),
                "event_type": "JOIN",
                "source": source,
                "confidence": confidence,
                "via_join_request": via_join_request
            }
        )

        # 7. Welcome Flow for new members
        if is_new_member and settings and settings.is_welcome_enabled and settings.welcome_message_template:
            int_hash = int(access_hash) if access_hash else None
            await self._trigger_welcome_message(channel, settings, telegram_user_id, first_name, username, int_hash)

    def _inject_anti_hash_fingerprint(self, text: str, user_seed: int) -> str:
        """
        Injects invisible zero-width characters (\u200b, \u200c, \u200d, \u2060) into word boundaries
        to generate a mathematically unique SHA-256 binary hash for each recipient.
        Completely invisible to humans, but defeats Telegram's duplicate text fingerprinting.
        """
        zw_chars = ["\u200b", "\u200c", "\u200d", "\u2060"]
        words = text.split(" ")
        if len(words) < 2:
            return text + zw_chars[user_seed % len(zw_chars)]

        new_words = []
        for i, word in enumerate(words):
            new_words.append(word)
            if i % 3 == (user_seed % 3) and i < len(words) - 1:
                zw = zw_chars[(user_seed + i) % len(zw_chars)]
                new_words[-1] = new_words[-1] + zw
        return " ".join(new_words)

    def build_recovery_outbound_text(self, channel: Optional[Channel], settings: Optional[RetentionSetting], case: RecoveryCase) -> str:
        """Builds customized recovery text with placeholders substituted and anti-hash fingerprinting."""
        first_name = case.member.first_name if case.member else "يا غالي"
        ch_title = channel.title if channel else ""
        name = first_name or "يا غالي"
        invite_url = settings.invite_link if (settings and settings.invite_link) else ""
        user_seed = int(case.telegram_user_id) if str(case.telegram_user_id).isdigit() else 0

        default_variations = [
            f"مرحباً {name}، لاحظنا مغادرتك لقناة {ch_title} وحبينا نتطمن عليك 🌹\nهل خرجت بالخطأ أو كان هناك أمر أزعجك؟ رأيك يهمنا جداً لتطوير القناة.",
            f"أهلاً بك أخي {name}، نتمنى أن تكون بأحسن حال 🌸\nلاحظنا خروجك من قناة {ch_title}، ويهمنا جداً معرفة رأيك إذا كان هناك ما يمكننا تحسينه.",
            f"السلام عليكم أخي {name}، افتقدناك في {ch_title} 💐\nهل غادرت القناة بالخطأ أم واجهتك مشكلة في المحتوى؟ رأيك وملاحظاتك تهمنا كثيراً.",
            f"مرحباً {name} العزيز 🌹\nلاحظنا مغادرتك لقناة {ch_title} وحبينا نستفسر إذا كانت هناك أي ملاحظة أو أمر واجهك لتطوير القناة.",
            f"حياك الله أخي {name} 🌟\nلاحظنا ابتعادك عن {ch_title}، يهمنا جداً سماع رأيك وتجربتك معنا لمواصلة التحسين.",
            f"أهلاً {name}، افتقدنا تواجدك في قناة {ch_title} 🌷\nنود التأكد إذا كان خروجك غير مقصود أو إذا كان لديك أي اقتراح لتحسين المحتوى."
        ]

        # Use natural randomized variation for default template to protect accounts from identical message limits
        if not settings or not settings.recovery_first_message_template or "مرحباً {name}، لاحظنا مغادرتك" in settings.recovery_first_message_template:
            pick_idx = user_seed % len(default_variations)
            base_text = default_variations[pick_idx]
            if invite_url:
                base_text = f"{base_text}\n\n{invite_url}"
            return self._inject_anti_hash_fingerprint(base_text, user_seed)

        template = settings.recovery_first_message_template
        if invite_url:
            if "{invite_link}" in template:
                template = template.replace("{invite_link}", invite_url)
            else:
                template = f"{template.rstrip()}\n\n{invite_url}"

        final_text = template.replace("{name}", name)\
                             .replace("{channel}", ch_title)\
                             .replace("{invite_link}", invite_url or "")
        return self._inject_anti_hash_fingerprint(final_text, user_seed)

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

        # Multi-Account Failover & Load Balancing for the tenant
        tenant_userbots = db.query(ChannelUserbot).filter(
            ChannelUserbot.tenant_id == channel.tenant_id,
            ChannelUserbot.is_active == True
        ).all()

        # Clean expired cooldowns
        for ub in tenant_userbots:
            ub_cd = self._to_utc(ub.cooldown_until)
            if ub.status == "FLOOD_WAIT" and (not ub_cd or ub_cd <= now):
                ub.status = "CONNECTED"
                ub.cooldown_until = None
                ub.last_error = None
        db.commit()

        # ── STRICT SINGLE-MESSENGER ENFORCEMENT ───────────────────────────────
        assigned_bot_name = case.assigned_userbot
        if not assigned_bot_name and case.telegram_user_id:
            prev_contact = db.query(RecoveryCase.assigned_userbot).filter(
                RecoveryCase.tenant_id == channel.tenant_id,
                RecoveryCase.telegram_user_id == case.telegram_user_id,
                RecoveryCase.assigned_userbot != None
            ).order_by(RecoveryCase.created_at.desc()).first()
            if prev_contact and prev_contact[0]:
                assigned_bot_name = prev_contact[0]
                case.assigned_userbot = assigned_bot_name
                db.commit()

        res = {"success": False, "error": "NO_AVAILABLE_BOTS"}

        # Partition bots: Ready vs Limited (enforce safe daily quota of 30)
        ready_userbots = [
            ub for ub in tenant_userbots
            if (not ub.cooldown_until or self._to_utc(ub.cooldown_until) <= now)
            and (ub.daily_contacts_count or 0) < 30
            and ub.status == "CONNECTED"
        ]
        limited_userbots = [ub for ub in tenant_userbots if ub not in ready_userbots]

        if assigned_bot_name:
            clean_assigned = assigned_bot_name.lstrip('@').lower()
            matching_bot = next(
                (ub for ub in tenant_userbots if (ub.username and ub.username.lower() == clean_assigned) or (ub.phone == assigned_bot_name) or (ub.id == assigned_bot_name)),
                None
            )
            if matching_bot:
                cd = self._to_utc(matching_bot.cooldown_until)
                if matching_bot.status == "FLOOD_WAIT" and cd and cd > now:
                    wait_min = max(1, int((cd - now).total_seconds()) // 60)
                    case.scheduled_contact_at = cd
                    case.status = "SCHEDULED"
                    case.contactable = True
                    case.uncontactable_reason = None
                    db.commit()
                    return {
                        "success": False,
                        "error_code": "ASSIGNED_BOT_LIMITED",
                        "message": f"الحساب المخصص لهذا العميل (@{matching_bot.username}) في راحة مؤقتة حتى {cd.strftime('%H:%M UTC')}. ستتم المراسلة تلقائياً عبره فور انتهاء الراحة للحفاظ على استمرارية نفس الرقم وعدم المراسلة من رقم آخر."
                    }

                # Send ONLY via this matching bot to guarantee single messenger!
                res = await dedicated_userbot_service.send_direct_message_for_channel(
                    db=db,
                    channel_id=matching_bot.channel_id,
                    target_user_id=int(case.telegram_user_id),
                    text=outbound_text,
                    target_username=username,
                    access_hash=access_hash,
                    userbot_id=matching_bot.id
                )

        can_failover = (not assigned_bot_name) or (
            not res.get("success") and res.get("error") in ["NO_DEDICATED_USERBOT", "CANNOT_RESOLVE_PEER"] and not case.first_contacted_at
        )

        if can_failover:
            ordered_userbots = []
            if ready_userbots:
                failed_id = matching_bot.id if (assigned_bot_name and matching_bot) else None
                candidates = [ub for ub in ready_userbots if ub.id != failed_id]
                candidates.sort(key=lambda ub: ub.id)
                if candidates:
                    start_idx = self._rr_index % len(candidates)
                    self._rr_index += 1
                    ordered_userbots = candidates[start_idx:] + candidates[:start_idx]

            # Try candidate accounts in sequence (failover chain)
            for bot in ordered_userbots:
                logger.info(f"[⚖️ Userbot Dispatch]: Trying {bot.phone} (@{bot.username}) for case {case.id} (user {case.telegram_user_id} @{username or 'no_user'})")
                send_res = await dedicated_userbot_service.send_direct_message_for_channel(
                    db=db,
                    channel_id=bot.channel_id,
                    target_user_id=int(case.telegram_user_id),
                    text=outbound_text,
                    target_username=username,
                    access_hash=access_hash,
                    userbot_id=bot.id
                )
                if send_res.get("success"):
                    res = send_res
                    case.assigned_userbot = bot.username or bot.phone
                    db.commit()
                    break
                else:
                    err = send_res.get("error", "")
                    logger.warning(f"[⚠️ Bot @{bot.username} Failed]: {err}. Checking alternate account...")
                    res = send_res

                    # User-level restrictions (cannot be fixed by trying other bots)
                    if err in ["PRIVACY_RESTRICTED", "USER_BLOCKED_OR_DELETED", "NOT_MUTUAL_CONTACT", "PEER_IS_CHANNEL_OR_GROUP"]:
                        break
                    # Otherwise (PeerFlood, FloodWait, Cannot Resolve Peer, etc.):
                    # Continue loop to try next userbot!
                    continue

        # If not successful and tenant userbots exist, handle gracefully:
        if not res.get("success"):
            # Check if this user has no username and needs the primary session hash owner
            if not username and access_hash:
                hash_owner = next(
                    (ub for ub in tenant_userbots if "AutoMassge1" in (ub.username or "") or "+48455536804" in (ub.phone or "")),
                    None
                )
                if hash_owner and hash_owner.cooldown_until:
                    cd = self._to_utc(hash_owner.cooldown_until)
                    if cd and cd > now:
                        case.scheduled_contact_at = cd
                        case.status = "SCHEDULED"
                        case.contactable = True
                        case.uncontactable_reason = None
                        db.commit()
                        wait_min = max(1, int((cd - now).total_seconds()) // 60)
                        logger.info(f"[⏳ Case Queued for Hash Owner]: Case {case.id} delayed until {cd} for {hash_owner.username}")
                        return {
                            "success": False,
                            "error_code": "WAITING_FOR_HASH_OWNER",
                            "message": f"هذا العضو ليس لديه معرف (@username)، وحساب الاسترداد الأساسي (@{hash_owner.username}) في فترة راحة مؤقتة من تيليجرام. ستتم المراسلة تلقائياً بعد {wait_min} دقيقة، أو يمكنك مراسلته الآن عبر زر تيليجرام ↗."
                        }

            # If all accounts are limited:
            if not ready_userbots and limited_userbots:
                cooldowns = [self._to_utc(ub.cooldown_until) for ub in limited_userbots if ub.cooldown_until]
                min_cd = min(cooldowns) if cooldowns else (now + timedelta(minutes=15))
                wait_min = max(1, int((min_cd - now).total_seconds()) // 60)
                case.scheduled_contact_at = min_cd
                case.status = "SCHEDULED"
                case.contactable = True
                case.uncontactable_reason = None
                db.commit()
                return {
                    "success": False,
                    "error_code": "ALL_BOTS_LIMITED",
                    "message": f"جميع حسابات المراسلة في فترة راحة مؤقتة من تيليجرام. ستتم المراسلة تلقائياً بعد {wait_min} دقيقة، أو يمكنك الضغط على زر تيليجرام ↗ للمراسلة مباشرة."
                }

            # If no dedicated userbots exist at all:
            if not tenant_userbots:
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
            return {"success": True, "userbot": res["userbot_username"], "message": f"تم إرسال رسالة الاسترداد بنجاح عبر @{res['userbot_username']}! ⚡"}

        elif res.get("uncontactable_reason") in ["PRIVACY_RESTRICTED", "NOT_MUTUAL_CONTACT", "USER_BLOCKED_OR_DELETED", "INVOLUNTARY_BAN", "INVOLUNTARY_KICK"]:
            # Genuine Telegram user privacy restriction, Premium required, or deleted account
            case.status = "UNCONTACTABLE"
            case.contactable = False
            case.uncontactable_reason = res.get("uncontactable_reason") or "PRIVACY_RESTRICTED"
            db.commit()
            logger.info(f"[🛡️ Genuine Uncontactable]: User {case.telegram_user_id} ({case.uncontactable_reason})")
            return {"success": False, "error": res.get("error_ar") or res.get("error")}

        else:
            # Temporary backoff delay (cooldowns, temporary peer delays, network): keep in SCHEDULED
            retry_seconds = min(res.get("retry_delay_seconds", 30), 120)
            case.status = "SCHEDULED"
            case.contactable = True
            case.uncontactable_reason = None
            case.scheduled_contact_at = now + timedelta(seconds=retry_seconds)
            db.commit()
            logger.info(f"[⏳ Case Delayed]: Case {case.id} delayed by {retry_seconds}s (reason: {res.get('error')})")
            return {
                "success": False,
                "error_code": res.get("error"),
                "error": res.get("error_ar") or res.get("error"),
                "retry_delay": retry_seconds
            }

        return res

    async def process_pending_recovery_contacts(self, db: Session):
        """
        Executes scheduled initial recovery contacts per tenant with parallel userbot dispatch,
        fair queuing, single-messenger guarantee, and anti-spam human jitter.
        """
        now = datetime.now(timezone.utc)
        active_tenants = db.query(Tenant).filter(Tenant.is_active == True).all()

        for tenant in active_tenants:
            # 1. Auto-heal any dedicated userbots in FLOOD_WAIT when their cooldown expires
            flood_bots = db.query(ChannelUserbot).filter(
                ChannelUserbot.tenant_id == tenant.id,
                ChannelUserbot.is_active == True,
                ChannelUserbot.status == "FLOOD_WAIT"
            ).all()
            for fb in flood_bots:
                fb_cd = self._to_utc(fb.cooldown_until)
                if not fb_cd or fb_cd <= now:
                    fb.status = "CONNECTED"
                    fb.cooldown_until = None
                    fb.last_error = None
                    db.commit()
                    logger.info(f"[Worker Auto-Restore]: Cooldown expired for {fb.username}. Status restored to CONNECTED.")

            # 2. Query all active userbots for this tenant
            tenant_userbots = db.query(ChannelUserbot).filter(
                ChannelUserbot.tenant_id == tenant.id,
                ChannelUserbot.is_active == True
            ).all()

            ready_userbots = [
                ub for ub in tenant_userbots
                if (not ub.cooldown_until or self._to_utc(ub.cooldown_until) <= now)
                and (ub.daily_contacts_count or 0) < 30
                and ub.status == "CONNECTED"
            ]

            if not ready_userbots:
                limited_userbots = [ub for ub in tenant_userbots if ub not in ready_userbots]
                if limited_userbots:
                    logger.debug(f"[Outreach Paused]: All {len(limited_userbots)} userbots for tenant {tenant.id} are in cooldown or reached daily ceiling.")
                continue

            # 3. Pull pending recovery cases (fetch up to 30 cases for parallel load)
            pending_cases = db.query(RecoveryCase).filter(
                RecoveryCase.tenant_id == tenant.id,
                RecoveryCase.status == "SCHEDULED",
                RecoveryCase.scheduled_contact_at <= now
            ).order_by(RecoveryCase.scheduled_contact_at.asc()).limit(30).all()

            if not pending_cases:
                continue

            # 4. Partition cases into per-bot queues
            # Strict Single-Messenger Rule:
            # - If a member was previously messaged by bot X, the case MUST stay with bot X.
            # - Unassigned cases are distributed evenly/alternating across ready userbots.
            bot_queues: Dict[str, List[str]] = {ub.id: [] for ub in ready_userbots}

            bot_lookup: Dict[str, ChannelUserbot] = {}
            for ub in tenant_userbots:
                if ub.username:
                    bot_lookup[ub.username.lower().lstrip('@')] = ub
                if ub.phone:
                    bot_lookup[ub.phone] = ub
                bot_lookup[ub.id] = ub

            rr_idx = 0
            for case in pending_cases:
                assigned_bot_name = case.assigned_userbot
                if not assigned_bot_name and case.telegram_user_id:
                    # Check history for this user
                    prev_contact = db.query(RecoveryCase.assigned_userbot).filter(
                        RecoveryCase.tenant_id == tenant.id,
                        RecoveryCase.telegram_user_id == case.telegram_user_id,
                        RecoveryCase.assigned_userbot != None
                    ).order_by(RecoveryCase.created_at.desc()).first()
                    if prev_contact and prev_contact[0]:
                        assigned_bot_name = prev_contact[0]
                        case.assigned_userbot = assigned_bot_name
                        db.commit()

                target_ub = None
                if assigned_bot_name:
                    clean_assigned = assigned_bot_name.lower().lstrip('@')
                    target_ub = bot_lookup.get(clean_assigned) or bot_lookup.get(assigned_bot_name)

                if target_ub:
                    if target_ub.id in bot_queues:
                        bot_queues[target_ub.id].append(case.id)
                    else:
                        # The assigned bot is in cooldown; preserve single-messenger rule and delay case
                        cd = self._to_utc(target_ub.cooldown_until) or (now + timedelta(minutes=15))
                        case.scheduled_contact_at = cd
                        db.commit()
                else:
                    selected_bot = ready_userbots[rr_idx % len(ready_userbots)]
                    rr_idx += 1
                    bot_display = selected_bot.username or selected_bot.phone or selected_bot.id
                    case.assigned_userbot = bot_display
                    db.commit()
                    bot_queues[selected_bot.id].append(case.id)

            # 5. Launch parallel worker coroutines (one per ready bot)
            async def run_bot_outreach(bot_obj: ChannelUserbot, case_ids: List[str]):
                if not case_ids:
                    return 0
                worker_db: Session = SessionLocal()
                sent_total = 0
                bot_name = bot_obj.username or bot_obj.phone
                try:
                    for cid in case_ids:
                        fresh_case = worker_db.query(RecoveryCase).filter(RecoveryCase.id == cid).first()
                        if not fresh_case or fresh_case.status != "SCHEDULED":
                            continue

                        logger.info(f"[🚀 Parallel Dispatch (@{bot_name})]: Processing case {fresh_case.id} for user {fresh_case.telegram_user_id}...")
                        res = await self.send_recovery_to_case(worker_db, fresh_case)

                        if res.get("success"):
                            sent_total += 1
                            # Human jitter pause between sends on this account (45.0s - 85.0s)
                            post_pause = random.uniform(45.0, 85.0)
                            logger.info(f"[☕ Parallel Account Pacing (@{bot_name})]: Sent successfully. Pausing {post_pause:.1f}s for human simulation...")
                            await asyncio.sleep(post_pause)
                        elif res.get("error_code") in ["PEER_FLOOD", "FLOOD_WAIT", "ACCOUNT_COOLDOWN", "HOURLY_RATE_LIMIT", "ASSIGNED_BOT_LIMITED"]:
                            logger.warning(f"[⚠️ Account @{bot_name} Paused]: {res.get('error_code')}. Stopping this account's batch.")
                            break
                        else:
                            # Short pause for uncontactable or temporary skips
                            await asyncio.sleep(random.uniform(3.0, 6.0))
                except Exception as worker_err:
                    logger.error(f"[Worker Exception on @{bot_name}]: {worker_err}", exc_info=True)
                finally:
                    worker_db.close()
                return sent_total

            worker_tasks = [
                run_bot_outreach(ub, bot_queues[ub.id])
                for ub in ready_userbots
                if bot_queues.get(ub.id)
            ]

            if worker_tasks:
                total_enqueued = sum(len(q) for q in bot_queues.values())
                logger.info(f"[⚡ Parallel Outreach Started]: Dispatching {total_enqueued} cases across {len(worker_tasks)} parallel bot tasks for {tenant.name}...")
                results = await asyncio.gather(*worker_tasks, return_exceptions=True)
                total_sent = sum(r for r in results if isinstance(r, int))
                logger.info(f"[🏁 Parallel Outreach Finished for {tenant.name}]: Sent {total_sent} messages successfully across all accounts.")

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

    def calculate_cohort_winback(
        self,
        db: Session,
        channel_id: str,
        cohort_start: datetime,
        cohort_end: datetime,
        window_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Calculates retention/winback rate using cohort-based SQL query.
        Winback rate = (users who left in cohort AND returned) / (users who left in cohort).
        """
        if cohort_start.tzinfo is None:
            cohort_start = cohort_start.replace(tzinfo=timezone.utc)
        if cohort_end.tzinfo is None:
            cohort_end = cohort_end.replace(tzinfo=timezone.utc)

        # 1. Distinct users who left in this cohort window
        leavers_query = db.query(MembershipEvent.telegram_user_id).filter(
            MembershipEvent.channel_id == channel_id,
            MembershipEvent.event_type == "LEAVE",
            MembershipEvent.timestamp >= cohort_start,
            MembershipEvent.timestamp <= cohort_end
        ).distinct()
        leaver_ids = [row[0] for row in leavers_query.all()]
        total_leavers = len(leaver_ids)

        if total_leavers == 0:
            return {
                "channel_id": channel_id,
                "cohort_start": cohort_start,
                "cohort_end": cohort_end,
                "window": f"{window_days}d" if window_days else "custom",
                "total_leavers": 0,
                "total_returned": 0,
                "winback_rate_percent": 0.0
            }

        # 2. Distinct leavers who rejoined after cohort_start
        returned_query = db.query(MembershipEvent.telegram_user_id).filter(
            MembershipEvent.channel_id == channel_id,
            MembershipEvent.event_type == "JOIN",
            MembershipEvent.timestamp > cohort_start,
            MembershipEvent.telegram_user_id.in_(leaver_ids)
        )
        if window_days:
            max_return_time = cohort_end + timedelta(days=window_days)
            returned_query = returned_query.filter(MembershipEvent.timestamp <= max_return_time)

        returned_ids = {row[0] for row in returned_query.distinct().all()}
        total_returned = len(returned_ids)
        winback_rate = round((total_returned / total_leavers) * 100.0, 2)

        return {
            "channel_id": channel_id,
            "cohort_start": cohort_start,
            "cohort_end": cohort_end,
            "window": f"{window_days}d" if window_days else "custom",
            "total_leavers": total_leavers,
            "total_returned": total_returned,
            "winback_rate_percent": winback_rate
        }

retention_engine = RetentionEngine()

