import os
import sys
import asyncio
from telethon import TelegramClient

API_ID = 31925523
API_HASH = '6448299ee7fb91c63cbc82511b435594'

os.makedirs('sessions', exist_ok=True)

# تعريف إعدادات الجهاز الرسمية حتى يقبلها سيرفر تيليجرام بدون تصنيف كـ Spam
client = TelegramClient(
    'sessions/multi_tenant_userbot',
    API_ID,
    API_HASH,
    device_model='Desktop PC',
    system_version='Windows 10',
    app_version='4.16.8 x64',
    lang_code='ar',
    system_lang_code='ar'
)

def get_phone():
    phone = input(">> أدخل رقم هاتفك مع مفتاح الدولة (مثال: +48455536804 أو +201xxxxxxxxx): ").strip()
    return phone

def get_code():
    print("\n" + "=" * 60)
    print("📩 تم إرسال الكود من تيليجرام!")
    print("👉 افتح تطبيق التيليجرام على الموبايل أو الكمبيوتر")
    print("👉 ادخل على محادثة 'Telegram' الرسمية وانسخ الكود")
    print("=" * 60)
    return input(">> اكتب الكود الذي وصلك: ").strip()

def get_password():
    return input(">> الحساب محمي بكلمة سر 2FA، أدخل الباسورد: ").strip()

async def main():
    print("=" * 60)
    print("🚀 بدء تسجيل الدخول لتيليجرام...")
    print("=" * 60)
    
    await client.start(
        phone=get_phone,
        code_callback=get_code,
        password=get_password
    )
    
    me = await client.get_me()
    print("\n" + "=" * 60)
    print(f"[🎉] تم تسجيل الدخول بنجاح تام!")
    print(f"👤 الاسم: {me.first_name} {me.last_name or ''}")
    print(f"📱 الرقم: +{me.phone}")
    print(f"🆔 المعرف (ID): {me.id}")
    print("=" * 60)

if __name__ == '__main__':
    asyncio.run(main())

