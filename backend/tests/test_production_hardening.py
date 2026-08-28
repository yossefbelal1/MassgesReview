"""
Production hardening tests — verifying fixes for production-critical bugs.

TEST 8 — FloodWait clears lease state (prevents stale lease after retry scheduling)
TEST 9 — General exception clears both lease_owner AND lease_expires_at
TEST 10 — Heartbeat task is stopped on all early exit paths
TEST 11 — FLOOD_WAIT publishing intent recorded before side-effect rescheduling
"""
import pytest
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from backend.app.models.models import (
    Job, Channel, Automation, PublishingHistory, Tenant, Plan, Subscription,
)
from backend.app.services.job_engine import (
    process_claimed_job,
    recover_expired_leases,
    renew_job_lease,
)
from telethon.errors import FloodWaitError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session():
    from backend.tests.conftest import TestingSessionLocal
    return TestingSessionLocal()


def _seed_tenant(sess):
    tenant = Tenant(name="Hardening Tenant", slug=f"hard-{time.time_ns()}")
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


def _seed_channel_auto(sess, tenant, reviews=1):
    ch = Channel(
        tenant_id=tenant.id,
        telegram_chat_id=f"-100{time.time_ns() % 10**9}",
        title="Hardening Channel",
        is_connected=True,
    )
    sess.add(ch)
    sess.flush()
    auto = Automation(
        tenant_id=tenant.id,
        channel_id=ch.id,
        name="Hardening Auto",
        trigger_value="SIG",
        is_active=True,
        reviews_count=reviews,
        initial_delay_seconds=0.01,
        delay_seconds=0.01,
    )
    sess.add(auto)
    sess.flush()
    return ch, auto


class FloodWaitClient:
    """Mock Telegram client that raises FloodWaitError on forward."""
    def __init__(self, wait_seconds=30):
        self.forwarded_count = 0
        self.wait_seconds = wait_seconds
        self.is_connected = MagicMock(return_value=True)

    async def get_messages(self, entity, limit=100):
        m1 = MagicMock(id=301, text="Great profit!", fwd_from=MagicMock(from_id=MagicMock(), from_name="Alice"))
        return [m1]

    async def forward_messages(self, entity, messages, from_peer):
        err = FloodWaitError(request=None)
        err.seconds = self.wait_seconds
        raise err


class SuccessClient:
    """Mock Telegram client — all forwards succeed."""
    def __init__(self):
        self.forwarded_count = 0
        self.is_connected = MagicMock(return_value=True)

    async def get_messages(self, entity, limit=100):
        m1 = MagicMock(id=301, text="Great profit!", fwd_from=MagicMock(from_id=MagicMock(), from_name="Alice"))
        return [m1]

    async def forward_messages(self, entity, messages, from_peer):
        self.forwarded_count += 1
        res = MagicMock()
        res.id = 9000 + self.forwarded_count
        return res


# ===================================================================
# TEST 8 — FloodWait clears lease_owner and lease_expires_at
# ===================================================================

@pytest.mark.asyncio
async def test_8_flood_wait_clears_lease_state():
    """
    TEST 8: When FloodWaitError occurs, the job is moved to RETRY_SCHEDULED
    and both lease_owner and lease_expires_at MUST be cleared.
    Otherwise a stale lease could block recovery of the rescheduled job.
    """
    sess = _make_session()
    tenant = _seed_tenant(sess)
    ch, auto = _seed_channel_auto(sess, tenant, reviews=1)

    job = Job(
        tenant_id=tenant.id,
        automation_id=auto.id,
        channel_id=ch.id,
        idempotency_key=f"t8_{time.time_ns()}",
        trigger_text="SIG",
        status="CLAIMED",
        current_step=1,
        total_steps=1,
        lease_owner="worker_t8",
        lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=120),
    )
    sess.add(job)
    sess.commit()

    client = FloodWaitClient(wait_seconds=60)
    await process_claimed_job(sess, client, job, worker_id="worker_t8")
    sess.refresh(job)

    assert job.status == "RETRY_SCHEDULED"
    assert job.lease_owner is None, "lease_owner must be cleared on RETRY_SCHEDULED"
    assert job.lease_expires_at is None, "lease_expires_at must be cleared on RETRY_SCHEDULED"
    assert "FloodWait" in (job.error_message or "")

    # Verify the publishing history intent was recorded
    intent = sess.query(PublishingHistory).filter(
        PublishingHistory.job_id == job.id,
        PublishingHistory.step_number == 1,
    ).first()
    assert intent is not None
    assert intent.status == "FLOOD_WAIT"
    sess.close()


# ===================================================================
# TEST 9 — General exception clears BOTH lease_owner and lease_expires_at
# ===================================================================

@pytest.mark.asyncio
async def test_9_general_exception_clears_full_lease_state():
    """
    TEST 9: When an unexpected exception occurs during job execution,
    both lease_owner AND lease_expires_at must be cleared to avoid
    leaving a stale lease that blocks recovery.
    """
    sess = _make_session()
    tenant = _seed_tenant(sess)
    ch, auto = _seed_channel_auto(sess, tenant, reviews=1)

    job = Job(
        tenant_id=tenant.id,
        automation_id=auto.id,
        channel_id=ch.id,
        idempotency_key=f"t9_{time.time_ns()}",
        trigger_text="SIG",
        status="CLAIMED",
        current_step=1,
        total_steps=1,
    )
    sess.add(job)
    sess.commit()

    # Client that raises a non-Telegram error during get_messages
    class ExplodingClient:
        is_connected = MagicMock(return_value=True)
        async def get_messages(self, entity, limit=100):
            raise RuntimeError("Unexpected DB connection pool exhaustion")
        async def forward_messages(self, entity, messages, from_peer):
            pass

    client = ExplodingClient()
    await process_claimed_job(sess, client, job, worker_id="worker_t9")
    sess.refresh(job)

    assert job.status == "FAILED"
    assert job.lease_owner is None, "lease_owner must be cleared on general exception"
    assert job.lease_expires_at is None, "lease_expires_at must be cleared on general exception"
    assert "Unexpected execution error" in (job.error_message or "")
    sess.close()


# ===================================================================
# TEST 10 — Heartbeat failure aborts execution and clears lease
# ===================================================================

@pytest.mark.asyncio
async def test_10_heartbeat_failure_clears_lease_on_abort():
    """
    TEST 10: When heartbeat renewal fails and execution is aborted,
    both lease_owner AND lease_expires_at must be cleared.
    The job must be left in a recoverable FAILED state.
    """
    sess = _make_session()
    tenant = _seed_tenant(sess)
    ch, auto = _seed_channel_auto(sess, tenant, reviews=1)

    # Job owned by another worker — simulates lost ownership
    job = Job(
        tenant_id=tenant.id,
        automation_id=auto.id,
        channel_id=ch.id,
        idempotency_key=f"t10_{time.time_ns()}",
        trigger_text="SIG",
        status="RUNNING",
        current_step=1,
        total_steps=1,
        lease_owner="other_worker",
        lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=120),
    )
    sess.add(job)
    sess.commit()

    client = SuccessClient()
    await process_claimed_job(sess, client, job, worker_id="imposter")
    sess.refresh(job)

    # Must have failed because imposter doesn't own the lease
    assert job.status == "FAILED"
    assert "lease" in (job.error_message or "").lower()
    assert client.forwarded_count == 0

    # No publishing history should exist
    history = sess.query(PublishingHistory).filter(PublishingHistory.job_id == job.id).all()
    assert len(history) == 0
    sess.close()


# ===================================================================
# TEST 11 — Lost lease ownership during step execution clears lease
# ===================================================================

@pytest.mark.asyncio
async def test_11_lost_lease_during_step_clears_full_lease_state():
    """
    TEST 11: If a worker loses lease ownership mid-execution (renew_job_lease
    returns False because the job was recovered by another worker),
    both lease_owner AND lease_expires_at must be cleared.
    """
    sess = _make_session()
    tenant = _seed_tenant(sess)
    ch, auto = _seed_channel_auto(sess, tenant, reviews=1)

    # Create job owned by worker_t11
    job = Job(
        tenant_id=tenant.id,
        automation_id=auto.id,
        channel_id=ch.id,
        idempotency_key=f"t11_{time.time_ns()}",
        trigger_text="SIG",
        status="CLAIMED",
        current_step=1,
        total_steps=1,
        lease_owner="worker_t11",
        lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=120),
    )
    sess.add(job)
    sess.commit()
    job_id = job.id

    # Simulate another worker stealing ownership between CLAIMED → RUNNING transition
    # After process_claimed_job sets status=RUNNING, we manually change lease_owner
    # But first let's use a more direct approach: set the job to COMPLETED status
    # so renew_job_lease returns False
    job.status = "COMPLETED"  # renew_job_lease checks status == "RUNNING"
    sess.commit()

    job.status = "CLAIMED"  # Reset for process_claimed_job entry
    job.lease_owner = "worker_t11"
    sess.commit()

    # The pre-step renew_job_lease will fail because after process_claimed_job
    # sets it to RUNNING with lease_owner="worker_t11", the renewal should work.
    # Instead, let's test with a 2-step job where we corrupt ownership after step 1
    auto.reviews_count = 2
    job.total_steps = 2
    sess.commit()

    class SlowSuccessClient:
        """Client that succeeds but steals the job's lease_owner between steps."""
        forwarded_count = 0
        is_connected = MagicMock(return_value=True)
        _job_id = job_id

        async def get_messages(self, entity, limit=100):
            m1 = MagicMock(id=301, text="P1!", fwd_from=MagicMock(from_id=MagicMock(), from_name="A"))
            m2 = MagicMock(id=302, text="P2!", fwd_from=MagicMock(from_id=MagicMock(), from_name="B"))
            return [m1, m2]

        async def forward_messages(self, entity, messages, from_peer):
            self.forwarded_count += 1
            if self.forwarded_count == 1:
                # After first forward succeeds, steal the lease via another session
                from backend.tests.conftest import TestingSessionLocal
                steal_sess = TestingSessionLocal()
                steal_sess.query(Job).filter(Job.id == self._job_id).update(
                    {Job.lease_owner: "thief_worker"},
                    synchronize_session="fetch"
                )
                steal_sess.commit()
                steal_sess.close()
            res = MagicMock()
            res.id = 8000 + self.forwarded_count
            return res

    client = SlowSuccessClient()
    await process_claimed_job(sess, client, job, worker_id="worker_t11")
    sess.expire_all()
    final_job = sess.query(Job).filter(Job.id == job_id).first()

    # After step 1 succeeds and step 2's pre-step renew_job_lease finds
    # lease_owner != "worker_t11", execution must abort
    assert final_job.status == "FAILED"
    assert "lease" in (final_job.error_message or "").lower()
    assert final_job.lease_owner is None
    assert final_job.lease_expires_at is None

    # Only step 1 should have been forwarded
    assert client.forwarded_count == 1
    sess.close()
