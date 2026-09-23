import asyncio
import logging
from backend.app.core.config import settings
from backend.app.core.database import SessionLocal
from backend.app.models.models import Channel, ChannelUserbot, Tenant
from backend.app.services.dedicated_userbot_service import dedicated_userbot_service
from telethon import TelegramClient
from telethon.sessions import StringSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sync_bots")

TENANT_ID = "35a9ed01-05f3-4056-8da2-45598469d646"
CHANNEL_ID = "0eb3385e-733a-417c-bc8a-997c445ed77d"  # ARAB ICT 🔐

NEW_API_ID = 30763555
NEW_API_HASH = "0882162c262075ff459937fcfe5501cd"
NEW_PHONE = "+201145318050"

async def ensure_primary_bot_registered(db):
    """Ensures AutoMassge1 is registered as the first dedicated bot for this channel/tenant."""
    session_str = settings.TELEGRAM_STRING_SESSION
    if not session_str:
        logger.warning("No TELEGRAM_STRING_SESSION found in settings.")
        return

    # Check if already registered
    existing = db.query(ChannelUserbot).filter(
        ChannelUserbot.tenant_id == TENANT_ID,
        (ChannelUserbot.string_session == session_str) | (ChannelUserbot.username == "AutoMassge1")
    ).first()

    if existing:
        logger.info(f"[✓] Primary bot AutoMassge1 already in channel_userbots (id={existing.id})")
        return existing

    # Connect to verify and get details
    client = TelegramClient(StringSession(session_str), settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)
    await client.connect()
    try:
        me = await client.get_me()
        bot_username = getattr(me, "username", "AutoMassge1") or "AutoMassge1"
        bot_first_name = getattr(me, "first_name", "Auto") or "Auto"
        bot_phone = getattr(me, "phone", "") or "+201000000000"
        bot_tg_id = str(me.id)
    except Exception as e:
        logger.error(f"Error inspecting primary bot: {e}")
        bot_username = "AutoMassge1"
        bot_first_name = "Auto"
        bot_phone = "+201000000000"
        bot_tg_id = None
    finally:
        await client.disconnect()

    primary_bot = ChannelUserbot(
        tenant_id=TENANT_ID,
        channel_id=CHANNEL_ID,
        api_id=settings.TELEGRAM_API_ID,
        api_hash=settings.TELEGRAM_API_HASH,
        phone=bot_phone if bot_phone.startswith("+") else f"+{bot_phone}",
        string_session=session_str,
        telegram_user_id=bot_tg_id,
        username=bot_username,
        first_name=bot_first_name,
        is_active=True,
        status="CONNECTED",
        daily_contacts_count=0
    )
    db.add(primary_bot)
    db.commit()
    db.refresh(primary_bot)
    logger.info(f"[🎉] Successfully added primary bot AutoMassge1 to channel_userbots (id={primary_bot.id})")
    return primary_bot

async def trigger_code_request(db):
    """Triggers login code for the new second account."""
    logger.info(f"Requesting login code for second account {NEW_PHONE}...")
    res = await dedicated_userbot_service.send_login_code(
        db=db,
        tenant_id=TENANT_ID,
        channel_id=CHANNEL_ID,
        api_id=NEW_API_ID,
        api_hash=NEW_API_HASH,
        phone=NEW_PHONE
    )
    logger.info(f"Send Code Result: {res}")
    return res

async def main():
    db = SessionLocal()
    try:
        await ensure_primary_bot_registered(db)
        res = await trigger_code_request(db)
        print("--- SUMMARY ---")
        print("SUCCESS:", res.get("success"))
        print("ATTEMPT_ID:", res.get("login_attempt_id"))
        print("MESSAGE:", res.get("message"))
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
