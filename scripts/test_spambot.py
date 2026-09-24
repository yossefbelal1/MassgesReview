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

async def run_spambot_flow():
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    userbot = db.query(ChannelUserbot).filter(ChannelUserbot.username == "AutoMassge1").first()
    if not userbot:
        userbot = db.query(ChannelUserbot).filter(ChannelUserbot.phone.like("%48455536804%")).first()
    
    if not userbot:
        print("Userbot AutoMassge1 not found!")
        return

    print(f"Found userbot: {userbot.username} ({userbot.phone}), status: {userbot.status}, cooldown: {userbot.cooldown_until}")

    api_id = userbot.api_id or int(settings.TELEGRAM_API_ID)
    api_hash = userbot.api_hash or str(settings.TELEGRAM_API_HASH)

    client = TelegramClient(
        StringSession(userbot.string_session),
        api_id,
        api_hash,
        device_model="ReviewFlow Auto",
        system_version="Linux",
        app_version="2.0.0",
        lang_code="ar"
    )

    await client.connect()
    if not await client.is_user_authorized():
        print("Client session is not authorized!")
        return

    me = await client.get_me()
    print(f"Connected as {me.first_name} (@{me.username}, phone: {me.phone})")

    print("\n--- STEP 1: Sending /start to @SpamBot ---")
    await client.send_message("@SpamBot", "/start")
    await asyncio.sleep(3)

    msgs = await client.get_messages("@SpamBot", limit=1)
    if not msgs:
        print("No response from @SpamBot!")
        await client.disconnect()
        return

    msg = msgs[0]
    print(f"SpamBot reply 1 text:\n{msg.text}\n")
    if msg.buttons:
        for r_idx, row in enumerate(msg.buttons):
            for b_idx, btn in enumerate(row):
                print(f"Button [{r_idx},{b_idx}]: '{btn.text}' (data={getattr(btn, 'data', None)})")

    lower_text = (msg.text or "").lower()
    if any(w in lower_text for w in ["free as a bird", "no limits", "حر طليق", "لاتوجد قيود", "لا توجد قيود"]):
        print("\n>>> Account is already FREE! Updating DB...")
        userbot.status = "CONNECTED"
        userbot.cooldown_until = None
        userbot.last_error = None
        db.commit()
        print("DB updated successfully!")
        await client.disconnect()
        db.close()
        return

    # Step 2: "ليه تم البلاغ عني" / "Why was I reported?"
    print("\n--- STEP 2: Answering 'Why was I reported?' / 'ليه تم البلاغ عني' ---")
    clicked = False
    if msg.buttons:
        for row in msg.buttons:
            for btn in row:
                b_txt = btn.text.lower()
                if any(w in b_txt for w in ["why was i reported", "لماذا تم", "ليه تم", "تم الإبلاغ", "بلاغ", "reported"]):
                    print(f"Clicking button: '{btn.text}'")
                    await btn.click()
                    clicked = True
                    break
            if clicked:
                break
    
    if not clicked:
        if msg.buttons and len(msg.buttons) > 0 and len(msg.buttons[0]) > 0:
            print(f"Button text didn't match keyword, clicking first button: '{msg.buttons[0][0].text}'")
            await msg.buttons[0][0].click()
        else:
            print("No buttons found, sending text: لماذا تم الإبلاغ عن حسابي؟")
            await client.send_message("@SpamBot", "لماذا تم الإبلاغ عن حسابي؟")

    await asyncio.sleep(4)
    msgs2 = await client.get_messages("@SpamBot", limit=1)
    if msgs2:
        msg2 = msgs2[0]
        print(f"\nSpamBot reply 2 text:\n{msg2.text}\n")
        if msg2.buttons:
            for r_idx, row in enumerate(msg2.buttons):
                for b_idx, btn in enumerate(row):
                    print(f"Button [{r_idx},{b_idx}]: '{btn.text}' (data={getattr(btn, 'data', None)})")

        # Step 3: "انا فهمت شكرا" / "I understand, thanks"
        print("\n--- STEP 3: Answering 'I understand, thanks' / 'انا فهمت شكرا' ---")
        clicked_thanks = False
        if msg2.buttons:
            for row in msg2.buttons:
                for btn in row:
                    b_txt = btn.text.lower()
                    if any(w in b_txt for w in ["understand", "thanks", "فهمت", "شكرا", "أفهم", "شكراً"]):
                        print(f"Clicking button: '{btn.text}'")
                        await btn.click()
                        clicked_thanks = True
                        break
                if clicked_thanks:
                    break

        if not clicked_thanks:
            if msg2.buttons and len(msg2.buttons) > 0 and len(msg2.buttons[0]) > 0:
                print(f"Button text didn't match keyword, clicking first button in reply 2: '{msg2.buttons[0][0].text}'")
                await msg2.buttons[0][0].click()
            else:
                print("No buttons found, sending text: أنا أفهم ذلك، شكراً")
                await client.send_message("@SpamBot", "أنا أفهم ذلك، شكراً")

        await asyncio.sleep(4)
        msgs3 = await client.get_messages("@SpamBot", limit=1)
        if msgs3:
            print(f"\nSpamBot reply 3 text:\n{msgs3[0].text}\n")
            if msgs3[0].buttons:
                for r_idx, row in enumerate(msgs3[0].buttons):
                    for b_idx, btn in enumerate(row):
                        print(f"Button [{r_idx},{b_idx}]: '{btn.text}'")

        # Step 4: Send /start again
        print("\n--- STEP 4: Sending /start again ---")
        await client.send_message("@SpamBot", "/start")
        await asyncio.sleep(3)

        msgs_final = await client.get_messages("@SpamBot", limit=1)
        if msgs_final:
            final_text = msgs_final[0].text or ""
            print(f"\nSpamBot FINAL reply:\n{final_text}\n")
            if any(w in final_text.lower() for w in ["free as a bird", "no limits", "حر طليق", "لاتوجد قيود", "لا توجد قيود"]):
                print("\n>>> 🎉 SUCCESS: Ban is lifted! Account is FREE! Restoring to CONNECTED...")
                userbot.status = "CONNECTED"
                userbot.cooldown_until = None
                userbot.last_error = None
                db.commit()
                print("DB updated successfully to CONNECTED!")
            else:
                print(f"\n>>> Final message check: {final_text}")
                # Check if it was restored or still has a cooldown
                userbot.last_error = final_text[:200]
                db.commit()

    await client.disconnect()
    db.close()
    print("Done!")

if __name__ == "__main__":
    asyncio.run(run_spambot_flow())
