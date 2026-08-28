import os
import sys
import time
import uuid
import asyncio
from datetime import datetime, timezone
from telethon import TelegramClient
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import SessionLocal
from backend.app.models.models import Channel, Automation, Job
from backend.app.services.telegram_service import telegram_service
from backend.app.services.job_engine import (
    ingest_channel_messages,
    claim_next_job,
    recover_expired_leases,
    update_worker_heartbeat,
    process_claimed_job
)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

WORKER_ID = f"listener-{uuid.uuid4().hex[:8]}"
RUNNING = True
CHANNEL_ENTITIES = {}
BOT_USER_ID = None

async def active_channel_watcher():
    """Polls connected channels for new messages and durably persists triggers into DB."""
    global CHANNEL_ENTITIES, BOT_USER_ID, RUNNING

    client = await telegram_service.get_client()

    try:
        me = await client.get_me()
        if me:
            BOT_USER_ID = me.id
            print(f"[🤖 Telegram Identity]: Logged in as User ID {BOT_USER_ID} (@{getattr(me, 'username', 'N/A')})", flush=True)
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
    client = await telegram_service.get_client()

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
                continue

            db.close()
        except Exception as exec_err:
            print(f"[!] Worker executor loop error: {exec_err}", flush=True)

        await asyncio.sleep(1.0)

async def main():
    print("=" * 65, flush=True)
    print(f"🛰️ [ReviewFlow Telegram Engine] Initializing Worker {WORKER_ID}...", flush=True)
    print("=" * 65, flush=True)

    client = await telegram_service.get_client()
    try:
        me = await client.get_me()
        bot_username = getattr(me, 'username', 'Unknown')
        bot_name = getattr(me, 'first_name', 'Bot')
        print(f"🛰️ [ReviewFlow Telegram Engine] Active as @{bot_username} ({bot_name})", flush=True)
    except Exception:
        pass

    await asyncio.gather(
        active_channel_watcher(),
        worker_job_executor()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\n[✓] ReviewFlow Telegram Engine shutdown complete.", flush=True)
