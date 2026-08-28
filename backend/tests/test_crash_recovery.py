import pytest
from datetime import datetime, timedelta, timezone
from backend.app.models.models import Job, Channel, Automation
from backend.app.services.job_engine import (
    ingest_channel_messages,
    claim_next_job,
    recover_expired_leases
)

class MockMessage:
    def __init__(self, id, text):
        self.id = id
        self.text = text
        self.out = False
        self.fwd_from = None

def test_durable_event_ingestion_and_cursor_safety(db, tenant_a):
    channel = Channel(
        tenant_id=tenant_a["tenant"].id,
        telegram_chat_id="-100123456789",
        title="Durable Ingest Channel",
        is_connected=True,
        last_seen_message_id=10
    )
    db.add(channel)
    db.flush()

    auto = Automation(
        tenant_id=tenant_a["tenant"].id,
        channel_id=channel.id,
        name="Target Auto",
        trigger_value="BUY EURUSD",
        trigger_type="exact",
        is_active=True
    )
    db.add(auto)
    db.commit()

    # Incoming batch with message 11 matching trigger
    messages = [MockMessage(id=11, text="BUY EURUSD"), MockMessage(id=12, text="Random Chat")]
    
    # Ingest messages durably
    created_count = ingest_channel_messages(db, channel, messages, [auto])
    assert created_count == 1

    # Check job was persisted with PENDING status
    job = db.query(Job).filter(Job.idempotency_key == f"{channel.id}:11:{auto.id}").first()
    assert job is not None
    assert job.status == "PENDING"
    assert channel.last_seen_message_id == 12

def test_lease_recovery_of_crashed_worker(db, tenant_a):
    channel = Channel(
        tenant_id=tenant_a["tenant"].id,
        telegram_chat_id="-100123456780",
        title="Crash Channel",
        is_connected=True
    )
    db.add(channel)
    db.flush()

    auto = Automation(
        tenant_id=tenant_a["tenant"].id,
        channel_id=channel.id,
        name="Crash Auto",
        trigger_value="TEST",
        is_active=True
    )
    db.add(auto)
    db.flush()

    # Stale job with expired lease from a crashed worker
    expired_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    stale_job = Job(
        tenant_id=tenant_a["tenant"].id,
        automation_id=auto.id,
        channel_id=channel.id,
        idempotency_key="stale_job_recovery_1",
        status="RUNNING",
        lease_owner="crashed_worker_999",
        lease_expires_at=expired_time
    )
    db.add(stale_job)

    # Active job with valid unexpired lease from a healthy worker
    valid_time = datetime.now(timezone.utc) + timedelta(minutes=5)
    active_job = Job(
        tenant_id=tenant_a["tenant"].id,
        automation_id=auto.id,
        channel_id=channel.id,
        idempotency_key="active_job_healthy_2",
        status="RUNNING",
        lease_owner="healthy_worker_1",
        lease_expires_at=valid_time
    )
    db.add(active_job)
    db.commit()

    # Recovery pass
    recovered = recover_expired_leases(db, worker_id="recovery_worker")
    assert recovered == 1

    db.refresh(stale_job)
    db.refresh(active_job)

    assert stale_job.status == "PENDING"
    assert stale_job.lease_owner is None

    assert active_job.status == "RUNNING"
    assert active_job.lease_owner == "healthy_worker_1"
