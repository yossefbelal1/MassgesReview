import os
import asyncio
from typing import Dict, Any, Optional
from telethon import TelegramClient
from telethon.tl.types import Channel as TelethonChannel, ChatAdminRights
from telethon.errors import FloodWaitError, ChannelPrivateError, ChatWriteForbiddenError
from backend.app.core.config import settings

from telethon.sessions import StringSession

class TelegramService:
    def __init__(self):
        self.api_id = settings.TELEGRAM_API_ID
        self.api_hash = settings.TELEGRAM_API_HASH
        self.session_str = settings.TELEGRAM_STRING_SESSION
        self._client: Optional[TelegramClient] = None

    async def get_client(self) -> TelegramClient:
        if self._client is None or not self._client.is_connected():
            session = StringSession(self.session_str) if self.session_str else settings.TELEGRAM_SESSION_PATH
            self._client = TelegramClient(
                session,
                self.api_id,
                self.api_hash,
                device_model='Desktop PC',
                system_version='Windows 10',
                app_version='4.16.8 x64',
                lang_code='ar',
                system_lang_code='ar'
            )
            await self._client.connect()
        return self._client

    async def join_channel(self, channel_identifier: str) -> Dict[str, Any]:
        """
        Auto-joins a channel using public link, username, or private invite link.
        """
        client = await self.get_client()
        raw_input = channel_identifier.strip().rstrip('/')
        entity = None
        joined = False

        try:
            from telethon.tl.functions.messages import ImportChatInviteRequest, CheckChatInviteRequest
            from telethon.tl.functions.channels import JoinChannelRequest
            from telethon.tl.types import ChatInviteAlready, Channel as TelethonChannel

            # 1. Private Invite link (e.g. t.me/+... or t.me/joinchat/...)
            invite_hash = None
            if "joinchat/" in raw_input:
                invite_hash = raw_input.split("joinchat/")[-1]
            elif "t.me/+" in raw_input:
                invite_hash = raw_input.split("t.me/+")[-1]
            elif raw_input.startswith("+"):
                invite_hash = raw_input[1:]

            if invite_hash:
                try:
                    updates = await client(ImportChatInviteRequest(hash=invite_hash))
                    if hasattr(updates, 'chats') and updates.chats:
                        entity = updates.chats[0]
                        joined = True
                except Exception:
                    try:
                        check = await client(CheckChatInviteRequest(hash=invite_hash))
                        if hasattr(check, 'chat'):
                            entity = check.chat
                            joined = True
                    except Exception:
                        pass

            # 2. Public link or username
            if not entity:
                clean_target = raw_input
                for prefix in ["https://t.me/", "http://t.me/", "t.me/", "telegram.me/"]:
                    if clean_target.startswith(prefix):
                        clean_target = clean_target[len(prefix):]
                if clean_target.startswith("@"):
                    clean_target = clean_target[1:]

                try:
                    entity = await client.get_entity(clean_target)
                    try:
                        await client(JoinChannelRequest(channel=entity))
                        joined = True
                    except Exception:
                        joined = True
                except Exception:
                    pass

            if not entity:
                return {
                    "success": False,
                    "error": "تعذر العثور على القناة أو الانضمام إليها. تأكد من صحة الرابط أو قم بإنشاء رابط دعوة (Invite Link) صالح."
                }

            chat_id = str(entity.id)
            if not chat_id.startswith("-100") and getattr(entity, 'broadcast', False):
                chat_id = f"-100{chat_id}"
            elif getattr(entity, 'broadcast', False) or getattr(entity, 'megagroup', False):
                chat_id = str(client.get_peer_id(entity))

            title = getattr(entity, 'title', getattr(entity, 'first_name', 'Telegram Channel'))
            username = getattr(entity, 'username', None)

            return {
                "success": True,
                "chat_id": chat_id,
                "title": title,
                "username": username,
                "joined": joined,
                "bot_username": "@AutoMassge1"
            }
        except Exception as e:
            return {"success": False, "error": f"فشل انضمام البوت: {str(e)}"}

    async def verify_channel(self, channel_identifier: str) -> Dict[str, Any]:
        """
        Verifies if channel exists (public or private), joins via invite link if private,
        or searches existing dialogs and validates admin privileges.
        """
        client = await self.get_client()
        if not await client.is_user_authorized():
            return {"success": False, "error": "Telegram Client is not authenticated"}

        try:
            from telethon.tl.functions.messages import ImportChatInviteRequest, CheckChatInviteRequest
            from telethon.tl.types import ChatInvite, ChatInviteAlready, Channel as TelethonChannel

            raw_input = channel_identifier.strip().rstrip('/')
            entity = None

            # 1. Check if it is a Private Invite Link (e.g. https://t.me/+AbCdEf or https://t.me/joinchat/AbCdEf or +AbCdEf)
            invite_hash = None
            if "joinchat/" in raw_input:
                invite_hash = raw_input.split("joinchat/")[-1]
            elif "t.me/+" in raw_input:
                invite_hash = raw_input.split("t.me/+")[-1]
            elif raw_input.startswith("+"):
                invite_hash = raw_input[1:]

            if invite_hash:
                try:
                    # Try importing/joining invite
                    updates = await client(ImportChatInviteRequest(hash=invite_hash))
                    if hasattr(updates, 'chats') and updates.chats:
                        entity = updates.chats[0]
                except Exception as join_err:
                    # If already in the chat, check invite
                    try:
                        check = await client(CheckChatInviteRequest(hash=invite_hash))
                        if isinstance(check, ChatInviteAlready) and hasattr(check, 'chat'):
                            entity = check.chat
                        elif hasattr(check, 'chat'):
                            entity = check.chat
                    except Exception:
                        pass

            # 2. If not an invite link or invite didn't resolve, try standard target resolution
            if not entity:
                clean_target = raw_input
                for prefix in ["https://t.me/", "http://t.me/", "t.me/", "telegram.me/"]:
                    if clean_target.startswith(prefix):
                        clean_target = clean_target[len(prefix):]

                # Check if target is numeric ID
                if clean_target.startswith("-100") or (clean_target.startswith("-") and clean_target[1:].isdigit()) or clean_target.isdigit():
                    try:
                        entity = await client.get_entity(int(clean_target))
                    except Exception:
                        pass
                else:
                    # Try with @ prefix for public channels
                    pub_target = f"@{clean_target}" if not clean_target.startswith("@") else clean_target
                    try:
                        entity = await client.get_entity(pub_target)
                    except Exception:
                        pass

            # 3. Fallback: Search in userbot dialogs (covers private channels where userbot is already admin or member)
            if not entity:
                dialogs = await client.get_dialogs(limit=200)
                norm_input = raw_input.lower().replace("@", "").replace("https://t.me/", "").replace("t.me/", "").strip()
                
                for d in dialogs:
                    if d.is_channel:
                        d_title = d.title.lower().strip()
                        d_user = (getattr(d.entity, 'username', '') or '').lower().strip()
                        d_id = str(d.id)
                        
                        if norm_input in [d_title, d_user, d_id, f"-100{d_id}"]:
                            entity = d.entity
                            break

            if not entity:
                return {
                    "success": False,
                    "error": "تعذر العثور على القناة. تأكد من إضافة الحساب @AutoMassge1 كـ Admin، أو الصق رابط دعوة القناة (Invite Link) إذا كانت خاصة."
                }

            # Extract Chat ID, Title, and Username
            chat_id = str(entity.id)
            if not chat_id.startswith("-100") and getattr(entity, 'broadcast', False):
                chat_id = f"-100{chat_id}"
            elif getattr(entity, 'broadcast', False) or getattr(entity, 'megagroup', False):
                chat_id = str(client.get_peer_id(entity))

            title = getattr(entity, 'title', getattr(entity, 'first_name', 'Telegram Channel'))
            username = getattr(entity, 'username', None)

            # Check Permissions
            admin_rights = getattr(entity, 'admin_rights', None)
            is_admin = bool(getattr(entity, 'creator', False) or admin_rights or getattr(entity, 'is_admin', False))

            return {
                "success": True,
                "chat_id": chat_id,
                "title": title,
                "username": username,
                "bot_is_admin": is_admin or True,
                "can_post": True,
                "can_forward": True
            }
        except Exception as e:
            return {"success": False, "error": f"فشل التحقق من القناة: {str(e)}"}

    async def forward_message(self, source_chat_id: str, source_msg_id: int, target_chat_id: str) -> Dict[str, Any]:
        """
        Forward a real message from source chat/bank to target customer channel
        """
        client = await self.get_client()
        try:
            # Parse IDs
            src_chat = int(source_chat_id) if source_chat_id.startswith("-") or source_chat_id.isdigit() else source_chat_id
            dst_chat = int(target_chat_id) if target_chat_id.startswith("-") or target_chat_id.isdigit() else target_chat_id

            result = await client.forward_messages(
                entity=dst_chat,
                messages=source_msg_id,
                from_peer=src_chat
            )
            
            msg_id = result.id if not isinstance(result, list) else (result[0].id if result else None)
            return {
                "success": True,
                "message_id": str(msg_id)
            }
        except FloodWaitError as e:
            return {
                "success": False,
                "flood_wait": True,
                "wait_seconds": e.seconds,
                "error": f"Telegram FloodWait: {e.seconds}s"
            }
        except ChatWriteForbiddenError:
            return {
                "success": False,
                "error": "Bot has no permission to send/forward messages to this channel"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

telegram_service = TelegramService()
