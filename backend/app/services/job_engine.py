import sys
import os
import re
import time
import random
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text, or_, and_
from sqlalchemy.exc import IntegrityError
from telethon import TelegramClient, types
from telethon.errors import FloodWaitError, ChatWriteForbiddenError, ChannelPrivateError, RPCError

from backend.app.core.config import settings
from backend.app.models.models import (
    Job, Automation, AutomationStep, Channel, MessageLibrary, 
    PublishingHistory, Tenant, Subscription, WorkerHeartbeat
)

BANK_ID = int(settings.DEFAULT_REVIEW_BANK_ID) if settings.DEFAULT_REVIEW_BANK_ID.lstrip("-").isdigit() else -1003969850866
logger = logging.getLogger("reviewflow.job_engine")

def normalize_text(text: str) -> str:
    """
    Robust multilingual and Arabic normalization:
    - Lowercase and strip whitespace.
    - Strips URLs (https://, http://, t.me, www.).
    - Normalizes all forms of Arabic Alef (أ, إ, آ, ٱ -> ا).
    - Normalizes Taa Marbuta (ة -> ه).
    - Normalizes Yaa / Alef Maksura (ى, ئ -> ي).
    - Removes Arabic Tashkeel (diacritics: Fatha, Damma, Kasra, Sukun, Tanwin, Shadda).
    - Removes Tatweel (ـ).
    - Collapses multiple whitespace characters to a single space.
    """
    if not text:
        return ""
    text = text.lower().strip()
    # 1. Remove URLs
    text = re.sub(r'https?://\S+|www\.\S+|t\.me/\S+', ' ', text)
    # 2. Normalize Arabic Alef
    text = re.sub(r'[إأآٱ]', 'ا', text)
    # 3. Normalize Taa Marbuta
    text = re.sub(r'ة', 'ه', text)
    # 4. Normalize Yaa / Alef Maksura
    text = re.sub(r'[ىئ]', 'ي', text)
    # 5. Remove Tashkeel (diacritics)
    text = re.sub(r'[\u064B-\u065F\u0670]', '', text)
    # 6. Remove Tatweel
    text = re.sub(r'ـ+', '', text)
    # 7. Collapse spaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def matches_trigger(msg_text: str, trigger_value: str, trigger_type: str) -> bool:
    """
    Smart, forgiving and precise trigger matching:
    - Normalizes Arabic and Latin text for bulletproof compatibility.
    - If trigger_type is 'exact': exact match after normalization.
    - If trigger_type is 'prefix': starts with after normalization.
    - If trigger_type is 'contains' (default): checks if normalized trigger keyword/phrase exists in normalized message.
    - For short ASCII keywords (<=4 chars like 'TP', 'SL'), enforces word boundaries so 'output' doesn't falsely match 'tp'.
    """
    if not msg_text or not trigger_value:
        return False

    norm_msg = normalize_text(msg_text)
    norm_trig = normalize_text(trigger_value)

    if not norm_trig or not norm_msg:
        return False

    if trigger_type == "exact":
        return norm_msg == norm_trig
    elif trigger_type == "prefix":
        return norm_msg.startswith(norm_trig)
    else:  # "contains" (standard default)
        if norm_trig.isascii() and len(norm_trig) <= 4:
            pattern = r'(?:^|[\s\W_])' + re.escape(norm_trig) + r'(?:$|[\s\W_])'
            return bool(re.search(pattern, norm_msg))
        return norm_trig in norm_msg


def is_valid_member_review(m) -> bool:
    """
    Filters bank messages to select valid review items.
    Supports text messages, photos, profit screenshots, videos, voice notes, and media.
    Excludes internal bank headers and channel loops.
    """
    if not getattr(m, 'fwd_from', None):
        # Also allow direct bank media/reviews if posted directly
        has_direct_content = bool(m.text or m.media or getattr(m, 'message', None))
        return has_direct_content

    from_id = getattr(m.fwd_from, 'from_id', None)
    from_name = getattr(m.fwd_from, 'from_name', None)

    # Strictly reject channel forwards or internal bank headers
    if isinstance(from_id, types.PeerChannel):
        return False
    if from_name and "massgesreview" in from_name.lower().replace(" ", ""):
        return False

    has_content = bool(m.text or m.media or getattr(m, 'message', None))
    return has_content

def ingest_channel_messages(
    db: Session, 
    channel: Channel, 
    messages: List[Any], 
    automations: List[Automation]
) -> int:
    """
    DURABLE EVENT INGESTION:
    Persists matched triggers into the database as PENDING jobs before updating channel cursor.
    Guarantees zero lost events across crashes or restarts.
    """
    created_jobs_count = 0
    now_utc = datetime.now(timezone.utc)

    for msg in reversed(messages):
        if getattr(msg, 'out', False) or getattr(msg, 'fwd_from', None):
            continue

        msg_text = getattr(msg, 'text', None) or getattr(msg, 'message', None) or ""
        if not msg_text.strip():
            continue

        # Sort automations so the most specific/longest keyword matches first
        sorted_autos = sorted(automations, key=lambda a: (a.trigger_type == "exact", len(a.trigger_value)), reverse=True)

        for auto in sorted_autos:
            if not auto.is_active:
                continue

            if matches_trigger(msg_text, auto.trigger_value, auto.trigger_type):
                idempotency_key = f"{channel.id}:{msg.id}:{auto.id}"
                existing_job = db.query(Job).filter(Job.idempotency_key == idempotency_key).first()
                if not existing_job:
                    try:
                        # Use a nested transaction (SAVEPOINT) for atomic, race-safe job creation.
                        init_delay = float(getattr(auto, 'initial_delay_seconds', 5.0) or 5.0)
                        with db.begin_nested():
                            job = Job(
                                tenant_id=channel.tenant_id,
                                automation_id=auto.id,
                                channel_id=channel.id,
                                idempotency_key=idempotency_key,
                                trigger_message_id=str(msg.id),
                                trigger_text=msg_text,
                                current_step=1,
                                total_steps=auto.reviews_count or 2,
                                status="PENDING",
                                execute_at=now_utc + timedelta(seconds=init_delay)
                            )
                            db.add(job)
                            db.flush()
                            created_jobs_count += 1
                    except IntegrityError:
                        logger.info("Concurrent duplicate job insertion safely ignored for key %s", idempotency_key)

                # STRICT RULE: 1 Telegram message triggers at most 1 matching automation
                break

    db.commit()

    if messages:
        max_id = max(m.id for m in messages)
        if max_id > (channel.last_seen_message_id or 0):
            channel.last_seen_message_id = max_id
            db.commit()

    return created_jobs_count

def claim_next_job(db: Session, worker_id: str, lease_duration_seconds: int = 60) -> Optional[Job]:
    """
    CONCURRENCY-SAFE ATOMIC JOB CLAIMING:
    Uses PostgreSQL SELECT ... FOR UPDATE SKIP LOCKED or atomic conditional update.
    Guarantees two workers NEVER claim the same job concurrently.
    """
    now_utc = datetime.now(timezone.utc)
    lease_expiration = now_utc + timedelta(seconds=lease_duration_seconds)

    bind = db.get_bind()
    if bind and "postgresql" in bind.dialect.name:
        sql = text("""
            SELECT id FROM jobs 
            WHERE (status = 'PENDING' OR (status = 'RETRY_SCHEDULED' AND execute_at <= :now))
            ORDER BY execute_at ASC, created_at ASC 
            LIMIT 1 
            FOR UPDATE SKIP LOCKED
        """)
        result = db.execute(sql, {"now": now_utc}).fetchone()
        if not result:
            return None
        job_id = result[0]
        
        db.query(Job).filter(Job.id == job_id).update({
            Job.status: "CLAIMED",
            Job.lease_owner: worker_id,
            Job.lease_expires_at: lease_expiration,
            Job.attempts: Job.attempts + 1,
            Job.updated_at: now_utc
        }, synchronize_session="fetch")
        db.commit()
        return db.query(Job).filter(Job.id == job_id).first()
    else:
        # Atomic Compare-and-Swap conditional claim for SQLite / Universal SQL engines
        candidate = db.query(Job).filter(
            or_(
                Job.status == "PENDING",
                and_(Job.status == "RETRY_SCHEDULED", Job.execute_at <= now_utc)
            )
        ).order_by(Job.execute_at.asc(), Job.created_at.asc()).first()

        if not candidate:
            return None

        # Atomic conditional update: Only update if the row is STILL PENDING / RETRY_SCHEDULED
        updated = db.query(Job).filter(
            Job.id == candidate.id,
            or_(
                Job.status == "PENDING",
                and_(Job.status == "RETRY_SCHEDULED", Job.execute_at <= now_utc)
            )
        ).update({
            Job.status: "CLAIMED",
            Job.lease_owner: worker_id,
            Job.lease_expires_at: lease_expiration,
            Job.attempts: Job.attempts + 1,
            Job.updated_at: now_utc
        }, synchronize_session="fetch")

        if updated == 0:
            db.rollback()
            return None

        db.commit()
        return db.query(Job).filter(Job.id == candidate.id).first()

def recover_expired_leases(db: Session, worker_id: str) -> int:
    """
    ATOMIC LEASE-AWARE CRASH RECOVERY:
    Atomically updates expired jobs in a single atomic SQL UPDATE statement.
    Prevents race conditions where multiple workers try to recover the same job simultaneously.
    Never steals actively running jobs with valid leases from live workers.
    """
    now_utc = datetime.now(timezone.utc)
    recovered_count = db.query(Job).filter(
        Job.status.in_(["CLAIMED", "RUNNING"]),
        Job.lease_expires_at < now_utc
    ).update(
        {
            Job.status: "PENDING",
            Job.error_message: f"Recovered from expired lease by worker {worker_id}",
            Job.lease_owner: None,
            Job.lease_expires_at: None,
            Job.updated_at: now_utc
        },
        synchronize_session="fetch"
    )

    if recovered_count > 0:
        db.commit()
    return recovered_count

def renew_job_lease(db: Session, job_id: str, worker_id: str, additional_seconds: int = 60) -> bool:
    """
    ATOMIC JOB-LEVEL LEASE RENEWAL:
    Renews the lease of an actively executing job so long-running operations never get stolen.
    Only the legitimate lease owner can renew their lease.
    """
    now_utc = datetime.now(timezone.utc)
    updated_rows = db.query(Job).filter(
        Job.id == job_id,
        Job.lease_owner == worker_id,
        Job.status == "RUNNING"
    ).update(
        {
            Job.lease_expires_at: now_utc + timedelta(seconds=additional_seconds),
            Job.updated_at: now_utc
        },
        synchronize_session="fetch"
    )
    if updated_rows > 0:
        db.commit()
        return True
    return False

def update_worker_heartbeat(db: Session, worker_id: str, hostname: str = "localhost", details: Dict[str, Any] = None):
    """Updates persistent worker heartbeat in database."""
    now_utc = datetime.now(timezone.utc)
    hb = db.query(WorkerHeartbeat).filter(WorkerHeartbeat.worker_id == worker_id).first()
    if not hb:
        hb = WorkerHeartbeat(
            worker_id=worker_id,
            hostname=hostname,
            status="active",
            last_heartbeat_at=now_utc,
            started_at=now_utc,
            details=details or {}
        )
        db.add(hb)
    else:
        hb.status = "active"
        hb.last_heartbeat_at = now_utc
        if details:
            hb.details = details
    db.commit()

async def process_claimed_job(db: Session, client: TelegramClient, job: Job, worker_id: str):
    """
    Executes a claimed job sequence with continuous background lease renewal,
    centralized Telegram FloodWait, step resumption, and error reconciliation.
    """
    now_utc = datetime.now(timezone.utc)

    # Verify worker ownership of this job before proceeding
    if job.lease_owner and job.lease_owner != worker_id and job.status in ("RUNNING", "CLAIMED"):
        job.status = "FAILED"
        job.error_message = f"Execution aborted: worker {worker_id} does not own the active lease (owned by {job.lease_owner})"
        db.commit()
        return

    job.status = "RUNNING"
    job.lease_owner = worker_id
    job.lease_expires_at = now_utc + timedelta(seconds=120)
    db.commit()

    # Continuous background lease renewal task with observable failure tracking
    stop_heartbeat = asyncio.Event()
    heartbeat_failed = asyncio.Event()

    async def _heartbeat_loop():
        consecutive_failures = 0
        while not stop_heartbeat.is_set():
            try:
                await asyncio.sleep(5)
                if stop_heartbeat.is_set():
                    break
                from backend.app.core.database import SessionLocal
                hb_db = SessionLocal()
                try:
                    renewed = renew_job_lease(hb_db, job.id, worker_id, additional_seconds=120)
                    if renewed:
                        consecutive_failures = 0
                    else:
                        consecutive_failures += 1
                        logger.warning(
                            "Lease renewal returned False for job %s worker %s (attempt %d/2)",
                            job.id[:8], worker_id, consecutive_failures,
                        )
                        if consecutive_failures >= 2:
                            logger.error(
                                "Lease renewal FAILED for job %s — worker %s lost ownership",
                                job.id[:8], worker_id,
                            )
                            heartbeat_failed.set()
                            break
                finally:
                    hb_db.close()
            except Exception as hb_err:
                consecutive_failures += 1
                logger.warning(
                    "Lease renewal exception for job %s worker %s (attempt %d/2): %s",
                    job.id[:8], worker_id, consecutive_failures, hb_err,
                )
                if consecutive_failures >= 2:
                    logger.error(
                        "Lease renewal FAILED (exception) for job %s — worker %s aborting",
                        job.id[:8], worker_id,
                    )
                    heartbeat_failed.set()
                    break

    heartbeat_task = asyncio.create_task(_heartbeat_loop())

    try:
        channel = job.channel
        auto = job.automation
        tenant = job.tenant

        if not channel or not channel.is_connected:
            job.status = "FAILED"
            job.error_message = "Target channel not found or disconnected"
            job.lease_owner = None
            job.lease_expires_at = None
            db.commit()
            return

        if not auto or not auto.is_active:
            job.status = "FAILED"
            job.error_message = "Automation is inactive or deleted"
            job.lease_owner = None
            job.lease_expires_at = None
            db.commit()
            return

        sub = tenant.subscription if tenant else None
        if sub and sub.expires_at:
            exp_at = sub.expires_at if sub.expires_at.tzinfo else sub.expires_at.replace(tzinfo=timezone.utc)
            if sub.status not in ["active", "trial", "grace_period"] or exp_at < now_utc:
                job.status = "FAILED"
                job.error_message = "Subscription is expired or inactive"
                job.lease_owner = None
                job.lease_expires_at = None
                db.commit()
                return

        try:
            bank_msgs = await client.get_messages(BANK_ID, limit=100)
            valid_reviews = [m for m in bank_msgs if is_valid_member_review(m)]

            if not valid_reviews:
                job.status = "FAILED"
                job.error_message = "No valid member reviews available in central bank"
                job.lease_owner = None
                job.lease_expires_at = None
                db.commit()
                return

            target_count = getattr(auto, 'reviews_count', 2) or 2
            initial_delay = float(getattr(auto, 'initial_delay_seconds', 5.0) or 5.0)
            base_delay = float(getattr(auto, 'delay_seconds', 4.0) or 4.0)

            count = min(target_count, len(valid_reviews))
            selected_msgs = random.sample(valid_reviews, k=count)
            target_chat_peer = int(channel.telegram_chat_id)

            # Resume from current step if previously interrupted
            start_step = getattr(job, 'current_step', 1) or 1

            for idx in range(start_step, count + 1):
                if heartbeat_failed.is_set():
                    job.status = "FAILED"
                    job.error_message = "Execution aborted: background lease renewal failed"
                    job.lease_owner = None
                    job.lease_expires_at = None
                    db.commit()
                    return

                # Synchronous verification of lease ownership before executing step
                has_lease = renew_job_lease(db, job.id, worker_id, additional_seconds=120)
                if not has_lease:
                    job.status = "FAILED"
                    job.error_message = "Execution aborted: worker lost lease ownership"
                    job.lease_owner = None
                    job.lease_expires_at = None
                    db.commit()
                    return

                m = selected_msgs[idx - 1]
                fwd_name = getattr(m.fwd_from, 'from_name', 'Member') if m.fwd_from else 'Member'

                # ── Step Reconciliation (Publish-Intent Outbox Pattern) ──
                # Check if a prior run already touched this step.
                existing_record = db.query(PublishingHistory).filter(
                    PublishingHistory.job_id == job.id,
                    PublishingHistory.step_number == idx,
                ).first()

                intent_record = None

                if existing_record:
                    if existing_record.status == "SUCCESS":
                        # Step fully completed in a prior run — skip
                        job.current_step = idx + 1
                        db.commit()
                        continue
                    elif existing_record.status in ("PUBLISHING", "UNKNOWN", "ASSUMED_DELIVERED"):
                        # CRASH / TIMEOUT / AMBIGUOUS OUTCOME:
                        # A prior worker wrote the intent and entered PUBLISHING,
                        # but the process crashed or disconnected before confirming SUCCESS.
                        # The external side-effect is in an UNKNOWN state.
                        # Reconcile safely: mark as UNKNOWN / ASSUMED_DELIVERED to prevent blind duplicate.
                        existing_record.status = "UNKNOWN"
                        existing_record.error_details = (
                            f"Prior worker crashed after intent commit. "
                            f"Reconciled by {worker_id} (ambiguous delivery state) — skipping to avoid duplicate."
                        )
                        job.current_step = idx + 1
                        db.commit()
                        continue
                    elif existing_record.status in ("FAILED",):
                        # Prior attempt explicitly failed before Telegram side-effect — safe to retry.
                        # Reuse existing record to satisfy unique constraint without ID churn.
                        intent_record = existing_record
                        intent_record.status = "PUBLISHING"
                        intent_record.error_details = None
                        intent_record.message_title = f"Review from {fwd_name}"
                        intent_record.automation_name = auto.name
                        intent_record.telegram_message_id = None
                        db.commit()

                if idx == 1:
                    delay = max(0.5, round(random.uniform(0.5, 1.5), 1))
                else:
                    delay = max(1.5, round(base_delay + random.uniform(-0.5, 1.5), 1))

                await asyncio.sleep(delay)

                if not intent_record:
                    # ── PHASE 1: Write durable publish INTENT before Telegram call ──
                    try:
                        intent_record = PublishingHistory(
                            tenant_id=tenant.id,
                            job_id=job.id,
                            channel_id=channel.id,
                            message_title=f"Review from {fwd_name}",
                            automation_name=auto.name,
                            step_number=idx,
                            status="PUBLISHING",       # Intent — not yet confirmed
                            telegram_message_id=None,
                        )
                        db.add(intent_record)
                        db.commit()  # ← DURABLE: if we crash after this, the intent survives
                    except IntegrityError:
                        db.rollback()
                        # Another concurrent worker already wrote the intent row for this exact step.
                        intent_record = db.query(PublishingHistory).filter(
                            PublishingHistory.job_id == job.id,
                            PublishingHistory.step_number == idx,
                        ).first()
                        if intent_record and intent_record.status == "SUCCESS":
                            job.current_step = idx + 1
                            db.commit()
                            continue

                try:
                    # ── PHASE 2: Execute external side-effect ──
                    if hasattr(client, 'forward_with_failover'):
                        res = await client.forward_with_failover(
                            target_chat_peer=target_chat_peer,
                            message_id=m.id,
                            from_peer=BANK_ID,
                            channel_model=channel,
                            db=db
                        )
                    else:
                        res = await client.forward_messages(
                            entity=target_chat_peer,
                            messages=m.id,
                            from_peer=BANK_ID
                        )
                    msg_id = res.id if not isinstance(res, list) else (res[0].id if res else None)

                    # ── PHASE 3: Confirm delivery in DB ──
                    intent_record.status = "SUCCESS"
                    intent_record.telegram_message_id = str(msg_id)
                    job.current_step = idx + 1
                    db.commit()  # ← If crash here, intent stays PUBLISHING → recovered as UNKNOWN

                except FloodWaitError as flood_err:
                    intent_record.status = "FLOOD_WAIT"
                    intent_record.error_details = f"FloodWait of {flood_err.seconds}s"
                    job.status = "RETRY_SCHEDULED"
                    job.execute_at = datetime.now(timezone.utc) + timedelta(seconds=flood_err.seconds + 2)
                    job.error_message = f"Telegram FloodWait: {flood_err.seconds}s required"
                    job.lease_owner = None
                    job.lease_expires_at = None
                    db.commit()
                    return

                except (ChatWriteForbiddenError, ChannelPrivateError) as perm_err:
                    intent_record.status = "FAILED"
                    intent_record.error_details = str(perm_err)
                    job.status = "FAILED"
                    job.lease_owner = None
                    job.lease_expires_at = None
                    job.error_message = f"Telegram Permission Error: {perm_err}"
                    db.commit()
                    return

                except Exception as send_err:
                    intent_record.status = "FAILED"
                    intent_record.error_details = f"Send error: {str(send_err)}"
                    job.status = "FAILED"
                    job.lease_owner = None
                    job.lease_expires_at = None
                    job.error_message = f"Send error: {str(send_err)}"
                    db.commit()
                    return

            job.status = "COMPLETED"
            job.lease_owner = None
            job.lease_expires_at = None
            auto.total_executions += 1
            auto.last_executed_at = datetime.now(timezone.utc)
            db.commit()

        except Exception as general_err:
            job.status = "FAILED"
            job.error_message = f"Unexpected execution error: {str(general_err)}"
            job.lease_owner = None
            job.lease_expires_at = None
            db.commit()
    finally:
        stop_heartbeat.set()
        heartbeat_task.cancel()
        # Use gather(return_exceptions=True) to silently consume CancelledError.
        # In Python 3.10+, CancelledError is a BaseException that can propagate
        # through finally blocks — gather with return_exceptions avoids this.
        await asyncio.gather(heartbeat_task, return_exceptions=True)
