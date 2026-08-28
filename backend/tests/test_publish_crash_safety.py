"""
Telegram Publishing Crash Safety & Reconciliation Tests — Publish-Intent Outbox Pattern

Explicitly tests the 6 critical crash, failure, and recovery scenarios:
TEST 1 — Normal success: publish succeeds, DB finalization succeeds -> 1 publish, SUCCESS state
TEST 2 — Telegram fails BEFORE side effect -> retry is safe, no false SUCCESS
TEST 3 — Telegram succeeds, DB finalization crashes -> durable state = PUBLISHING/UNKNOWN, no blind duplicate publish
TEST 4 — Restart/recovery: worker restart reconciles interrupted step safely
TEST 5 — Two workers recover same interrupted job -> only one worker owns and reconciles the step
TEST 6 — Duplicate retry: repeated recovery pass produces zero duplicate forwards
"""
import pytest
import time
import threading
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from backend.app.models.models import (
    Job, Channel, Automation, PublishingHistory, Tenant, Plan, Subscription,
)
from backend.app.services.job_engine import (
    process_claimed_job,
    claim_next_job,
    recover_expired_leases,
    renew_job_lease,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session():
    from backend.tests.conftest import TestingSessionLocal
    return TestingSessionLocal()


def _seed_tenant(sess):
    tenant = Tenant(name="Crash Test Tenant", slug=f"crash-{time.time_ns()}")
    sess.add(tenant)
    sess.flush()
    plan = sess.query(Plan).filter(Plan.slug == "starter").first()
    sub = Subscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        status="active",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    sess.add(sub)
    sess.flush()
    return tenant


def _seed_channel_auto(sess, tenant, reviews=2):
    ch = Channel(
        tenant_id=tenant.id,
        telegram_chat_id=f"-100{time.time_ns() % 10**9}",
        title="Crash Channel",
        is_connected=True,
    )
    sess.add(ch)
    sess.flush()
    auto = Automation(
        tenant_id=tenant.id,
        channel_id=ch.id,
        name="Crash Auto",
        trigger_value="SIG",
        is_active=True,
        reviews_count=reviews,
        initial_delay_seconds=0.01,
        delay_seconds=0.01,
    )
    sess.add(auto)
    sess.flush()
    return ch, auto


class SuccessClient:
    """Mock Telegram client — all forwards succeed."""
    def __init__(self):
        self.forwarded_count = 0
        self.forwarded_messages = []
        self.is_connected = MagicMock(return_value=True)

    async def get_messages(self, entity, limit=100):
        m1 = MagicMock(id=301, text="Great profit!", fwd_from=MagicMock(from_id=MagicMock(), from_name="Alice"))
        m2 = MagicMock(id=302, text="Hit TP!", fwd_from=MagicMock(from_id=MagicMock(), from_name="Bob"))
        return [m1, m2]

    async def forward_messages(self, entity, messages, from_peer):
        self.forwarded_count += 1
        self.forwarded_messages.append(messages)
        res = MagicMock()
        res.id = 7000 + self.forwarded_count
        return res


class FailBeforeSideEffectClient:
    """Mock client — forward_messages raises BEFORE any side-effect."""
    def __init__(self):
        self.forwarded_count = 0
        self.is_connected = MagicMock(return_value=True)

    async def get_messages(self, entity, limit=100):
        m1 = MagicMock(id=301, text="Great profit!", fwd_from=MagicMock(from_id=MagicMock(), from_name="Alice"))
        return [m1]

    async def forward_messages(self, entity, messages, from_peer):
        raise ConnectionError("Network connection reset before transmission — no side-effect")


# ===================================================================
# TEST 1 — Normal success
# ===================================================================

@pytest.mark.asyncio
async def test_1_normal_success_publish_and_db_finalization():
    """
    TEST 1: Normal path.
    Publish succeeds, DB finalization succeeds.
    Expected: exactly one publish, status=SUCCESS, telegram_message_id recorded.
    """
    sess = _make_session()
    tenant = _seed_tenant(sess)
    ch, auto = _seed_channel_auto(sess, tenant, reviews=1)

    job = Job(
        tenant_id=tenant.id,
        automation_id=auto.id,
        channel_id=ch.id,
        idempotency_key=f"t1_{time.time_ns()}",
        trigger_text="SIG",
        status="CLAIMED",
        current_step=1,
        total_steps=1,
    )
    sess.add(job)
    sess.commit()
    job_id = job.id

    client = SuccessClient()
    await process_claimed_job(sess, client, job, worker_id="worker_t1")
    sess.refresh(job)

    assert job.status == "COMPLETED"
    assert client.forwarded_count == 1

    history = sess.query(PublishingHistory).filter(
        PublishingHistory.job_id == job_id,
    ).all()
    assert len(history) == 1
    assert history[0].status == "SUCCESS"
    assert history[0].step_number == 1
    assert history[0].telegram_message_id == "7001"
    sess.close()


# ===================================================================
# TEST 2 — Telegram fails BEFORE side effect
# ===================================================================

@pytest.mark.asyncio
async def test_2_telegram_fails_before_side_effect():
    """
    TEST 2: Telegram fails BEFORE external side-effect occurs.
    Expected: marked FAILED (not false SUCCESS), safe to retry on recovery.
    """
    sess = _make_session()
    tenant = _seed_tenant(sess)
    ch, auto = _seed_channel_auto(sess, tenant, reviews=1)

    job = Job(
        tenant_id=tenant.id,
        automation_id=auto.id,
        channel_id=ch.id,
        idempotency_key=f"t2_{time.time_ns()}",
        trigger_text="SIG",
        status="CLAIMED",
        current_step=1,
        total_steps=1,
    )
    sess.add(job)
    sess.commit()
    job_id = job.id

    # Attempt 1: fails before side effect
    fail_client = FailBeforeSideEffectClient()
    await process_claimed_job(sess, fail_client, job, worker_id="worker_t2a")
    sess.refresh(job)

    assert job.status == "FAILED"
    assert "Send error" in (job.error_message or "")

    intent = sess.query(PublishingHistory).filter(
        PublishingHistory.job_id == job_id,
        PublishingHistory.step_number == 1,
    ).first()
    assert intent is not None
    assert intent.status == "FAILED"
    assert intent.telegram_message_id is None

    # Retry attempt: reset to CLAIMED
    job.status = "CLAIMED"
    job.error_message = None
    sess.commit()

    ok_client = SuccessClient()
    await process_claimed_job(sess, ok_client, job, worker_id="worker_t2b")
    sess.refresh(job)

    assert job.status == "COMPLETED"
    assert ok_client.forwarded_count == 1

    # Unique constraint satisfied: exactly 1 history row with SUCCESS
    histories = sess.query(PublishingHistory).filter(
        PublishingHistory.job_id == job_id,
    ).all()
    assert len(histories) == 1
    assert histories[0].status == "SUCCESS"
    assert histories[0].telegram_message_id is not None
    sess.close()


# ===================================================================
# TEST 3 — Telegram succeeds, DB finalization crashes
# ===================================================================

@pytest.mark.asyncio
async def test_3_telegram_succeeds_db_finalization_crashes():
    """
    TEST 3: Telegram side effect succeeds, but process crashes before DB finalization.
    Expected: durable state in DB is PUBLISHING/UNKNOWN, crash recovery reconciles without blind duplicate.
    """
    sess = _make_session()
    tenant = _seed_tenant(sess)
    ch, auto = _seed_channel_auto(sess, tenant, reviews=2)

    # Job simulating Worker A crashed mid-execution of Step 1
    expired = datetime.now(timezone.utc) - timedelta(minutes=5)
    job = Job(
        tenant_id=tenant.id,
        automation_id=auto.id,
        channel_id=ch.id,
        idempotency_key=f"t3_{time.time_ns()}",
        trigger_text="SIG",
        status="RUNNING",
        current_step=1,
        total_steps=2,
        lease_owner="worker_crashed",
        lease_expires_at=expired,
    )
    sess.add(job)
    sess.flush()
    job_id = job.id

    # Durable PUBLISHING intent was committed by Worker A before crashing
    sess.add(PublishingHistory(
        tenant_id=tenant.id,
        job_id=job.id,
        channel_id=ch.id,
        message_title="Review from Alice",
        automation_name=auto.name,
        step_number=1,
        status="PUBLISHING",
        telegram_message_id=None,
    ))
    sess.commit()

    # Recovery pass: recovery daemon detects expired lease and resets to PENDING
    recovered = recover_expired_leases(sess, worker_id="recovery_daemon")
    assert recovered >= 1
    sess.expire_all()

    rec_job = sess.query(Job).filter(Job.id == job_id).first()
    assert rec_job.status == "PENDING"
    assert rec_job.lease_owner is None

    # Worker B claims and processes
    rec_job.status = "CLAIMED"
    rec_job.lease_owner = "worker_B"
    rec_job.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=120)
    sess.commit()

    client_b = SuccessClient()
    await process_claimed_job(sess, client_b, rec_job, worker_id="worker_B")
    sess.refresh(rec_job)

    assert rec_job.status == "COMPLETED"

    # Step 1 was reconciled as UNKNOWN / ambiguous delivery — NOT blindly duplicated!
    step1_record = sess.query(PublishingHistory).filter(
        PublishingHistory.job_id == job_id,
        PublishingHistory.step_number == 1,
    ).first()
    assert step1_record.status in ("UNKNOWN", "ASSUMED_DELIVERED")

    # Step 2 was cleanly forwarded
    step2_record = sess.query(PublishingHistory).filter(
        PublishingHistory.job_id == job_id,
        PublishingHistory.step_number == 2,
    ).first()
    assert step2_record.status == "SUCCESS"

    # Only step 2 was forwarded during Worker B's run
    assert client_b.forwarded_count == 1
    sess.close()


# ===================================================================
# TEST 4 — Restart/recovery
# ===================================================================

@pytest.mark.asyncio
async def test_4_restart_and_recovery_reconciles_interrupted_step():
    """
    TEST 4: Worker restart after crash.
    Expected: interrupted step is reconciled safely, subsequent steps executed cleanly.
    """
    sess = _make_session()
    tenant = _seed_tenant(sess)
    ch, auto = _seed_channel_auto(sess, tenant, reviews=2)

    job = Job(
        tenant_id=tenant.id,
        automation_id=auto.id,
        channel_id=ch.id,
        idempotency_key=f"t4_{time.time_ns()}",
        trigger_text="SIG",
        status="CLAIMED",
        current_step=1,
        total_steps=2,
        lease_owner="restarted_worker",
        lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=120),
    )
    sess.add(job)
    sess.flush()
    job_id = job.id

    # Simulated crash state: Step 1 left in UNKNOWN state from prior run
    sess.add(PublishingHistory(
        tenant_id=tenant.id,
        job_id=job.id,
        channel_id=ch.id,
        message_title="Review from Alice",
        automation_name=auto.name,
        step_number=1,
        status="UNKNOWN",
        error_details="Ambiguous delivery state from prior crash",
    ))
    sess.commit()

    restarted_client = SuccessClient()
    await process_claimed_job(sess, restarted_client, job, worker_id="restarted_worker")
    sess.refresh(job)

    assert job.status == "COMPLETED"
    # Step 1 was skipped (reconciled), only Step 2 was forwarded
    assert restarted_client.forwarded_count == 1

    records = sess.query(PublishingHistory).filter(
        PublishingHistory.job_id == job_id,
    ).order_by(PublishingHistory.step_number.asc()).all()

    assert len(records) == 2
    assert records[0].status in ("UNKNOWN", "ASSUMED_DELIVERED")
    assert records[1].status == "SUCCESS"
    sess.close()


# ===================================================================
# TEST 5 — Two workers recover the same interrupted job
# ===================================================================

def test_5_two_workers_recover_same_interrupted_job():
    """
    TEST 5: Two workers concurrently attempt to recover the same interrupted job.
    Expected: exactly one worker successfully recovers the job, avoiding duplicate claims.
    """
    sess = _make_session()
    tenant = _seed_tenant(sess)
    ch, auto = _seed_channel_auto(sess, tenant, reviews=2)

    expired = datetime.now(timezone.utc) - timedelta(minutes=10)
    job = Job(
        tenant_id=tenant.id,
        automation_id=auto.id,
        channel_id=ch.id,
        idempotency_key=f"t5_{time.time_ns()}",
        trigger_text="SIG",
        status="RUNNING",
        current_step=1,
        total_steps=2,
        lease_owner="dead_worker",
        lease_expires_at=expired,
    )
    sess.add(job)
    sess.flush()
    job_id = job.id

    sess.add(PublishingHistory(
        tenant_id=tenant.id,
        job_id=job.id,
        channel_id=ch.id,
        message_title="Review from Alice",
        automation_name=auto.name,
        step_number=1,
        status="PUBLISHING",
    ))
    sess.commit()
    sess.close()

    barrier = threading.Barrier(2, timeout=10)
    results = [None, None]

    def recover_worker(idx, worker_id):
        s = _make_session()
        try:
            barrier.wait()
            results[idx] = recover_expired_leases(s, worker_id=worker_id)
        except Exception as exc:
            results[idx] = f"ERROR: {exc}"
        finally:
            s.close()

    t1 = threading.Thread(target=recover_worker, args=(0, "rec_worker_1"))
    t2 = threading.Thread(target=recover_worker, args=(1, "rec_worker_2"))
    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)

    assert isinstance(results[0], int), f"Thread 0 error: {results[0]}"
    assert isinstance(results[1], int), f"Thread 1 error: {results[1]}"
    assert results[0] + results[1] == 1, f"Expected exactly 1 recovery winner, got {results}"

    verify = _make_session()
    final_job = verify.query(Job).filter(Job.id == job_id).first()
    assert final_job.status == "PENDING"
    assert final_job.lease_owner is None
    verify.close()


# ===================================================================
# TEST 6 — Duplicate retry after recovery
# ===================================================================

@pytest.mark.asyncio
async def test_6_duplicate_retry_after_recovery_no_duplicate():
    """
    TEST 6: Full duplicate retry test.
    Run recovery and execution again after all steps are completed or reconciled.
    Expected: zero additional forwards (0 duplicate messages).
    """
    sess = _make_session()
    tenant = _seed_tenant(sess)
    ch, auto = _seed_channel_auto(sess, tenant, reviews=2)

    job = Job(
        tenant_id=tenant.id,
        automation_id=auto.id,
        channel_id=ch.id,
        idempotency_key=f"t6_{time.time_ns()}",
        trigger_text="SIG",
        status="CLAIMED",
        current_step=1,
        total_steps=2,
        lease_owner="worker_t6",
        lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=120),
    )
    sess.add(job)
    sess.flush()
    job_id = job.id

    # Step 1: SUCCESS
    sess.add(PublishingHistory(
        tenant_id=tenant.id,
        job_id=job.id,
        channel_id=ch.id,
        message_title="Review from Alice",
        automation_name=auto.name,
        step_number=1,
        status="SUCCESS",
        telegram_message_id="7001",
    ))
    # Step 2: UNKNOWN (interrupted in prior attempt)
    sess.add(PublishingHistory(
        tenant_id=tenant.id,
        job_id=job.id,
        channel_id=ch.id,
        message_title="Review from Bob",
        automation_name=auto.name,
        step_number=2,
        status="UNKNOWN",
        error_details="Reconciled ambiguous state",
    ))
    sess.commit()

    # Recovery worker attempts execution on this job
    client = SuccessClient()
    await process_claimed_job(sess, client, job, worker_id="worker_t6")
    sess.refresh(job)

    assert job.status == "COMPLETED"
    # Zero forwards: both steps were recognized as already handled
    assert client.forwarded_count == 0

    # Ensure no duplicate rows created
    rows = sess.query(PublishingHistory).filter(PublishingHistory.job_id == job_id).all()
    assert len(rows) == 2
    sess.close()


# ===================================================================
# TEST 7 — Lease renewal failure halts execution (observable failure)
# ===================================================================

@pytest.mark.asyncio
async def test_7_lease_renewal_failure_aborts_execution_safely():
    """
    TEST 7: Lease renewal failure handling.
    If a worker loses its lease ownership (e.g. lease expired and recovered,
    or stolen by another worker), the worker MUST NOT continue publishing.
    It must observe the loss of ownership, fail the job safely, and send 0 messages.
    """
    sess = _make_session()
    tenant = _seed_tenant(sess)
    ch, auto = _seed_channel_auto(sess, tenant, reviews=1)

    # Job owned by another worker (e.g. "other_worker_xyz")
    job = Job(
        tenant_id=tenant.id,
        automation_id=auto.id,
        channel_id=ch.id,
        idempotency_key=f"t7_{time.time_ns()}",
        trigger_text="SIG",
        status="RUNNING",
        current_step=1,
        total_steps=1,
        lease_owner="other_worker_xyz",  # Worker "imposter_worker" does NOT own this lease
        lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=120),
    )
    sess.add(job)
    sess.commit()
    job_id = job.id

    client = SuccessClient()
    # "imposter_worker" attempts to execute a job it doesn't own
    await process_claimed_job(sess, client, job, worker_id="imposter_worker")
    sess.refresh(job)

    # Must abort and NOT publish
    assert job.status == "FAILED"
    assert "lease" in (job.error_message or "").lower()
    assert client.forwarded_count == 0

    # No publishing history should be written
    history = sess.query(PublishingHistory).filter(PublishingHistory.job_id == job_id).all()
    assert len(history) == 0
    sess.close()
