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

RUNNING = True
CHANNEL_ENTITIES = {}
BOT_USER_ID = None

async def active_channel_watcher():
    """Polls channels for new messages and ingests triggers durably into the DB."""
    global CHANNEL_ENTITIES, BOT_USER_ID, RUNNING

    try:
        me = await client.get_me()
        if me:
            BOT_USER_ID = me.id
            print(f"[🤖 Telegram Identity]: Logged in as User ID {BOT_USER_ID} (@{me.username})", flush=True)
    except Exception as e:
        print(f"[!] Warning fetching Telegram identity: {e}", flush=True)

    while RUNNING:
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

                # Initialize cursor if missing
                if not ch.last_seen_message_id or ch.last_seen_message_id == 0:
                    try:
                        latest_msg = await client.get_messages(entity, limit=1)
                        ch.last_seen_message_id = latest_msg[0].id if latest_msg else 1
                        db.commit()
                    except Exception:
                        pass
                    continue

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

                # Ingest new messages durably
                try:
                    new_msgs = await client.get_messages(entity, min_id=ch.last_seen_message_id, limit=20)
                    if new_msgs:
                        created = ingest_channel_messages(db, ch, new_msgs, automations)
                        if created > 0:
                            print(f"[📥 Durable Ingestion]: Enqueued {created} pending jobs for channel '{ch.title}'", flush=True)
                        
                        # Update cursor
                        ch.last_seen_message_id = max(m.id for m in new_msgs)
                        db.commit()
                except Exception as ingest_err:
                    print(f"[!] Channel '{ch.title}' ingestion error: {ingest_err}", flush=True)

            db.close()
        except Exception as loop_err:
            print(f"[!] Active channel watcher loop error: {loop_err}", flush=True)

        await asyncio.sleep(1.0)

async def worker_job_executor():
    """Continuously claims and executes pending jobs with atomic locking and lease management."""
    global RUNNING
    last_recovery_time = 0

    while RUNNING:
        try:
            db: Session = SessionLocal()

            # Heartbeat every 10 seconds
            update_worker_heartbeat(db, WORKER_ID, details={"service": "telegram_engine", "status": "active"})

            # Periodic lease recovery every 30 seconds
            if time.time() - last_recovery_time > 30:
                recovered = recover_expired_leases(db, WORKER_ID)
                if recovered > 0:
                    print(f"[🔄 Lease Recovery]: Recovered {recovered} orphaned jobs with expired leases.", flush=True)
                last_recovery_time = time.time()

            # Atomically claim next job
            job = claim_next_job(db, WORKER_ID, lease_duration_seconds=60)
            if job:
                print(f"\n[⚡ Claimed Job {job.id[:8]}]: Channel {job.channel_id} | Trigger '{job.trigger_text}'", flush=True)
                await process_claimed_job(db, client, job, WORKER_ID)
                db.close()
                continue  # Immediately check for next job

            db.close()
        except Exception as exec_err:
            print(f"[!] Worker executor loop error: {exec_err}", flush=True)

        await asyncio.sleep(1.0)

async def main():
    print("=" * 65, flush=True)
    print(f"🛰️ [ReviewFlow Telegram Engine] Initializing Worker {WORKER_ID}...", flush=True)
    print("=" * 65, flush=True)

    await client.start()
    me = await client.get_me()
    print(f"🛰️ [ReviewFlow Telegram Engine] Active as @{me.username} ({me.first_name})", flush=True)

    await asyncio.gather(
        active_channel_watcher(),
        worker_job_executor()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\n[✓] ReviewFlow Telegram Engine shutdown complete.", flush=True)
