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

async def complete_complaint():
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

    msgs = await client.get_messages("@SpamBot", limit=1)
    if msgs and msgs[0].buttons:
        print(f"Current message:\n{msgs[0].text}\n")
        never_btn = None
        for row in msgs[0].buttons:
            for btn in row:
                print(f"Button: '{btn.text}'")
                if "never" in btn.text.lower():
                    never_btn = btn
                    break
            if never_btn:
                break
        
        if never_btn:
            print(f"Clicking: '{never_btn.text}'")
            await never_btn.click()
            await asyncio.sleep(4)

            msgs2 = await client.get_messages("@SpamBot", limit=1)
            if msgs2:
                print(f"Reply after 'Never':\n{msgs2[0].text}\n")
                if msgs2[0].buttons:
                    for r, row in enumerate(msgs2[0].buttons):
                        for b, btn in enumerate(row):
                            print(f"Btn [{r},{b}]: '{btn.text}'")
                
                # Check if it asks to write text
                # Often it says: "Great! Please write something about what happened:"
                # Or "Your complaint has been successfully submitted."
                txt = msgs2[0].text or ""
                if "write" in txt.lower() or "explain" in txt.lower() or "details" in txt.lower():
                    print("Sending explanation text...")
                    await client.send_message("@SpamBot", "I did not send any spam or unwanted messages. I only follow up with members of my channel.")
                    await asyncio.sleep(4)
                    msgs3 = await client.get_messages("@SpamBot", limit=1)
                    if msgs3:
                        print(f"Final reply after explanation:\n{msgs3[0].text}\n")

    # Now test /start
    print("\n--- Sending /start to check final status ---")
    await client.send_message("@SpamBot", "/start")
    await asyncio.sleep(3)
    final_msgs = await client.get_messages("@SpamBot", limit=1)
    if final_msgs:
        txt = final_msgs[0].text or ""
        print(f"Final /start text:\n{txt}\n")
        if any(w in txt.lower() for w in ["free as a bird", "no limits", "حر طليق", "لاتوجد قيود", "لا توجد قيود"]):
            print(">>> 🎉 ACCOUNT IS FREE! Updating DB...")
            userbot.status = "CONNECTED"
            userbot.cooldown_until = None
            userbot.last_error = None
            db.commit()
        else:
            print(">>> Account still in moderation or cooldown until specified date.")
            userbot.last_error = txt[:200]
            db.commit()

    await client.disconnect()
    db.close()

if __name__ == "__main__":
    asyncio.run(complete_complaint())
