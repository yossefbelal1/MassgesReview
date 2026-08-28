import sys
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from backend.app.core.config import settings

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

async def check():
    client = TelegramClient(StringSession(settings.TELEGRAM_STRING_SESSION), settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)
    await client.connect()
    msgs = await client.get_messages(-1003969850866, limit=15)
    print(f"Total messages fetched from Bank: {len(msgs)}")
    for m in msgs:
        fwd_info = getattr(m, 'fwd_from', None)
        fwd_name = getattr(fwd_info, 'from_name', None) if fwd_info else 'Direct Post'
        print(f"Message ID {m.id} -> From: {fwd_name} -> '{(m.text or '')[:35]}'")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(check())
