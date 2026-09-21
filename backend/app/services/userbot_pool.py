import asyncio
import logging
import random
import time
from datetime import datetime, timezone, date
from typing import Dict, Any, Optional, List, Callable, Tuple
from telethon import TelegramClient, events
from telethon.errors import (
    FloodWaitError,
    UserPrivacyRestrictedError,
    UserNotMutualContactError,
    PeerFloodError,
    UserIsBlockedError,
    InputUserDeactivatedError,
    ChatWriteForbiddenError,
    RPCError
)
from backend.app.services.telegram_service import telegram_service
from backend.app.core.config import settings

logger = logging.getLogger("reviewflow.userbot_pool")

class UserbotSession:
    def __init__(self, name: str, get_client_fn: Callable[[], Any], max_daily_contacts: int = 35):
        self.name = name
        self.get_client_fn = get_client_fn
        self.max_daily_contacts = max_daily_contacts
        self.daily_contacts_count = 0
        self.last_contact_date: Optional[date] = None
        self.cooldown_until: float = 0.0
        self.last_message_sent_at: float = 0.0
        self.username: Optional[str] = None
        self.user_id: Optional[int] = None
        self.is_healthy: bool = True
        self.last_error: Optional[str] = None

    def _refresh_daily_quota(self):
        today = datetime.now(timezone.utc).date()
        if self.last_contact_date != today:
            self.last_contact_date = today
            self.daily_contacts_count = 0

    def can_send_contact(self) -> Tuple[bool, str]:
        self._refresh_daily_quota()
        now = time.time()
        if now < self.cooldown_until:
            wait_remaining = int(self.cooldown_until - now)
            return False, f"Account in cooldown for {wait_remaining}s"
        if self.daily_contacts_count >= self.max_daily_contacts:
            return False, f"Daily contact limit reached ({self.daily_contacts_count}/{self.max_daily_contacts})"
        return True, "Ready"

    async def get_client(self) -> Optional[TelegramClient]:
        try:
            client = await self.get_client_fn()
            if client and (not self.username or not self.user_id):
                try:
                    me = await client.get_me()
                    if me:
                        self.username = getattr(me, 'username', None) or f"user_{me.id}"
                        self.user_id = me.id
                except Exception:
                    pass
            return client
        except Exception as e:
            self.is_healthy = False
            self.last_error = str(e)
            return None


class UserbotPool:
    """
    Unified Multi-Userbot Session Pool.
    Manages Telegram user accounts as a unified team with intelligent failover,
    FloodWait backoff, anti-spam spacing, and daily contact limits.
    """
    def __init__(self):
        self.sessions: List[UserbotSession] = [
            UserbotSession("primary", telegram_service.ensure_connected, max_daily_contacts=35)
        ]
        if getattr(settings, 'TELEGRAM_BACKUP_STRING_SESSION', None):
            self.sessions.append(
                UserbotSession("backup", telegram_service.get_backup_client, max_daily_contacts=30)
            )
        self._inbound_handlers: List[Callable[[Any, TelegramClient, str], Any]] = []
        self._listeners_registered = False

    def register_inbound_handler(self, handler: Callable[[Any, TelegramClient, str], Any]):
        """Registers a handler for incoming private messages across all userbots."""
        self._inbound_handlers.append(handler)

    async def ensure_listeners_registered(self):
        """Attaches incoming message listeners to all connected userbot sessions."""
        if self._listeners_registered:
            return

        for s in self.sessions:
            client = await s.get_client()
            if not client:
                continue

            bot_name = s.name

            @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
            async def _on_private_message(event, session_name=bot_name, active_client=client):
                # Ignore messages from self or bots
                if event.is_channel or event.is_group:
                    return
                sender = await event.get_sender()
                if not sender or getattr(sender, 'bot', False):
                    return

                logger.info(f"[💬 Inbound Userbot DM ({session_name})]: From {sender.id} (@{getattr(sender, 'username', 'no_user')}): '{event.raw_text[:60]}'")
                for handler in self._inbound_handlers:
                    try:
                        await handler(event, active_client, session_name)
                    except Exception as he:
                        logger.error(f"[!] Error in inbound retention handler: {he}", exc_info=True)

        self._listeners_registered = True
        logger.info("[✓] UserbotPool inbound DM listeners registered successfully.")

    def select_best_session(self, preferred: Optional[str] = None) -> Optional[UserbotSession]:
        """Selects the best available userbot session based on health and quota."""
        # 1. Try preferred session first if healthy and capable
        if preferred:
            for s in self.sessions:
                if (s.name == preferred or s.username == preferred) and s.is_healthy:
                    ok, _ = s.can_send_contact()
                    if ok:
                        return s

        # 2. Pick any ready session with lowest daily count for load balancing
        ready_sessions = []
        for s in self.sessions:
            if s.is_healthy:
                ok, _ = s.can_send_contact()
                if ok:
                    ready_sessions.append(s)

        if not ready_sessions:
            return None

        # Sort by least contacts sent today
        ready_sessions.sort(key=lambda s: s.daily_contacts_count)
        return ready_sessions[0]

    async def send_direct_message(
        self,
        target_user_id: int,
        text: str,
        channel_id: Optional[str] = None,
        preferred_session: Optional[str] = None,
        target_username: Optional[str] = None,
        access_hash: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Sends a direct private message to a Telegram user.
        Guarantees respectful pacing, safety checks, and seamless failover.
        """
        session = self.select_best_session(preferred_session)
        if not session:
            logger.warning("[⚠️ UserbotPool]: No active userbot session has available daily quota or all are in cooldown.")
            return {
                "success": False,
                "error": "ALL_SESSIONS_BUSY_OR_LIMIT_REACHED",
                "error_ar": "حساب اليوزربوت في فترة انتظار حالياً أو استنفد الحد اليومي. يمكنك المراسلة عبر زر تيليجرام ↗ مباشرة.",
                "can_retry": True,
                "retry_delay_seconds": 1800
            }

        client = await session.get_client()
        if not client:
            session.is_healthy = False
            alternate = [s for s in self.sessions if s != session and s.is_healthy and time.time() >= s.cooldown_until]
            if alternate:
                return await self.send_direct_message(target_user_id, text, channel_id, preferred_session=alternate[0].name, target_username=target_username, access_hash=access_hash)
            return {
                "success": False,
                "error": "CLIENT_DISCONNECTED",
                "error_ar": "تعذر الاتصال بحساب اليوزربوت حالياً. يمكنك استخدام زر تيليجرام ↗ للمراسلة الفورية من حسابك.",
                "can_retry": True,
                "retry_delay_seconds": 60
            }

        # Anti-spam safety spacing (8-14s between cold outreach)
        now = time.time()
        elapsed_since_last = now - session.last_message_sent_at
        if elapsed_since_last < 10.0:
            await asyncio.sleep(random.uniform(8.0, 14.0))

        try:
            # 1. If access_hash is provided, use InputPeerUser directly (100% reliable across restarts)
            if access_hash:
                from telethon.tl.types import InputPeerUser
                entity = InputPeerUser(int(target_user_id), int(access_hash))
            elif target_username:
                entity = target_username
            else:
                try:
                    entity = await client.get_entity(target_user_id)
                except Exception:
                    entity = target_user_id

            # Send message
            sent_msg = await client.send_message(entity, text)
            session.daily_contacts_count += 1
            session.last_message_sent_at = time.time()
            session.is_healthy = True
            session.last_error = None

            bot_display = session.username or session.name
            logger.info(f"[🚀 Userbot Outbound ({bot_display})]: Sent recovery message to user {target_user_id} (@{target_username or 'no_user'})")
            return {
                "success": True,
                "session_name": session.name,
                "userbot_username": bot_display,
                "telegram_message_id": str(sent_msg.id),
                "error": None
            }

        except UserPrivacyRestrictedError:
            logger.info(f"[🛡️ Privacy Restricted]: User {target_user_id} does not allow DMs from non-contacts.")
            return {
                "success": False,
                "error": "USER_PRIVACY_RESTRICTED",
                "error_ar": "إعدادات خصوصية هذا المستخدم تمنع استقبال الرسائل من غير جهات الاتصال لديه.",
                "uncontactable_reason": "PRIVACY_RESTRICTED",
                "can_retry": False
            }

        except UserNotMutualContactError:
            logger.info(f"[🛡️ Not Mutual Contact]: User {target_user_id} requires mutual contact.")
            return {
                "success": False,
                "error": "NOT_MUTUAL_CONTACT",
                "error_ar": "المستخدم يشترط أن تكون جهة اتصال متبادلة لمراسلته.",
                "uncontactable_reason": "NOT_MUTUAL_CONTACT",
                "can_retry": False
            }

        except (UserIsBlockedError, InputUserDeactivatedError):
            logger.info(f"[🚫 User Inaccessible]: User {target_user_id} is deleted or has blocked the bot.")
            return {
                "success": False,
                "error": "USER_BLOCKED_OR_DELETED",
                "error_ar": "حساب هذا المستخدم محذوف أو قام بحظر البوت.",
                "uncontactable_reason": "USER_BLOCKED_OR_DELETED",
                "can_retry": False
            }

        except PeerFloodError:
            logger.warning(f"[⚠️ PeerFlood Triggered]: Session {session.name} received PeerFloodError. Initiating cooldown.")
            session.cooldown_until = time.time() + 1200
            session.last_error = "PeerFloodError"

            # Failover to secondary session if healthy
            alternate = [s for s in self.sessions if s != session and s.is_healthy and time.time() >= s.cooldown_until]
            if alternate:
                logger.info(f"[🔄 Failover]: Re-attempting via alternate session {alternate[0].name}...")
                return await self.send_direct_message(target_user_id, text, channel_id, preferred_session=alternate[0].name, target_username=target_username, access_hash=access_hash)

            return {
                "success": False,
                "error": "PEER_FLOOD",
                "error_ar": "حساب اليوزربوت مقيد مؤقتاً من تيليجرام لمراسلة غير جهات الاتصال (PeerFlood). يمكنك المراسلة عبر زر تيليجرام ↗ مباشرة من حسابك.",
                "can_retry": True,
                "retry_delay_seconds": 1200
            }

        except FloodWaitError as fwe:
            wait_time = int(getattr(fwe, 'seconds', 60))
            logger.warning(f"[⏳ FloodWait]: Session {session.name} hit FloodWait for {wait_time}s.")
            session.cooldown_until = time.time() + wait_time

            alternate = [s for s in self.sessions if s != session and s.is_healthy and time.time() >= s.cooldown_until]
            if alternate:
                return await self.send_direct_message(target_user_id, text, channel_id, preferred_session=alternate[0].name, target_username=target_username, access_hash=access_hash)

            return {
                "success": False,
                "error": f"FLOOD_WAIT_{wait_time}",
                "error_ar": f"طلب تيليجرام الانتظار {wait_time} ثانية قبل إرسال رسائل جديدة.",
                "can_retry": True,
                "retry_after": wait_time,
                "retry_delay_seconds": wait_time
            }

        except Exception as err:
            logger.error(f"[!] Error sending direct message to {target_user_id}: {err}", exc_info=True)
            return {
                "success": False,
                "error": str(err),
                "error_ar": f"خطأ أثناء الإرسال: {str(err)}",
                "can_retry": True,
                "retry_delay_seconds": 300
            }

    async def get_userbot_avatar(self, session_name: str = "primary") -> Optional[bytes]:
        """Downloads and returns profile picture bytes for the requested userbot session."""
        session = next((s for s in self.sessions if s.name == session_name), None)
        if not session:
            return None
        client = await session.get_client()
        if not client:
            return None
        try:
            return await client.download_profile_photo('me', bytes)
        except Exception as e:
            logger.error(f"Error fetching avatar for {session_name}: {e}")
            return None

    async def update_userbot_avatar(self, session_name: str, file_bytes: bytes, filename: str = "avatar.jpg") -> bool:
        """Uploads a new profile picture to Telegram for the userbot session."""
        session = next((s for s in self.sessions if s.name == session_name), None)
        if not session:
            return False
        client = await session.get_client()
        if not client:
            return False
        try:
            from telethon.tl.functions.photos import UploadProfilePhotoRequest
            import io
            buf = io.BytesIO(file_bytes)
            buf.name = filename
            uploaded = await client.upload_file(buf)
            await client(UploadProfilePhotoRequest(fallback=False, file=uploaded))
            logger.info(f"[✓ Avatar Updated]: Successfully changed Telegram profile photo for session '{session_name}'.")
            return True
        except Exception as e:
            logger.error(f"[!] Error updating avatar for {session_name}: {e}", exc_info=True)
            raise e

    async def get_pool_status(self) -> List[Dict[str, Any]]:
        """Returns health, quota, and identity metrics for all userbot sessions."""
        status_list = []
        for s in self.sessions:
            s._refresh_daily_quota()
            client = await s.get_client()
            has_photo = False
            if client:
                try:
                    me = await client.get_me()
                    has_photo = bool(getattr(me, 'photo', None))
                except Exception:
                    pass
            status_list.append({
                "name": s.name,
                "username": s.username or "Unknown",
                "user_id": s.user_id,
                "is_healthy": s.is_healthy,
                "has_photo": has_photo,
                "daily_contacts_sent": s.daily_contacts_count,
                "max_daily_contacts": s.max_daily_contacts,
                "in_cooldown": time.time() < s.cooldown_until,
                "last_error": s.last_error
            })
        return status_list

userbot_pool = UserbotPool()
