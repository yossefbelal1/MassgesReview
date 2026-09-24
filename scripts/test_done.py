import asyncio
import os
import sys
from telethon import TelegramClient
from telethon.sessions import StringSession
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, "/app")
from backend.app.core.config import settings
from backend.app.models.models import ChannelUserbot

async def check_done():
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    userbot = db.query(ChannelUserbot).filter(ChannelUserbot.username == "AutoMassge1").first()
    api_id = userbot.api_id or int(settings.TELEGRAM_API_ID)
    api_hash = userbot.api_hash or str(settings.TELEGRAM_API_HASH)

    client = TelegramClient(
        StringSession(userbot.string_session),
        api_id,
        api_hash,
        device_model="ReviewFlow Auto",
        system_version="Linux",
        app_version="2.0.0"
    )

    await client.connect()
    msgs = await client.get_messages("@SpamBot", limit=1)
    if msgs and msgs[0].buttons:
        for row in msgs[0].buttons:
            for btn in row:
                print(f"Button: {btn.text}")
                if "done" in btn.text.lower():
                    print("Clicking Done...")
                    await btn.click()
                    await asyncio.sleep(3)
                    msgs2 = await client.get_messages("@SpamBot", limit=1)
                    if msgs2:
                        print(f"After Done reply:\n{msgs2[0].text}")

    await client.send_message("@SpamBot", "/start")
    await asyncio.sleep(3)
    final_msgs = await client.get_messages("@SpamBot", limit=1)
    if final_msgs:
        print(f"Final /start reply:\n{final_msgs[0].text}")

    await client.disconnect()
    db.close()

if __name__ == "__main__":
    asyncio.run(check_done())
