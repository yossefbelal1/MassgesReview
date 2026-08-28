import os
import sys
import re
import asyncio
from datetime import datetime, timezone
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from sqlalchemy.orm import Session
from telethon.sessions import StringSession
from backend.app.core.config import settings
from backend.app.core.database import SessionLocal
from backend.app.models.models import Channel, Automation, Job, AutomationStep

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

session = StringSession(settings.TELEGRAM_STRING_SESSION) if settings.TELEGRAM_STRING_SESSION else settings.TELEGRAM_SESSION_PATH

client = TelegramClient(
    session,
    settings.TELEGRAM_API_ID,
    settings.TELEGRAM_API_HASH,
    device_model='Desktop PC',
    system_version='Windows 10',
    app_version='4.16.8 x64',
    lang_code='ar',
    system_lang_code='ar'
)

def matches_trigger(trigger_type: str, trigger_value: str, text: str) -> bool:
    if not text:
        return False
    t_val = trigger_value.strip().lower()
    msg = text.strip().lower()

    if trigger_type == "exact":
        return msg == t_val
    elif trigger_type == "prefix":
        return msg.startswith(t_val)
    elif trigger_type == "regex":
        try:
            return bool(re.search(trigger_value, text, re.IGNORECASE))
        except Exception:
            return False
    else:  # contains
        return t_val in msg

from backend.app.models.models import Channel, Automation, Job, AutomationStep, PublishingHistory, MessageLibrary

import random

BANK_ID = -1003969850866

async def run_automation_sequence(auto_id: str, channel_id: int, trigger_msg_id: int, trigger_text: str):
    if not client.is_connected():
        await client.connect()

    db: Session = SessionLocal()
    try:
        auto = db.query(Automation).filter(Automation.id == auto_id).first()
        if not auto or not auto.is_active:
            return

        tenant = auto.tenant
        channel_obj = auto.channel

        print(f"\n[🚀 Launching Sequence] '{auto.name}' to Channel '{channel_obj.title}'...", flush=True)

        from telethon import types

        def is_valid_member_review(m):
            if not m.fwd_from:
                return False
            from_id = getattr(m.fwd_from, 'from_id', None)
            from_name = getattr(m.fwd_from, 'from_name', None)

            # Strictly reject any channel forwards or MassgesReviews
            if isinstance(from_id, types.PeerChannel):
                return False
            if from_name and "massgesreview" in from_name.lower().replace(" ", ""):
                return False

            # Must be a genuine forwarded member with text
            return bool(m.text and (from_name or isinstance(from_id, types.PeerUser)))

        # Fetch messages from bank and strictly pick ONLY those with genuine individual member headers
        bank_msgs = await client.get_messages(BANK_ID, limit=100)
        valid_reviews = [m for m in bank_msgs if is_valid_member_review(m)]

        if not valid_reviews:
            print(f"[⚠️ No valid member reviews found in bank]", flush=True)
            return

        # 1. Determine configured review count and delays
        target_count = getattr(auto, 'reviews_count', 2) or 2
        initial_delay = float(getattr(auto, 'initial_delay_seconds', 5.0) or 5.0)
        base_delay = float(getattr(auto, 'delay_seconds', 4.0) or 4.0)
        
        count = min(target_count, len(valid_reviews))
        selected_msgs = random.sample(valid_reviews, k=count)

        print(f"[⚙️ Configured Target]: {count} reviews | Initial Start Delay: {initial_delay}s | Inter-delay: ~{base_delay}s (+ human jitter)")

        for idx, m in enumerate(selected_msgs, 1):
            if idx == 1:
                # Initial delay before the first review starts
                actual_delay = max(0.5, round(initial_delay + random.uniform(-0.5, 0.8), 1))
                print(f"[⏳ Initial Start Delay] Waiting {actual_delay}s before First Review #{idx}...")
            else:
                # Human-like random jitter between reviews
                jitter = random.uniform(-0.8, 1.8)
                actual_delay = max(1.5, round(base_delay + jitter, 1))
                print(f"[⏳ Human Delay] Waiting {actual_delay}s before Review #{idx}...")
            
            await asyncio.sleep(actual_delay)

            try:
                res = await client.forward_messages(
                    entity=channel_id,
                    messages=m.id,
                    from_peer=BANK_ID
                )
                msg_id = res.id if not isinstance(res, list) else (res[0].id if res else None)
                fwd_name = getattr(m.fwd_from, 'from_name', 'Member') if m.fwd_from else 'Member'
                print(f" [🎉 Review #{idx}/{count} Forwarded Successfully from '{fwd_name}'] -> Msg ID: {msg_id}")

                # Record in Audit History
                db.add(PublishingHistory(
                    tenant_id=tenant.id,
                    channel_id=channel_obj.id,
                    message_title=f"Review from {fwd_name}",
                    automation_name=auto.name,
                    step_number=idx,
                    status="SUCCESS",
                    telegram_message_id=str(msg_id)
                ))
                db.commit()

            except FloodWaitError as flood_err:
                print(f" [⚠️ Telegram FloodWait]: Required to wait {flood_err.seconds}s. Handling backoff...")
                db.add(PublishingHistory(
                    tenant_id=tenant.id,
                    channel_id=channel_obj.id,
                    message_title=f"Review (FloodWait: {flood_err.seconds}s)",
                    automation_name=auto.name,
                    step_number=idx,
                    status="FLOOD_WAIT",
                    error_details=f"Telegram FloodWait of {flood_err.seconds}s"
                ))
                db.commit()
                await asyncio.sleep(flood_err.seconds + 1)
            except Exception as fwd_err:
                print(f" [❌ Review #{idx} Forward Error]: {fwd_err}")
                db.add(PublishingHistory(
                    tenant_id=tenant.id,
                    channel_id=channel_obj.id,
                    message_title="Review",
                    automation_name=auto.name,
                    step_number=idx,
                    status="FAILED",
                    error_details=str(fwd_err)
                ))
                db.commit()

        auto.total_executions += 1
        auto.last_executed_at = datetime.now(timezone.utc)
        db.commit()
        print(f"[✓ Sequence Finished] '{auto.name}' completed for channel '{channel_obj.title}'! Sent exactly {count} reviews.\n")

    except Exception as e:
        print(f"[❌ Sequence Error]: {e}")
    finally:
        db.close()

PROCESSED_MESSAGES = set()
CHANNEL_ENTITIES = {}
BOT_USER_ID = None

async def active_channel_watcher():
    """High-speed 1.0s active channel poller with persistent per-channel database cursor and strict filtering."""
    global CHANNEL_ENTITIES, BOT_USER_ID, PROCESSED_MESSAGES

    try:
        me = await client.get_me()
        if me:
            BOT_USER_ID = me.id
            print(f"[🤖 Telegram Engine Self-Identity]: Logged in as User ID {BOT_USER_ID} (@{me.username})", flush=True)
    except Exception:
        pass

    while True:
        try:
            db: Session = SessionLocal()
            channels = db.query(Channel).filter(Channel.is_connected == True).all()
            for ch in channels:
                if not ch.tenant or not ch.tenant.is_active:
                    continue

                chat_peer = int(ch.telegram_chat_id)
                if chat_peer not in CHANNEL_ENTITIES:
                    try:
                        CHANNEL_ENTITIES[chat_peer] = await client.get_entity(chat_peer)
                    except Exception:
                        continue

                entity = CHANNEL_ENTITIES[chat_peer]

                # 1. If channel cursor has never been initialized, set to latest message ID
                if not ch.last_seen_message_id or ch.last_seen_message_id == 0:
                    try:
                        latest_msg = await client.get_messages(entity, limit=1)
                        ch.last_seen_message_id = latest_msg[0].id if latest_msg else 1
                        db.commit()
                        print(f"[*] Initialized Channel '{ch.title}' ({ch.telegram_chat_id}) at Msg ID: {ch.last_seen_message_id}", flush=True)
                    except Exception as e:
                        print(f"[!] Init error for {ch.title}: {e}")
                    continue

                # 2. Query active automations belonging STRICTLY to THIS channel
                automations = db.query(Automation).filter(
                    Automation.channel_id == ch.id,
                    Automation.is_active == True
                ).all()

                if not automations:
                    try:
                        latest_msg = await client.get_messages(entity, limit=1)
                        if latest_msg and latest_msg[0].id > ch.last_seen_message_id:
                            ch.last_seen_message_id = latest_msg[0].id
                            db.commit()
                    except Exception:
                        pass
                    continue

                # 3. Fetch ONLY new messages strictly after ch.last_seen_message_id
                try:
                    new_msgs = await client.get_messages(entity, min_id=ch.last_seen_message_id, limit=20)
                    if not new_msgs:
                        continue

                    # Advance cursor in DB IMMEDIATELY to highest message ID seen
                    max_id = max(m.id for m in new_msgs)
                    ch.last_seen_message_id = max_id
                    db.commit()

                    now_utc = datetime.now(timezone.utc)

                    # Process messages in chronological order (oldest to newest)
                    for msg in reversed(new_msgs):
                        dedup_key = (chat_peer, msg.id)
                        if dedup_key in PROCESSED_MESSAGES:
                            continue
                        PROCESSED_MESSAGES.add(dedup_key)
                        if len(PROCESSED_MESSAGES) > 5000:
                            PROCESSED_MESSAGES = set(list(PROCESSED_MESSAGES)[-2500:])

                        # Ignore messages sent by the bot itself
                        if getattr(msg, 'out', False) or (BOT_USER_ID and getattr(msg, 'sender_id', None) == BOT_USER_ID):
                            continue

                        # Ignore forwarded review messages from members or channels
                        if getattr(msg, 'fwd_from', None):
                            continue

                        # Ignore stale messages older than 180 seconds
                        if msg.date:
                            msg_dt = msg.date if msg.date.tzinfo else msg.date.replace(tzinfo=timezone.utc)
                            if (now_utc - msg_dt).total_seconds() > 180:
                                continue

                        msg_text = msg.text or msg.message or ""
                        if not msg_text.strip():
                            continue

                        # Check triggers strictly for this channel
                        for auto in automations:
                            if not auto.is_active:
                                continue

                            is_match = matches_trigger(auto.trigger_type, auto.trigger_value, msg_text)

                            if is_match:
                                target_count = auto.reviews_count or 2
                                print(f"\n[🎯 Live Signal Triggered]: '{auto.trigger_value}' in Channel '{ch.title}' (Msg ID: {msg.id})! Launching {target_count} reviews...", flush=True)
                                asyncio.create_task(
                                    run_automation_sequence(
                                        auto_id=auto.id,
                                        channel_id=int(ch.telegram_chat_id),
                                        trigger_msg_id=msg.id,
                                        trigger_text=msg_text
                                    )
                                )
                                break  # Prevent multiple automations from triggering on the same message
                except Exception:
                    pass

            db.close()
        except Exception:
            pass
        await asyncio.sleep(1.0)

async def poll_pending_jobs():
    """Polls database for manual trigger jobs dispatched from the web dashboard."""
    while True:
        try:
            db: Session = SessionLocal()
            pending_jobs = db.query(Job).filter(Job.status == "PENDING").all()
            for job in pending_jobs:
                job.status = "RUNNING"
                db.commit()

                print(f"\n[⚡ Executing Manual Job] Automation ID: {job.automation_id} on Channel ID: {job.channel_id}...", flush=True)
                asyncio.create_task(
                    run_automation_sequence(
                        auto_id=job.automation_id,
                        channel_id=int(job.channel.telegram_chat_id) if job.channel else int(job.channel_id),
                        trigger_msg_id=0,
                        trigger_text="[Manual Web Trigger]"
                    )
                )
                job.status = "COMPLETED"
                db.commit()
            db.close()
        except Exception:
            pass
        await asyncio.sleep(1.0)

async def main():
    print("[🛰️ Telegram Listener Engine] Connecting to Telegram...", flush=True)
    await client.connect()
    if not await client.is_user_authorized():
        print("[❌ Error] Telethon Client session is not authorized!", flush=True)
        return

    me = await client.get_me()
    print("Preloading all channel dialogs to activate realtime MTProto subscription...", flush=True)
    dialogs = await client.get_dialogs(limit=200)

    # Populate already existing message IDs to prevent firing on historical messages
    db: Session = SessionLocal()
    for ch in db.query(Channel).filter(Channel.is_connected == True).all():
        try:
            hist_msgs = await client.get_messages(int(ch.telegram_chat_id), limit=20)
            for hm in hist_msgs:
                PROCESSED_MESSAGES.add(f"{ch.telegram_chat_id}_{hm.id}")
            INITIALIZED_CHANNELS.add(ch.telegram_chat_id)
        except Exception:
            pass
    db.close()

    print("=" * 65, flush=True)
    print(f"🛰️ [ReviewFlow Telegram Engine] Active as @{me.username} ({me.first_name})", flush=True)
    print(f"🛰️ Subscribed to {len(dialogs)} channels | Dual-Layer Live Listener & Watcher Running 24/7!", flush=True)
    print("=" * 65, flush=True)

    # Launch background tasks concurrently
    asyncio.create_task(poll_pending_jobs())
    asyncio.create_task(active_channel_watcher())
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
