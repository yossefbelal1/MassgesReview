import asyncio
from telethon import TelegramClient

API_ID = 31925523
API_HASH = '6448299ee7fb91c63cbc82511b435594'

client = TelegramClient('sessions/multi_tenant_userbot', API_ID, API_HASH)

async def main():
    await client.start()
    query = input(">> اكتب اسم القناة أو الرابط للبحث عنها: ").strip()
    try:
        entity = await client.get_entity(query)
        print(f"\n[✓] تم العثور عليها:")
        print(f"📌 الاسم: {getattr(entity, 'title', getattr(entity, 'first_name', ''))}")
        print(f"🆔 الـ ID: {entity.id}")
        if hasattr(entity, 'username') and entity.username:
            print(f"🔗 اليوزر: @{entity.username}")
    except Exception as e:
        print(f"[❌] لم يتم العثور على القناة أو حدث خطأ: {e}")

if __name__ == '__main__':
    asyncio.run(main())
