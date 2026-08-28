import os
import sys
import json
import random
import asyncio
from telethon import TelegramClient, events
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

API_ID = int(os.getenv("API_ID", 31925523))
API_HASH = os.getenv("API_HASH", "6448299ee7fb91c63cbc82511b435594")
CONFIG_FILE = "clients.json"

# بنك الرسائل الافتراضي العام
DEFAULT_BANK_ID = -1003969850866 
os.makedirs("sessions", exist_ok=True)
client = TelegramClient('sessions/multi_tenant_userbot', API_ID, API_HASH)

def load_tenants():
    """تحميل إعدادات القنوات المشتركة بشكل ديناميكي"""
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            return json.loads(content) if content else {}
    except Exception as e:
        print(f"[⚠️] خطأ أثناء قراءة {CONFIG_FILE}: {e}")
        return {}

def match_tenant_trigger(tenant_config, message_text):
    """فحص الكلمات المفتاحية الخاصة بالعميل"""
    if not message_text:
        return False
    triggers = tenant_config.get("triggers", [])
    text_lower = message_text.lower().strip()
    return any(t.lower() in text_lower for t in triggers)

# استماع لجميع الرسائل الواردة والمنشورة في القنوات
@client.on(events.NewMessage)
async def dynamic_channel_listener(event):
    chat_id_str = str(event.chat_id)
    tenants = load_tenants()

    # فحص هل المحادثة مسجلة في ملف clients.json
    if chat_id_str not in tenants:
        return

    tenant = tenants[chat_id_str]
    if not tenant.get("active", False):
        return

    msg_text = event.message.message or ""
    
    # تجنب التفاعل مع الرسائل المعاد توجيهها من بنك الرسائل
    if event.message.fwd_from:
        return

    if match_tenant_trigger(tenant, msg_text):
        print(f"\n[🔥] تم رصد تريجر في: '{tenant.get('name', chat_id_str)}' | نص الرسالة: '{msg_text}'")

        bank_id = tenant.get("source_bank_id", DEFAULT_BANK_ID)
        
        try:
            # سحب الرسائل من بنك الريفيوز
            messages = await client.get_messages(bank_id, limit=50)
            valid_msgs = [m for m in messages if m.message or m.media]

            if not valid_msgs:
                print(f"[⚠️] بنك الرسائل ({bank_id}) فارغ!")
                return

            min_rev = tenant.get("min_reviews", 2)
            max_rev = tenant.get("max_reviews", 4)
            count = min(random.randint(min_rev, max_rev), len(valid_msgs))
            selected = random.sample(valid_msgs, k=count)

            delays = tenant.get("delay_range", [2.0, 5.0])

            print(f"[*] جاري إرسال {count} ريفيوز إلى '{tenant.get('name')}'...")
            for i, m in enumerate(selected, 1):
                delay = random.uniform(delays[0], delays[1])
                await asyncio.sleep(delay)

                await client.forward_messages(
                    entity=event.chat_id,
                    messages=m.id,
                    from_peer=bank_id
                )
                print(f" [✓] تم إرسال ريفيو {i}/{count}")

            print(f"[🎉] اكتمل إرسال الريفيوز بنجاح إلى '{tenant.get('name')}'\n")

        except Exception as e:
            print(f"[❌] خطأ أثناء إرسال الريفيوز للقناة {chat_id_str}: {e}")

async def main():
    await client.start()
    print("=" * 60)
    print("[🚀] Multi-Tenant Reviews Bot شغال وجاهز لاستقبال الرسائل...")
    print(f"📋 تم تحميل القنوات المفعلة: {list(load_tenants().keys())}")
    print("=" * 60)
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())