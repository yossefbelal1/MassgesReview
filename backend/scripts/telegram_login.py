import os
import sys
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")

async def login():
    print("=" * 60)
    print("🔐 [ReviewFlow] Telegram Account Login & Session Generator")
    print("=" * 60)

    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()

    phone = input("\n📱 أدخل رقم الهاتف مع كود الدولة (مثال: +2010... أو +966...): ").strip()
    
    try:
        sent_code = await client.send_code_request(phone)
        print(f"\n[✓] تم إرسال كود التحقق إلى حساب تيليجرام الخاص بالرقم: {phone}")
    except Exception as e:
        print(f"\n[!] خطأ أثناء إرسال الكود: {e}")
        await client.disconnect()
        return

    code = input("\n🔑 أدخل كود التحقق المكون من 5 أرقام (OTP): ").strip()
    
    try:
        await client.sign_in(phone, code)
    except Exception as e:
        if "password" in str(e).lower() or "two-step" in str(e).lower():
            pwd = input("\n🔒 الحساب محمي بكلمة مرور التحقق بخطوتين (2FA) - أدخل كلمة المرور: ").strip()
            try:
                await client.sign_in(password=pwd)
            except Exception as pe:
                print(f"\n[!] خطأ في كلمة المرور: {pe}")
                await client.disconnect()
                return
        else:
            print(f"\n[!] خطأ في تسجيل الدخول: {e}")
            await client.disconnect()
            return

    me = await client.get_me()
    session_str = StringSession.save(client.session)

    print("\n" + "=" * 60)
    print(f"🎉 تم تسجيل الدخول بنجاح بحساب: {me.first_name} (@{me.username}) ID: {me.id}")
    print("=" * 60)

    # Save to .env
    env_path = "/root/MassgesReview/.env" if os.path.exists("/root/MassgesReview/.env") else ".env"
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            content = f.read()

        import re
        if "TELEGRAM_STRING_SESSION=" in content:
            content = re.sub(r'TELEGRAM_STRING_SESSION=.*', f'TELEGRAM_STRING_SESSION="{session_str}"', content)
        else:
            content += f'\nTELEGRAM_STRING_SESSION="{session_str}"\n'

        with open(env_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"[✓] تم حفظ جلسة التيليجرام الجديدة في ملف الإعدادات ({env_path}) بنجاح!")
    else:
        print(f"\nTELEGRAM_STRING_SESSION=\"{session_str}\"")

    await client.disconnect()
    print("\n🚀 يمكنك الآن إعادة تشغيل الحاوية وسيعمل البوت فوراً وبشكل مستمر 24/7.")

if __name__ == "__main__":
    asyncio.run(login())
