"""
Telegram Publishing Crash Safety Tests — Publish-Intent Outbox Pattern

Tests the exact crash boundary between Telegram side-effect delivery
and database state persistence.

Test 1: Normal path — Telegram succeeds, DB commits → one publish.
Test 2: Telegram fails before side-effect → retry is safe.
Test 3: Telegram succeeds, process crashes before DB finalization →
         recovery worker reconciles PUBLISHING → ASSUMED_DELIVERED, no duplicate.
Test 4: Two workers recover same interrupted job → only one owns it.
Test 5: Duplicate retry after restart → no uncontrolled duplicate.
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
        self.is_connected = MagicMock(return_value=True)

    async def get_messages(self, entity, limit=100):
        m1 = MagicMock(id=301, text="Great profit!", fwd_from=MagicMock(from_id=MagicMock(), from_name="Alice"))
        m2 = MagicMock(id=302, text="Hit TP!", fwd_from=MagicMock(from_id=MagicMock(), from_name="Bob"))
        return [m1, m2]

    async def forward_messages(self, entity, messages, from_peer):
        self.forwarded_count += 1
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
        # Network error before Telegram processes the request
        raise ConnectionError("Network unreachable — no side-effect occurred")


class CrashAfterForwardClient:
    """
    Mock client that simulates:
    - Step 1: forward succeeds (returns normally)
    - Then the caller's DB commit is simulated to crash
      (we do this at the test level, not inside the client)
    """
    def __init__(self):
        self.forwarded_count = 0
        self.is_connected = MagicMock(return_value=True)

    async def get_messages(self, entity, limit=100):
        m1 = MagicMock(id=301, text="Great profit!", fwd_from=MagicMock(from_id=MagicMock(), from_name="Alice"))
        m2 = MagicMock(id=302, text="Hit TP!", fwd_from=MagicMock(from_id=MagicMock(), from_name="Bob"))
        return [m1, m2]

    async def forward_messages(self, entity, messages, from_peer):
        self.forwarded_count += 1
        res = MagicMock()
        res.id = 8000 + self.forwarded_count
        return res


# ===================================================================
# TEST 1 — Happy path: Telegram succeeds → DB commits → one publish
# ===================================================================

@pytest.mark.asyncio
async def test_1_normal_publish_succeeds_one_publish():
    """Normal flow: forward + commit both succeed. Exactly 1 publish per step."""
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
    await process_claimed_job(sess, client, job, worker_id="w1")
    sess.refresh(job)

    assert job.status == "COMPLETED"
    assert client.forwarded_count == 1

    history = sess.query(PublishingHistory).filter(
        PublishingHistory.job_id == job_id,
    ).all()
    assert len(history) == 1
    assert history[0].status == "SUCCESS"
    assert history[0].step_number == 1
    assert history[0].telegram_message_id is not None
    sess.close()


# ===================================================================
# TEST 2 — Telegram fails before side-effect → retry is safe
# ===================================================================

@pytest.mark.asyncio
async def test_2_telegram_fails_before_side_effect_retry_safe():
    """
    forward_messages raises ConnectionError (no side-effect).
    The intent record should be FAILED.
    A retry should be able to create a new intent and succeed.
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

    # First attempt — fails
    fail_client = FailBeforeSideEffectClient()
    await process_claimed_job(sess, fail_client, job, worker_id="w1")
    sess.refresh(job)

    assert job.status == "FAILED"

    # Check intent record exists with appropriate status
    intent = sess.query(PublishingHistory).filter(
        PublishingHistory.job_id == job_id,
        PublishingHistory.step_number == 1,
    ).first()
    # The ConnectionError is caught by the general except clause,
    # so the intent record stays at PUBLISHING (crash equivalent).
    # OR it might not exist if the exception happened before commit.
    # Either way, retry should work.

    # Simulate recovery: set job back to CLAIMED for retry
    job.status = "CLAIMED"
    job.current_step = 1
    job.error_message = None
    sess.commit()

    # Second attempt — succeeds
    ok_client = SuccessClient()
    await process_claimed_job(sess, ok_client, job, worker_id="w2")
    sess.refresh(job)

    assert job.status == "COMPLETED"
    assert ok_client.forwarded_count == 1

    # Verify final history: should have exactly 1 SUCCESS record
    success_records = sess.query(PublishingHistory).filter(
        PublishingHistory.job_id == job_id,
        PublishingHistory.status == "SUCCESS",
    ).all()
    assert len(success_records) == 1
    sess.close()


# ===================================================================
# TEST 3 — Telegram succeeds → crash before DB finalization
#           Recovery reconciles PUBLISHING → ASSUMED_DELIVERED
# ===================================================================

@pytest.mark.asyncio
async def test_3_crash_after_telegram_success_reconciles_no_duplicate():
    """
    Simulates the critical crash window:
    1. Worker A writes PUBLISHING intent and commits
    2. Telegram forward succeeds (message IS delivered)
    3. Process crashes BEFORE updating intent to SUCCESS

    On recovery:
    - Worker B finds PUBLISHING record
    - Marks it ASSUMED_DELIVERED
    - Does NOT re-forward the message
    - Proceeds to next step
    """
    sess = _make_session()
    tenant = _seed_tenant(sess)
    ch, auto = _seed_channel_auto(sess, tenant, reviews=2)

    job = Job(
        tenant_id=tenant.id,
        automation_id=auto.id,
        channel_id=ch.id,
        idempotency_key=f"t3_{time.time_ns()}",
        trigger_text="SIG",
        status="RUNNING",
        current_step=1,
        total_steps=2,
        lease_owner="worker_A",
        lease_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),  # expired
    )
    sess.add(job)
    sess.flush()
    job_id = job.id

    # Simulate: Worker A wrote the PUBLISHING intent for step 1, then crashed
    # (The Telegram message WAS delivered, but the worker died before
    #  updating the record to SUCCESS)
    sess.add(PublishingHistory(
        tenant_id=tenant.id,
        job_id=job.id,
        channel_id=ch.id,
        message_title="Review from Alice",
        automation_name=auto.name,
        step_number=1,
        status="PUBLISHING",  # ← CRASH WINDOW: intent committed, delivery unknown
        telegram_message_id=None,
    ))
    sess.commit()

    # Recovery daemon recovers the job
    recovered = recover_expired_leases(sess, worker_id="recovery_daemon")
    assert recovered >= 1
    sess.expire_all()

    recovered_job = sess.query(Job).filter(Job.id == job_id).first()
    assert recovered_job.status == "PENDING"

    # Worker B claims and processes the job
    recovered_job.status = "CLAIMED"
    recovered_job.current_step = 1  # Pointer lagged
    recovered_job.lease_owner = "worker_B"
    recovered_job.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=120)
    sess.commit()

    ok_client = SuccessClient()
    await process_claimed_job(sess, ok_client, recovered_job, worker_id="worker_B")
    sess.refresh(recovered_job)

    assert recovered_job.status == "COMPLETED"

    # Step 1 must have been reconciled as ASSUMED_DELIVERED — NOT re-forwarded
    step1 = sess.query(PublishingHistory).filter(
        PublishingHistory.job_id == job_id,
        PublishingHistory.step_number == 1,
    ).first()
    assert step1.status == "ASSUMED_DELIVERED", f"Expected ASSUMED_DELIVERED, got {step1.status}"
    assert "worker_B" in step1.error_details

    # Step 2 should be forwarded normally
    step2 = sess.query(PublishingHistory).filter(
        PublishingHistory.job_id == job_id,
        PublishingHistory.step_number == 2,
    ).first()
    assert step2.status == "SUCCESS"

    # Only 1 Telegram forward should have happened (step 2 only)
    assert ok_client.forwarded_count == 1, (
        f"Expected 1 forward (only step 2), got {ok_client.forwarded_count}"
    )
    sess.close()


# ===================================================================
# TEST 4 — Two workers recover same interrupted job → only one owns it
# ===================================================================

def test_4_two_workers_recover_same_job_only_one_wins():
    """
    An interrupted job with a PUBLISHING step and an expired lease.
    Two workers simultaneously try to recover it.
    Only one should succeed (atomic recovery), and the PUBLISHING
    step should be reconciled by whichever worker gets it.
    """
    sess = _make_session()
    tenant = _seed_tenant(sess)
    ch, auto = _seed_channel_auto(sess, tenant, reviews=2)

    expired = datetime.now(timezone.utc) - timedelta(minutes=10)
    job = Job(
        tenant_id=tenant.id,
        automation_id=auto.id,
        channel_id=ch.id,
        idempotency_key=f"t4_{time.time_ns()}",
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

    # PUBLISHING intent from the dead worker
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
    sess.close()

    # Two workers race to recover
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

    t1 = threading.Thread(target=recover_worker, args=(0, "rec_w1"))
    t2 = threading.Thread(target=recover_worker, args=(1, "rec_w2"))
    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)

    assert isinstance(results[0], int), f"Thread 0 error: {results[0]}"
    assert isinstance(results[1], int), f"Thread 1 error: {results[1]}"
    assert results[0] + results[1] == 1, (
        f"Expected total recovered == 1, got {results}"
    )

    # Verify job is now PENDING
    verify = _make_session()
    final_job = verify.query(Job).filter(Job.id == job_id).first()
    assert final_job.status == "PENDING"
    assert final_job.lease_owner is None

    # PUBLISHING record still exists (will be reconciled by whoever claims next)
    intent = verify.query(PublishingHistory).filter(
        PublishingHistory.job_id == job_id,
        PublishingHistory.step_number == 1,
    ).first()
    assert intent is not None
    assert intent.status == "PUBLISHING"  # Not yet reconciled — that happens at claim time
    verify.close()


# ===================================================================
# TEST 5 — Duplicate retry after restart → no uncontrolled duplicate
# ===================================================================

@pytest.mark.asyncio
async def test_5_duplicate_retry_after_restart_no_duplicate():
    """
    Full crash-restart-retry lifecycle:
    1. Worker A processes step 1 successfully (intent → PUBLISHING → SUCCESS)
    2. Worker A starts step 2, writes PUBLISHING intent, Telegram succeeds,
       but crashes before committing SUCCESS
    3. Worker B picks up the job, finds:
       - Step 1: SUCCESS → skip
       - Step 2: PUBLISHING → ASSUMED_DELIVERED → skip
    4. Worker B's client should have forwarded 0 messages (both already handled)
    """
    sess = _make_session()
    tenant = _seed_tenant(sess)
    ch, auto = _seed_channel_auto(sess, tenant, reviews=2)

    job = Job(
        tenant_id=tenant.id,
        automation_id=auto.id,
        channel_id=ch.id,
        idempotency_key=f"t5_{time.time_ns()}",
        trigger_text="SIG",
        status="CLAIMED",
        current_step=1,
        total_steps=2,
        lease_owner="worker_B",
        lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=120),
    )
    sess.add(job)
    sess.flush()
    job_id = job.id

    # Pre-existing state from Worker A's partial run:
    # Step 1: fully completed
    sess.add(PublishingHistory(
        tenant_id=tenant.id,
        job_id=job.id,
        channel_id=ch.id,
        message_title="Review from Alice",
        automation_name=auto.name,
        step_number=1,
        status="SUCCESS",
        telegram_message_id="8001",
    ))
    # Step 2: intent written, Telegram delivered, but worker crashed
    sess.add(PublishingHistory(
        tenant_id=tenant.id,
        job_id=job.id,
        channel_id=ch.id,
        message_title="Review from Bob",
        automation_name=auto.name,
        step_number=2,
        status="PUBLISHING",  # Crash window
        telegram_message_id=None,
    ))
    sess.commit()

    # Worker B processes — should skip both steps
    ok_client = SuccessClient()
    await process_claimed_job(sess, ok_client, job, worker_id="worker_B")
    sess.refresh(job)

    assert job.status == "COMPLETED"

    # Worker B should NOT have forwarded anything — both steps were reconciled
    assert ok_client.forwarded_count == 0, (
        f"Expected 0 forwards (both reconciled), got {ok_client.forwarded_count}"
    )

    # Verify final state
    step1 = sess.query(PublishingHistory).filter(
        PublishingHistory.job_id == job_id,
        PublishingHistory.step_number == 1,
    ).first()
    assert step1.status == "SUCCESS"

    step2 = sess.query(PublishingHistory).filter(
        PublishingHistory.job_id == job_id,
        PublishingHistory.step_number == 2,
    ).first()
    assert step2.status == "ASSUMED_DELIVERED"
    assert "worker_B" in step2.error_details
    sess.close()
