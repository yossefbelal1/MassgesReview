import os
import sys
import time
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from telethon import TelegramClient, events
from sqlalchemy.orm import Session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

from backend.app.core.config import settings
from backend.app.core.database import SessionLocal
from backend.app.models.models import Channel, Automation, ChannelUserbot
from backend.app.services.telegram_service import telegram_service
from backend.app.services.userbot_pool import userbot_pool
from backend.app.services.retention_engine import retention_engine
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
    """
    Polls connected channels for new messages and durably persists triggers into DB.
    Self-heals and auto-reconnects on any network or Telegram connection drop.
    """
    global CHANNEL_ENTITIES, BOT_USER_ID, RUNNING

    while RUNNING:
        try:
            client = await telegram_service.ensure_connected()

            db: Session = SessionLocal()
            channels = db.query(Channel).filter(Channel.is_connected == True).all()

            for ch in channels:
                if not ch.tenant or not ch.tenant.is_active:
                    continue

                chat_peer = int(ch.telegram_chat_id)
                if chat_peer not in CHANNEL_ENTITIES:
                    try:
                        CHANNEL_ENTITIES[chat_peer] = await client.get_entity(chat_peer)
                    except Exception as ent_err:
                        if "disconnected" in str(ent_err).lower():
                            await telegram_service.ensure_connected()
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
                    err_str = str(ingest_err).lower()
                    print(f"[!] Channel '{ch.title}' ingestion error: {ingest_err}", flush=True)
                    if "disconnected" in err_str or "connection" in err_str:
                        await telegram_service.ensure_connected()

            db.close()
        except Exception as loop_err:
            err_str = str(loop_err).lower()
            print(f"[!] Active channel watcher loop error: {loop_err}", flush=True)
            if "disconnected" in err_str or "connection" in err_str:
                await telegram_service.ensure_connected()

        await asyncio.sleep(2.0)

async def retention_channel_watcher():
    """
    Monitors channel Recent Actions (Admin Log) for member leaves and joins.
    ONLY syncs admin log — does NOT send messages. Runs independently every 5s.
    """
    global CHANNEL_ENTITIES, RUNNING

    # Give primary connection time to settle
    await asyncio.sleep(5.0)
    poll_count = 0

    while RUNNING:
        try:
            client = await telegram_service.ensure_connected()
            db: Session = SessionLocal()

            channels = db.query(Channel).filter(Channel.is_connected == True).all()
            total_events = 0
            for ch in channels:
                if not ch.tenant or not ch.tenant.is_active:
                    continue
                try:
                    events_count = await retention_engine.sync_channel_admin_log(db, ch, client)
                    total_events += events_count
                    if events_count > 0:
                        print(f"[🎯 Retention Watcher]: Processed {events_count} join/leave events for '{ch.title}'", flush=True)
                except Exception as sync_err:
                    print(f"[!] Retention sync error for channel '{ch.title}': {sync_err}", flush=True)

            db.close()

            # Log heartbeat every 60 polls (~5 minutes) even when no events
            poll_count += 1
            if poll_count % 60 == 0:
                print(f"[🔄 Retention Watcher Heartbeat]: Poll #{poll_count}, channels={len(channels)}, last cycle events={total_events}", flush=True)

        except Exception as loop_err:
            err_str = str(loop_err).lower()
            print(f"[!] Retention watcher loop error: {loop_err}", flush=True)
            if "disconnected" in err_str or "connection" in err_str:
                await telegram_service.ensure_connected()

        await asyncio.sleep(5.0)


async def retention_outreach_dispatcher():
    """
    Separate coroutine that processes pending recovery contacts.
    Runs independently from admin log sync to never block leave detection.
    Has circuit breaker: backs off when all accounts have PeerFlood.
    """
    global RUNNING

    await asyncio.sleep(8.0)  # Let watcher populate cases first
    backoff_seconds = 10.0  # Normal polling interval

    while RUNNING:
        try:
            db: Session = SessionLocal()

            # Auto-heal any dedicated userbots whose cooldown has expired
            now_utc = datetime.now(timezone.utc)
            expired_bots = db.query(ChannelUserbot).filter(
                ChannelUserbot.status == "FLOOD_WAIT",
                (ChannelUserbot.cooldown_until == None) | (ChannelUserbot.cooldown_until <= now_utc)
            ).all()
            if expired_bots:
                for eb in expired_bots:
                    eb.status = "CONNECTED"
                    eb.cooldown_until = None
                    eb.last_error = None
                db.commit()

            # Circuit breaker: only back off if fallback pool is in cooldown AND no active dedicated userbots exist
            has_dedicated_bots = db.query(ChannelUserbot).filter(
                ChannelUserbot.is_active == True,
                (
                    (ChannelUserbot.status == "CONNECTED") |
                    ((ChannelUserbot.status == "FLOOD_WAIT") & (
                        (ChannelUserbot.cooldown_until == None) | (ChannelUserbot.cooldown_until <= now_utc)
                    ))
                )
            ).first() is not None

            all_fallback_in_cooldown = len(userbot_pool.sessions) > 0 and all(
                time.time() < s.cooldown_until for s in userbot_pool.sessions
            )
            if not has_dedicated_bots and all_fallback_in_cooldown:
                cooldowns = [s.cooldown_until - time.time() for s in userbot_pool.sessions]
                wait_remaining = int(max(cooldowns)) if cooldowns else 60
                if backoff_seconds < 300:  # Max 5 min backoff
                    backoff_seconds = min(backoff_seconds * 2, 300)
                print(f"[⏸️ Outreach Circuit Breaker]: All fallback sessions in PeerFlood cooldown and no dedicated bots. "
                      f"Next check in {int(backoff_seconds)}s. Cooldown remaining: {wait_remaining}s", flush=True)
                db.close()
                await asyncio.sleep(backoff_seconds)
                continue

            # Reset backoff when sessions are available
            backoff_seconds = 5.0

            await retention_engine.process_pending_recovery_contacts(db)
            db.close()
        except Exception as loop_err:
            print(f"[!] Outreach dispatcher error: {loop_err}", flush=True)

        await asyncio.sleep(5.0)

async def worker_job_executor():
    """
    Continuously claims and executes pending jobs with atomic locking,
    auto-reconnecting client, and lease management.
    """
    global RUNNING
    last_recovery_time = 0

    while RUNNING:
        try:
            client = await telegram_service.ensure_connected()
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
                job_id = job.id
                db.close()

                async def _run_job_task(target_job_id: str):
                    task_db: Session = SessionLocal()
                    try:
                        j = task_db.query(Job).filter(Job.id == target_job_id).first()
                        if j:
                            await process_claimed_job(task_db, telegram_service, j, WORKER_ID)
                    except Exception as j_err:
                        print(f"[!] Job {target_job_id[:8]} execution error: {j_err}", flush=True)
                    finally:
                        task_db.close()

                asyncio.create_task(_run_job_task(job_id))
                continue

            db.close()
        except Exception as exec_err:
            err_str = str(exec_err).lower()
            print(f"[!] Worker executor loop error: {exec_err}", flush=True)
            if "disconnected" in err_str or "connection" in err_str:
                await telegram_service.ensure_connected()

        await asyncio.sleep(0.5)

async def retention_reconciliation_worker():
    """
    Runs periodic reconciliation for all connected channels hourly and computes
    daily retention metrics. Ensures 100% data audit and self-healing.
    """
    global RUNNING
    # Initial pause to allow watcher and client to stabilize
    await asyncio.sleep(60.0)

    while RUNNING:
        try:
            db: Session = SessionLocal()
            channels = db.query(Channel).filter(Channel.is_connected == True).all()
            for ch in channels:
                if not ch.tenant or not ch.tenant.is_active:
                    continue
                try:
                    report = await retention_engine.reconcile_channel_membership(db, ch)
                    if report.get("discrepancy", 0) != 0:
                        print(f"[🔍 Reconciliation Audit]: Channel '{ch.title}' | TG: {report['actual_telegram_members']} vs DB: {report['db_active_members']} | Diff: {report['discrepancy']} ({report['status']})", flush=True)
                    # Automatically compute / update daily metrics
                    retention_engine.compute_daily_retention_metrics(db, ch.id)
                except Exception as rec_err:
                    print(f"[!] Reconciliation error for '{ch.title}': {rec_err}", flush=True)

            db.close()
        except Exception as e:
            print(f"[!] Error in retention reconciliation worker loop: {e}", flush=True)

        # Run every 1 hour (3600s)
        await asyncio.sleep(3600.0)

async def keepalive_ping():
    """Keeps the MTProto TCP session alive and healthy 24/7."""
    global RUNNING
    while RUNNING:
        try:
            client = await telegram_service.ensure_connected()
            me = await client.get_me()
            if me:
                BOT_USER_ID = me.id
        except Exception as e:
            print(f"[!] Keepalive reconnecting: {e}", flush=True)
            await telegram_service.reset_client()
        await asyncio.sleep(60.0)

async def main():
    print("=" * 65, flush=True)
    print(f"🛰️ [ReviewFlow Telegram Engine] Initializing Worker {WORKER_ID}...", flush=True)
    print("=" * 65, flush=True)

    client = await telegram_service.ensure_connected()
    try:
        me = await client.get_me()
        bot_username = getattr(me, 'username', 'Unknown')
        bot_name = getattr(me, 'first_name', 'Bot')
        print(f"🛰️ [ReviewFlow Telegram Engine] Active as @{bot_username} ({bot_name})", flush=True)
    except Exception as e:
        print(f"[!] Warning fetching Telegram identity: {e}", flush=True)

    # Register conversational retention reply handler for incoming userbot DMs
    userbot_pool.register_inbound_handler(retention_engine.handle_inbound_reply)
    await userbot_pool.ensure_listeners_registered()
    print("🛰️ [ReviewFlow Telegram Engine] Retention Inbound Listeners Active.", flush=True)

    await asyncio.gather(
        active_channel_watcher(),
        retention_channel_watcher(),
        retention_outreach_dispatcher(),
        retention_reconciliation_worker(),
        worker_job_executor(),
        keepalive_ping()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\n[✓] ReviewFlow Telegram Engine shutdown complete.", flush=True)
