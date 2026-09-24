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

async def test_mistake():
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
    print("Connected.")

    await client.send_message("@SpamBot", "/start")
    await asyncio.sleep(3)

    msgs = await client.get_messages("@SpamBot", limit=1)
    if msgs and msgs[0].buttons:
        mistake_btn = None
        for row in msgs[0].buttons:
            for btn in row:
                if "mistake" in btn.text.lower():
                    mistake_btn = btn
                    break
            if mistake_btn:
                break
        
        if mistake_btn:
            print(f"Clicking: {mistake_btn.text}")
            await mistake_btn.click()
            await asyncio.sleep(4)

            msgs2 = await client.get_messages("@SpamBot", limit=1)
            if msgs2:
                print(f"Reply 2:\n{msgs2[0].text}\n")
                if msgs2[0].buttons:
                    for r, row in enumerate(msgs2[0].buttons):
                        for b, btn in enumerate(row):
                            print(f"Btn [{r},{b}]: '{btn.text}'")

                    # If buttons like 'Yes' / 'No' / 'Submit complaint'
                    # Let's see what buttons appear and click the appeal button
                    first_btn = msgs2[0].buttons[0][0]
                    print(f"Clicking reply 2 button: '{first_btn.text}'")
                    await first_btn.click()
                    await asyncio.sleep(4)

                    msgs3 = await client.get_messages("@SpamBot", limit=1)
                    if msgs3:
                        print(f"Reply 3:\n{msgs3[0].text}\n")
                        if msgs3[0].buttons:
                            for r, row in enumerate(msgs3[0].buttons):
                                for b, btn in enumerate(row):
                                    print(f"Btn [{r},{b}]: '{btn.text}'")

    await client.disconnect()
    db.close()

if __name__ == "__main__":
    asyncio.run(test_mistake())
