import sys
import asyncio
from telethon import TelegramClient

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

API_ID = 31925523
API_HASH = '6448299ee7fb91c63cbc82511b435594'

client = TelegramClient('sessions/multi_tenant_userbot', API_ID, API_HASH)

async def main():
    await client.connect()
    print("=" * 60)
    print("قائمة بالقنوات والمجموعات والـ IDs الخاصة بها:")
    print("=" * 60)
    
    async for dialog in client.iter_dialogs():
        entity_type = "قناة" if dialog.is_channel else ("مجموعة" if dialog.is_group else "محادثة")
        print(f"[{entity_type}] {dialog.name} | ID: {dialog.id}")
            
    print("=" * 60)

if __name__ == '__main__':
    asyncio.run(main())
