import pytest
from datetime import datetime, timezone, timedelta
from backend.app.models.models import Job, Channel, Automation
from backend.app.services.job_engine import claim_next_job, recover_expired_leases

def test_two_workers_atomic_job_claim(db, tenant_a):
    channel = Channel(tenant_id=tenant_a["tenant"].id, telegram_chat_id="-100888777666", title="Race Channel", is_connected=True)
    db.add(channel)
    db.flush()

    auto = Automation(tenant_id=tenant_a["tenant"].id, channel_id=channel.id, name="Race Auto", trigger_value="RACE", is_active=True)
    db.add(auto)
    db.flush()

    job = Job(tenant_id=tenant_a["tenant"].id, automation_id=auto.id, channel_id=channel.id, idempotency_key="race_job_single_claim", trigger_text="RACE", status="PENDING")
    db.add(job)
    db.commit()

    # Worker A claims job
    claim_a = claim_next_job(db, worker_id="worker_a", lease_duration_seconds=60)
    assert claim_a is not None
    assert claim_a.id == job.id
    assert claim_a.status == "CLAIMED"
    assert claim_a.lease_owner == "worker_a"

    # Worker B tries to claim at the exact same moment
    claim_b = claim_next_job(db, worker_id="worker_b", lease_duration_seconds=60)
    assert claim_b is None  # Worker B gets nothing

def test_stale_lease_recovery_concurrency(db, tenant_a):
    channel = Channel(tenant_id=tenant_a["tenant"].id, telegram_chat_id="-100888777555", title="Stale Channel", is_connected=True)
    db.add(channel)
    db.flush()

    auto = Automation(tenant_id=tenant_a["tenant"].id, channel_id=channel.id, name="Stale Auto", trigger_value="STALE", is_active=True)
    db.add(auto)
    db.flush()

    # Job with expired lease
    expired = datetime.now(timezone.utc) - timedelta(minutes=10)
    job = Job(tenant_id=tenant_a["tenant"].id, automation_id=auto.id, channel_id=channel.id, idempotency_key="stale_lease_job", trigger_text="STALE", status="RUNNING", lease_owner="dead_worker", lease_expires_at=expired)
    db.add(job)
    db.commit()

    # Recovery worker runs
    recovered_count = recover_expired_leases(db, worker_id="recovery_daemon")
    assert recovered_count == 1

    db.refresh(job)
    assert job.status == "PENDING"
    assert job.lease_owner is None
