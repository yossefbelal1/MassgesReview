import sys
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from backend.app.core.config import settings

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

client = TelegramClient(
    StringSession(settings.TELEGRAM_STRING_SESSION),
    settings.TELEGRAM_API_ID,
    settings.TELEGRAM_API_HASH
)

@client.on(events.NewMessage)
async def handler(event):
    print(f"\n[🚨 LIVE EVENT DETECTED] Chat ID: {event.chat_id} | Text: '{event.raw_text}' | Fwd: {bool(event.message.fwd_from)}")
    if not event.message.fwd_from and ("tp1" in (event.raw_text or "").lower() or "tp2" in (event.raw_text or "").lower()):
        print(f"[🔥 TRIGGER HIT] Sending real reviews from Bank to {event.chat_id}...")
        import random
        bank_msgs = await client.get_messages(-1003969850866, limit=30)
        valid = [m for m in bank_msgs if m.fwd_from or m.message]
        selected = random.sample(valid, 2)
        for m in selected:
            await asyncio.sleep(2)
            res = await client.forward_messages(entity=event.chat_id, messages=m.id, from_peer=-1003969850866)
            fwd_name = getattr(m.fwd_from, 'from_name', 'Member') if m.fwd_from else 'Member'
            print(f" [✓ Forwarded Review from {fwd_name}] -> Msg ID: {res.id}")

async def main():
    await client.start()
    print("=" * 60)
    print("🛰️ [LIVE LISTENER ACTIVE] Listening to all channel updates...")
    print("=" * 60)
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
