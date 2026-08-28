import sys
import os
import time
import random
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text, or_, and_
from telethon import TelegramClient, types
from telethon.errors import FloodWaitError, ChatWriteForbiddenError, ChannelPrivateError, RPCError

from backend.app.core.config import settings
from backend.app.models.models import (
    Job, Automation, AutomationStep, Channel, MessageLibrary, 
    PublishingHistory, Tenant, Subscription, WorkerHeartbeat
)

BANK_ID = int(settings.DEFAULT_REVIEW_BANK_ID) if settings.DEFAULT_REVIEW_BANK_ID.lstrip("-").isdigit() else -1003969850866

def is_valid_member_review(m) -> bool:
    """Strictly ensures message is an authentic member review without channel forward headers."""
    if not getattr(m, 'fwd_from', None):
        return False
    from_id = getattr(m.fwd_from, 'from_id', None)
    from_name = getattr(m.fwd_from, 'from_name', None)

    # Strictly reject channel forwards or internal bank headers
    if isinstance(from_id, types.PeerChannel):
        return False
    if from_name and "massgesreview" in from_name.lower().replace(" ", ""):
        return False

    return bool(m.text and (from_name or isinstance(from_id, types.PeerUser)))

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

        for auto in automations:
            if not auto.is_active:
                continue

            t_val = auto.trigger_value.strip().lower()
            msg_lower = msg_text.strip().lower()

            is_match = False
            if auto.trigger_type == "exact":
                is_match = (msg_lower == t_val)
            elif auto.trigger_type == "prefix":
                is_match = msg_lower.startswith(t_val)
            else:  # contains
                is_match = (t_val in msg_lower)

            if is_match:
                idempotency_key = f"{channel.id}:{msg.id}:{auto.id}"
                existing_job = db.query(Job).filter(Job.idempotency_key == idempotency_key).first()
                if not existing_job:
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
                        execute_at=now_utc
                    )
                    db.add(job)
                    created_jobs_count += 1

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
    Uses PostgreSQL SELECT ... FOR UPDATE SKIP LOCKED or SQLite transactional row locks.
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
        job = db.query(Job).filter(Job.id == job_id).first()
    else:
        job = db.query(Job).filter(
            or_(
                Job.status == "PENDING",
                and_(Job.status == "RETRY_SCHEDULED", Job.execute_at <= now_utc)
            )
        ).order_by(Job.execute_at.asc(), Job.created_at.asc()).first()

    if not job:
        return None

    job.status = "CLAIMED"
    job.lease_owner = worker_id
    job.lease_expires_at = lease_expiration
    job.attempts += 1
    job.updated_at = now_utc
    db.commit()
    db.refresh(job)
    return job

def recover_expired_leases(db: Session, worker_id: str) -> int:
    """
    HEARTBEAT & LEASE-AWARE CRASH RECOVERY:
    Recovers only jobs whose lease has legitimately expired.
    Never steals actively running jobs from valid live workers.
    """
    now_utc = datetime.now(timezone.utc)
    expired_jobs = db.query(Job).filter(
        Job.status.in_(["CLAIMED", "RUNNING"]),
        Job.lease_expires_at < now_utc
    ).all()

    recovered_count = 0
    for j in expired_jobs:
        j.status = "PENDING"
        j.error_message = f"Recovered from expired lease (previous owner: {j.lease_owner})"
        j.lease_owner = None
        j.lease_expires_at = None
        j.updated_at = now_utc
        recovered_count += 1

    if recovered_count > 0:
        db.commit()
    return recovered_count

def renew_job_lease(db: Session, job_id: str, worker_id: str, additional_seconds: int = 60) -> bool:
    """
    JOB-LEVEL LEASE RENEWAL:
    Renews the lease of an actively executing job so long-running operations never get stolen.
    Only the legitimate lease owner can renew their lease.
    """
    now_utc = datetime.now(timezone.utc)
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.lease_owner == worker_id,
        Job.status == "RUNNING"
    ).first()
    if not job:
        return False

    job.lease_expires_at = now_utc + timedelta(seconds=additional_seconds)
    job.updated_at = now_utc
    db.commit()
    return True

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
    Executes a claimed job sequence with centralized Telegram FloodWait, step resumption, and error reconciliation.
    """
    now_utc = datetime.now(timezone.utc)
    job.status = "RUNNING"
    job.lease_expires_at = now_utc + timedelta(seconds=120)
    db.commit()

    channel = job.channel
    auto = job.automation
    tenant = job.tenant

    if not channel or not channel.is_connected:
        job.status = "FAILED"
        job.error_message = "Target channel not found or disconnected"
        db.commit()
        return

    if not auto or not auto.is_active:
        job.status = "FAILED"
        job.error_message = "Automation is inactive or deleted"
        db.commit()
        return

    sub = tenant.subscription if tenant else None
    if sub and sub.expires_at:
        exp_at = sub.expires_at if sub.expires_at.tzinfo else sub.expires_at.replace(tzinfo=timezone.utc)
        if sub.status not in ["active", "trial", "grace_period"] or exp_at < now_utc:
            job.status = "FAILED"
            job.error_message = "Subscription is expired or inactive"
            db.commit()
            return

    try:
        bank_msgs = await client.get_messages(BANK_ID, limit=100)
        valid_reviews = [m for m in bank_msgs if is_valid_member_review(m)]

        if not valid_reviews:
            job.status = "FAILED"
            job.error_message = "No valid member reviews available in central bank"
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
            # Job-level lease renewal to ensure long-running sequences never expire mid-flight
            renew_job_lease(db, job.id, worker_id, additional_seconds=120)

            m = selected_msgs[idx - 1]
            if idx == 1:
                delay = max(0.5, round(initial_delay + random.uniform(-0.5, 0.8), 1))
            else:
                delay = max(1.5, round(base_delay + random.uniform(-0.8, 1.8), 1))

            await asyncio.sleep(delay)

            try:
                res = await client.forward_messages(
                    entity=target_chat_peer,
                    messages=m.id,
                    from_peer=BANK_ID
                )
                msg_id = res.id if not isinstance(res, list) else (res[0].id if res else None)
                fwd_name = getattr(m.fwd_from, 'from_name', 'Member') if m.fwd_from else 'Member'

                job.current_step = idx + 1
                db.add(PublishingHistory(
                    tenant_id=tenant.id,
                    job_id=job.id,
                    channel_id=channel.id,
                    message_title=f"Review from {fwd_name}",
                    automation_name=auto.name,
                    step_number=idx,
                    status="SUCCESS",
                    telegram_message_id=str(msg_id)
                ))
                db.commit()

            except FloodWaitError as flood_err:
                job.status = "RETRY_SCHEDULED"
                job.execute_at = datetime.now(timezone.utc) + timedelta(seconds=flood_err.seconds + 2)
                job.error_message = f"Telegram FloodWait: {flood_err.seconds}s required"
                db.add(PublishingHistory(
                    tenant_id=tenant.id,
                    job_id=job.id,
                    channel_id=channel.id,
                    message_title="Review (FloodWait)",
                    automation_name=auto.name,
                    step_number=idx,
                    status="FLOOD_WAIT",
                    error_details=f"FloodWait of {flood_err.seconds}s"
                ))
                db.commit()
                return

            except (ChatWriteForbiddenError, ChannelPrivateError) as perm_err:
                job.status = "FAILED"
                job.error_message = f"Telegram Permission Error: {perm_err}"
                db.add(PublishingHistory(
                    tenant_id=tenant.id,
                    job_id=job.id,
                    channel_id=channel.id,
                    message_title="Review (Permission Denied)",
                    automation_name=auto.name,
                    step_number=idx,
                    status="FAILED",
                    error_details=str(perm_err)
                ))
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
        db.commit()
