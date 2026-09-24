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

async def inspect_spambot():
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
    print("Connected to Telegram.")

    print("\n--- Sending /start ---")
    await client.send_message("@SpamBot", "/start")
    await asyncio.sleep(3)

    msgs = await client.get_messages("@SpamBot", limit=1)
    if msgs and msgs[0].buttons:
        print("Buttons on /start:")
        for r_idx, row in enumerate(msgs[0].buttons):
            for b_idx, btn in enumerate(row):
                print(f"[{r_idx},{b_idx}]: '{btn.text}'")

        # Let's see if 'I was wrong, please release me now' is present
        release_btn = None
        mistake_btn = None
        for row in msgs[0].buttons:
            for btn in row:
                if "please release me" in btn.text.lower() or "was wrong" in btn.text.lower():
                    release_btn = btn
                elif "mistake" in btn.text.lower():
                    mistake_btn = btn

        target_btn = release_btn or mistake_btn
        if target_btn:
            print(f"\n--- Clicking: '{target_btn.text}' ---")
            await target_btn.click()
            await asyncio.sleep(4)

            msgs2 = await client.get_messages("@SpamBot", limit=1)
            if msgs2:
                print(f"\nSpamBot reply after clicking '{target_btn.text}':\n{msgs2[0].text}\n")
                if msgs2[0].buttons:
                    print("Next buttons available:")
                    for r_idx, row in enumerate(msgs2[0].buttons):
                        for b_idx, btn in enumerate(row):
                            print(f"[{r_idx},{b_idx}]: '{btn.text}'")
                    
                    # If there's a button to confirm or submit:
                    # Let's inspect what buttons appear
                    for row in msgs2[0].buttons:
                        for btn in row:
                            b_lower = btn.text.lower()
                            if any(w in b_lower for w in ["yes", "agree", "release", "confirm", "submit", "promise", "won't do it"]):
                                print(f"\n--- Clicking follow-up button: '{btn.text}' ---")
                                await btn.click()
                                await asyncio.sleep(4)
                                msgs3 = await client.get_messages("@SpamBot", limit=1)
                                if msgs3:
                                    print(f"\nSpamBot reply 3:\n{msgs3[0].text}\n")
                                    if msgs3[0].buttons:
                                        for r, row3 in enumerate(msgs3[0].buttons):
                                            for b, btn3 in enumerate(row3):
                                                print(f"[{r},{b}]: '{btn3.text}'")
                                break

            # Now send /start again to check status
            print("\n--- Sending /start to verify final state ---")
            await client.send_message("@SpamBot", "/start")
            await asyncio.sleep(3)
            final_msgs = await client.get_messages("@SpamBot", limit=1)
            if final_msgs:
                txt = final_msgs[0].text or ""
                print(f"Final status text:\n{txt}")
                if any(w in txt.lower() for w in ["free as a bird", "no limits", "حر طليق", "لاتوجد قيود", "لا توجد قيود"]):
                    print("\n>>> 🎉 ACCOUNT UNLOCKED! Restoring CONNECTED in DB...")
                    userbot.status = "CONNECTED"
                    userbot.cooldown_until = None
                    userbot.last_error = None
                    db.commit()
                else:
                    print("\n>>> Account status updated.")
                    userbot.last_error = txt[:200]
                    db.commit()

    await client.disconnect()
    db.close()

if __name__ == "__main__":
    asyncio.run(inspect_spambot())
