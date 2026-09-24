import asyncio
import logging
import random
import time
from datetime import datetime, timezone, date, timedelta
from typing import Dict, Any, Optional, Tuple
from fastapi import HTTPException
from sqlalchemy.orm import Session
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    FloodWaitError,
    UserPrivacyRestrictedError,
    UserNotMutualContactError,
    PeerFloodError,
    UserIsBlockedError,
    InputUserDeactivatedError,
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    ApiIdInvalidError,
    PhoneNumberInvalidError,
    PeerIdInvalidError,
    RPCError
)
from telethon.tl.types import InputPeerUser
from telethon.tl.functions.photos import UploadProfilePhotoRequest

from backend.app.models.models import Channel, ChannelUserbot, UserbotLoginAttempt

logger = logging.getLogger("reviewflow.dedicated_userbot")

class DedicatedUserbotService:
    """
    Manages dedicated per-channel Telegram userbots:
    - Interactive onboarding (send_code_request -> sign_in with OTP and 2FA)
    - Session caching and lifetime management
    - Cold outreach execution with quota isolation per channel
    """
    def __init__(self):
        self._clients: Dict[str, TelegramClient] = {}
        self._last_message_times: Dict[str, float] = {}

    async def send_login_code(
        self,
        db: Session,
        tenant_id: str,
        channel_id: str,
        api_id: int,
        api_hash: str,
        phone: str
    ) -> Dict[str, Any]:
        """
        Initiates Telegram authentication for a channel owner.
        Generates initial auth key, requests SMS/app login code from Telegram,
        and saves the temporary session state.
        """
        # 1. Verify channel ownership
        channel = db.query(Channel).filter(
            Channel.id == channel_id,
            Channel.tenant_id == tenant_id
        ).first()
        if not channel:
            raise HTTPException(status_code=404, detail="القناة المحددة غير موجودة أو غير مصرح لك بإدارتها.")

        # 2. Sanitize inputs and fallback to platform credentials if omitted
        clean_phone = "".join(ch for ch in phone if ch.isdigit() or ch == "+").strip()
        if not clean_phone.startswith("+"):
            clean_phone = "+" + clean_phone
        
        final_api_id = int(api_id) if (api_id and str(api_id).strip()) else int(settings.TELEGRAM_API_ID)
        final_api_hash = str(api_hash).strip() if (api_hash and str(api_hash).strip()) else str(settings.TELEGRAM_API_HASH).strip()

        # 3. Request login code from Telegram MTProto
        temp_client = TelegramClient(
            StringSession(),
            final_api_id,
            final_api_hash,
            device_model="ReviewFlow SaaS",
            system_version="Linux / Cloud",
            app_version="2.0.0",
            lang_code="ar"
        )

        try:
            await temp_client.connect()
            res = await temp_client.send_code_request(clean_phone)
            temp_session_str = temp_client.session.save()
            phone_code_hash = res.phone_code_hash
        except PhoneNumberInvalidError:
            raise HTTPException(status_code=400, detail="رقم الهاتف غير صالح. يرجى التأكد من كتابة الرقم بصيغته الدولية الكاملة (مثال: +966501234567 أو +201012345678).")
        except ApiIdInvalidError:
            raise HTTPException(status_code=400, detail="الـ API ID أو API HASH غير صحيح. يرجى التأكد من نسخهما بدقة من موقع my.telegram.org.")
        except FloodWaitError as fwe:
            raise HTTPException(status_code=429, detail=f"طلب تيليجرام الانتظار {fwe.seconds} ثانية قبل طلب كود جديد لهذا الرقم.")
        except Exception as e:
            logger.error(f"Error sending login code for channel {channel_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"حدث خطأ أثناء الاتصال بتيليجرام: {str(e)}")
        finally:
            try:
                await temp_client.disconnect()
            except Exception:
                pass

        # 4. Remove previous login attempts for this channel
        db.query(UserbotLoginAttempt).filter(UserbotLoginAttempt.channel_id == channel_id).delete()

        # 5. Store active login attempt
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        attempt = UserbotLoginAttempt(
            tenant_id=tenant_id,
            channel_id=channel_id,
            api_id=final_api_id,
            api_hash=final_api_hash,
            phone=clean_phone,
            phone_code_hash=phone_code_hash,
            temp_session_str=temp_session_str,
            expires_at=expires_at
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        return {
            "success": True,
            "login_attempt_id": attempt.id,
            "phone_code_hash": phone_code_hash,
            "message": "تم إرسال كود التحقق بنجاح إلى تطبيق تيليجرام الخاص بك 📲"
        }

    async def verify_login_code(
        self,
        db: Session,
        tenant_id: str,
        login_attempt_id: str,
        code: str,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verifies login code (+ optional 2FA password) and establishes persistent userbot session.
        """
        # 1. Fetch active login attempt
        attempt = db.query(UserbotLoginAttempt).filter(
            UserbotLoginAttempt.id == login_attempt_id,
            UserbotLoginAttempt.tenant_id == tenant_id
        ).first()
        if not attempt:
            raise HTTPException(status_code=404, detail="جلسة تسجيل الدخول غير موجودة أو انتهت صلاحيتها. يرجى طلب كود جديد.")

        now = datetime.now(timezone.utc)
        expires_at = attempt.expires_at
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at and expires_at < now:
            db.delete(attempt)
            db.commit()
            raise HTTPException(status_code=400, detail="انتهت صلاحية كود التحقق (10 دقائق). يرجى طلب كود جديد.")

        clean_code = "".join(ch for ch in code if ch.isdigit() or ch.isalpha()).strip()

        # 2. Connect with Telethon using temporary StringSession
        client = TelegramClient(
            StringSession(attempt.temp_session_str),
            attempt.api_id,
            attempt.api_hash,
            device_model="ReviewFlow SaaS",
            system_version="Linux / Cloud",
            app_version="2.0.0",
            lang_code="ar"
        )

        try:
            await client.connect()
            try:
                await client.sign_in(
                    phone=attempt.phone,
                    code=clean_code,
                    phone_code_hash=attempt.phone_code_hash
                )
            except SessionPasswordNeededError:
                if not password or not str(password).strip():
                    return {
                        "success": False,
                        "needs_2fa": True,
                        "message": "حسابك محمي بخاصية التحقق بخطوتين (2FA). يرجى إدخال كلمة المرور السحابية للمتابعة 🔐"
                    }
                await client.sign_in(password=password.strip())

            # 3. Verification succeeded -> extract permanent session and account profile
            final_session_str = client.session.save()
            me = await client.get_me()
            tg_user_id = str(me.id)
            tg_username = getattr(me, 'username', None)
            tg_first_name = getattr(me, 'first_name', None) or f"user_{me.id}"

        except (PhoneCodeInvalidError, PhoneCodeExpiredError):
            raise HTTPException(status_code=400, detail="كود التحقق غير صحيح أو منتهي الصلاحية. يرجى التأكد من إدخال الكود الأحدث.")
        except SessionPasswordNeededError:
            return {
                "success": False,
                "needs_2fa": True,
                "message": "يرجى كتابة كلمة مرور التحقق بخطوتين (2FA) الخاصة بحسابك."
            }
        except Exception as e:
            logger.error(f"Error verifying code for attempt {login_attempt_id}: {e}", exc_info=True)
            raise HTTPException(status_code=400, detail=f"فشل التحقق من الحساب: {str(e)}")
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

        # 4. Upsert into channel_userbots by tenant_id and phone
        userbot = db.query(ChannelUserbot).filter(
            ChannelUserbot.tenant_id == tenant_id,
            ChannelUserbot.phone == attempt.phone
        ).first()
        if not userbot:
            userbot = ChannelUserbot(
                tenant_id=tenant_id,
                channel_id=attempt.channel_id,
                api_id=attempt.api_id,
                api_hash=attempt.api_hash,
                phone=attempt.phone,
                string_session=final_session_str,
                telegram_user_id=tg_user_id,
                username=tg_username,
                first_name=tg_first_name,
                is_active=True,
                status="CONNECTED",
                daily_contacts_count=0
            )
            db.add(userbot)
        else:
            userbot.channel_id = attempt.channel_id
            userbot.api_id = attempt.api_id
            userbot.api_hash = attempt.api_hash
            userbot.phone = attempt.phone
            userbot.string_session = final_session_str
            userbot.telegram_user_id = tg_user_id
            userbot.username = tg_username
            userbot.first_name = tg_first_name
            userbot.is_active = True
            userbot.status = "CONNECTED"
            userbot.last_error = None

        # Clean up login attempt
        db.delete(attempt)
        db.commit()
        db.refresh(userbot)

        # Clear any cached client
        cache_key = userbot.id
        if cache_key in self._clients:
            try:
                await self._clients[cache_key].disconnect()
            except Exception:
                pass
            del self._clients[cache_key]

        logger.info(f"[✓] Dedicated userbot @{tg_username or tg_user_id} ({userbot.phone}) linked to channel {attempt.channel_id} successfully.")

        return {
            "success": True,
            "needs_2fa": False,
            "message": f"تم ربط اليوزربوت بنجاح! متصل الآن باسم: {tg_first_name} (@{tg_username or 'بدون معرف'}) 🎉",
            "userbot": {
                "telegram_user_id": tg_user_id,
                "username": tg_username,
                "first_name": tg_first_name,
                "phone": userbot.phone,
                "channel_id": userbot.channel_id
            }
        }

    async def get_client_for_channel(self, db: Session, channel_id: str, userbot_id: Optional[str] = None) -> Optional[TelegramClient]:
        """
        Retrieves or instantiates an active, authenticated TelegramClient for the channel's userbot.
        """
        cache_key = userbot_id or channel_id
        if cache_key in self._clients:
            client = self._clients[cache_key]
            if client.is_connected():
                return client
            try:
                await client.connect()
                return client
            except Exception:
                pass

        if userbot_id:
            userbot = db.query(ChannelUserbot).filter(
                ChannelUserbot.id == userbot_id,
                ChannelUserbot.is_active == True
            ).first()
        else:
            userbot = db.query(ChannelUserbot).filter(
                ChannelUserbot.channel_id == channel_id,
                ChannelUserbot.is_active == True
            ).first()

        if not userbot or not userbot.string_session:
            return None

        client = TelegramClient(
            StringSession(userbot.string_session),
            userbot.api_id,
            userbot.api_hash,
            device_model="ReviewFlow SaaS",
            system_version="Linux / Cloud",
            app_version="2.0.0",
            lang_code="ar",
            auto_reconnect=True,
            connection_retries=3,
            retry_delay=2
        )

        try:
            await client.connect()
            if not await client.is_user_authorized():
                userbot.status = "NEEDS_REAUTH"
                userbot.last_error = "Session expired or revoked on Telegram"
                db.commit()
                return None

            self._clients[cache_key] = client
            self._clients[userbot.id] = client
            return client
        except Exception as e:
            userbot.last_error = str(e)
            db.commit()
            logger.error(f"Error connecting dedicated userbot {userbot.id} for channel {channel_id}: {e}")
            return None

    async def send_direct_message_for_channel(
        self,
        db: Session,
        channel_id: str,
        target_user_id: int,
        text: str,
        target_username: Optional[str] = None,
        access_hash: Optional[int] = None,
        userbot_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sends cold recovery message via channel's dedicated userbot with quota safety and pacing.
        """
        query = db.query(ChannelUserbot).filter(ChannelUserbot.is_active == True)
        if userbot_id:
            userbot = query.filter(ChannelUserbot.id == userbot_id).first()
        else:
            userbot = query.filter(ChannelUserbot.channel_id == channel_id).first()

        if not userbot:
            return {"success": False, "error": "NO_DEDICATED_USERBOT", "can_retry": False}

        # Check daily quota
        today = datetime.now(timezone.utc).date()
        if userbot.last_contact_date != today:
            userbot.last_contact_date = today
            userbot.daily_contacts_count = 0
            db.commit()

        if userbot.daily_contacts_count >= 35:
            return {
                "success": False,
                "error": "DAILY_QUOTA_REACHED",
                "error_ar": "تم بلوغ الحد الأقصى للمراسلات اليومية لهذا الحساب (35 رسالة).",
                "can_retry": True,
                "retry_delay_seconds": 3600
            }

        # Check cooldown
        if userbot.cooldown_until:
            cooldown = userbot.cooldown_until
            if cooldown.tzinfo is None:
                cooldown = cooldown.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if cooldown > now:
                rem = int((cooldown - now).total_seconds())
                return {
                    "success": False,
                    "error": "ACCOUNT_COOLDOWN",
                    "error_ar": f"الحساب في فترة راحة مؤقتة لـ {rem} ثانية.",
                    "can_retry": True,
                    "retry_delay_seconds": rem
                }
            else:
                # Cooldown expired! Auto-restore status to CONNECTED
                userbot.status = "CONNECTED"
                userbot.cooldown_until = None
                userbot.last_error = None
                db.commit()

        client = await self.get_client_for_channel(db, channel_id, userbot_id=userbot.id)
        if not client:
            return {
                "success": False,
                "error": "CLIENT_DISCONNECTED",
                "error_ar": "تعذر الاتصال بيوزربوت القناة. يرجى التحقق من حالة الحساب في الإعدادات.",
                "can_retry": True,
                "retry_delay_seconds": 300
            }

        # Fast minimal anti-spam pacing (1.5 - 3.0s) per userbot
        bot_key = userbot.id or channel_id
        last_sent = self._last_message_times.get(bot_key, 0.0)
        elapsed = time.time() - last_sent
        if elapsed < 2.0:
            await asyncio.sleep(random.uniform(1.5, 3.0))

        try:
            # Resolve target entity
            if target_username:
                entity = target_username
            elif access_hash:
                entity = InputPeerUser(int(target_user_id), int(access_hash))
            else:
                try:
                    entity = await client.get_entity(int(target_user_id))
                except Exception:
                    entity = int(target_user_id)

            # Simulate natural human typing action to satisfy Telegram anti-spam heuristics
            try:
                async with client.action(entity, 'typing'):
                    await asyncio.sleep(random.uniform(1.2, 2.2))
            except Exception:
                pass

            sent_msg = await client.send_message(entity, text)
            userbot.daily_contacts_count += 1
            userbot.status = "CONNECTED"
            userbot.last_error = None
            self._last_message_times[bot_key] = time.time()
            db.commit()

            bot_display = userbot.username or userbot.first_name or f"Userbot_{userbot.phone}"
            logger.info(f"[🚀 Dedicated Userbot ({bot_display})]: Sent recovery message to {target_user_id} for channel {channel_id}")
            return {
                "success": True,
                "userbot_username": bot_display,
                "telegram_message_id": str(sent_msg.id),
                "is_dedicated": True,
                "error": None
            }

        except UserPrivacyRestrictedError:
            return {
                "success": False,
                "error": "USER_PRIVACY_RESTRICTED",
                "error_ar": "إعدادات خصوصية هذا المستخدم تمنع استقبال الرسائل من غير جهات الاتصال.",
                "uncontactable_reason": "PRIVACY_RESTRICTED",
                "can_retry": False
            }
        except UserNotMutualContactError:
            return {
                "success": False,
                "error": "NOT_MUTUAL_CONTACT",
                "error_ar": "المستخدم يشترط أن تكون جهة اتصال متبادلة لمراسلته.",
                "uncontactable_reason": "NOT_MUTUAL_CONTACT",
                "can_retry": False
            }
        except (UserIsBlockedError, InputUserDeactivatedError):
            return {
                "success": False,
                "error": "USER_BLOCKED_OR_DELETED",
                "error_ar": "حساب المستخدم محذوف أو قام بحظر المراسلة.",
                "uncontactable_reason": "USER_BLOCKED_OR_DELETED",
                "can_retry": False
            }
        except (ValueError, TypeError, KeyError) as val_err:
            logger.info(f"[🛡️ Unresolvable Telegram Entity]: User {target_user_id} cannot be resolved by MTProto: {val_err}")
            return {
                "success": False,
                "error": "CANNOT_RESOLVE_PEER",
                "error_ar": "لا يملك المستخدم معرفاً عاماً (@username) أو جهة اتصال متبادلة، وتمنع بروتوكولات تيليجرام مراسلته بدون معرف.",
                "uncontactable_reason": "NO_USERNAME_OR_ACCESS_HASH",
                "can_retry": False
            }
        except PeerFloodError:
            userbot.cooldown_until = datetime.now(timezone.utc) + timedelta(minutes=15)
            userbot.status = "FLOOD_WAIT"
            userbot.last_error = "PeerFloodError from Telegram"
            db.commit()
            return {
                "success": False,
                "error": "PEER_FLOOD",
                "error_ar": "الحساب مقيد مؤقتاً لدقائق من تيليجرام لمراسلة غير جهات الاتصال.",
                "can_retry": True,
                "retry_delay_seconds": 900
            }
        except FloodWaitError as fwe:
            wait = int(getattr(fwe, 'seconds', 60))
            userbot.cooldown_until = datetime.now(timezone.utc) + timedelta(seconds=wait)
            userbot.status = "FLOOD_WAIT"
            userbot.last_error = f"FloodWaitError: {wait}s"
            db.commit()
            return {
                "success": False,
                "error": f"FLOOD_WAIT_{wait}",
                "error_ar": f"طلب تيليجرام الانتظار {wait} ثانية.",
                "can_retry": True,
                "retry_delay_seconds": wait
            }
        except PeerIdInvalidError:
            return {
                "success": False,
                "error": "PEER_ID_INVALID",
                "error_ar": "لا يملك المستخدم معرفاً عاماً (@username) أو إعدادات خصوصيته تمنع المراسلة المباشرة.",
                "uncontactable_reason": "NO_USERNAME_OR_ACCESS_HASH",
                "can_retry": False
            }
        except RPCError as rpc_err:
            err_msg = str(rpc_err).upper()
            logger.warning(f"[⚠️ RPC Error in dedicated userbot {channel_id} for user {target_user_id}]: {rpc_err}")
            if any(term in err_msg for term in ["PRIVACY_PREMIUM_REQUIRED", "PRIVACY_RESTRICTED", "USER_PRIVACY", "CHAT_WRITE_FORBIDDEN", "PEER_ID_INVALID", "USER_BANNED"]):
                return {
                    "success": False,
                    "error": "PRIVACY_RESTRICTED",
                    "error_ar": "إعدادات خصوصية هذا المستخدم (أو اشتراط تيليجرام بريميوم) تمنع مراسلته من الحسابات غير المضافة لديه.",
                    "uncontactable_reason": "PRIVACY_RESTRICTED" if "PRIVACY" in err_msg else "USER_BLOCKED_OR_DELETED",
                    "can_retry": False
                }
            return {
                "success": False,
                "error": str(rpc_err),
                "error_ar": f"خطأ أثناء الإرسال: {str(rpc_err)}",
                "can_retry": True,
                "retry_delay_seconds": 120
            }
        except Exception as e:
            err_msg = str(e).upper()
            logger.error(f"Error sending message from dedicated userbot {channel_id}: {e}", exc_info=True)
            if any(term in err_msg for term in ["INPUT ENTITY", "COULD NOT FIND", "CANNOT CAST"]):
                return {
                    "success": False,
                    "error": "CANNOT_RESOLVE_PEER",
                    "error_ar": "لا يمكن الوصول للمستخدم بدون معرف تيليجرام (@username).",
                    "uncontactable_reason": "NO_USERNAME_OR_ACCESS_HASH",
                    "can_retry": False
                }
            userbot.last_error = str(e)
            db.commit()
            return {
                "success": False,
                "error": str(e),
                "error_ar": f"خطأ أثناء الإرسال: {str(e)}",
                "can_retry": True,
                "retry_delay_seconds": 300
            }

    async def upload_userbot_avatar(self, db: Session, channel_id: str, image_bytes: bytes) -> Dict[str, Any]:
        """Uploads and changes profile picture of channel's dedicated userbot."""
        client = await self.get_client_for_channel(db, channel_id)
        if not client:
            raise HTTPException(status_code=400, detail="يوزربوت القناة غير متصل حالياً.")

        import io
        photo_file = io.BytesIO(image_bytes)
        photo_file.name = "profile_photo.jpg"

        try:
            uploaded = await client.upload_file(photo_file)
            await client(UploadProfilePhotoRequest(file=uploaded))
            return {"success": True, "message": "تم تحديث صورة بروفايل اليوزربوت على تيليجرام بنجاح! 🎉"}
        except Exception as e:
            logger.error(f"Failed to upload userbot avatar for channel {channel_id}: {e}")
            raise HTTPException(status_code=500, detail=f"فشل رفع الصورة: {str(e)}")

    async def disconnect_userbot(self, db: Session, tenant_id: str, channel_id: str) -> Dict[str, Any]:
        """Removes dedicated userbot for channel."""
        userbot = db.query(ChannelUserbot).filter(
            ChannelUserbot.channel_id == channel_id,
            ChannelUserbot.tenant_id == tenant_id
        ).first()

        if not userbot:
            raise HTTPException(status_code=404, detail="لا يوجد يوزربوت مخصص مرتبط بهذه القناة.")

        if channel_id in self._clients:
            try:
                await self._clients[channel_id].disconnect()
            except Exception:
                pass
            del self._clients[channel_id]

        db.delete(userbot)
        db.commit()
        return {"success": True, "message": "تم فصل اليوزربوت عن القناة بنجاح. ستعمل القناة الآن عبر المجمع العام."}

dedicated_userbot_service = DedicatedUserbotService()
