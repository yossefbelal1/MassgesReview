import pytest
from datetime import datetime, timezone
from backend.app.models.models import Job, Channel, Automation
from backend.app.services.job_engine import claim_next_job

def test_atomic_job_claiming_concurrency(db, tenant_a):
    channel = Channel(
        tenant_id=tenant_a["tenant"].id,
        telegram_chat_id="-100999888777",
        title="Concurrency Test Channel",
        is_connected=True
    )
    db.add(channel)
    db.flush()

    auto = Automation(
        tenant_id=tenant_a["tenant"].id,
        channel_id=channel.id,
        name="Auto Test",
        trigger_value="SIGNAL",
        is_active=True
    )
    db.add(auto)
    db.flush()

    job = Job(
        tenant_id=tenant_a["tenant"].id,
        automation_id=auto.id,
        channel_id=channel.id,
        idempotency_key="unique_claim_test_key_1",
        trigger_text="SIGNAL",
        status="PENDING",
        execute_at=datetime.now(timezone.utc)
    )
    db.add(job)
    db.commit()

    # Worker 1 claims job
    claimed_by_w1 = claim_next_job(db, worker_id="worker_1", lease_duration_seconds=60)
    assert claimed_by_w1 is not None
    assert claimed_by_w1.id == job.id
    assert claimed_by_w1.lease_owner == "worker_1"
    assert claimed_by_w1.status == "CLAIMED"

    # Worker 2 attempts to claim the same pending pool immediately
    claimed_by_w2 = claim_next_job(db, worker_id="worker_2", lease_duration_seconds=60)
    assert claimed_by_w2 is None  # Must NOT be able to claim the same job!
